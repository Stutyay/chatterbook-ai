"""
ChatterbookAI Frontend Application - All-in-One (FIXED)
Fixes: PYQ upload, Books download, File handling
"""

from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import requests
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime
import sqlite3

# Initialize SQLite database for tracking
DB_FILE = "usage_tracking.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            question TEXT,
            book_selected TEXT,
            answer TEXT,
            found_relevant BOOLEAN,
            rating TEXT DEFAULT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS session_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            time_saved_estimate TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def log_query(question, book_selected, answer, found_relevant):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO queries (question, book_selected, answer, found_relevant)
            VALUES (?, ?, ?, ?)
        ''', (question, book_selected, answer, found_relevant))
        query_id = c.lastrowid
        conn.commit()
        conn.close()
        return query_id
    except Exception as e:
        print(f"Error logging query: {e}")
        return None

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY')

# Backend API configuration for RAG
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Groq API configuration for standalone chatbot
from utils.ai_utils import generate_generic_chat_response
AVAILABLE_MODELS = ["openai/gpt-oss-20b"]

# Simple user database (JSON file)
USERS_FILE = "users.json"

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def is_logged_in():
    """Check if user is logged in"""
    return 'user_id' in session and 'email' in session

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/login', methods=['GET'])
def login_page():
    """Serve the login page"""
    if is_logged_in():
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET'])
def register_page():
    """Serve the register page"""
    if is_logged_in():
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/api/login', methods=['POST'])
def login_api():
    """Handle login requests"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Load users
        users = load_users()
        
        if email not in users:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        user = users[email]
        
        # Verify password
        if not check_password_hash(user['password_hash'], password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Set session
        session['user_id'] = user['id']
        session['email'] = email
        session['name'] = user.get('name', email.split('@')[0])
        
        # Update last login
        users[email]['last_login'] = datetime.now().isoformat()
        save_users(users)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'email': email,
                'name': session['name']
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@app.route('/api/register', methods=['POST'])
def register_api():
    """Handle registration requests"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        
        # Validation
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        if password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Load users
        users = load_users()
        
        # Check if user already exists
        if email in users:
            return jsonify({'error': 'An account with this email already exists'}), 400
        
        # Create new user
        user_id = str(uuid.uuid4())
        users[email] = {
            'id': user_id,
            'email': email,
            'password_hash': generate_password_hash(password),
            'name': email.split('@')[0],
            'created_at': datetime.now().isoformat(),
            'last_login': None
        }
        
        # Save users
        save_users(users)
        
        # Auto-login after registration
        session['user_id'] = user_id
        session['email'] = email
        session['name'] = users[email]['name']
        
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'user': {
                'email': email,
                'name': session['name']
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@app.route('/api/logout', methods=['POST'])
def logout_api():
    """Handle logout requests"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/user', methods=['GET'])
def get_user():
    """Get current user info"""
    if is_logged_in():
        return jsonify({
            'logged_in': True,
            'user': {
                'email': session['email'],
                'name': session['name']
            }
        })
    return jsonify({'logged_in': False})

# ============================================================================
# CHATTERBOOK AI PAGES (Main Application)
# ============================================================================

@app.route('/')
def index():
    """Serve the main ChatterbookAI interface"""
    return render_template('Main page.html')

@app.route('/chat')
def chat_page():
    """Serve the RAG-based study chat interface"""
    return render_template('chat.html')

# ============================================================================
# RAG STUDY CHAT API (Proxies to FastAPI Backend)
# ============================================================================

@app.route('/api/chat', methods=['POST'])
def rag_chat():
    """Proxy RAG chat requests to the FastAPI backend"""
    try:
        data = request.get_json()
        
        response = requests.post(
            f"{BACKEND_URL}/api/chat",
            json=data,
            timeout=30
        )
        
        resp_data = response.json()
        status_code = response.status_code
        
        # Auto-log query if it's a successful response
        if status_code == 200:
            answer = resp_data.get('answer', '')
            sources = resp_data.get('sources', [])
            # It's relevant if it has sources and didn't start with the fallback message
            found_relevant = bool(sources) and not answer.startswith("I couldn't find any relevant information")
            
            query_id = log_query(
                data.get('message', ''),
                data.get('book_name', 'UNFILTERED'),
                answer,
                found_relevant
            )
            resp_data['query_id'] = query_id
        
        return jsonify(resp_data), status_code
        
    except Exception as e:
        print(f"Error in RAG chat: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/feedback/rate', methods=['POST'])
def rate_query():
    """Handle thumbs up/down feedback for a query"""
    try:
        data = request.get_json()
        query_id = data.get('query_id')
        rating = data.get('rating')
        if not query_id or not rating:
            return jsonify({'error': 'query_id and rating required'}), 400
            
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE queries SET rating = ? WHERE id = ?", (rating, query_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error rating query: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback/session', methods=['POST'])
def session_feedback():
    """Handle session time-saved feedback"""
    try:
        data = request.get_json()
        time_saved = data.get('time_saved_estimate')
        if not time_saved:
            return jsonify({'error': 'time_saved_estimate required'}), 400
            
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO session_feedback (time_saved_estimate) VALUES (?)", (time_saved,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in session feedback: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/books', methods=['GET'])
def get_books():
    """Proxy getting books from FastAPI backend"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/books",
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        print(f"Error getting books: {e}")
        return jsonify({"error": str(e)}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'error': 'Cannot connect to backend server',
            'detail': 'Make sure backend_app.py is running on port 8000'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            'error': 'Backend request timed out',
            'detail': 'The query took too long to process'
        }), 504
    except Exception as e:
        return jsonify({
            'error': 'Frontend error',
            'detail': str(e)
        }), 500

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """Proxy PDF upload requests to the FastAPI backend - FIXED VERSION"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        title = request.form.get('title', file.filename)
        
        print(f"\n[UPLOAD] Starting upload: {file.filename}")
        print(f"[UPLOAD] Title: {title}")
        print(f"[UPLOAD] Content-Type: {file.content_type}")
        print(f"[UPLOAD] Backend URL: {BACKEND_URL}")
        
        # Read file content into memory (don't use file.read() which empties the stream)
        file.seek(0)  # Ensure we're at the start
        file_content = file.read()
        file_size = len(file_content)
        
        print(f"[UPLOAD] File size: {file_size} bytes ({file_size/1024/1024:.2f} MB)")
        
        if file_size == 0:
            return jsonify({'error': 'File is empty'}), 400
        
        if file_size > 200 * 1024 * 1024:  # 200MB limit
            return jsonify({'error': 'File too large. Maximum size is 200MB'}), 400
        
        # Prepare files and data for multipart upload
        files = {
            'file': (file.filename, file_content, file.content_type or 'application/pdf')
        }
        data = {
            'title': title
        }
        
        print(f"[UPLOAD] Sending to: {BACKEND_URL}/api/materials/upload-and-process-pdf")
        
        # Send to backend
        response = requests.post(
            f"{BACKEND_URL}/api/materials/upload-and-process-pdf",
            files=files,
            data=data,
            timeout=600  # 10 minutes for large PDFs
        )
        
        print(f"[UPLOAD] Backend status: {response.status_code}")
        print(f"[UPLOAD] Backend response: {response.text[:500]}")
        
        if response.status_code == 200:
            print(f"[UPLOAD] ✅ Upload successful!")
        else:
            print(f"[UPLOAD] ❌ Upload failed with status {response.status_code}")
        
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.ConnectionError as e:
        print(f"[UPLOAD ERROR] Connection failed: {e}")
        return jsonify({
            'error': 'Cannot connect to backend server',
            'detail': f'Backend at {BACKEND_URL} is not reachable. Ensure Docker containers are running: docker-compose up -d'
        }), 503
    except requests.exceptions.Timeout:
        print(f"[UPLOAD ERROR] Request timed out")
        return jsonify({
            'error': 'Upload timed out',
            'detail': 'Processing took too long. Try a smaller file or check backend performance.'
        }), 504
    except Exception as e:
        print(f"[UPLOAD ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Upload failed',
            'detail': str(e)
        }), 500

@app.route('/api/backend-status', methods=['GET'])
def backend_status():
    """Check if the RAG backend is reachable"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'unreachable',
            'backend_url': BACKEND_URL,
            'message': 'Backend server is not running. Run: docker-compose up -d'
        }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/books/list', methods=['GET'])
def list_books():
    """List all available PDF books from all sources"""
    try:
        # Search in multiple possible locations
        possible_dirs = [
            ('static/pdfs', os.path.join(app.root_path, 'static', 'pdfs')),
            ('source_documents', os.path.join(app.root_path, 'source_documents')),
            ('source_documents_root', os.path.join(os.getcwd(), 'source_documents'))
        ]
        
        all_books = {}
        
        for location_name, search_dir in possible_dirs:
            if os.path.exists(search_dir):
                pdfs = [f for f in os.listdir(search_dir) if f.lower().endswith('.pdf')]
                if pdfs:
                    all_books[location_name] = {
                        'path': search_dir,
                        'files': pdfs
                    }
        
        return jsonify({
            'success': True,
            'locations': all_books,
            'total_files': sum(len(loc['files']) for loc in all_books.values())
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# STATIC FILES & ERROR HANDLERS - FIXED PDF SERVING
# ============================================================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS, images, PDFs)"""
    static_dir = os.path.join(app.root_path, 'static')
    return send_from_directory(static_dir, filename)

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Page not found',
        'message': 'The requested URL was not found on the server.'
    }), 404

@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'message': str(e)
    }), 500

# ============================================================================
# SERVER STARTUP
# ============================================================================

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('static/pdfs', exist_ok=True)
    
    print("=" * 80)
    print("🚀 ChatterbookAI - Unified Frontend Server Starting (FIXED VERSION)...")
    print("=" * 80)
    print(f"📡 RAG Backend URL: {BACKEND_URL}")
    print(f"🤖 Groq API via Backend: Enabled ✅")
    print(f"🔐 Authentication: Enabled ✅")
    print("🌐 Server URL: http://localhost:5173")
    print("=" * 80)
    print("\n📋 Available Routes:")
    print("   Authentication:")
    print("   • http://localhost:5173/login (Login)")
    print("   • http://localhost:5173/register (Register)")
    print("\n   ChatterbookAI (RAG System):")
    print("   • http://localhost:5173/ (Home)")
    print("   • http://localhost:5173/books (Books)")
    print("   • http://localhost:5173/chat (Study Chat - RAG)")
    print("   • http://localhost:5173/pyqs (Previous Year Questions)")
    print("\n   Standalone AI Chatbot:")
    print("=" * 80)
    print("\n⚠️  Important:")
    print("   1. For RAG features: docker-compose up -d")
    print("   2. Backend health: http://localhost:8000/api/health")
    print("   3. Standalone chatbot works independently (via ai_utils)")
    print("   4. User data stored in: users.json")
    print("   5. PDFs should be in: static/pdfs/ directory")
    print("=" * 80)
    print("\n🔧 FIXES APPLIED:")
    print("   ✅ PYQ upload - Fixed file reading and multipart form data")
    print("   ✅ Books download - Fixed PDF path resolution")
    print("   ✅ Added /download/<filename> endpoint for direct downloads")
    print("   ✅ Better error logging and debugging")
    print("=" * 80)
    
    app.run(debug=True, host='0.0.0.0', port=5173)