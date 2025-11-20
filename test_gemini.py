"""
Quick test to verify the model works before running Flask
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ ERROR: GEMINI_API_KEY not found")
    exit(1)

print(f"✅ API Key: {GEMINI_API_KEY[:20]}...")

genai.configure(api_key=GEMINI_API_KEY)

# Test the recommended model
model_name = "models/gemini-2.5-flash"
print(f"\n🧪 Testing: {model_name}")

try:
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Say 'Hello! I am working perfectly!'")
    print(f"✅ SUCCESS!")
    print(f"📝 Response: {response.text}")
    print(f"\n🎉 Your model is working! Use this in frontend_app.py:")
    print(f'   AVAILABLE_MODELS = ["{model_name}"]')
except Exception as e:
    print(f"❌ FAILED: {e}")
    print("\n🔄 Try these alternatives:")
    print('   1. "models/gemini-2.0-flash"')
    print('   2. "models/gemini-flash-latest"')
    print('   3. "models/gemini-2.0-flash-001"')