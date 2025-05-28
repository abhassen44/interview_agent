import os
from typing import Annotated, List, Optional
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model
import google.generativeai as genai

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
llm = init_chat_model("google_genai:gemini-1.5-flash")

# === Enhanced State with Question Tracking ===
class State(TypedDict):
    messages: Annotated[list, add_messages]
    question_count: int
    max_questions: int
    interview_concluded: bool
    candidate_responses: List[str]
    current_phase: str  # "resume_based" or "role_based" or "concluded"
    identified_role: Optional[str]
    resume_file_path: Optional[str]
    question_scores: List[dict]  # Store question-answer pairs with scores

# === Tools ===
@tool
def parse_resume_and_identify_role(file_path: str) -> str:
    """Parse the resume PDF and identify the role."""
    docs = load_and_split_documents(file_path)
    return get_role_from_role(docs)

@tool
def generate_questions_for_role(role: str) -> str:
    """Generate technical interview questions based on the identified role."""
    prompt = f"Generate 5 technical interview questions for the role: {role}. Number and list them."
    return llm.invoke([SystemMessage(content=prompt)]).content

@tool
def generate_resume_questions(file_path: str) -> str:
    """Generate questions based on the resume content."""
    docs = load_and_split_documents(file_path)
    return generate_resume_based_questions(docs)

@tool
def evaluate_answer(question: str, answer: str) -> str:
    """Evaluate the provided answer to a question and return a score."""
    prompt = f"""Evaluate this interview answer and provide a score:

Question: {question}
Answer: {answer}

Please provide:
1. Score out of 10
2. Brief reasoning
3. Key strengths (if any)
4. Areas for improvement (if any)

Format: Score: X/10 | Reasoning: [brief explanation]"""
    
    return llm.invoke([SystemMessage(content=prompt)]).content

@tool
def retrieve_resume_context(file_path: str, query: str) -> str:
    """Retrieve relevant context from the resume based on the query."""
    docs = load_and_split_documents(file_path)
    embedder = initialize_vector_store(docs)
    retriever = get_retriever(embedder)
    sub_qs = decompose_query(query)
    results = rrf_parallel_retrieval(retriever, sub_qs)
    return generate_response(query, results)

@tool
def generate_final_scorecard(question_scores: List[dict], total_questions: int, identified_role: str) -> str:
    """Generate comprehensive final scorecard."""
    if not question_scores:
        return "No questions were answered to generate a scorecard."
    
    # Calculate scores
    scores = []
    total_score = 0
    
    for qa in question_scores:
        if 'score' in qa:
            try:
                # Extract numeric score from evaluation
                score_text = str(qa['score'])
                if '/10' in score_text:
                    score = float(score_text.split('/10')[0].split(':')[-1].strip())
                else:
                    # Try to extract first number
                    import re
                    numbers = re.findall(r'\d+', score_text)
                    score = float(numbers[0]) if numbers else 5.0
                scores.append(min(10.0, max(0.0, score)))
            except:
                scores.append(5.0)  # Default score if parsing fails
    
    if scores:
        avg_score = sum(scores) / len(scores)
        total_score = avg_score
    else:
        avg_score = 0
        total_score = 0
    
    # Generate comprehensive scorecard
    scorecard = f"""
🎯 INTERVIEW SCORECARD
{'='*60}

👤 CANDIDATE PROFILE:
• Identified Role: {identified_role}
• Questions Completed: {len(question_scores)}/{total_questions}
• Completion Rate: {(len(question_scores)/total_questions)*100:.1f}%

📊 PERFORMANCE BREAKDOWN:
"""
    
    for i, qa in enumerate(question_scores, 1):
        score = scores[i-1] if i-1 < len(scores) else 0
        scorecard += f"• Q{i}: {score:.1f}/10 - {qa.get('question', 'N/A')[:50]}...\n"
    
    scorecard += f"""
🏆 OVERALL PERFORMANCE:
• Average Score: {avg_score:.1f}/10
• Performance Level: {get_performance_level(avg_score)}

📈 DETAILED ANALYSIS:
"""
    
    # Add performance insights
    if avg_score >= 8.0:
        scorecard += "• 🌟 Excellent performance! Strong technical knowledge and communication skills.\n"
    elif avg_score >= 6.0:
        scorecard += "• 👍 Good performance with solid understanding of key concepts.\n"
    elif avg_score >= 4.0:
        scorecard += "• 📚 Fair performance. Consider reviewing fundamental concepts.\n"
    else:
        scorecard += "• 📖 Needs improvement. Focus on building stronger foundation.\n"
    
    if len(question_scores) < total_questions:
        scorecard += f"• ⏰ Interview ended early ({len(question_scores)}/{total_questions} questions completed)\n"
    
    scorecard += f"""
💡 RECOMMENDATIONS:
{generate_recommendations(avg_score, identified_role, len(question_scores), total_questions)}

Thank you for participating in the interview process!
{'='*60}
"""
    
    return scorecard

def get_performance_level(score: float) -> str:
    """Get performance level based on score."""
    if score >= 9.0:
        return "Outstanding"
    elif score >= 8.0:
        return "Excellent"
    elif score >= 7.0:
        return "Very Good"
    elif score >= 6.0:
        return "Good"
    elif score >= 5.0:
        return "Satisfactory"
    elif score >= 4.0:
        return "Needs Improvement"
    else:
        return "Unsatisfactory"

def generate_recommendations(score: float, role: str, completed: int, total: int) -> str:
    """Generate personalized recommendations."""
    recommendations = []
    
    if score < 6.0:
        recommendations.append(f"• Focus on strengthening core {role} fundamentals")
        recommendations.append("• Practice explaining technical concepts clearly")
    
    if score >= 6.0 and score < 8.0:
        recommendations.append("• Continue building on your solid foundation")
        recommendations.append("• Work on providing more detailed examples")
    
    if completed < total:
        recommendations.append("• Consider completing full interview sessions for better evaluation")
    
    if score >= 8.0:
        recommendations.append("• Excellent work! You're well-prepared for this role")
        recommendations.append("• Continue staying updated with latest industry trends")
    
    return "\n".join(recommendations) if recommendations else "• Keep up the great work!"

# === Enhanced Interview Agent ===
llm_with_tools = llm.bind_tools([
    parse_resume_and_identify_role,
    generate_questions_for_role,
    generate_resume_questions,
    evaluate_answer,
    retrieve_resume_context,
    generate_final_scorecard
])

def interview_agent(state: State):
    """Enhanced interview agent with question limiting and scoring."""
    messages = state.get("messages", [])
    question_count = state.get("question_count", 0)
    max_questions = state.get("max_questions", 10)
    interview_concluded = state.get("interview_concluded", False)
    current_phase = state.get("current_phase", "resume_based")
    candidate_responses = state.get("candidate_responses", [])
    question_scores = state.get("question_scores", [])
    identified_role = state.get("identified_role", "")
    resume_file_path = state.get("resume_file_path", "")
    
    # Check if we need to generate final scorecard
    if interview_concluded or question_count >= max_questions:
        if messages and isinstance(messages[-1], (HumanMessage, dict)):
            last_msg = messages[-1]
            content = last_msg.content if hasattr(last_msg, 'content') else last_msg.get('content', '')
            
            if content.strip().lower() == "generate_final_scorecard":
                # Generate final scorecard
                scorecard = generate_final_scorecard.invoke({
                    "question_scores": question_scores,
                    "total_questions": max_questions,
                    "identified_role": identified_role
                })
                
                return {
                    "messages": [AIMessage(content=scorecard)],
                    "interview_concluded": True
                }
    
    # Handle initial setup or phase transitions
    if question_count == 0:
        system_prompt = f"""You are an AI interviewer conducting a structured interview with exactly {max_questions} questions maximum.

INTERVIEW PROCESS:
1. Start with resume-based questions (3-4 questions)
2. Then move to role-specific technical questions
3. Ask ONE question at a time
4. Wait for candidate response before next question
5. Keep questions clear and focused

IMPORTANT RULES:
- Ask ONLY ONE question per response
- Number each question (Question 1, Question 2, etc.)
- After {max_questions} questions, conclude the interview
- Be professional and encouraging

Current Status: Question {question_count + 1}/{max_questions}
Phase: {current_phase}
"""
    else:
        system_prompt = f"""Continue the interview. 

Current Status: Question {question_count + 1}/{max_questions}
Phase: {current_phase}
Questions Remaining: {max_questions - question_count}

Ask the next appropriate question based on the conversation flow."""
    
    system_message = SystemMessage(content=system_prompt)
    all_messages = [system_message] + messages
    response = llm_with_tools.invoke(all_messages)
    
    return {"messages": [response]}

def should_continue(state: State) -> str:
    """Determine if interview should continue or end."""
    question_count = state.get("question_count", 0)
    max_questions = state.get("max_questions", 10)
    interview_concluded = state.get("interview_concluded", False)
    
    if interview_concluded or question_count >= max_questions:
        return END
    return "interview_agent"

def track_questions(state: State):
    """Track questions and evaluate responses."""
    messages = state.get("messages", [])
    question_count = state.get("question_count", 0)
    candidate_responses = state.get("candidate_responses", [])
    question_scores = state.get("question_scores", [])
    current_phase = state.get("current_phase", "resume_based")
    identified_role = state.get("identified_role", "")
    
    # Find the latest AI question and human response
    ai_questions = []
    human_responses = []
    
    for msg in messages:
        if isinstance(msg, AIMessage) or (isinstance(msg, dict) and msg.get("role") == "assistant"):
            content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
            if '?' in content and not content.lower().startswith('here') and not content.lower().startswith('thank'):
                ai_questions.append(content)
        elif isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
            if content.strip() and not content.lower().startswith("generate"):
                human_responses.append(content)
    
    # Update question count and phase
    new_question_count = len(ai_questions)
    
    # Transition phases
    if new_question_count > 3 and current_phase == "resume_based":
        current_phase = "role_based"
    
    # Evaluate latest response if we have a new Q&A pair
    if len(human_responses) > len(question_scores) and len(ai_questions) > 0:
        latest_question = ai_questions[len(question_scores)]
        latest_response = human_responses[len(question_scores)]
        
        # Evaluate the response
        evaluation = evaluate_answer.invoke({
            "question": latest_question,
            "answer": latest_response
        })
        
        question_scores.append({
            "question": latest_question,
            "answer": latest_response,
            "score": evaluation
        })
    
    return {
        "question_count": new_question_count,
        "candidate_responses": human_responses,
        "question_scores": question_scores,
        "current_phase": current_phase,
        "interview_concluded": new_question_count >= state.get("max_questions", 10)
    }

# === Graph Construction ===
def create_interview_graph(checkpointer=None):
    builder = StateGraph(State)
    
    # Add nodes
    builder.add_node("interview_agent", interview_agent)
    builder.add_node("track_questions", track_questions)
    builder.add_node("tools", ToolNode(tools=[
        parse_resume_and_identify_role,
        generate_questions_for_role,
        generate_resume_questions,
        evaluate_answer,
        retrieve_resume_context,
        generate_final_scorecard
    ]))
    
    # Set entry point
    builder.add_edge(START, "interview_agent")
    
    # Add conditional edges
    builder.add_conditional_edges("interview_agent", tools_condition, {
        "tools": "tools",
        END: "track_questions"
    })
    
    builder.add_edge("tools", "interview_agent")
    builder.add_conditional_edges("track_questions", should_continue, {
        "interview_agent": "interview_agent",
        END: END
    })
    
    return builder.compile(checkpointer=checkpointer)