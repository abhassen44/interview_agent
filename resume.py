from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import concurrent.futures
import os
from collections import defaultdict

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# === Load and Split PDF ===
def load_and_split_documents(pdf_filename: str, chunk_size=1000, chunk_overlap=200):
    # Handle both relative and absolute paths
    if os.path.isabs(pdf_filename):
        pdf_path = pdf_filename
    else:
        pdf_path = Path(__file__).parent / pdf_filename
    
    loader = PyPDFLoader(file_path=str(pdf_path))
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return text_splitter.split_documents(documents=docs)

# === Initialize Vector Store ===
def initialize_vector_store(documents, collection_name="resume_collection"):
    embedder = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=GOOGLE_API_KEY
    )
    vector_store = QdrantVectorStore.from_documents(
        documents=[],
        collection_name=collection_name,
        url="http://localhost:6333",
        embedding=embedder,
    )
    vector_store.add_documents(documents=documents)
    return embedder

def get_retriever(embedder, collection_name="resume_collection"):
    return QdrantVectorStore.from_existing_collection(
        collection_name=collection_name,
        url="http://localhost:6333",
        embedding=embedder,
    )

# === Query Decomposition ===
def decompose_query(original_query):
    model = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')
    prompt = f"""
Decompose the following question into simpler, independent sub-questions separated by '|':
"{original_query}"
"""
    response = model.generate_content(prompt)
    return response.text.strip().split("|")

# === RRF Fusion Retrieval ===
def rrf_merge_ranked_lists(results_lists, k=60):
    scores = defaultdict(float)
    for result_list in results_lists:
        for rank, doc in enumerate(result_list):
            key = doc.page_content
            scores[key] += 1 / (k + rank)
    sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
    unique_docs = {doc.page_content: doc for sublist in results_lists for doc in sublist}
    return [unique_docs[doc_text] for doc_text, _ in sorted_docs]

def rrf_parallel_retrieval(retriever, query_variants, k=3):
    def retrieve(q): return retriever.similarity_search(q, k=k)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        result_lists = list(executor.map(retrieve, query_variants))
    return rrf_merge_ranked_lists(result_lists)

# === LLM-Generated Answer ===
def generate_response(query: str, context_chunks):
    llm = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')
    context = "\n".join([doc.page_content for doc in context_chunks])
    content = f"user: {query}\ncontext:\n{context}"
    response = llm.generate_content(content)
    return response.text

# === Role Inference from Resume ===
def get_role_from_resume(docs):
    llm = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')
    sample = "\n".join([doc.page_content for doc in docs[:3]])
    prompt = f"""
Analyze the following resume content and identify the job specialization or role. Return it as a single concise title.

Content:
{sample}

Output: (Example: Machine Learning Engineer, Backend Developer, etc.)
"""
    return llm.generate_content(prompt).text.strip()

# === Ask Questions Based on Resume ===
def generate_resume_based_questions(docs):
    sample = "\n".join([doc.page_content for doc in docs[:3]])
    prompt = f"""
Generate 3 insightful questions based on this candidate's resume:

{sample}
"""
    llm = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')
    return llm.generate_content(prompt).text.strip()