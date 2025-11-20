import os
import google.generativeai as genai
from dotenv import load_dotenv
import sys
import traceback

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure the Gemini client only if the key exists
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("Gemini API configured successfully.")
    except Exception as e:
        print(f"ERROR: Failed to configure Gemini API: {e}")
else:
    print("CRITICAL WARNING: GEMINI_API_KEY not found. AI functions WILL fail.")

# --- MODEL CONFIGURATION ---
EMBED_MODEL_NAME = "text-embedding-004"  # Keep this - embeddings model
GENERATIVE_MODEL_NAME = "models/gemini-2.5-flash"  # UPDATED: Was "gemini-1.5-flash"
# --- END MODEL CONFIGURATION ---

# --- Function to Embed Document Chunks ---
def get_embeddings_for_chunks(chunks: list[str]) -> list[list[float]]:
    """
    Generates vector embeddings for a list of text chunks (documents).
    Uses RETRIEVAL_DOCUMENT task type.
    """
    if not GEMINI_API_KEY:
        print("Error: Cannot generate embeddings, GEMINI_API_KEY is missing.")
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

        print(f"Sending {len(valid_chunks)} valid chunks to Gemini API...")
        
        # CRITICAL FIX: Call embed_content ONCE FOR EACH CHUNK
        # The API doesn't support batch processing with a simple list
        embeddings = []
        for i, chunk in enumerate(valid_chunks):
            try:
                result = genai.embed_content(
                    model=f"models/{EMBED_MODEL_NAME}",
                    content=chunk,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                # Extract the embedding values from the result
                embeddings.append(result['embedding'])
                
                # Print progress every 10 chunks
                if (i + 1) % 10 == 0:
                    print(f"  Processed {i + 1}/{len(valid_chunks)} chunks...")
                    
            except Exception as e:
                print(f"ERROR embedding chunk {i+1}: {e}")
                # Return empty list on any failure to maintain consistency
                return []

        print("Gemini API call successful. Processing embeddings...")
        
        if len(embeddings) != len(valid_chunks):
            print(f"ERROR: Embedding result mismatch. Expected {len(valid_chunks)}, got {len(embeddings)}.")
            return []
            
        print("Document embeddings generated successfully.")
        return embeddings

    except Exception as e:
        print(f"UNEXPECTED ERROR generating document embeddings: {e}")
        traceback.print_exc()
        return []

# --- Function to Embed User Queries ---
def get_embedding_for_query(query: str) -> list[float] | None:
    """
    Generates a vector embedding for a single user query string.
    Uses RETRIEVAL_QUERY task type.
    """
    if not GEMINI_API_KEY:
        print("Error: Cannot generate query embedding, GEMINI_API_KEY is missing.")
        return None
        
    print(f"Attempting to generate embedding for query: '{query[:50]}...'")
    try:
        result = genai.embed_content(
            model=f"models/{EMBED_MODEL_NAME}",
            content=query,
            task_type="RETRIEVAL_QUERY"
        )

        print("Query embedding generated successfully.")
        # For single content, result has 'embedding' key with the values
        return result['embedding']
        
    except Exception as e:
        print(f"UNEXPECTED ERROR generating query embedding: {e}")
        traceback.print_exc()
        return None

# --- Function to Generate Answer from Context ---
def generate_answer_from_context(context: str, query: str) -> str | None:
    """Generates an answer using the Gemini generative model based on context."""
    if not GEMINI_API_KEY: 
        print("Error: Cannot generate answer, GEMINI_API_KEY is missing.")
        return "Error: Gemini API Key not configured."
        
    print("Attempting to generate answer from context...")
    try:
        model = genai.GenerativeModel(GENERATIVE_MODEL_NAME)
        
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

        response = model.generate_content(prompt)
        print("Answer generation call successful. Processing response...")
        
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
            print(f"Warning: Prompt was blocked. Reason: {response.prompt_feedback.block_reason}")
            return f"My safety filters prevented me from generating an answer. Reason: {response.prompt_feedback.block_reason}"
        
        if hasattr(response, 'text'):
            print("Answer text generated successfully.")
            return response.text
        else:
             print("Warning: Model response did not contain text.")
             try:
                 return response.parts[0].text 
             except (AttributeError, IndexError):
                 print("ERROR: Could not extract text from response.")
                 return "I received a response from the AI, but couldn't extract the answer text."

    except Exception as e:
        print(f"UNEXPECTED ERROR during Gemini generation: {e}")
        traceback.print_exc()
        return f"Error generating answer: {e}"