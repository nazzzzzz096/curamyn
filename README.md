# 🏥 Curamyn

**Personalized, Multi-Modal AI Healthcare & Psychological Support System**

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Curamyn is an AI-powered healthcare companion that provides emotional support, medical document understanding, and personalized health guidance through multiple interaction modalities.

---

## ✨ Features

### 🤖 Multi-Modal AI Interaction
- **Text Chat**: Natural language conversations for health and wellness support
- **Voice Interaction**: Speech-to-text and text-to-speech for hands-free interaction
- **Document Analysis**: OCR-powered medical lab report extraction and explanation
- **Image Analysis**: CNN-based risk assessment for medical images (X-rays, skin lesions)

### 🧠 Intelligent Capabilities
- **Educational Mode**: Explain medical terminology from uploaded documents without diagnosis
- **Self-Care Mode**: Personalized wellness advice and emotional support
- **Context-Aware Responses**: Session memory and conversation continuity
- **Safety-First Design**: Built-in safety guards, emergency detection, and consent management

### 🔒 Privacy & Security
- **User Consent Management**: Granular control over voice, image, document, and memory storage
- **Privacy-Safe OCR**: Automatic removal of PII (Personal Identifiable Information)
- **Secure Authentication**: JWT-based authentication system
- **Encrypted Storage**: MongoDB with TLS for sensitive data

### 📊 Advanced Features
- **Session Summarization**: AI-generated privacy-safe session summaries
- **MLflow Integration**: Experiment tracking and model observability
- **Cloud Storage**: S3-based CNN model storage and retrieval
- **Responsive UI**: Modern dark-themed interface built with NiceGUI

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│                  (NiceGUI + Tailwind CSS)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Orchestration Layer                       │  │
│  │  • Input Router  • Safety Guards  • Session Manager   │  │
│  └─────────┬───────────────┬─────────────────┬───────────┘  │
│            │               │                 │               │
│  ┌─────────▼─────┐ ┌──────▼──────┐ ┌───────▼────────┐     │
│  │  Voice        │ │  Document   │ │  Health        │     │
│  │  Pipeline     │ │  Understanding│ │  Advisor       │     │
│  │  • Whisper    │ │  • OCR       │ │  • Educational │     │
│  │  • Edge-TTS   │ │  • Gemini LLM│ │  • Self-Care   │     │
│  └───────────────┘ └─────────────┘ └────────────────┘     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    Data Layer                                │
│  • MongoDB (Sessions, Users, Consent)                       │
│  • S3 (CNN Models)                                          │
│  • MLflow (Experiment Tracking)                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- MongoDB 6+
- FFmpeg (for audio processing)
- Tesseract OCR
- AWS S3 account (for CNN models)
- Google Gemini API key

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/curamyn.git
cd curamyn
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
```env
CURAMYN_ENV=dev
CURAMYN_MONGO_URI=mongodb://localhost:27017
CURAMYN_MONGO_DB=curamyn_db
CURAMYN_JWT_SECRET=your-secret-key
CURAMYN_STORAGE_SECRET=your-storage-secret
CURAMYN_GEMINI_API_KEY=your-gemini-api-key
CURAMYN_AWS_ACCESS_KEY_ID=your-aws-key
CURAMYN_AWS_SECRET_ACCESS_KEY=your-aws-secret
CURAMYN_S3_BUCKET_NAME=your-bucket-name
CURAMYN_MLFLOW_TRACKING_URI=your-mlflow-uri
```

5. **Install system dependencies**

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg tesseract-ocr
```

**macOS:**
```bash
brew install ffmpeg tesseract
```

**Windows:**
- Download FFmpeg from https://ffmpeg.org/download.html
- Download Tesseract from https://github.com/UB-Mannheim/tesseract/wiki

6. **Run the application**

**Backend:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
python frontend/main.py
```

Access the application at `http://localhost:8080`

---

## 🧪 Testing

Curamyn follows a **behavior-focused testing philosophy** that validates system reliability without testing AI model intelligence.

### Run All Tests
```bash
pytest
```

### Run Specific Test Suites
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/
```

### Test Coverage
```bash
pytest --cov=app --cov-report=html
```

See [TESTING.md](TESTING.md) for detailed testing strategy.

---

## 📖 Usage

### 1. User Registration & Onboarding
- Sign up with email and password
- Complete optional onboarding questions (age, gender, health context)
- Set consent preferences for voice, images, documents, and memory

### 2. Document Upload & Analysis
```python
# Upload a medical lab report (PDF/Image)
# System will:
# 1. Extract text using OCR
# 2. Clean and format the data
# 3. Present structured information
```

Example interaction:
```
User: [Uploads haematology report]
Curamyn: "Report Type: HAEMATOLOGY REPORT
          
          Test Results:
          - Hemoglobin: 10.8 g/dL (Reference: 12.0-15.5 g/dL)
          - WBC Count: 11,200 cells/uL (Reference: 4,000-11,000/uL)
          ..."

User: "What is RBC?"
Curamyn: "RBC stands for Red Blood Cells. These are the cells in your 
          blood that carry oxygen from your lungs to the rest of your 
          body. The count shown in your report indicates how many RBCs 
          you have per unit of blood."
```

### 3. Voice Interaction
```python
# Click "🎤 Record" button
# Speak your question
# Click "🛑 Stop"
# System will transcribe, process, and respond with voice
```

### 4. Health Guidance
```
User: "I'm feeling stressed lately"
Curamyn: "It takes strength to notice how you're feeling. Here are 
          some gentle steps:
          1. Take 5 deep breaths
          2. Step outside for fresh air
          3. Connect with someone you trust"
```

---

## 🔧 Configuration

### Consent Management
Users can control data processing through the consent menu:
- **Memory**: Store conversation history
- **Voice**: Enable voice processing
- **Documents**: Allow document uploads
- **Images**: Enable image analysis

### Session Management
- Sessions auto-expire after 30 minutes of inactivity
- Session summaries generated on logout (if memory consent enabled)
- In-memory state cleared on application restart

### Safety Features
- **Input Safety**: Validates consent before processing
- **Output Safety**: Blocks diagnosis and medication advice
- **Emergency Detection**: Recognizes crisis language
- **PII Removal**: Automatically removes personal information from documents

---

## 🏗️ Project Structure

```
curamyn/
├── app/
│   ├── chat_service/           # Core chat functionality
│   │   ├── api/                # API routes
│   │   ├── repositories/       # Database access
│   │   ├── services/           # Business logic
│   │   │   ├── orchestrator/   # Request orchestration
│   │   │   ├── cnn_service.py  # Image risk analysis
│   │   │   ├── ocr_service.py  # Document text extraction
│   │   │   ├── llm_service.py  # Voice psychologist
│   │   │   ├── health_advisor_service.py  # Self-care mode
│   │   │   ├── educational_llm_service.py # Term explanation
│   │   │   └── whisper_service.py  # Speech-to-text
│   │   └── utils/              # Utilities
│   ├── consent_service/        # User consent management
│   ├── question_service/       # Onboarding questions
│   ├── user_service/           # Authentication
│   ├── core/                   # Security & dependencies
│   ├── db/                     # Database connections
│   └── main.py                 # FastAPI application
├── frontend/
│   ├── api/                    # API clients
│   ├── pages/                  # UI pages
│   ├── state/                  # Frontend state
│   └── main.py                 # NiceGUI application
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
├── .github/workflows/          # CI/CD pipelines
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Test configuration
└── README.md                   # This file
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Write tests** for new functionality
4. **Follow code style** (use `black` formatter)
5. **Commit changes** (`git commit -m 'Add amazing feature'`)
6. **Push to branch** (`git push origin feature/amazing-feature`)
7. **Open a Pull Request**

### Code Style
```bash
# Format code
black .

# Check formatting
black --check .

# Run linter
ruff check .
```

---

## 🐛 Known Issues

- Voice recording requires HTTPS in production (browser security requirement)
- Large PDF files (>10MB) may cause timeouts during OCR processing
- Session summaries use LLM calls which may fail if quota exceeded

---

## 🗺️ Roadmap

- [ ] Multi-language support (Hindi, Spanish, French)
- [ ] Mobile app (React Native)
- [ ] Real-time collaboration for family health tracking
- [ ] Integration with wearable devices
- [ ] Advanced analytics dashboard
- [ ] Telemedicine appointment booking
- [ ] Medication reminder system

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini** for LLM capabilities
- **OpenAI Whisper** for speech recognition
- **PyTorch** and **torchvision** for CNN models
- **FastAPI** for the robust backend framework
- **NiceGUI** for the intuitive frontend interface
- **MLflow** for experiment tracking

---

## 📧 Contact

**Author**: Nazina N  
**Email**: your.email@example.com  
**GitHub**: [@yourusername](https://github.com/yourusername)  
**Project Link**: https://github.com/yourusername/curamyn

---

## ⚠️ Disclaimer

**Curamyn is NOT a medical device and does NOT provide medical diagnoses.**

This system is designed for:
- ✅ Educational purposes (explaining medical terminology)
- ✅ Emotional support and wellness guidance
- ✅ Document organization and information extraction

This system is NOT designed for:
- ❌ Medical diagnosis
- ❌ Treatment recommendations
- ❌ Emergency medical situations
- ❌ Replacing healthcare professionals

**Always consult qualified healthcare providers for medical advice, diagnosis, and treatment.**

---

<div align="center">

**Made with ❤️ for better health and wellbeing**

[⭐ Star this repo](https://github.com/yourusername/curamyn) | [🐛 Report Bug](https://github.com/yourusername/curamyn/issues) | [💡 Request Feature](https://github.com/yourusername/curamyn/issues)

</div>
