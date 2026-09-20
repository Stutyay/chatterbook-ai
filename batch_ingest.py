import os
print("\nStarting batch ingest...\n")
# --- Standard Imports ---
import shutil
import traceback

# --- Import project functions ---
from db.qdrant_handler import upsert_material_chunks, ensure_collection_exists, get_qdrant_client
from utils.pdf_utils import extract_text_from_pdf, chunk_text_by_tokens
from utils.ai_utils import get_embeddings_for_chunks

# --- Configuration ---
SOURCE_DOCUMENTS_PATH = os.getenv("BATCH_SOURCE_PATH", "./data/documents")
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/app/pdf_storage")
TEMP_DIR = "./temp_uploads"
BATCH_SIZE = 10
PAUSE_DURATION_SECONDS = 60

def extract_text_from_docx(docx_path):
    import docx
    try:
        doc = docx.Document(docx_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Error extracting text from {docx_path}: {e}")
        return ""

def process_all_documents(skip_existing=True):
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
        print(f"Failed to connect to Qdrant: {e}")
        print("Ensure the Qdrant Cloud settings (QDRANT_URL/QDRANT_API_KEY) in .env are correct.")
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

    import time
    
    # Collect all files first
    all_files = []
    for root, dirs, files in os.walk(SOURCE_DOCUMENTS_PATH):
        for filename in files:
            if filename.lower().endswith((".pdf", ".docx")):
                all_files.append((root, filename))
                
    total_files = len(all_files)
    print(f"Found {total_files} documents to process.")

    for i, (root, filename) in enumerate(all_files):
        if True:
            if True:
                if skip_existing:
                    try:
                        from qdrant_client.http import models
                        result = qdrant_client.scroll(
                            collection_name="study_materials",
                            scroll_filter=models.Filter(
                                must=[
                                    models.FieldCondition(
                                        key="original_filename",
                                        match=models.MatchValue(value=filename)
                                    )
                                ]
                            ),
                            limit=1
                        )
                        if result[0]:  # If there's at least one chunk for this file
                            print(f"Skipping {filename} as it already exists in Qdrant.")
                            continue
                    except Exception as check_e:
                        print(f"Warning: Could not check if {filename} exists in Qdrant: {check_e}")

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
                
                # Detect semester from filename or path if present
                semester = "Unknown"
                filename_lower = filename.lower()
                path_lower = relative_path.replace("\\", "/").lower()
                import re
                sem_match = re.search(r'sem(?:ester)?[\s_-]*([1-6])', path_lower)
                if sem_match:
                    semester = f"{sem_match.group(1)}"
                else:
                    # Fallback mapping based on filename keywords
                    if any(k in path_lower for k in ["probability", "c++", "programming with c++"]):
                        semester = "1"
                    elif any(k in path_lower for k in ["data structure", "data communication"]):
                        semester = "2"
                    elif any(k in path_lower for k in ["algorithm", "operating system"]):
                        semester = "3"
                    elif any(k in path_lower for k in ["software engineering", "dbms", "database"]):
                        semester = "4"
                    elif any(k in path_lower for k in ["network", "cloud"]):
                        semester = "5"
                    elif any(k in path_lower for k in ["machine learning", "ml", "artificial intelligence", "ai "]):
                        semester = "6"

                
                doc_type = "Unknown"
                if "pyq" in path_lower or "question paper" in path_lower or "paper" in path_lower or "20" in path_lower:
                    doc_type = "PYQ"
                elif "textbook" in path_lower or "book" in path_lower or "notes" in path_lower or "chapter" in path_lower or "guidelines" in path_lower:
                    doc_type = "Textbook"

                file_metadata = {
                    "container_path": container_file_path,
                    "original_local_path": relative_path.replace("\\", "/"),
                    "semester": semester,
                    "document_type": doc_type,
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
                    if filename.lower().endswith(".pdf"):
                        text = extract_text_from_pdf(temp_file_path)
                    elif filename.lower().endswith(".docx"):
                        text = extract_text_from_docx(temp_file_path)
                    else:
                        text = ""
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
                            
            # Cooldown logic after every BATCH_SIZE files
            files_handled = i + 1
            if files_handled % BATCH_SIZE == 0 and files_handled < total_files:
                batch_num = files_handled // BATCH_SIZE
                total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE
                print(f"\nBatch {batch_num} of {total_batches} complete ({files_handled}/{total_files} files). Cooling down for {PAUSE_DURATION_SECONDS} seconds...")
                time.sleep(PAUSE_DURATION_SECONDS)

    print("\n=============================================")
    print(f"Batch ingestion finished.")
    print(f"Successfully processed files: {processed_files}")
    print(f"Failed files: {failed_files}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Batch Ingest Documents")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files that already exist in Qdrant")
    args = parser.parse_args()
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    process_all_documents(skip_existing=args.skip_existing)