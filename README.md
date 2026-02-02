# 🏥 Curamyn

**Personalized, Multi-Modal AI Healthcare & Psychological Support System**

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live-curamyn.ddns.net-brightgreen.svg)](https://curamyn.ddns.net)

Curamyn is a production-grade AI-powered healthcare companion that provides emotional support, medical document understanding, and personalized health guidance through multiple interaction modalities—deployed at **[curamyn.ddns.net](https://curamyn.ddns.net)**.

---

## 📋 Table of Contents

- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Backend Deep Dive](#-backend-deep-dive)
- [Deployment Architecture](#-deployment-architecture)
- [Analytics Pipeline](#-analytics-pipeline)
- [Quick Start](#-quick-start)
- [API Documentation](#-api-documentation)
- [Testing Strategy](#-testing-strategy)
- [Roadmap](#️-roadmap)
- [Contributing](#-contributing)
- [License](#-license)
- [Disclaimer](#️-disclaimer)

---

## ✨ Features

### 🤖 Multi-Modal AI Interaction
- **Text Chat**: Natural language conversations for health and wellness support
- **Voice Interaction**: Fast speech-to-text (Deepgram) and text-to-speech (Piper TTS) for hands-free interaction
- **Document Analysis**: OCR-powered medical lab report extraction and explanation (Tesseract + Gemini)
- **Image Analysis**: CNN-based risk assessment for medical images (X-rays, skin lesions)

### 🧠 Intelligent Capabilities
- **Educational Mode**: Explain medical terminology from uploaded documents without diagnosis
- **Self-Care Mode**: Personalized wellness advice and emotional support (Gemini Flash)
- **Context-Aware Responses**: Sliding window memory with persistent document/image context
- **Safety-First Design**: Built-in safety guards, emergency detection, and consent management

### 🔒 Privacy & Security
- **User Consent Management**: Granular control over voice, image, document, and memory storage
- **Privacy-Safe OCR**: Automatic removal of PII using Presidio
- **Secure Authentication**: JWT-based authentication with Argon2 password hashing
- **Encrypted Storage**: MongoDB Atlas with TLS for sensitive data
- **HIPAA-Compliant Audit Logging**: Immutable audit trails for all data access

### 📊 Advanced Features
- **Session Summarization**: AI-generated privacy-safe session summaries on logout
- **MLflow Integration**: Experiment tracking and model observability (DagsHub)
- **Cloud Storage**: S3-based CNN model and Piper TTS model storage
- **Analytics Dashboard**: PowerBI dashboard for user engagement and consent metrics
- **Responsive UI**: Modern dark-themed interface built with NiceGUI

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Production Deployment                       │
│                    https://curamyn.ddns.net                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │   AWS EC2 Instance  │
                │  (Ubuntu + Docker)  │
                └──────────┬──────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼─────┐    ┌──────▼──────┐    ┌─────▼──────┐
   │ Frontend │    │   Backend   │    │    ETL     │
   │ (NiceGUI)│    │  (FastAPI)  │    │  Pipeline  │
   │  :8080   │    │    :8000    │    │  (Cron)    │
   └────┬─────┘    └──────┬──────┘    └─────┬──────┘
        │                 │                  │
        └────────┬────────┴──────────────────┘
                 │
    ┌────────────▼───────────────┐
    │      Data & Storage        │
    ├────────────────────────────┤
    │ MongoDB Atlas (Prod Data)  │
    │ PostgreSQL (Analytics DW)  │
    │ AWS S3 (CNN/TTS Models)    │
    └────────────┬───────────────┘
                 │
        ┌────────▼─────────┐
        │   Power BI       │
        │   Dashboards     │
        │ (User Analytics) │
        └──────────────────┘
```

### Component Breakdown

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | NiceGUI, FastAPI, Tailwind CSS | User interface with chat, voice, file upload |
| **Backend API** | FastAPI, Uvicorn | REST API for AI interactions |
| **LLM** | Google Gemini Flash | Intent analysis, health advice, education |
| **Speech-to-Text** | Deepgram API (primary), OpenAI Whisper (fallback) | Fast voice transcription (0.5-0.8s) |
| **Text-to-Speech** | Piper TTS | Natural voice synthesis |
| **OCR** | Tesseract OCR + Presidio | Document extraction with PII removal |
| **CNN Models** | PyTorch ResNet-18 | Medical image risk assessment |
| **Database** | MongoDB Atlas (TLS) | User data, sessions, consent, audit logs |
| **Analytics DW** | PostgreSQL | Aggregated metrics for reporting |
| **Model Storage** | AWS S3 | CNN weights, Piper TTS models |
| **Experiment Tracking** | MLflow + DagsHub | Model versioning, latency monitoring |
| **Authentication** | JWT + Argon2 | Secure token-based auth |
| **Rate Limiting** | SlowAPI | User-based and IP-based rate limits |
| **Error Tracking** | Sentry | Production error monitoring |
| **Deployment** | Docker Compose on EC2 | Containerized production environment |

---

## 🧠 Backend Deep Dive

### Core Architecture Principles

1. **Orchestration-First Design**: All AI interactions flow through a unified orchestrator that handles routing, safety, context enrichment, and fallback logic.

2. **Graceful Degradation**: Every AI service (LLM, STT, TTS, CNN) has fallback mechanisms to ensure the system never crashes:
   - **Deepgram STT fails** → Falls back to Whisper
   - **Gemini Flash fails** → Falls back to Gemini Flash Lite → Falls back to safe static response
   - **Piper TTS fails** → Returns text-only response with error flag
   - **CNN inference fails** → Returns safe generic message

3. **Privacy-First Memory**: 
   - **Sliding Window Memory**: Keeps last 15 messages in context, condensed summaries for older messages
   - **Persistent Context**: Documents and images remain accessible throughout entire session
   - **Privacy-Safe Summaries**: LLM-generated summaries with health topics and context details (no PII)

4. **Safety Guards**:
   - **Input Safety**: Blocks unauthorized voice/image/document processing based on user consent
   - **Output Safety**: Blocks diagnosis requests, medication dosage advice, and out-of-scope queries (e.g., "Who is the president?")
   - **Emergency Detection**: Identifies crisis language and provides crisis resources
   - **Consent Enforcement**: All data processing requires explicit user consent

---

### Request Flow Example: Voice Interaction

```
┌─────────────────────────────────────────────────────────────┐
│  1. User records voice message in browser                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Frontend sends audio bytes (WebM) to /ai/interact       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Backend: Check consent["voice"] = True                  │
│     ├─ If False → Return error                              │
│     └─ If True  → Continue                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Speech-to-Text Pipeline                                 │
│     ├─ Try Deepgram API (0.5-0.8s latency)                  │
│     ├─ If fails → Fallback to Whisper (2-3s latency)        │
│     └─ Result: "I'm feeling stressed about work"            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Context Enrichment                                      │
│     ├─ Load session state from MongoDB (if exists)          │
│     ├─ Inject sliding window memory (last 15 messages)      │
│     ├─ Add document context if uploaded in session          │
│     ├─ Add image analysis if uploaded in session            │
│     └─ Build enriched prompt for LLM                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  6. LLM Analysis (Gemini Flash)                             │
│     ├─ Intent: "health_support"                             │
│     ├─ Severity: "moderate"                                 │
│     ├─ Emotion: "stressed"                                  │
│     ├─ Sentiment: "negative"                                │
│     └─ Response: "Work stress can be overwhelming..."       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  7. Output Safety Check                                     │
│     ├─ Block diagnosis/dosage advice                        │
│     ├─ Detect emergency keywords                            │
│     └─ Pass → Continue                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  8. Text-to-Speech (Piper TTS)                              │
│     ├─ Synthesize response as WAV audio                     │
│     ├─ Convert to base64                                    │
│     └─ Cache common phrases (hello, goodbye, error)         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  9. Persist Session State                                   │
│     ├─ Save conversation to MongoDB                         │
│     ├─ Update session metadata (severity, emotion, topic)   │
│     └─ Store in both memory cache + MongoDB                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  10. Return Response to Frontend                            │
│      {                                                      │
│        "message": "Work stress can be overwhelming...",     │
│        "audio_base64": "UklGRiQAAABXQVZF...",               │
│        "session_id": "abc-123",                             │
│        "severity": "moderate",                              │
│        "intent": "health_support"                           │
│      }                                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  11. Frontend: Auto-play audio + Display text               │
└─────────────────────────────────────────────────────────────┘
```

---

### Smart Routing Logic

The backend uses intelligent routing to determine which AI service to invoke:

| Input Type | Conditions | Service Used |
|------------|-----------|--------------|
| **Text** | User asks about medical terms from uploaded doc | Educational LLM |
| **Text** | User asks for full document summary | Health Advisor (with doc context) |
| **Text** | General health conversation | Health Advisor LLM |
| **Audio** | Always | Voice Psychologist LLM |
| **Image** (document) | Always | OCR + OCR LLM |
| **Image** (xray/skin) | Always | CNN Risk Prediction |

**Example Smart Routing:**
```
User uploads document → "HAEMATOLOGY REPORT, Hemoglobin: 10.8 g/dL"
User asks: "What is hemoglobin?" → Routes to Educational LLM
User asks: "Is this normal?" → Routes to Health Advisor (with safety block on interpretation)
User asks: "What was in my report?" → Routes to Health Advisor with document summary
```

---

### Session Memory Strategy

Curamyn uses a **hybrid memory system** to balance context richness with token efficiency:

#### 1. **Sliding Window Memory** (Last 15 messages)
- Keeps recent conversation fresh in LLM context
- Automatically prunes older messages
- Stored in `SessionState.all_messages`

#### 2. **Condensed Historical Summary**
- Older messages (beyond 15) are summarized into topics
- Example: "Earlier conversation covered: headache, work stress, sleep issues"
- Prevents token overflow while maintaining continuity

#### 3. **Persistent Document/Image Context**
- Documents and images remain accessible **throughout entire session**
- Tracks upload position: "Document uploaded 12 messages ago"
- Only injected into LLM prompt when relevant
- Auto-cleared after 10 minutes of inactivity or topic change

#### 4. **Cross-Session Summaries**
- On logout, LLM generates privacy-safe session summary
- Includes: health topics, severity, emotion, duration, triggers, actions taken
- Stored in MongoDB for future context (if memory consent enabled)
- Example:
  ```json
  {
    "summary_text": "User discussed persistent headaches for 3 days, triggered by screen time and work stress",
    "health_topics": ["headache", "work stress", "eye strain"],
    "context_details": {
      "duration": "3 days",
      "triggers": "screen time, work deadlines",
      "severity_notes": "moderate pain, affecting focus",
      "actions_taken": "tried breaks, reduced brightness"
    }
  }
  ```

---

### Fallback Architecture

Every critical service has **multi-tier fallback**:

#### **Speech-to-Text Fallback Chain**
```
Deepgram API (Primary)
  ↓ [Fails]
OpenAI Whisper (Fallback)
  ↓ [Fails]
Return error with cached TTS response
```

#### **LLM Fallback Chain**
```
Gemini Flash (Primary)
  ↓ [Fails or empty output]
Gemini Flash Lite (Fallback)
  ↓ [Fails or empty output]
Safe Static Response ("I'm here with you.")
```

#### **Text-to-Speech Fallback**
```
Piper TTS Synthesis
  ↓ [Fails]
Emergency TTS ("I hear you.")
  ↓ [Fails]
Return text-only response with tts_failed=True flag
```

#### **CNN Fallback**
```
Load model from S3 cache
  ↓ [Model unavailable]
Download from S3
  ↓ [Download fails]
Return safe generic message
```

---

## 🚀 Deployment Architecture

### Production Environment: AWS EC2

**Instance Details:**
- **Instance Type**: `t2.medium` (2 vCPU, 4GB RAM)
- **OS**: Ubuntu 24.04 LTS
- **Domain**: [https://curamyn.ddns.net](https://curamyn.ddns.net)
- **Deployment**: Docker Compose
- **Reverse Proxy**: Nginx (for HTTPS and domain routing)

**Services Running:**
```
┌──────────────────────────────────────┐
│        EC2 Instance (Ubuntu)         │
├──────────────────────────────────────┤
│  Docker Compose Services:            │
│    • Frontend (NiceGUI) - Port 8080  │
│    • Backend (FastAPI) - Port 8000   │
│                                      │
│  Cron Jobs:                          │
│    • ETL Pipeline (hourly)           │
│    • Session Cleanup (hourly)        │
│                                      │
│  Nginx:                              │
│    • HTTPS (Let's Encrypt SSL)       │
│    • Domain routing to :8080         │
└──────────────────────────────────────┘
```

### Docker Deployment

**docker-compose.yml:**
```yaml
services:
  backend:
    image: nazina/curamyn-backend:latest
    ports:
      - "8000:8000"
    environment:
      - CURAMYN_ENV=prod
      - CURAMYN_MONGO_URI=${CURAMYN_MONGO_URI}
      - CURAMYN_GEMINI_API_KEY=${CURAMYN_GEMINI_API_KEY}
      - CURAMYN_AWS_ACCESS_KEY_ID=${CURAMYN_AWS_ACCESS_KEY_ID}
      - CURAMYN_AWS_SECRET_ACCESS_KEY=${CURAMYN_AWS_SECRET_ACCESS_KEY}
    restart: unless-stopped

  frontend:
    image: nazina/curamyn-frontend:latest
    ports:
      - "8080:8080"
    environment:
      - CURAMYN_API_BASE_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped
```

### CI/CD Pipeline

**GitHub Actions Workflow** (`.github/workflows/ci.yml`):

```
┌─────────────────────────────────────────────┐
│  1. Push to main/develop branch             │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  2. Run Tests (pytest)                      │
│     • MongoDB service (Docker)              │
│     • Unit tests (mocked AI services)       │
│     • Integration tests (mocked auth)       │
│     • E2E smoke tests                       │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  3. Code Quality Check                      │
│     • Black formatter check                 │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  4. Build Docker Images                     │
│     • Backend (FastAPI + PyTorch)           │
│     • Frontend (NiceGUI)                    │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  5. Push to Docker Hub                      │
│     • nazina/curamyn-backend:latest         │
│     • nazina/curamyn-backend:<git-sha>      │
│     • nazina/curamyn-frontend:latest        │
│     • nazina/curamyn-frontend:<git-sha>     │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  6. Deploy to EC2 (manual pull + restart)   │
└─────────────────────────────────────────────┘
```

---

## 📊 Analytics Pipeline

### ETL Architecture

Curamyn includes a **production-grade analytics pipeline** that transforms operational MongoDB data into business-ready metrics for Power BI dashboards.

```
┌──────────────────────────────────────────────────────┐
│  MongoDB Atlas (Operational Data)                    │
│    • users                                           │
│    • consent_settings                                │
│    • user_profile (onboarding)                       │
│    • chat_sessions                                   │
│    • session_summaries                               │
│    • audit_logs                                      │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  Incremental ETL (Python Script on EC2)              │
│    • Runs hourly via cron                            │
│    • Incremental load (only new data since last run) │
│    • Idempotent inserts (ON CONFLICT DO NOTHING)     │
│    • Privacy-safe (no PII, no chat content)          │
│    • Rollback on failure                             │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  PostgreSQL Analytics Warehouse                      │
│    Tables:                                           │
│      • users_daily (signup tracking)                 │
│      • consents_snapshot (consent state per day)     │
│      • daily_metrics (aggregated KPIs)               │
│      • etl_runs (observability & debugging)          │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  Power BI Dashboards                                 │
│    • User Growth Trends                              │
│    • Consent Adoption Analysis                       │
│    • Feature Usage Metrics                           │
│    • Session Duration & Engagement                   │
└──────────────────────────────────────────────────────┘
```

### ETL Design Principles

| Feature | Implementation |
|---------|----------------|
| **Incremental Loads** | Uses `etl_runs.run_time` to fetch only new data |
| **Idempotent Inserts** | `ON CONFLICT DO NOTHING` for safe re-runs |
| **Daily Aggregation** | One row per day in `daily_metrics` |
| **Failure Safety** | Rollback on error + failure logging in `etl_runs` |
| **Stateless** | Safe to re-run anytime without duplicates |
| **Privacy-First** | **No PII, no chat content, no medical data** |

### What Data Is Collected

**Privacy-Safe Metadata Only:**
- Daily new user signups
- Consent flags (voice, memory, document, image) per user per day
- Onboarding completion rates
- Feature adoption trends (voice usage, document uploads, image analysis)
- ETL run health (success/failure timestamps)

**NOT Collected:**
- ❌ Chat message text
- ❌ Medical document content
- ❌ User names, emails, or personal identifiers
- ❌ Session summaries
- ❌ Image analysis results

### ETL Cron Job

**Crontab Entry:**
```bash
# Run ETL every hour at minute 0
0 * * * * cd /home/ubuntu/curamyn/etl && /home/ubuntu/curamyn/etl/venv/bin/python scripts/etl_run.py >> etl.log 2>&1
```

**ETL Script Location:**
```
etl/
├── scripts/
│   └── etl_run.py        # Incremental ETL logic
├── etl.log               # Execution logs
├── .env                  # MongoDB & PostgreSQL credentials
└── venv/                 # Isolated Python environment
```

### Analytics Tables (PostgreSQL)

| Table | Purpose |
|-------|---------|
| `users_daily` | User signup tracking (date, user_count) |
| `consents_snapshot` | Consent state per day (user_id, date, memory, voice, document, image) |
| `daily_metrics` | Aggregated KPIs (total_users, active_consent_users, document_uploads, etc.) |
| `etl_runs` | ETL observability (run_id, status, records_processed, error_message, timestamp) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- MongoDB 6+ (or MongoDB Atlas account)
- FFmpeg (for audio processing)
- Tesseract OCR
- AWS S3 account (for CNN/TTS models)
- Google Gemini API key
- Deepgram API key (optional, for faster STT)

### Local Development Setup

#### 1. **Clone the repository**
```bash
git clone https://github.com/nazina096/curamyn.git
cd curamyn
```

#### 2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. **Install dependencies**
```bash
pip install -r requirements.txt
```

#### 4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required environment variables:**
```env
CURAMYN_ENV=dev
CURAMYN_MONGO_URI=mongodb://localhost:27017
CURAMYN_MONGO_DB=curamyn_db
CURAMYN_JWT_SECRET=your-secret-key-change-in-production
CURAMYN_STORAGE_SECRET=your-storage-secret-change-in-production
CURAMYN_GEMINI_API_KEY=your-gemini-api-key
CURAMYN_DEEPGRAM_API_KEY=your-deepgram-api-key
CURAMYN_AWS_ACCESS_KEY_ID=your-aws-key
CURAMYN_AWS_SECRET_ACCESS_KEY=your-aws-secret
CURAMYN_S3_BUCKET_NAME=your-bucket-name
CURAMYN_MLFLOW_TRACKING_URI=your-mlflow-uri
CURAMYN_DAGSHUB_USERNAME=your-dagshub-username
CURAMYN_DAGSHUB_TOKEN=your-dagshub-token
```

#### 5. **Install system dependencies**

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

#### 6. **Run the application**

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

## 📖 API Documentation

### Authentication Endpoints

#### **POST** `/auth/signup`
Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "user_id": "abc-123",
  "email": "user@example.com",
  "created_at": "2026-02-03T10:00:00Z"
}
```

---

#### **POST** `/auth/login`
Authenticate and receive JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "session_id": "session-456"
}
```

---

#### **POST** `/auth/logout`
End session and generate summary.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Params:**
```
session_id=session-456
```

**Response:**
```json
{
  "message": "Logged out successfully",
  "session_id": "session-456"
}
```

---

### AI Interaction Endpoints

#### **POST** `/ai/interact`
Main AI interaction endpoint (text, voice, image, document).

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Form Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input_type` | string | Yes | `text`, `audio`, or `image` |
| `session_id` | string | No | Session identifier (auto-generated if missing) |
| `response_mode` | string | No | `text` or `voice` (default: `text`) |
| `text` | string | Conditional | Required if `input_type=text` |
| `audio` | file | Conditional | Required if `input_type=audio` |
| `image` | file | Conditional | Required if `input_type=image` |
| `image_type` | string | Conditional | `xray`, `skin`, or `document` (required if `input_type=image`) |

**Response (Text Input):**
```json
{
  "message": "I hear you. Work stress can be overwhelming. Here are some gentle steps...",
  "session_id": "session-789",
  "severity": "moderate",
  "intent": "health_support"
}
```

**Response (Voice Input with Audio Output):**
```json
{
  "message": "I hear you. Let's take this one step at a time.",
  "audio_base64": "UklGRiQAAABXQVZF...",
  "session_id": "session-789",
  "severity": "moderate",
  "intent": "health_support",
  "tts_failed": false,
  "latency": {
    "stt": 0.65,
    "llm": 1.2,
    "tts": 0.8,
    "total": 2.65
  }
}
```

**Response (Document Upload):**
```json
{
  "message": "Report Type: HAEMATOLOGY REPORT\n\nKey Findings:\n- Hemoglobin: 10.8 g/dL (Reference: 12.0-15.5 g/dL)\n- WBC Count: 11,200 cells/uL...",
  "session_id": "session-789",
  "intent": "document_understanding"
}
```

**Response (Image Analysis):**
```json
{
  "message": "This image shows patterns that may need medical attention. Please consult a qualified healthcare professional.",
  "disclaimer": "This information is generated by an AI system and is for informational purposes only.",
  "session_id": "session-789"
}
```

---

### Consent Management

#### **GET** `/consent/status`
Get user consent preferences.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "user_id": "abc-123",
  "memory": true,
  "voice": true,
  "document": false,
  "image": true
}
```

---

#### **POST** `/consent/update`
Update user consent preferences.

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request:**
```json
{
  "memory": true,
  "voice": true,
  "document": true,
  "image": true
}
```

**Response:**
```json
{
  "user_id": "abc-123",
  "memory": true,
  "voice": true,
  "document": true,
  "image": true
}
```

---

### Chat History

#### **GET** `/chat/history`
Retrieve chat messages for a session.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Params:**
```
session_id=session-789
```

**Response:**
```json
{
  "messages": [
    {
      "author": "You",
      "type": "text",
      "text": "I'm feeling stressed",
      "sent": true,
      "timestamp": "2026-02-03T10:30:00Z"
    },
    {
      "author": "Curamyn",
      "type": "text",
      "text": "It takes strength to notice how you're feeling...",
      "sent": false,
      "timestamp": "2026-02-03T10:30:05Z"
    }
  ]
}
```

---

### Memory Management

#### **DELETE** `/memory/clear`
Delete all stored memory.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Memory cleared successfully.",
  "deleted_sessions": 15,
  "deleted_chat_session": 3
}
```

---

#### **DELETE** `/memory/clear-and-disable`
Delete memory and disable future storage.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Memory cleared and future storage disabled.",
  "deleted_sessions": 15,
  "deleted_chat_session": 3
}
```

---

## 🧪 Testing Strategy

Curamyn follows a **behavior-focused testing philosophy** that validates system reliability without testing AI model intelligence.

### Testing Principles

**"Test system behavior, not model intelligence."**

The goal is to verify that:
- ✅ The system responds safely
- ✅ Failures are handled gracefully
- ✅ Incorrect inputs never crash the system
- ✅ External services are isolated from core logic

**Model accuracy is evaluated separately from software tests.**

---

### Test Types

#### **Unit Tests** (`tests/unit/`)
- Validate individual service behavior
- No external calls (LLM, Whisper, CNN, S3)
- Use mocking for deterministic outcomes

**Examples:**
- LLM fallback handling when Gemini returns empty response
- Safety rule enforcement (blocking diagnosis requests)
- Voice pipeline control flow with mocked STT/TTS
- CNN routing logic with mocked model inference

---

#### **Integration Tests** (`tests/integration/`)
- Validate interaction between internal components
- Authentication is mocked
- External services remain isolated

**Example:**
- `/ai/interact` endpoint behavior with mocked user authentication

---

#### **End-to-End Tests** (`tests/e2e/`)
- Smoke tests only
- Validate that the application boots and responds
- No real AI inference

---

### Run Tests

**Run all tests:**
```bash
pytest
```

**Run specific test suites:**
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/
```

**Test coverage:**
```bash
pytest --cov=app --cov-report=html
```

See [TESTING.md](TESTING.md) for detailed testing strategy.

---

### Why AI Outputs Are NOT Asserted

LLM responses vary due to:
- Token limits
- Provider behavior changes
- Internal model reasoning
- Network or API failures

**Instead, tests validate:**
- ✅ Presence of a response
- ✅ Correct response structure
- ✅ Execution of fallback logic when LLM output is unusable

This reflects **real-world production conditions**.

---

## 🗺️ Roadmap

### Phase 1: Core Enhancements (Q2 2026)
- [ ] Multi-language support (Hindi, Spanish, French)
- [ ] Mobile app (React Native)
- [ ] Advanced session memory with vector embeddings
- [ ] Improved CNN models (custom architectures)

### Phase 2: Integrations (Q3 2026)
- [ ] Integration with wearable devices (Fitbit, Apple Health)
- [ ] Telemedicine appointment booking
- [ ] Medication reminder system
- [ ] Real-time collaboration for family health tracking

### Phase 3: Advanced Analytics (Q4 2026)
- [ ] Predictive health insights using time-series models
- [ ] Anomaly detection in user health patterns
- [ ] Advanced Power BI dashboards with ML predictions

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
- Piper TTS requires model files (~50MB) to be downloaded from S3 on first run

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini** for LLM capabilities
- **Deepgram** for ultra-fast speech-to-text
- **OpenAI Whisper** for fallback speech recognition
- **Piper TTS** for natural voice synthesis
- **PyTorch** and **torchvision** for CNN models
- **FastAPI** for the robust backend framework
- **NiceGUI** for the intuitive frontend interface
- **MLflow** and **DagsHub** for experiment tracking
- **Microsoft Presidio** for PII detection and removal
- **Tesseract OCR** for medical document extraction

---

## 📧 Contact

**Author**: Nazina N  
**Email**: nazina096@gmail.com  
**Live Demo**: [https://curamyn.ddns.net](https://curamyn.ddns.net)

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

## 🎯 Production Deployment Summary

| Component | Details |
|-----------|---------|
| **Domain** | [https://curamyn.ddns.net](https://curamyn.ddns.net) |
| **Infrastructure** | AWS EC2 (t2.medium) + Docker Compose |
| **Backend** | FastAPI (Port 8000) |
| **Frontend** | NiceGUI (Port 8080) |
| **Database** | MongoDB Atlas (TLS) |
| **Analytics** | PostgreSQL + Power BI |
| **ETL** | Cron job (daily) |
| **SSL** | Let's Encrypt (auto-renewal) |
| **Reverse Proxy** | Nginx |
| **CI/CD** | GitHub Actions → Docker Hub |
| **Monitoring** | Sentry (error tracking), MLflow (model observability) |

---

## 📊 System Metrics

### Performance Benchmarks
| Operation | Latency |
|-----------|---------|
| Text chat response | 1.5-2.5s |
| Voice interaction (end-to-end) | 2.5-3.5s |
| Document OCR | 5-10s |
| Image risk analysis | 2-4s |
| Session summary generation | 3-5s |

### Scalability
- **Concurrent users**: 50+ (tested)
- **Session storage**: MongoDB Atlas (scalable)
- **Rate limits**: 25 requests/minute per user (chat), 5/minute (login)

---

**Built with ❤️ for healthcare accessibility and mental health support.**