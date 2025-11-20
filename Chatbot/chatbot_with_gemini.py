from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import google.generativeai as genai
import os
from datetime import datetime
import uuid
import traceback

app = Flask(__name__)
CORS(app)
app.secret_key = 'gemini_chatbot_secret_2025'

# Configure Gemini API with your key
GEMINI_API_KEY = "AIzaSyDlDJK3RHrP_IZYKK_EayaAqvYRhZpi_-s"
genai.configure(api_key=GEMINI_API_KEY)

# Use the correct model name
AVAILABLE_MODELS = ["gemini-1.5-flash-latest"]

@app.route('/')
@app.route('/gemini')
def index():
    """Main chatbot page"""
    session.clear()
    session['conversation_id'] = str(uuid.uuid4())
    session['conversation'] = []
    session['current_model'] = AVAILABLE_MODELS[0]
    return render_template('gemini_chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        print("\n[CHAT] New message received")
        
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        print(f"[CHAT] User: {user_message[:50]}...")
        
        conversation = session.get('conversation', [])
        current_model = session.get('current_model', AVAILABLE_MODELS[0])
        
        # Initialize Gemini model with CORRECT model name
        model = genai.GenerativeModel(current_model)
        
        # Generate response with conversation history
        if conversation:
            history = []
            for msg in conversation:
                if msg["role"] == "user":
                    history.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    history.append({"role": "model", "parts": [msg["content"]]})
            
            chat_session = model.start_chat(history=history)
            response = chat_session.send_message(user_message)
        else:
            response = model.generate_content(user_message)
        
        bot_response = response.text
        print(f"[CHAT] Bot: {bot_response[:50]}...")
        
        # Save to conversation history
        conversation.append({"role": "user", "content": user_message})
        conversation.append({"role": "assistant", "content": bot_response})
        session['conversation'] = conversation
        
        return jsonify({
            'response': bot_response,
            'model': current_model,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        
        return jsonify({
            'error': f'Chat error: {error_msg}'
        }), 500

@app.route('/clear', methods=['POST'])
def clear_conversation():
    """Clear chat history"""
    try:
        session['conversation'] = []
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug', methods=['GET'])
def debug_info():
    """Debug information"""
    return jsonify({
        'model': session.get('current_model'),
        'conversation_length': len(session.get('conversation', [])),
        'session_id': session.get('conversation_id'),
        'api_configured': True
    })

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini AI Chatbot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .chat-container {
            width: 100%;
            max-width: 900px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 700px;
        }
        .chat-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            text-align: center;
            position: relative;
        }
        .chat-header h1 { font-size: 2rem; margin-bottom: 8px; }
        .chat-header p { opacity: 0.9; font-size: 1rem; }
        .status-dot {
            position: absolute;
            top: 25px;
            right: 25px;
            width: 12px;
            height: 12px;
            background: #4ade80;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.3); opacity: 0.6; }
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 25px;
            background: #f5f5f5;
        }
        .message {
            margin-bottom: 20px;
            display: flex;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user { justify-content: flex-end; }
        .message-bubble {
            max-width: 75%;
            padding: 16px 20px;
            border-radius: 18px;
            word-wrap: break-word;
            line-height: 1.5;
            white-space: pre-wrap;
        }
        .user .message-bubble {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 4px;
        }
        .bot .message-bubble {
            background: white;
            color: #333;
            border: 1px solid #e0e0e0;
            border-bottom-left-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .error .message-bubble {
            background: #fee;
            border-color: #fcc;
            color: #c00;
        }
        .welcome {
            text-align: center;
            color: #666;
            padding: 60px 30px;
        }
        .welcome h2 { font-size: 1.8rem; margin-bottom: 15px; color: #667eea; }
        .welcome p { font-size: 1.1rem; margin-bottom: 10px; }
        .typing { display: none; padding: 15px 25px; color: #999; font-style: italic; }
        .chat-input-area {
            padding: 20px;
            background: white;
            border-top: 2px solid #e0e0e0;
        }
        .controls { display: flex; gap: 12px; margin-bottom: 15px; }
        .btn {
            padding: 10px 18px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
            font-weight: 500;
        }
        .btn:hover {
            background: #f5f5f5;
            border-color: #667eea;
            transform: translateY(-1px);
        }
        .input-form { display: flex; gap: 12px; align-items: flex-end; }
        .input-box {
            flex: 1;
            padding: 16px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
            transition: border-color 0.3s;
            resize: none;
            font-family: inherit;
            min-height: 54px;
            max-height: 120px;
        }
        .input-box:focus { border-color: #667eea; }
        .send-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            width: 54px;
            height: 54px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            font-size: 22px;
        }
        .send-btn:hover:not(:disabled) {
            transform: scale(1.08);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        .send-btn:disabled { background: #ccc; cursor: not-allowed; transform: none; }
        @media (max-width: 768px) {
            .chat-container { height: 90vh; }
            .message-bubble { max-width: 85%; }
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <div class="status-dot"></div>
            <h1>🤖 Gemini AI Chat</h1>
            <p>Powered by Google Gemini 1.5 Flash</p>
        </div>
        <div class="chat-messages" id="messages">
            <div class="welcome">
                <h2>Welcome! 👋</h2>
                <p>I'm your AI assistant powered by Gemini</p>
                <p>Ask me anything!</p>
            </div>
        </div>
        <div class="typing" id="typing">AI is thinking...</div>
        <div class="chat-input-area">
            <div class="controls">
                <button class="btn" onclick="clearChat()">🗑️ Clear Chat</button>
                <button class="btn" onclick="showDebug()">🔍 Debug</button>
            </div>
            <form class="input-form" id="form">
                <textarea id="input" class="input-box" placeholder="Type your message..." rows="1" required></textarea>
                <button type="submit" class="send-btn" id="sendBtn">➤</button>
            </form>
        </div>
    </div>
    <script>
        class ChatBot {
            constructor() {
                this.form = document.getElementById('form');
                this.input = document.getElementById('input');
                this.messages = document.getElementById('messages');
                this.typing = document.getElementById('typing');
                this.sendBtn = document.getElementById('sendBtn');
                this.form.onsubmit = (e) => { e.preventDefault(); this.send(); };
                this.input.onkeydown = (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send(); }
                };
                this.input.oninput = () => {
                    this.input.style.height = 'auto';
                    this.input.style.height = Math.min(this.input.scrollHeight, 120) + 'px';
                };
            }
            async send() {
                const text = this.input.value.trim();
                if (!text) return;
                this.input.value = '';
                this.input.style.height = 'auto';
                this.addMsg(text, 'user');
                this.showTyping(true);
                this.sendBtn.disabled = true;
                try {
                    const res = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        this.addMsg(data.response, 'bot');
                    } else {
                        throw new Error(data.error || 'Error occurred');
                    }
                } catch (err) {
                    console.error(err);
                    this.addMsg('❌ ' + err.message, 'error');
                } finally {
                    this.showTyping(false);
                    this.sendBtn.disabled = false;
                    this.input.focus();
                }
            }
            addMsg(text, type) {
                const welcome = this.messages.querySelector('.welcome');
                if (welcome) welcome.remove();
                const div = document.createElement('div');
                div.className = `message ${type}`;
                const bubble = document.createElement('div');
                bubble.className = 'message-bubble';
                bubble.textContent = text;
                div.appendChild(bubble);
                this.messages.appendChild(div);
                this.messages.scrollTop = this.messages.scrollHeight;
            }
            showTyping(show) {
                this.typing.style.display = show ? 'block' : 'none';
                if (show) this.messages.scrollTop = this.messages.scrollHeight;
            }
            async clear() {
                try {
                    await fetch('/clear', { method: 'POST' });
                    this.messages.innerHTML = '<div class="welcome"><h2>Chat cleared! 🧹</h2><p>Start a new conversation</p></div>';
                } catch (err) {
                    console.error(err);
                }
            }
            async debug() {
                try {
                    const res = await fetch('/debug');
                    const data = await res.json();
                    const info = `🔍 Debug Info:\\nModel: ${data.model}\\nMessages: ${data.conversation_length}\\nSession: ${data.session_id}`;
                    this.addMsg(info, 'bot');
                } catch (err) {
                    console.error(err);
                }
            }
        }
        let bot;
        function clearChat() { bot.clear(); }
        function showDebug() { bot.debug(); }
        document.addEventListener('DOMContentLoaded', () => {
            bot = new ChatBot();
        });
    </script>
</body>
</html>'''
    
    with open('templates/gemini_chat.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("=" * 70)
    print("🚀 Gemini AI Chatbot - Standalone Version")
    print("=" * 70)
    print("✅ Gemini API configured")
    print(f"📝 Model: {AVAILABLE_MODELS[0]}")
    print("\n🌐 Access at: http://localhost:5000")
    print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)