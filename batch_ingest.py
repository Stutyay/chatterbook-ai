# --- DEBUGGING IMPORTS ---
import sys
import google.generativeai as genai
import os

# --- DEBUGGING PRINTS ---
print("--- PYTHON ENVIRONMENT DEBUG ---")
print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")
try:
    print(f"Google GenAI Lib Location: {genai.__file__}")
    print(f"Google GenAI Lib Version: {genai.__version__}")
except Exception as e:
    print(f"Could not get Google GenAI library details: {e}")
print("System Path (sys.path):")
for p in sys.path:
    print(f"  - {p}")
print("--- END DEBUG ---")
print("\nStarting batch ingest...\n")

# --- Standard Imports ---
import shutil
import traceback

# --- Import project functions ---
from db.qdrant_handler import upsert_material_chunks, ensure_collection_exists, get_qdrant_client
from utils.pdf_utils import extract_text_from_pdf, chunk_text_by_tokens
from utils.ai_utils import get_embeddings_for_chunks

# --- Configuration ---
SOURCE_DOCUMENTS_PATH = os.getenv("BATCH_SOURCE_PATH", "./source_documents")
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/app/pdf_storage")
TEMP_DIR = "./temp_uploads"

def process_all_documents():
    """
    Finds PDFs in source_documents folder, processes them,
    and upserts chunks/embeddings to Qdrant.
    """
    try:
        # Connect to Qdrant
        qdrant_client = get_qdrant_client()
        if not ensure_collection_exists():
            print("CRITICAL ERROR: Could not ensure Qdrant collection exists. Exiting.")
            print("Check Qdrant connection details in .env and if the Qdrant container is running.")
            return
        print("Qdrant connection established and collection verified.")
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to Qdrant: {e}")
        print("Ensure the Qdrant container is running and .env settings (QDRANT_HOST/PORT) are correct.")
        return

    # Check source path
    print(f"Looking for source documents in: {os.path.abspath(SOURCE_DOCUMENTS_PATH)}")
    if not os.path.exists(SOURCE_DOCUMENTS_PATH):
        print(f"Error: Source documents folder not found at '{SOURCE_DOCUMENTS_PATH}'")
        print("Please ensure the folder exists and contains your PDF files.")
        return

    # Ensure temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)

    processed_files = 0
    failed_files = 0

    print(f"Starting PDF processing...")
    print(f"PDFs metadata will reference container path: {PDF_STORAGE_PATH}")

    # Process all PDFs in source_documents folder (including subfolders)
    for root, dirs, files in os.walk(SOURCE_DOCUMENTS_PATH):
        for filename in files:
            if filename.lower().endswith(".pdf"):
                local_file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(local_file_path, SOURCE_DOCUMENTS_PATH)
                container_file_path = os.path.join(PDF_STORAGE_PATH, relative_path).replace("\\", "/")

                # Extract metadata from filename and path
                path_parts = relative_path.replace("\\", "/").split('/')
                
                # Try to extract subject from filename
                # Common patterns: "Subject_Name.pdf", "subject-name.pdf", etc.
                subject = "Unknown"
                if len(path_parts) > 1:
                    # If in subfolder, use folder name as subject
                    subject = path_parts[-2]
                else:
                    # Extract from filename (remove extension and clean up)
                    subject = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
                
                # Detect semester from filename if present
                semester = "Unknown"
                filename_lower = filename.lower()
                if "sem" in filename_lower or "semester" in filename_lower:
                    # Try to extract semester number
                    import re
                    sem_match = re.search(r'sem(?:ester)?[\s_-]*(\d+)', filename_lower)
                    if sem_match:
                        semester = f"Sem {sem_match.group(1)}"

                file_metadata = {
                    "container_path": container_file_path,
                    "original_local_path": relative_path.replace("\\", "/"),
                    "semester": semester,
                    "subject": subject,
                    "original_filename": filename
                }

                print(f"\n================ PROCESSING: {filename} =================")
                print(f"Found at: {local_file_path}")
                print(f"Metadata: {file_metadata}")

                # Unique temp file path
                temp_filename_base = os.path.splitext(filename)[0]
                temp_file_path = os.path.join(TEMP_DIR, f"{temp_filename_base}_{processed_files + failed_files}.pdf")

                try:
                    # Copy to temp location
                    shutil.copy2(local_file_path, temp_file_path)

                    # 1. Extract Text
                    text = extract_text_from_pdf(temp_file_path)
                    if not text:
                        print(f"Could not extract text. Skipping.")
                        failed_files += 1
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                        continue

                    # 2. Chunk Text
                    chunks = chunk_text_by_tokens(text)
                    if not chunks:
                        print(f"Could not chunk text. Skipping.")
                        failed_files += 1
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                        continue

                    # 3. Generate Embeddings
                    embeddings = get_embeddings_for_chunks(chunks)
                    if not embeddings or len(embeddings) != len(chunks):
                        print(f"Failed to generate embeddings. Skipping save.")
                        failed_files += 1
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                        continue

                    # 4. Prepare Chunks for Qdrant
                    chunks_for_qdrant = []
                    for i, chunk_text in enumerate(chunks):
                        if i < len(embeddings):
                            chunk_meta = {**file_metadata, "page_number": i + 1}
                            chunks_for_qdrant.append({
                                "chunk_text": chunk_text,
                                "embedding": embeddings[i],
                                "metadata": chunk_meta
                            })
                        else:
                            print(f"Warning: Missing embedding for chunk {i+1} of {filename}. Skipping chunk.")

                    # 5. Upsert Chunks to Qdrant
                    if chunks_for_qdrant:
                        print(f"Upserting {len(chunks_for_qdrant)} chunks to Qdrant...")
                        success = upsert_material_chunks(chunks_for_qdrant)
                        if success:
                            print(f"SUCCESS: Finished processing {filename}.")
                            processed_files += 1
                        else:
                            print(f"FAILED: Could not upsert chunks for {filename} to Qdrant.")
                            failed_files += 1
                    else:
                        print(f"Skipping Qdrant upsert for {filename} as no valid chunks/embeddings were prepared.")
                        failed_files += 1

                except Exception as e:
                    failed_files += 1
                    print(f"!!!!!!!! UNEXPECTED FAILURE during processing {filename}: {e} !!!!!!!!")
                    traceback.print_exc()
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except OSError as e_remove:
                            print(f"Warning: Could not remove temporary file {temp_file_path}: {e_remove}")

    print("\n=============================================")
    print(f"Batch ingestion finished.")
    print(f"Successfully processed files: {processed_files}")
    print(f"Failed/Skipped files: {failed_files}")

if __name__ == "__main__":
    os.makedirs(TEMP_DIR, exist_ok=True)
    process_all_documents()