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

@tool
def parse_resume_and_identify_role(resume_path: str) -> str:
    """Parse the resume PDF and identify the professional role."""
    try:
        docs = load_and_split_documents(str(Path(resume_path).name))
        return get_role_from_resume(docs)
    except Exception as e:
        return f"Error processing resume: {str(e)}"

@tool
def generate_questions_for_role(role: str) -> str:
    """Generate technical interview questions for the identified role."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Generate 5 technical questions for a {role} position.
    Include 1 system design question and 1 behavioral question.
    Format as a numbered list.
    """
    response = model.generate_content(prompt)
    return response.text

@tool
def generate_resume_questions(resume_path: str) -> str:
    """Generate specific questions based on resume content."""
    try:
        docs = load_and_split_documents(str(Path(resume_path).name))
        return generate_resume_based_questions(docs)
    except Exception as e:
        return f"Error generating questions: {str(e)}"

@tool
def evaluate_answer(question: str, answer: str) -> str:
    """Evaluate the technical answer with detailed feedback."""
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Evaluate this technical interview answer strictly using JSON format:
    {{
        "question": "{question}",
        "human_answer": "{answer}",
        "ACTUAL_ANSWER": "The ideal technical answer",
        "SCORE": 0,
        "REASON": "Detailed technical feedback"
    }}
    
    Evaluation Criteria:
    1. Technical accuracy (0-10)
    2. Depth of knowledge
    3. Clarity of explanation
    4. Practical application
    """
    response = model.generate_content(prompt)
    return response.text

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
    """Main interview agent with resume context."""
    system_message = SystemMessage(
        content=f"""
        You are a technical interviewer analyzing this resume: {state['resume_path']}
        Follow this protocol:
        1. Start with resume-specific technical questions
        2. Progress to role-specific depth questions
        3. Include 1-2 behavioral questions
        4. Evaluate each answer thoroughly
        """
    )
    messages = [system_message] + state["messages"]
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    response = model.generate_content(messages)
    return {"messages": [HumanMessage(content=response.text)]}

def create_interview_graph(checkpointer=None):
    """Build the interview workflow graph."""
    builder = StateGraph(InterviewState)
    
    # Add nodes
    builder.add_node("interview_agent", interview_agent)
    builder.add_node("tools", ToolNode([
        parse_resume_and_identify_role,
        generate_questions_for_role,
        generate_resume_questions,
        evaluate_answer,
        retrieve_resume_context
    ]))
    
    # Define edges
    builder.add_edge(START, "interview_agent")
    builder.add_conditional_edges(
        "interview_agent",
        tools_condition,
        {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "interview_agent")
    
    # Make checkpointer optional
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    else:
        return builder.compile()