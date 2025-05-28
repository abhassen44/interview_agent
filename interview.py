import os
from typing import Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage
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

# === Tools ===
@tool
def parse_resume_and_identify_role(file_path: str) -> str:
    """Parse the resume PDF and identify the role."""

    docs = load_and_split_documents(file_path)
    return get_role_from_resume(docs)

@tool
def generate_questions_for_role(role: str) -> str:
    """Generate technical interview questions based on the identified role."""
    prompt = f"Generate 5 technical interview questions for the role: {role}. Number and list them."
    return llm.invoke([SystemMessage(content=prompt)]).text

@tool
def generate_resume_questions(file_path: str) -> str:
    """Generate questions based on the resume content."""
    docs = load_and_split_documents(file_path)
    return generate_resume_based_questions(docs)

@tool
def evaluate_answer(question: str, answer: str) -> str:
    """Evaluate the provided answer to a question and return a score."""
    prompt = f"Evaluate the answer:\nQ: {question}\nA: {answer}\nReturn score out of 10 with reason."
    return llm.invoke([SystemMessage(content=prompt)]).text

@tool
def retrieve_resume_context(file_path: str, query: str) -> str:
    """Retrieve relevant context from the resume based on the query."""
    docs = load_and_split_documents(file_path)
    embedder = initialize_vector_store(docs)
    retriever = get_retriever(embedder)
    sub_qs = decompose_query(query)
    results = rrf_parallel_retrieval(retriever, sub_qs)
    return generate_response(query, results)

# === LangGraph State ===
class State(TypedDict):
    messages: Annotated[list, add_messages]

llm_with_tools = llm.bind_tools([
    parse_resume_and_identify_role,
    generate_questions_for_role,
    generate_resume_questions,
    evaluate_answer,
    retrieve_resume_context
])

def interview_agent(state: State):
    system_message = SystemMessage(
        content="You are an AI interviewer. Start with resume-based questions then switch to role-specific ones."
    )
    messages = [system_message] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# === Graph Construction ===
def create_interview_graph(checkpointer=None):
    builder = StateGraph(State)
    builder.add_node("interview_agent", interview_agent)
    builder.add_node("tools", ToolNode(tools=[
        parse_resume_and_identify_role,
        generate_questions_for_role,
        generate_resume_questions,
        evaluate_answer,
        retrieve_resume_context
    ]))
    builder.add_edge(START, "interview_agent")
    builder.add_conditional_edges("interview_agent", tools_condition, {
        "tools": "tools",
        END: END
    })
    builder.add_edge("tools", "interview_agent")
    return builder.compile(checkpointer=checkpointer)
