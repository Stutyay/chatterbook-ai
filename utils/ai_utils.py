import os
from groq import Groq
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Configure the Groq client only if the key exists
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("Groq API configured successfully.")
    except Exception as e:
        print(f"ERROR: Failed to configure Groq API: {e}")
        groq_client = None
else:
    print("CRITICAL WARNING: GROQ_API_KEY not found. Generative AI functions WILL fail.")
    groq_client = None

# --- MODEL CONFIGURATION ---
# Load the sentence transformer model locally for embeddings
try:
    print("Loading local embedding model: all-MiniLM-L6-v2...")
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Embedding model loaded successfully.")
except Exception as e:
    print(f"ERROR: Failed to load local embedding model: {e}")
    embedding_model = None

GENERATIVE_MODEL_NAME = "openai/gpt-oss-20b"
# --- END MODEL CONFIGURATION ---

# --- Function to Embed Document Chunks ---
def get_embeddings_for_chunks(chunks: list[str]) -> list[list[float]]:
    """
    Generates vector embeddings for a list of text chunks (documents) using a local model.
    """
    if embedding_model is None:
        print("Error: Cannot generate embeddings, local model is not loaded.")
        return []
    
    print(f"Attempting to generate embeddings for {len(chunks)} document chunks...")
    try:
        if not chunks:
            print("Warning: No chunks provided to embed.")
            return []
            
        valid_chunks = [chunk for chunk in chunks if chunk and chunk.strip()]
        if not valid_chunks:
            print("Warning: No valid (non-empty) text chunks provided for embedding.")
            return []

        print(f"Generating embeddings for {len(valid_chunks)} valid chunks locally...")
        
        # SentenceTransformer supports batch encoding
        embeddings = embedding_model.encode(valid_chunks).tolist()
        
        print("Document embeddings generated successfully.")
        return embeddings

    except Exception as e:
        print(f"UNEXPECTED ERROR generating document embeddings: {e}")
        traceback.print_exc()
        return []

# --- Function to Embed User Queries ---
def get_embedding_for_query(query: str) -> list[float] | None:
    """
    Generates a vector embedding for a single user query string using a local model.
    """
    if embedding_model is None:
        print("Error: Cannot generate query embedding, local model is not loaded.")
        return None
        
    print(f"Attempting to generate embedding for query: '{query[:50]}...'")
    try:
        embedding = embedding_model.encode(query).tolist()
        print("Query embedding generated successfully.")
        return embedding
        
    except Exception as e:
        print(f"UNEXPECTED ERROR generating query embedding: {e}")
        traceback.print_exc()
        return None

# --- Function to Generate Answer from Context ---
def generate_answer_from_context(context: str, query: str) -> str | None:
    """Generates an answer using the Groq generative model based on context."""
    if not groq_client: 
        print("Error: Cannot generate answer, GROQ_API_KEY is missing.")
        return "Error: Groq API Key not configured."
        
    print("Attempting to generate answer from context using Groq...")
    try:
        prompt = f"""You are ChatterbookAI, a precise study assistant for college students. Your primary function is to answer questions based *only* on the provided context chunks retrieved from their study materials (like previous year questions or textbook sections).

Follow these instructions strictly:
1.  **Analyze the CONTEXT:** Read the provided text chunks carefully.
2.  **Answer the QUESTION:** Formulate a concise and accurate answer based *solely* on the information present in the CONTEXT.
3.  **Cite Sources:** If possible, mention the source title or filename associated with the relevant chunk(s) used for the answer.
4.  **No Outside Knowledge:** Do NOT use any information not present in the CONTEXT. Do not make assumptions or add extra details.
5.  **If Unanswerable:** If the CONTEXT does not contain the information needed to answer the QUESTION, state clearly: "Based on the provided documents, I cannot answer that question." or "The context does not contain information about [topic of question]."

CONTEXT:
---
{context}
---

USER QUESTION: {query}

ANSWER:"""

        response = groq_client.chat.completions.create(
            model=GENERATIVE_MODEL_NAME,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        print("Answer generation call successful. Processing response...")
        
        answer_text = response.choices[0].message.content
        if answer_text:
            print("Answer text generated successfully.")
            return answer_text
        else:
            print("Warning: Model response did not contain text.")
            return "I received a response from the AI, but couldn't extract the answer text."

    except Exception as e:
        print(f"UNEXPECTED ERROR during Groq generation: {e}")
        traceback.print_exc()
        return f"Error generating answer: {e}"

# --- Function to Generate Generic Chat Response ---
def generate_generic_chat_response(messages: list[dict]) -> str | None:
    """
    Generates a conversational response using Groq, meant for generic AI chat functionality.
    Messages format should be [{'role': 'user'|'assistant', 'content': '...'}, ...]
    """
    if not groq_client:
        print("Error: Cannot generate answer, GROQ_API_KEY is missing.")
        return "Error: Groq API Key not configured."
        
    try:
        print("Attempting to generate generic chat response using Groq...")
        response = groq_client.chat.completions.create(
            model=GENERATIVE_MODEL_NAME,
            messages=messages,
            temperature=0.7
        )
        
        answer_text = response.choices[0].message.content
        return answer_text
        
    except Exception as e:
        print(f"UNEXPECTED ERROR during Groq generation: {e}")
        traceback.print_exc()
        raise e