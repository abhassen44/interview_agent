import os
from typing import Annotated, List, Dict, Any
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
import google.generativeai as genai
import json
from pathlib import Path

from resume import (
    load_and_split_documents,
    initialize_vector_store,
    get_retriever,
    decompose_query,
    rrf_parallel_retrieval,
    generate_response,
    get_role_from_resume,
    generate_resume_based_questions
)

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

class EvaluationResult(TypedDict):
    question: str
    human_answer: str
    llm_actual_answer: str
    score: int
    reason: str

class InterviewState(TypedDict):
    messages: Annotated[list, add_messages]
    scorecard: List[EvaluationResult]
    current_question: str
    resume_path: str
    question_count: int
    interview_phase: str  # 'starting', 'questioning', 'completed'

@tool
def parse_resume_and_identify_role(resume_path: str) -> str:
    """Parse the resume PDF and identify the professional role."""
    try:
        docs = load_and_split_documents(str(Path(resume_path).name))
        role = get_role_from_resume(docs)
        return f"Identified role: {role}"
    except Exception as e:
        return f"Error processing resume: {str(e)}"

@tool
def generate_questions_for_role(role: str) -> str:
    """Generate technical interview questions for the identified role."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Generate a single, specific technical question for a {role} position.
    Make it focused and answerable in 2-3 minutes.
    Include practical scenarios or problem-solving elements.
    Do not include multiple questions - just one clear question.
    End with a question mark.
    """
    response = model.generate_content(prompt)
    return response.text.strip()

@tool
def generate_resume_questions(resume_path: str) -> str:
    """Generate specific questions based on resume content."""
    try:
        docs = load_and_split_documents(str(Path(resume_path).name))
        questions = generate_resume_based_questions(docs)
        # Return just the first question from the generated questions
        if questions:
            lines = questions.split('\n')
            for line in lines:
                if '?' in line and len(line.strip()) > 10:
                    return line.strip()
        return "Tell me about a challenging project mentioned in your resume?"
    except Exception as e:
        return f"Error generating questions: {str(e)}"

@tool
def retrieve_resume_context(resume_path: str, query: str) -> str:
    """Retrieve relevant context from the resume."""
    try:
        docs = load_and_split_documents(str(Path(resume_path).name))
        embedder = initialize_vector_store(docs)
        retriever = get_retriever(embedder)
        sub_qs = decompose_query(query)
        results = rrf_parallel_retrieval(retriever, sub_qs)
        return generate_response(query, results)
    except Exception as e:
        return f"Error retrieving context: {str(e)}"

def interview_agent(state: InterviewState):
    """Main interview agent that generates questions based on resume and role."""
    messages = state.get("messages", [])
    question_count = state.get("question_count", 0)
    resume_path = state.get("resume_path", "")
    
    # Determine what type of question to ask based on count
    if question_count == 0:
        # First question - resume specific
        question_prompt = f"""
        Based on the resume at {resume_path}, ask ONE specific technical question about 
        a project, technology, or experience mentioned in the resume. Make it detailed 
        and focused on their actual experience. End with a question mark.
        """
    elif question_count < 3:
        # Technical depth questions
        question_prompt = f"""
        Ask a technical question that tests deeper understanding of concepts relevant 
        to the candidate's background. Focus on problem-solving or system design. 
        Make it challenging but fair. End with a question mark.
        """
    elif question_count < 5:
        # Role-specific questions
        question_prompt = f"""
        Ask a practical, scenario-based question relevant to the role this candidate 
        is applying for based on their resume. Include real-world application. 
        End with a question mark.
        """
    else:
        # End the interview
        return {
            "messages": [HumanMessage(content="Thank you for completing the interview! I have all the information needed.")],
            "interview_phase": "completed"
        }
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # Get the last message for context
        last_message = messages[-1].content if messages else "Start interview"
        
        full_prompt = f"""
        You are conducting a technical interview. {question_prompt}
        
        Previous context: {last_message}
        
        Generate ONE clear, specific question. Do not provide multiple options.
        Make sure it ends with a question mark.
        Keep it concise but comprehensive.
        """
        
        response = model.generate_content(full_prompt)
        question = response.text.strip()
        
        # Ensure it's a proper question
        if not question.endswith('?'):
            question += "?"
        
        return {
            "messages": [HumanMessage(content=question)],
            "current_question": question,
            "question_count": question_count + 1
        }
        
    except Exception as e:
        fallback_questions = [
            "Can you walk me through a challenging technical problem you solved recently?",
            "How do you approach debugging complex issues in your code?",
            "Describe a time when you had to learn a new technology quickly. How did you approach it?",
            "What's your experience with system design and scalability considerations?",
            "How do you ensure code quality and maintainability in your projects?"
        ]
        
        question = fallback_questions[min(question_count, len(fallback_questions) - 1)]
        return {
            "messages": [HumanMessage(content=question)],
            "current_question": question,
            "question_count": question_count + 1
        }

def create_interview_graph(checkpointer=None):
    """Build the interview workflow graph."""
    builder = StateGraph(InterviewState)
    
    # Add nodes
    builder.add_node("interview_agent", interview_agent)
    builder.add_node("tools", ToolNode([
        parse_resume_and_identify_role,
        generate_questions_for_role,
        generate_resume_questions,
        retrieve_resume_context
    ]))
    
    # Define edges - simplified flow
    builder.add_edge(START, "interview_agent")
    builder.add_conditional_edges(
        "interview_agent",
        lambda state: END if state.get("interview_phase") == "completed" else "interview_agent"
    )
    
    # Compile with or without checkpointer
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    else:
        return builder.compile()