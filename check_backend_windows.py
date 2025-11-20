# Save as test_flask_connection.py
import os
from dotenv import load_dotenv
import requests

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

print(f"Testing connection to: {BACKEND_URL}")

try:
    response = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
    print(f"✅ SUCCESS! Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"❌ FAILED: {e}")