import os
from pypdf import PdfReader
import tiktoken
import sys

# Initialize token counter ONCE
try:
    ENC = tiktoken.get_encoding("cl100k_base")
    print("Tiktoken encoder loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load tiktoken encoder: {e}")
    ENC = None

# Try to import OCR libraries (optional)
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
    print("OCR libraries (pytesseract, pdf2image) loaded successfully.")
except ImportError:
    OCR_AVAILABLE = False
    print("OCR libraries not available. Scanned PDFs will be skipped.")
    print("To enable OCR, install: pip install pytesseract pdf2image pillow")
    print("And install system dependency: sudo apt-get install tesseract-ocr poppler-utils")


def extract_text_with_ocr(pdf_file_path: str, batch_size: int = 10) -> str:
    """
    Extract text from scanned PDF using OCR in batches to save memory.
    Processes pages in batches to avoid memory overflow on large PDFs.
    """
    if not OCR_AVAILABLE:
        return ""
    
    file_basename = os.path.basename(pdf_file_path)
    print(f"Attempting OCR extraction from {file_basename}...")
    
    try:
        from pdf2image import convert_from_path
        import pytesseract
        
        # Get total page count first
        reader = PdfReader(pdf_file_path)
        total_pages = len(reader.pages)
        print(f"OCR will process {total_pages} pages in batches of {batch_size}...")
        
        text = ""
        
        # Process in batches to avoid memory issues
        for start_page in range(1, total_pages + 1, batch_size):
            end_page = min(start_page + batch_size - 1, total_pages)
            print(f"  OCR processing pages {start_page}-{end_page}/{total_pages}...")
            
            try:
                # Convert only this batch of pages
                images = convert_from_path(
                    pdf_file_path,
                    dpi=200,  # Lower DPI = less memory (300 is too high for large PDFs)
                    first_page=start_page,
                    last_page=end_page
                )
                
                for i, image in enumerate(images):
                    page_num = start_page + i
                    page_text = pytesseract.image_to_string(image)
                    if page_text and page_text.strip():
                        text += f"\n\n--- Page {page_num} ---\n\n" + page_text.strip()
                
                # Free memory after each batch
                del images
                
            except Exception as batch_error:
                print(f"  Warning: Error processing batch pages {start_page}-{end_page}: {batch_error}")
                continue
        
        print(f"OCR extraction complete. Extracted approx {len(text)} characters.")
        return text.strip()
    
    except Exception as e:
        print(f"ERROR during OCR extraction: {e}")
        import traceback
        traceback.print_exc()
        return ""


def extract_text_from_pdf(pdf_file_path: str, use_ocr_fallback: bool = True, max_pages_for_ocr: int = 50) -> str:
    """
    Extracts text from a PDF file using pypdf.
    If no text is found and OCR is available, falls back to OCR extraction.
    
    Args:
        pdf_file_path: Path to the PDF file
        use_ocr_fallback: Whether to try OCR if regular extraction fails
        max_pages_for_ocr: Maximum number of pages to attempt OCR on (prevents memory issues)
    
    Returns:
        Extracted text as string, or empty string if extraction fails
    """
    file_basename = os.path.basename(pdf_file_path)
    print(f"Attempting to extract text from {file_basename}...")
    
    try:
        reader = PdfReader(pdf_file_path)
        text = ""
        num_pages = len(reader.pages)
        print(f"PDF has {num_pages} pages.")
        
        # Extract text from all pages
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += f"\n\n--- Page {i+1} ---\n\n" + page_text.strip()
            except Exception as page_e:
                print(f"Warning: Error extracting text from page {i+1}: {page_e}")
        
        text = text.strip()
        print(f"Standard extraction: approx {len(text)} characters from {file_basename}.")
        
        # If no text extracted and OCR is available, try OCR
        if len(text) < 100 and use_ocr_fallback and OCR_AVAILABLE:
            # SKIP OCR for large PDFs (memory intensive)
            if num_pages > max_pages_for_ocr:
                print(f"⚠️  PDF has {num_pages} pages (>{max_pages_for_ocr}). Skipping OCR to prevent memory issues.")
                print(f"   Consider splitting this PDF into smaller files or using dedicated OCR tools.")
                print(f"   Alternatively, increase Docker memory and raise max_pages_for_ocr parameter.")
                return ""
            
            print(f"Very little text extracted. Attempting OCR fallback...")
            ocr_text = extract_text_with_ocr(pdf_file_path)
            if len(ocr_text) > len(text):
                print(f"✅ OCR successful! Using OCR text instead.")
                return ocr_text
            else:
                print(f"⚠️  OCR did not extract more text than standard method.")
        
        return text
        
    except Exception as e:
        print(f"CRITICAL ERROR extracting text from PDF {file_basename}: {e}")
        import traceback
        traceback.print_exc()
        
        # Try OCR as last resort for files that can't be opened normally
        if use_ocr_fallback and OCR_AVAILABLE:
            try:
                reader = PdfReader(pdf_file_path)
                num_pages = len(reader.pages)
                if num_pages <= max_pages_for_ocr:
                    print("Attempting OCR as fallback for corrupted/unreadable PDF...")
                    return extract_text_with_ocr(pdf_file_path)
            except:
                pass
        
        return ""


def chunk_text_by_tokens(text: str, max_tokens: int = 400, overlap_tokens: int = 50) -> list[str]:
    """
    Splits text into overlapping chunks based on token count using tiktoken.
    
    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk (default 400 for optimal embedding)
        overlap_tokens: Number of tokens to overlap between chunks (preserves context)
    
    Returns:
        List of text chunks
    """
    if not ENC:
        print("ERROR: Tiktoken encoder not available. Cannot chunk text.")
        return []

    print(f"Attempting to chunk text into pieces of ~{max_tokens} tokens...")
    
    if not text or not text.strip():
        print("Warning: Input text is empty. No chunks generated.")
        return []

    try:
        tokens = ENC.encode(text)
        total_tokens = len(tokens)
        print(f"Total tokens in text: {total_tokens}")
        
        # If text is smaller than max_tokens, return as single chunk
        if total_tokens <= max_tokens:
            print(f"Text fits in single chunk ({total_tokens} tokens).")
            return [text.strip()]
        
        chunks = []
        start_index = 0
        
        while start_index < total_tokens:
            # Calculate end index for this chunk
            end_index = min(start_index + max_tokens, total_tokens)
            
            # Extract tokens for this chunk
            chunk_tokens = tokens[start_index:end_index]
            
            # Decode back to text
            chunk_text = ENC.decode(chunk_tokens)
            
            # Only add non-empty chunks
            if chunk_text and chunk_text.strip():
                chunks.append(chunk_text.strip())
            
            # Move to next chunk with overlap
            step = max(1, max_tokens - overlap_tokens)
            start_index += step
            
            # Safety check: prevent infinite loop
            if start_index >= total_tokens:
                break
        
        print(f"Chunked text into {len(chunks)} pieces.")
        return chunks
        
    except Exception as e:
        print(f"ERROR during text chunking: {e}")
        import traceback
        traceback.print_exc()
        return []


# Optional: Function to get chunk statistics
def get_chunk_stats(chunks: list[str]) -> dict:
    """
    Get statistics about chunks (useful for debugging)
    
    Args:
        chunks: List of text chunks
    
    Returns:
        Dictionary with chunk statistics
    """
    if not chunks or not ENC:
        return {}
    
    token_counts = [len(ENC.encode(chunk)) for chunk in chunks]
    
    return {
        "total_chunks": len(chunks),
        "min_tokens": min(token_counts) if token_counts else 0,
        "max_tokens": max(token_counts) if token_counts else 0,
        "avg_tokens": sum(token_counts) / len(token_counts) if token_counts else 0,
        "total_tokens": sum(token_counts)
    }