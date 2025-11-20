from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, validator
from contextlib import asynccontextmanager
import os
import shutil
import google.generativeai as genai
import traceback
from pathlib import Path
import time
from typing import Optional, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database and utility functions
from db.qdrant_handler import (
    upsert_material_chunks, 
    search_similar_chunks, 
    ensure_collection_exists, 
    get_qdrant_client,
    delete_document_chunks
)
from utils.pdf_utils import extract_text_from_pdf, chunk_text_by_tokens
from utils.ai_utils import (
    get_embedding_for_query, 
    get_embeddings_for_chunks, 
    generate_answer_from_context
)

# Load Config
from dotenv import load_dotenv
load_dotenv()

# Configuration
PDF_STORAGE_PATH = os.getenv("PDF_STORAGE_PATH", "/app/pdf_storage")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf"}
CHUNK_SIZE_TOKENS = int(os.getenv("CHUNK_SIZE_TOKENS", "400"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "50"))

# Application Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting ChatterbookAI backend...")
    
    # Connect to Qdrant
    try:
        ensure_collection_exists()
        logger.info("Qdrant connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        raise
    
    # Configure Gemini
    if os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        logger.info("Gemini API configured")
    else:
        logger.error("GEMINI_API_KEY not found!")
        raise ValueError("GEMINI_API_KEY is required")
    
    # Ensure PDF storage directory exists
    try:
        os.makedirs(PDF_STORAGE_PATH, exist_ok=True)
        logger.info(f"PDF storage path: {os.path.abspath(PDF_STORAGE_PATH)}")
    except OSError as e:
        logger.error(f"Failed to create PDF storage directory: {e}")
        raise
    
    yield
    
    logger.info("Shutting down ChatterbookAI backend...")

app = FastAPI(
    lifespan=lifespan,
    title="ChatterbookAI API",
    description="RAG-based study assistant with PDF processing",
    version="1.0.0"
)

# CORS Configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# --- Pydantic Models ---

class ChatQuery(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    k: int = Field(default=5, ge=1, le=20)
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty or whitespace only')
        return v.strip()

class Source(BaseModel):
    source: str
    page: int
    score: float
    path: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    processing_time: float

class UploadResponse(BaseModel):
    message: str
    filename: str
    container_path: str
    chunks_created: int
    processing_time: float

class HealthResponse(BaseModel):
    status: str
    qdrant_connected: bool
    gemini_configured: bool
    pdf_storage_writable: bool
    timestamp: float

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

# --- Helper Functions ---

def validate_pdf_file(file: UploadFile) -> tuple[bool, Optional[str]]:
    """Validate uploaded file"""
    # Check content type
    if file.content_type != "application/pdf":
        return False, "Invalid file type. Only PDF files are allowed."
    
    # Check file extension
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return False, "File must have .pdf extension."
    
    # Check filename for path traversal
    if '..' in file.filename or '/' in file.filename or '\\' in file.filename:
        return False, "Invalid filename. Path separators not allowed."
    
    return True, None

async def get_file_size(file: UploadFile) -> int:
    """Get file size by reading to end"""
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    return size

# --- API Routes ---

@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "service": "ChatterbookAI API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/api/health",
            "chat": "/api/chat",
            "upload": "/api/materials/upload-and-process-pdf",
            "download": "/api/materials/download-pdf",
            "delete": "/api/materials/delete-pdf",
            "test": "/api/test-connections"
        }
    }

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring"""
    qdrant_ok = False
    gemini_ok = bool(os.getenv("GEMINI_API_KEY"))
    storage_ok = False
    
    # Check Qdrant
    try:
        client = get_qdrant_client()
        if client:
            client.get_collections()
            qdrant_ok = True
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
    
    # Check storage
    try:
        test_file = Path(PDF_STORAGE_PATH) / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        storage_ok = True
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
    
    status = "healthy" if (qdrant_ok and gemini_ok and storage_ok) else "degraded"
    
    return HealthResponse(
        status=status,
        qdrant_connected=qdrant_ok,
        gemini_configured=gemini_ok,
        pdf_storage_writable=storage_ok,
        timestamp=time.time()
    )

@app.post("/api/chat", response_model=ChatResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def handle_chat_query(query: ChatQuery = Body(...)):
    """
    Handle chat queries using RAG with Qdrant vector search
    
    Process:
    1. Embed user query
    2. Search Qdrant for similar chunks
    3. Build context from top results
    4. Generate answer using Gemini
    5. Return answer with sources
    """
    start_time = time.time()
    
    try:
        logger.info(f"Chat query received: '{query.message[:50]}...'")
        
        # 1. Embed the user's query
        query_embedding = get_embedding_for_query(query.message)
        if not query_embedding:
            raise HTTPException(
                status_code=500,
                detail="Failed to embed user query. Check Gemini API Key and logs."
            )
        
        # 2. Perform Vector Search in Qdrant
        search_results = search_similar_chunks(query_embedding, query.k)
        logger.info(f"Found {len(search_results)} relevant chunks")
        
        if not search_results:
            return ChatResponse(
                answer="I couldn't find any relevant information in the uploaded documents matching your query.",
                sources=[],
                processing_time=time.time() - start_time
            )
        
        # 3. Build context for the generative model
        context_parts = []
        sources_meta = []
        
        for hit in search_results:
            payload = hit.get('payload', {})
            chunk_text = payload.get('chunk_text', '').strip()
            source = payload.get('original_filename', 'Unknown Source')
            page = payload.get('page_number', 'N/A')
            container_path = payload.get('container_path', '#')
            score = hit.get('score', 0.0)
            
            if chunk_text:
                context_parts.append(
                    f"Source: {source} (Page approx. {page}, Score: {score:.4f})\n{chunk_text}"
                )
                sources_meta.append(Source(
                    source=source,
                    page=page,
                    score=round(score, 4),
                    path=container_path
                ))
        
        if not context_parts:
            logger.warning("Top search results had no text content")
            return ChatResponse(
                answer="Found potentially relevant documents, but could not extract text context.",
                sources=[s.dict() for s in sources_meta],
                processing_time=time.time() - start_time
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        # 4. Generate answer using Gemini
        answer = generate_answer_from_context(context, query.message)
        
        if answer is None or answer.startswith("Error"):
            logger.error(f"Answer generation failed: {answer}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate answer. Please try again."
            )
        
        processing_time = time.time() - start_time
        logger.info(f"Chat query processed in {processing_time:.2f}s")
        
        return ChatResponse(
            answer=answer,
            sources=[s.dict() for s in sources_meta],
            processing_time=processing_time
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred: {str(e)}"
        )

@app.post("/api/materials/upload-and-process-pdf", response_model=UploadResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def upload_and_process_pdf(
    title: str = "",
    file: UploadFile = File(...)
):
    """
    Upload PDF, save to filesystem, process for RAG
    
    Process:
    1. Validate file (type, size, name)
    2. Save to filesystem
    3. Extract text
    4. Chunk text
    5. Generate embeddings
    6. Upsert to Qdrant
    """
    start_time = time.time()
    
    # Validate file
    is_valid, error_msg = validate_pdf_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Check file size
    try:
        file_size = await get_file_size(file)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB."
            )
    except Exception as e:
        logger.error(f"Error checking file size: {e}")
        raise HTTPException(status_code=400, detail="Could not read file size")
    
    # Safe filename
    safe_filename = Path(file.filename).name
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Add timestamp to avoid collisions
    timestamp = int(time.time())
    unique_filename = f"{timestamp}_{safe_filename}"
    container_save_path = Path(PDF_STORAGE_PATH) / unique_filename
    
    logger.info(f"Processing upload: {safe_filename} ({file_size} bytes)")
    
    try:
        # Save file
        container_save_path.parent.mkdir(parents=True, exist_ok=True)
        with container_save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File saved: {container_save_path}")
        
        # Extract text
        text = extract_text_from_pdf(str(container_save_path))
        if not text or len(text.strip()) < 50:
            logger.warning(f"Minimal text extracted from {safe_filename}")
            return UploadResponse(
                message="File saved, but very little text could be extracted. It may be a scanned PDF requiring OCR.",
                filename=safe_filename,
                container_path=str(container_save_path),
                chunks_created=0,
                processing_time=time.time() - start_time
            )
        
        # Chunk text
        chunks = chunk_text_by_tokens(
            text,
            max_tokens=CHUNK_SIZE_TOKENS,
            overlap_tokens=CHUNK_OVERLAP_TOKENS
        )
        if not chunks:
            raise HTTPException(
                status_code=500,
                detail="Failed to chunk document text"
            )
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # Generate embeddings
        embeddings = get_embeddings_for_chunks(chunks)
        if not embeddings or len(embeddings) != len(chunks):
            raise HTTPException(
                status_code=500,
                detail="Failed to generate embeddings. Check Gemini API key and quota."
            )
        
        # Prepare for Qdrant
        file_metadata = {
            "container_path": str(container_save_path),
            "original_filename": safe_filename,
            "title": title or safe_filename,
            "subject": title or "Unknown",
            "upload_timestamp": timestamp,
            "file_size_bytes": file_size
        }
        
        chunks_for_qdrant = []
        for i, chunk_text in enumerate(chunks):
            if chunk_text and chunk_text.strip():
                chunk_meta = {**file_metadata, "page_number": i + 1}
                chunks_for_qdrant.append({
                    "chunk_text": chunk_text,
                    "embedding": embeddings[i],
                    "metadata": chunk_meta
                })
        
        if not chunks_for_qdrant:
            raise HTTPException(
                status_code=500,
                detail="No valid chunks generated after processing"
            )
        
        # Upsert to Qdrant
        success = upsert_material_chunks(chunks_for_qdrant)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to save chunks to vector database"
            )
        
        processing_time = time.time() - start_time
        logger.info(f"Upload processed successfully in {processing_time:.2f}s: {len(chunks_for_qdrant)} chunks")
        
        return UploadResponse(
            message=f"File uploaded and processed successfully. Created {len(chunks_for_qdrant)} searchable chunks.",
            filename=safe_filename,
            container_path=str(container_save_path),
            chunks_created=len(chunks_for_qdrant),
            processing_time=processing_time
        )
    
    except HTTPException:
        # Clean up file on error
        if container_save_path.exists():
            try:
                container_save_path.unlink()
            except:
                pass
        raise
    except Exception as e:
        logger.error(f"Error processing upload {safe_filename}: {e}", exc_info=True)
        # Clean up file
        if container_save_path.exists():
            try:
                container_save_path.unlink()
            except:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )

@app.get("/api/materials/download-pdf")
async def download_pdf(file_path: str):
    """Download PDF from filesystem"""
    # Security: validate path
    base_dir = os.path.abspath(PDF_STORAGE_PATH)
    requested_path = os.path.abspath(file_path)
    
    if not requested_path.startswith(base_dir):
        logger.warning(f"Path traversal attempt: {file_path}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    path_obj = Path(requested_path)
    if not path_obj.exists() or not path_obj.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(path_obj),
        filename=path_obj.name,
        media_type='application/pdf'
    )

@app.delete("/api/materials/delete-pdf")
async def delete_pdf(file_path: str):
    """Delete PDF and associated chunks from Qdrant"""
    try:
        # Security check
        base_dir = os.path.abspath(PDF_STORAGE_PATH)
        requested_path = os.path.abspath(file_path)
        
        if not requested_path.startswith(base_dir):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete from Qdrant
        deleted_count = delete_document_chunks(file_path)
        
        # Delete file
        path_obj = Path(requested_path)
        if path_obj.exists():
            path_obj.unlink()
            logger.info(f"Deleted file: {file_path}")
        
        return {
            "message": "Document deleted successfully",
            "file_path": file_path,
            "chunks_deleted": deleted_count
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test-connections")
async def test_connections():
    """Test Qdrant connection and configuration"""
    qdrant_status = "Not Connected"
    q_collections = []
    target_collection_exists = False
    
    try:
        client = get_qdrant_client()
        if client:
            collections_resp = client.get_collections()
            q_collections = [c.name for c in collections_resp.collections]
            qdrant_status = "Connected"
            target_collection_exists = os.getenv("QDRANT_COLLECTION", "study_materials") in q_collections
        else:
            qdrant_status = "Client initialization failed"
    except Exception as e:
        qdrant_status = f"Connection failed: {e}"
        logger.error(f"Qdrant connection test failed: {e}")
    
    return {
        "qdrant_status": qdrant_status,
        "qdrant_host": os.getenv("QDRANT_HOST"),
        "qdrant_port": os.getenv("QDRANT_PORT"),
        "qdrant_collections_found": q_collections,
        "target_collection_name": os.getenv("QDRANT_COLLECTION"),
        "target_collection_exists": target_collection_exists,
        "pdf_storage_path": PDF_STORAGE_PATH,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY"))
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )