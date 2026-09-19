# 📚 ChatterbookAI - Intelligent Study Assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A powerful AI-powered study platform that combines Retrieval Augmented Generation (RAG) with local AI and Groq to help students learn more effectively. Upload your study materials, chat with AI about your content, access previous year questions, and download textbooks - all in one place!

## 🌟 Features

### 🤖 RAG-Powered Study Chat
- Upload PDF documents (lecture notes, textbooks, research papers)
- Ask questions and get accurate answers with source citations
- Vector-based semantic search using Qdrant
- Context-aware responses powered by Groq LLaMA/Mixtral



### 📖 Digital Library
- Browse and download textbooks
- Organized by subject (Algorithms, Databases, Operating Systems, etc.)
- Quick access to essential study materials

### 📝 Previous Year Questions (PYQs)
- Upload and organize past exam papers
- Filter by subject and semester
- Help students prepare for exams effectively

### 🔐 User Authentication
- Secure registration and login system
- Session management
- Password hashing with Werkzeug
- User data stored securely in JSON format

## 🏗️ Architecture

```
ChatterbookAI/
├── Frontend (Flask)
│   ├── User Interface (HTML/CSS/JS)
│   ├── Authentication System
│   ├── Static File Serving
│   └── API Gateway
│
├── Backend (FastAPI)
│   ├── PDF Processing
│   ├── Text Chunking
│   ├── Vector Embeddings
│   └── RAG Pipeline
│
├── Vector Database (Qdrant)
│   ├── Document Embeddings
│   └── Semantic Search
│
└── AI Engine (Groq)
    ├── Text Embeddings (local sentence-transformers)
    └── Text Generation (Groq LLaMA)
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Groq API Key

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Stutyay/chatterbook-ai
cd chatterbookai
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Create `.env` file**
```env
# Groq API Key
GROQ_API_KEY=your_groq_api_key_here

# Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here

# Backend URL
BACKEND_URL=http://localhost:8000

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=study_materials
VECTOR_DIMENSION=768

# Storage
PDF_STORAGE_PATH=./pdf_storage
BATCH_SOURCE_PATH=./source_documents

# Upload Limits
MAX_FILE_SIZE_MB=50
CHUNK_SIZE_TOKENS=400
CHUNK_OVERLAP_TOKENS=50

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:5000
```

4. **Start Docker services (Backend + Qdrant)**
```bash
docker-compose up -d
```

5. **Verify backend is running**
```bash
curl http://localhost:8000/api/health
```

6. **Start Flask frontend**
```bash
python frontend_app.py
```

7. **Access the application**
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **Qdrant Dashboard:** http://localhost:6333/dashboard

## 📋 Usage Guide

### 1. Register/Login
- Navigate to http://localhost:5173/register
- Create an account with your email and password
- You'll be automatically logged in after registration

### 2. RAG Study Chat
- Go to http://localhost:5173/chat
- Upload a PDF document (lecture notes, textbooks, etc.)
- Wait for processing (creates searchable chunks)
- Ask questions about the content
- Get answers with source citations

### 3. AI Chatbot

- Start chatting immediately (no uploads needed)
- Ask any question - perfect for explanations and brainstorming

### 4. Access Study Materials
- **Books:** http://localhost:5173/books
- **PYQs:** http://localhost:5173/pyqs
- Browse and download materials

## 🛠️ Technology Stack

### Frontend
- **Flask** - Web framework
- **HTML/CSS/JavaScript** - UI
- **Tailwind CSS** - Styling
- **Font Awesome** - Icons

### Backend
- **FastAPI** - High-performance API framework
- **Pydantic** - Data validation
- **Python-dotenv** - Environment management

### AI & ML
- **Groq API** - Fast LLaMA models
- **Text Embeddings** - text-embedding-004 model
- **Qdrant** - Vector database for semantic search

### Storage & Processing
- **PyPDF2/pdfplumber** - PDF text extraction
- **tiktoken** - Token counting and chunking
- **Docker** - Containerization

### Security
- **Werkzeug** - Password hashing
- **Flask Sessions** - User session management
- **CORS** - Cross-origin resource sharing

## 📁 Project Structure

```
ChatterbookAI/
├── frontend_app.py              # Flask frontend application
├── backend_app.py               # FastAPI backend application
├── docker-compose.yml           # Docker services configuration
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (create this)
├── users.json                   # User database (auto-generated)
│
├── templates/                   # HTML templates
│   ├── Main page.html          # Landing page
│   ├── login.html              # Login page
│   ├── register.html           # Registration page
│   ├── chat.html               # RAG Study Chat

│   ├── books.html              # Books library
│   └── pyq.html                # Previous Year Questions
│
├── static/                      # Static files
│   ├── css/                    # Stylesheets
│   ├── js/                     # JavaScript files
│   └── pdfs/                   # Downloadable books
│
├── utils/                       # Utility modules
│   ├── ai_utils.py             # AI functions
│   ├── pdf_utils.py            # PDF processing
│   └── __init__.py
│
├── db/                          # Database handlers
│   ├── qdrant_handler.py       # Qdrant operations
│   └── __init__.py
│
└── pdf_storage/                 # Uploaded PDFs (auto-created)
```

## 🔑 API Endpoints

### Frontend (Flask) - Port 5173

#### Authentication
- `POST /api/login` - User login
- `POST /api/register` - User registration
- `POST /api/logout` - User logout
- `GET /api/user` - Get current user info

#### RAG Chat
- `POST /api/chat` - Send chat query
- `POST /api/upload` - Upload PDF for processing
- `GET /api/backend-status` - Check backend health



### Backend (FastAPI) - Port 8000

#### Health & Status
- `GET /` - API information
- `GET /api/health` - Health check
- `GET /api/test-connections` - Test Qdrant connection

#### Documents
- `POST /api/chat` - RAG chat query
- `POST /api/materials/upload-and-process-pdf` - Upload & process PDF
- `GET /api/materials/download-pdf` - Download PDF
- `DELETE /api/materials/delete-pdf` - Delete PDF

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | Required |
| `FLASK_SECRET_KEY` | Flask session secret | Auto-generated |
| `BACKEND_URL` | FastAPI backend URL | `http://localhost:8000` |
| `QDRANT_HOST` | Qdrant host | `localhost` |
| `QDRANT_PORT` | Qdrant port | `6333` |
| `QDRANT_COLLECTION` | Collection name | `study_materials` |
| `PDF_STORAGE_PATH` | PDF storage directory | `./pdf_storage` |
| `MAX_FILE_SIZE_MB` | Max upload size | `50` |
| `CHUNK_SIZE_TOKENS` | Text chunk size | `400` |
| `CHUNK_OVERLAP_TOKENS` | Chunk overlap | `50` |

## 🐳 Docker Services

The application uses Docker Compose to manage services:

```yaml
services:
  backend:    # FastAPI backend on port 8000
  qdrant:     # Vector database on ports 6333-6334
```

### Docker Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker logs chatterbook_backend
docker logs chatterbook_qdrant

# Restart services
docker-compose restart

# Check status
docker ps
```

## 🧪 Testing

### Test Backend Connection
```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "qdrant_connected": true,
  "groq_configured": true,
  "pdf_storage_writable": true,
  "timestamp": 1234567890.123
}
```

### Test File Upload
```bash
curl -X POST http://localhost:5173/api/upload \
  -F "file=@test.pdf" \
  -F "title=Test Document"
```

## 🚨 Troubleshooting

### Backend Connection Error
**Problem:** "Cannot connect to backend"

**Solution:**
```bash
# Check if Docker is running
docker ps

# Start backend
docker-compose up -d

# Check logs
docker logs chatterbook_backend
```

### API Error
If the chatbot fails to generate a response:
- Verify your `.env` file has the correct API key
- Check if the API key has exceeded rate limits

### PDF Upload Failing
**Problem:** "Could not read file size"

**Solution:**
- Ensure file is a valid PDF
- Check file size (max 50MB)
- Verify backend is running

### Qdrant Connection Error
**Problem:** "Qdrant not connected"

**Solution:**
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Restart Qdrant
docker-compose restart qdrant

# Check in .env file
QDRANT_HOST=localhost  # NOT "qdrant" when running Flask locally
```

## 📊 Performance Optimization

### For Large PDFs
- Increase `CHUNK_SIZE_TOKENS` for better context
- Adjust `CHUNK_OVERLAP_TOKENS` for better continuity
- Use Docker with more memory allocation

### For Faster Responses
- Keep Qdrant collection size manageable
- Use appropriate `k` value in search queries (default: 5)
- Consider upgrading models for complex queries

## 🔒 Security Best Practices

1. **Never commit `.env` file** - Add to `.gitignore`
2. **Use strong secret keys** - Generate with `secrets.token_hex(32)`
3. **Keep API keys secure** - Don't hardcode in source
4. **Validate all user inputs** - Done automatically by Pydantic
5. **Use HTTPS in production** - Configure reverse proxy

## 🌐 Deployment

### Production Checklist

- [ ] Set strong `FLASK_SECRET_KEY`
- [ ] Use production-grade database (PostgreSQL)
- [ ] Enable HTTPS with SSL certificates
- [ ] Set up reverse proxy (Nginx)
- [ ] Configure firewall rules
- [ ] Enable logging and monitoring
- [ ] Set up automatic backups
- [ ] Use environment-specific `.env` files
- [ ] Disable Flask debug mode
- [ ] Set up CI/CD pipeline

### Recommended Hosting
- **Frontend:** Vercel, Heroku, Railway
- **Backend:** DigitalOcean, AWS, Google Cloud
- **Qdrant:** Qdrant Cloud, Self-hosted Docker

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Setup
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black .

# Lint code
flake8
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Stuti Gupta** -  [Stutyay](https://github.com/Stutyay)
- **Priyanka Verma** - [noshimi-imnida](https://github.com/noshimi-imnida)
- **Yamini Thepra** - [YaminiThepra](https://github.com/YaminiThepra)
- **Arushi Malviya** - [arushimalviya22](https://github.com/arushimalviya22)

## 🙏 Acknowledgments

- Groq API for powerful language models
- Qdrant for vector search capabilities
- Flask and FastAPI communities
- All contributors and testers

## 📧 Contact

- **Email:** stutigupta817@gmail.com
- **GitHub:** [@Stutyay](https://github.com/Stutyay)
- **LinkedIn:** [Stuti Gupta](https://www.linkedin.com/in/stuti-gupta-256839293/)

- **Email:** noshimi14india@gmail.com
- **Github:** [noshimi-imnida](https://github.com/noshimi-imnida)
- **LinkedIn:** [Priyanka Verma](https://www.linkedin.com/in/priyanka-verma-928723292)

- **Email:** yaminithepra@gmail.com
- **Github:** [YaminiThepra](https://github.com/YaminiThepra)

- **Email:** arushimalviya.16@gmail.com
- **Github:** [arushimalviya22](https://github.com/arushimalviya22)
- **LinkedIn:** [Arushi Malviya](https://www.linkedin.com/in/arushi-malviya-11998924a?utm_source=share&utm_campaign=share_via&utm_content=profile&utm_medium=android_app)

## 🗺️ Roadmap

- [ ] Add OCR for scanned PDFs
- [ ] Implement collaborative study rooms
- [ ] Add flashcard generation from notes
- [ ] Support for more file formats (DOCX, TXT)
- [ ] Mobile app (React Native)
- [ ] Quiz generation from uploaded content
- [ ] Integration with Google Drive
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Voice input/output

---

⭐ **Star this repo if you find it helpful!**

Built with ❤️ for students, by students.
