import os
import uuid
import time
import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance, 
    VectorParams, 
    PointStruct, 
    CollectionStatus,
    Filter,
    FieldCondition,
    MatchValue
)
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Smart host detection
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
# If running in Docker and QDRANT_HOST not explicitly set, use service name
if os.path.exists('/.dockerenv') and QDRANT_HOST == "localhost":
    QDRANT_HOST = "qdrant"

QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "study_materials")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", 768))

_qdrant_client = None


def get_qdrant_client():
    """Get or create a Qdrant client instance."""
    global _qdrant_client
    if _qdrant_client is None:
        try:
            logger.info(f"🔌 Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
            _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            _qdrant_client.get_collections()  # connection test
            logger.info(f"✅ Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
        except Exception as e:
            logger.error(f"❌ Could not connect to Qdrant: {e}")
            _qdrant_client = None
    return _qdrant_client


# ---------------------------
# Collection Management
# ---------------------------
def ensure_collection_exists(max_retries: int = 5, delay: float = 1.0) -> bool:
    """Ensure the Qdrant collection exists and is ready."""
    client = get_qdrant_client()
    if not client:
        return False

    try:
        collections = client.get_collections().collections
        if QDRANT_COLLECTION not in [c.name for c in collections]:
            logger.warning(f"Collection '{QDRANT_COLLECTION}' not found. Creating...")
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=VECTOR_DIMENSION,
                    distance=Distance.COSINE
                ),
            )

            # Wait until the collection is ready
            for attempt in range(max_retries):
                info = client.get_collection(QDRANT_COLLECTION)
                if info.status == CollectionStatus.GREEN:
                    logger.info("✅ Qdrant collection is ready.")
                    return True
                logger.info(
                    f"Waiting for collection to become ready (attempt {attempt + 1}/{max_retries})..."
                )
                time.sleep(delay)
            logger.warning(f"⚠️ Collection '{QDRANT_COLLECTION}' not green after retries.")
            return False
        else:
            logger.info(f"Collection '{QDRANT_COLLECTION}' already exists.")
            return True
    except Exception as e:
        logger.error(f"Error ensuring Qdrant collection '{QDRANT_COLLECTION}': {e}", exc_info=True)
        return False


# ---------------------------
# Upsert Function
# ---------------------------
def upsert_material_chunks(chunks_data: List[Dict[str, Any]]) -> bool:
    """Upsert (insert/update) chunks into the Qdrant collection."""
    client = get_qdrant_client()
    if not client:
        logger.error("Qdrant client not available for upsert.")
        return False

    valid_points = []
    for i, data in enumerate(chunks_data):
        embedding = data.get("embedding")
        payload = data.get("metadata", {})
        payload["chunk_text"] = data.get("chunk_text", "")

        if not embedding or not isinstance(embedding, list):
            logger.warning(f"Skipping chunk {i}: invalid embedding.")
            continue
        if len(embedding) != VECTOR_DIMENSION:
            logger.warning(f"Skipping chunk {i}: wrong embedding dimension {len(embedding)}.")
            continue
        if "container_path" not in payload:
            logger.warning(f"Skipping chunk {i}: missing 'container_path'.")
            continue

        valid_points.append(
            PointStruct(
                id=str(uuid.uuid4()),  # random UUID for uniqueness
                vector=embedding,
                payload=payload,
            )
        )

    if not valid_points:
        logger.warning("No valid chunks to upsert to Qdrant.")
        return False

    try:
        response = client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=valid_points,
            wait=True,
        )
        logger.info(
            f"✅ Qdrant upsert completed. Status: {response.status}. Points upserted: {len(valid_points)}"
        )
        return True
    except Exception as e:
        logger.error(f"Error during upsert to Qdrant: {e}", exc_info=True)
        return False


# ---------------------------
# Search Function
# ---------------------------
def search_similar_chunks(query_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
    """Search for similar chunks based on a query embedding."""
    client = get_qdrant_client()
    if not client:
        return []

    try:
        search_result = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=k,
            with_payload=True,
            with_vectors=False,
        )
        results = [
            {"id": hit.id, "score": hit.score, "payload": hit.payload} for hit in search_result
        ]
        logger.info(f"🔍 Found {len(results)} similar chunks.")
        return results
    except Exception as e:
        logger.error(f"Error searching Qdrant collection '{QDRANT_COLLECTION}': {e}", exc_info=True)
        return []


# ---------------------------
# Delete Function
# ---------------------------
def delete_document_chunks(container_path: str) -> int:
    """Delete all chunks associated with a specific document path."""
    client = get_qdrant_client()
    if not client:
        logger.error("Qdrant client not available for delete.")
        return 0

    try:
        result = client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=models.Filter(
                must=[
                    FieldCondition(
                        key="container_path",
                        match=MatchValue(value=container_path),
                    )
                ]
            ),
            wait=True,
        )
        logger.info(f"🗑️ Deleted chunks for document: {container_path}")
        return getattr(result, "operation_id", 0)
    except Exception as e:
        logger.error(f"Error deleting document chunks: {e}", exc_info=True)
        return 0


# ---------------------------
# Initialization (optional)
# ---------------------------
if __name__ == "__main__":
    """Test connection and collection creation when running this file directly."""
    if ensure_collection_exists():
        logger.info("Qdrant setup verified successfully.")
    else:
        logger.error("Qdrant setup failed. Please check connection and environment settings.")
