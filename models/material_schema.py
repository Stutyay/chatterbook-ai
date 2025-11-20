# --- Reference Schema for 'materials' collection ---
MATERIAL_SCHEMA = {
    "source_title": "string (e.g., 'CSA - book_chapter_1.pdf')",
    "original_filename": "string (e.g., 'book_chapter_1.pdf')",
    "source_file_id": "ObjectId (links to GridFS file)",
    "chunk_text": "string (a specific text chunk)",
    "embedding": "[float] (768-dimension vector)",
    "metadata": {
        "original_path": "string (relative path within source_documents)",
        "semester": "string (e.g., 'Sem 1')",
        "subject": "string (e.g., 'CSA')",
        "page_number": "integer (approximate page/chunk index)",
    }
}
