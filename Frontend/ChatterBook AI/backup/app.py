from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import google.generativeai as genai
import requests
import uuid
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'noshimi-change-this-for-production'
CORS(app)

# ========================================
# CONFIGURATION
# ========================================

# Gemini API Configuration
GEMINI_API_KEY = "AIzaSyDSdmcBz9vT4vX5ux_HnYR2Wc3bfrLlefA"
genai.configure(api_key=GEMINI_API_KEY)
AVAILABLE_GEMINI_MODELS = ["gemini-1.5-flash"]

# FastAPI Backend URL (for RAG-based chat)
FASTAPI_URL = "http://localhost:8000"

# ========================================
# MAIN PAGES (Landing, Books, Login, etc.)
# ========================================

@app.route('/')
def home():
    """Main landing page"""
    return render_template('Main page.html')

@app.route('/books')
def books():
    """Books catalog page"""
    return render_template('books.html')

@app.route('/pyq')
def pyq():
    """Previous Year Questions page"""
    return render_template('pyq.html')

@app.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@app.route('/register')
def register():
    """Registration page"""
    return render_template('register.html')

# ========================================
# RAG CHATBOT (Study Assistant with PDF Upload)
# ========================================

@app.route('/chat')
def rag_chat_interface():
    """RAG-based study assistant chat interface"""
    session['conversation_id'] = str(uuid.uuid4())
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def rag_chat():
    """
    RAG Chat API - Answers questions based on uploaded PDFs
    This connects to your FastAPI backend
    """
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        print(f"[RAG CHAT] User question: {user_message}")
        
        # Forward request to FastAPI backend
        response = requests.post(
            f"{FASTAPI_URL}/api/chat",
            json={
                "message": user_message,
                "k": data.get('k', 5)  # Number of document chunks to retrieve
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[RAG CHAT] Answer generated with {len(result.get('sources', []))} sources")
            return jsonify(result)
        else:
            error_detail = response.text
            print(f"[RAG CHAT] Backend error: {error_detail}")
            return jsonify({
                'error': 'Backend error', 
                'detail': error_detail
            }), response.status_code
            
    except requests.Timeout:
        print("[RAG CHAT] Request timeout")
        return jsonify({'error': 'Request timeout - backend took too long'}), 504
    except requests.ConnectionError:
        print("[RAG CHAT] Connection error - backend not reachable")
        return jsonify({'error': 'Cannot connect to backend. Is Docker running?'}), 503
    except Exception as e:
        print(f"[RAG CHAT] Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """
    Upload PDF to backend for processing
    The backend will extract text, create embeddings, and store in Qdrant
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        title = request.form.get('title', '')
        
        print(f"[UPLOAD] Processing: {file.filename} (title: {title})")
        
        # Forward to FastAPI
        files = {'file': (file.filename, file.stream, file.content_type)}
        data = {'title': title}
        
        response = requests.post(
            f"{FASTAPI_URL}/api/materials/upload-and-process-pdf",
            files=files,
            data=data,
            timeout=120  # PDF processing can take time
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[UPLOAD] Success: {result.get('chunks_created', 0)} chunks created")
            return jsonify(result)
        else:
            print(f"[UPLOAD] Failed: {response.text}")
            return jsonify({
                'error': 'Upload failed', 
                'detail': response.text
            }), response.status_code
            
    except Exception as e:
        print(f"[UPLOAD] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ========================================
# DIRECT GEMINI CHAT (General Purpose AI)
# ========================================

@app.route('/gemini')
def gemini_chat_interface():
    """Direct Gemini chat interface (no document context)"""
    session.clear()
    session['conversation_id'] = str(uuid.uuid4())
    session['conversation'] = []
    session['current_model'] = AVAILABLE_GEMINI_MODELS[0]
    return render_template('index.html', models=AVAILABLE_GEMINI_MODELS)

@app.route('/gemini/chat', methods=['POST'])
def gemini_chat():
    """
    Direct Gemini Chat API - General purpose AI chat
    Does NOT use your uploaded documents
    """
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        print(f"[GEMINI CHAT] User: {user_message[:50]}...")
        
        # Get conversation from session
        conversation = session.get('conversation', [])
        current_model = session.get('current_model', AVAILABLE_GEMINI_MODELS[0])
        
        # Initialize the model
        model = genai.GenerativeModel(
            model_name=current_model,
            generation_config={
                "temperature": 0.7,
                "top_p": 1.0,
                "top_k": 40,
                "max_output_tokens": 1024,
            },
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        )
        
        # Create chat session
        if conversation:
            history = []
            for msg in conversation:
                if msg["role"] == "user":
                    history.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    history.append({"role": "model", "parts": [msg["content"]]})
            
            chat = model.start_chat(history=history)
            response = chat.send_message(user_message)
        else:
            system_prompt = "You are a helpful AI assistant. Be concise, friendly, and engaging."
            initial_message = f"{system_prompt}\n\nUser: {user_message}"
            response = model.generate_content(initial_message)
        
        bot_response = response.text
        
        # Add messages to conversation history
        conversation.append({"role": "user", "content": user_message})
        conversation.append({"role": "assistant", "content": bot_response})
        session['conversation'] = conversation
        
        print(f"[GEMINI CHAT] Response length: {len(bot_response)} chars")
        
        return jsonify({
            'response': bot_response,
            'model': current_model,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"[GEMINI CHAT] Error: {str(e)}")
        return jsonify({'error': f'Gemini API Error: {str(e)}'}), 500

@app.route('/gemini/clear', methods=['POST'])
def gemini_clear():
    """Clear Gemini conversation history"""
    session['conversation'] = []
    return jsonify({'status': 'success'})

# ========================================
# HEALTH & DEBUG ENDPOINTS
# ========================================

@app.route('/api/health')
def health_check():
    """
    Combined health check for all services
    Returns status of Flask, FastAPI backend, Qdrant, and Gemini
    """
    health_data = {
        'flask_status': 'healthy',
        'gemini_configured': bool(GEMINI_API_KEY),
        'timestamp': datetime.now().isoformat()
    }
    
    # Check FastAPI backend
    try:
        backend_response = requests.get(f"{FASTAPI_URL}/api/health", timeout=5)
        if backend_response.status_code == 200:
            backend_health = backend_response.json()
            health_data.update({
                'backend_status': backend_health.get('status', 'unknown'),
                'qdrant_connected': backend_health.get('qdrant_connected', False),
                'pdf_storage_writable': backend_health.get('pdf_storage_writable', False)
            })
        else:
            health_data['backend_status'] = 'error'
            health_data['backend_error'] = backend_response.text
    except requests.ConnectionError:
        health_data['backend_status'] = 'unreachable'
        health_data['qdrant_connected'] = False
        health_data['error'] = 'Cannot connect to FastAPI backend. Is Docker running?'
    except Exception as e:
        health_data['backend_status'] = 'error'
        health_data['error'] = str(e)
    
    return jsonify(health_data)

@app.route('/debug', methods=['GET'])
def debug_session():
    """Debug endpoint to check Gemini session state"""
    return jsonify({
        'current_model': session.get('current_model'),
        'available_models': AVAILABLE_GEMINI_MODELS,
        'conversation_length': len(session.get('conversation', [])),
        'session_id': session.get('conversation_id')
    })

@app.route('/api/backend-status')
def backend_status():
    """Check if backend services are reachable"""
    try:
        # Test FastAPI
        fastapi_response = requests.get(f"{FASTAPI_URL}/api/health", timeout=3)
        fastapi_ok = fastapi_response.status_code == 200
        
        # Test Qdrant (via FastAPI)
        qdrant_ok = False
        if fastapi_ok:
            data = fastapi_response.json()
            qdrant_ok = data.get('qdrant_connected', False)
        
        return jsonify({
            'fastapi_reachable': fastapi_ok,
            'qdrant_reachable': qdrant_ok,
            'message': 'All systems operational' if (fastapi_ok and qdrant_ok) else 'Some services unavailable'
        })
    except:
        return jsonify({
            'fastapi_reachable': False,
            'qdrant_reachable': False,
            'message': 'Backend services not running. Start with: docker-compose up -d'
        }), 503

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return render_template('Main page.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error', 'detail': str(e)}), 500

# ========================================
# STARTUP
# ========================================

if __name__ == '__main__':
    print("=" * 80)
    print("🚀 ChatterBooK AI - Complete Integrated Application")
    print("=" * 80)
    print()
    print("📄 AVAILABLE PAGES:")
    print("   🏠 Landing Page:           http://localhost:5000/")
    print("   📚 Books Catalog:          http://localhost:5000/books")
    print("   📝 Previous Year Qs:       http://localhost:5000/pyq")
    print("   🔐 Login:                  http://localhost:5000/login")
    print("   ✍️  Register:               http://localhost:5000/register")
    print()
    print("💬 CHAT INTERFACES:")
    print("   🤖 RAG Study Assistant:    http://localhost:5000/chat")
    print("      ↳ Upload PDFs and ask questions about them")
    print("      ↳ Get answers with source citations")
    print()
    print("   💬 General AI Chat:        http://localhost:5000/gemini")
    print("      ↳ Direct Gemini chat (no document context)")
    print()
    print("🔌 API ENDPOINTS:")
    print("   📊 Health Check:           http://localhost:5000/api/health")
    print("   💬 RAG Chat API:           POST http://localhost:5000/api/chat")
    print("   📤 Upload PDF:             POST http://localhost:5000/api/upload")
    print("   🤖 Gemini Chat API:        POST http://localhost:5000/gemini/chat")
    print("   🔍 Backend Status:         http://localhost:5000/api/backend-status")
    print()
    print("⚙️  BACKEND SERVICES REQUIRED:")
    print("   🔧 FastAPI Backend:        http://localhost:8000")
    print("   🗄️  Qdrant Vector DB:      http://localhost:6333")
    print()
    print("=" * 80)
    print("📋 QUICK START CHECKLIST:")
    print("   1. ✅ Start Docker services:  docker-compose up -d")
    print("   2. ✅ Process your PDFs:       docker-compose exec backend python batch_ingest_pdf.py")
    print("   3. ✅ Open any page above in your browser")
    print()
    print("🔍 TROUBLESHOOTING:")
    print("   • RAG chat not working? → Check http://localhost:5000/api/backend-status")
    print("   • PDF upload fails? → Ensure Docker containers are running")
    print("   • Gemini chat works independently (no backend needed)")
    print("=" * 80)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
    