import os
import shutil
from dotenv import load_dotenv

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
# --- THIS IS THE FIX ---
from langchain_text_splitters import RecursiveCharacterTextSplitter
# --- END OF FIX ---

# --- NEW: Imports for Colab ---
import requests
import json
from langchain.embeddings.base import Embeddings
from typing import List

# --- Constants ---
INDEX_DIR = "faiss_vector_store"
load_dotenv()
COLAB_API_ENDPOINT = os.getenv("COLAB_API_ENDPOINT")

# --- NEW: Helper function to call Colab Embed API ---
def get_embedding_from_colab(text_chunk: str) -> List[float]:
    """
    Gets a vector embedding for a single text chunk from our Colab server.
    """
    if not COLAB_API_ENDPOINT:
        raise ValueError("COLAB_API_ENDPOINT not set in .env file")

    headers = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true"
    }
    payload = {
        "task": "embed",
        "data": text_chunk
    }
    try:
        response = requests.post(COLAB_API_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        embedding = result.get('embedding')
        if not embedding:
            raise Exception("No embedding returned from Colab")
        return embedding
    except Exception as e:
        print(f"Error getting embedding from Colab: {e}")
        # BGE-small-en-v1.5 has 384 dimensions
        return [0.0] * 384 

# --- NEW: Custom LangChain Embeddings Class ---
class ColabEmbeddings(Embeddings):
    """
    A custom LangChain embedding class that calls our Colab server.
    """
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        print(f"Embedding query (via Colab): {text[:50]}...")
        return get_embedding_from_colab(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        print(f"Embedding {len(texts)} documents (via Colab)...")
        results = []
        for i, text in enumerate(texts):
            print(f"  - Embedding chunk {i+1}/{len(texts)}")
            results.append(get_embedding_from_colab(text))
        return results

# --- Main Functions (Modified) ---

def create_and_save_vector_store(pdf_file_path):
    """
    Loads a PDF, splits it into chunks, embeds them using COLAB, 
    and saves to a local FAISS vector store.
    """
    print(f"Starting to process PDF: {pdf_file_path}")
    
    loader = PyMuPDFLoader(pdf_file_path)
    documents = loader.load()
    if not documents:
        raise ValueError("Could not load documents from the PDF.")
    print(f"Loaded {len(documents)} pages from PDF.")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    docs = text_splitter.split_documents(documents)
    if not docs:
        raise ValueError("Could not split documents into chunks.")
    print(f"Split document into {len(docs)} chunks.")

    # --- NEW: Initialize Colab embeddings ---
    print("Initializing Colab Embeddings...")
    embeddings = ColabEmbeddings()
    print("Embeddings interface ready.")

    db = FAISS.from_documents(docs, embeddings)
    db.save_local(INDEX_DIR)
    print(f"Vector store saved locally at {INDEX_DIR}")

def retrieve_relevant_chunks(question, k=5):
    """
    Retrieves the top k relevant chunks from the FAISS vector store
    for a given question using COLAB to embed the question.
    """
    if not check_index_exists():
        return []

    print(f"Retrieving relevant chunks for question: '{question}'")
    
    # --- NEW: Initialize Colab embeddings ---
    embeddings = ColabEmbeddings()

    db = FAISS.load_local(
        INDEX_DIR, 
        embeddings, 
        allow_dangerous_deserialization=True
    )

    retriever = db.as_retriever(search_kwargs={"k": k})
    relevant_docs = retriever.invoke(question)

    relevant_chunks = [doc.page_content for doc in relevant_docs]
    print(f"Found {len(relevant_chunks)} relevant chunks.")
    return relevant_chunks

# --- Unchanged Functions ---

def check_index_exists():
    """Checks if the FAISS index files exist."""
    faiss_file = os.path.join(INDEX_DIR, "index.faiss")
    pkl_file = os.path.join(INDEX_DIR, "index.pkl")
    return os.path.exists(faiss_file) and os.path.exists(pkl_file)

def delete_index():
    """Deletes the entire FAISS vector store directory."""
    if os.path.exists(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)
        print(f"Deleted old index directory: {INDEX_DIR}")