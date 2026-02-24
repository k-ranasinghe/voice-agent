# Bank ABC Voice Agent Platform

A full-stack conversational AI platform for banking customer service, built with LangGraph orchestration, real-time voice streaming, and comprehensive observability.

## 🏗️ Architecture

- **Backend**: FastAPI + LangGraph + PostgreSQL + Redis
- **Frontend**: React + Vite + TypeScript
- **Voice**: Deepgram STT + ElevenLabs TTS
- **Observability**: LangFuse

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+

### Backend Setup

1. **Clone repository**:
```bash
git clone https://github.comk-ranasinghe/voice-agent.git
cd "voice-agent"
```

2. **Create Python virtual environment**:
```bash
cd backend
python -m venv venv

.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your API keys and database URLs
```

5. **Run database migrations** (after setting up PostgreSQL):
```bash
# Initialize Alembic (first time only)
alembic init migrations

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

6. **Seed mock data**:
```bash
python -m src.database.seed
```

7. **Run development server**:
```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Frontend Setup

1. **Navigate to frontend directory**:
```bash
cd frontend
```

2. **Install dependencies**:
```bash
npm install
```

3. **Configure environment**:
```bash
cp .env.example .env
# Ensure VITE_API_URL and VITE_WS_URL point to your backend
```

4. **Run development server**:
```bash
npm run dev
```

The frontend application will be available at `http://localhost:5173`

## 📁 Project Structure

```
backend/
├── src/
│   ├── agents/          # LangGraph agent logic
│   ├── api/             # FastAPI application
│   ├── cache/           # Redis client
│   ├── database/        # SQLAlchemy models & migrations
│   ├── observability/   # LangFuse & logging
│   ├── security/        # PII redaction, fraud detection
│   ├── tools/           # Mock banking API tools
│   ├── voice/           # Deepgram STT, ElevenLabs TTS
│   └── config.py        # Settings management
├── tests/               # Test suite
├── migrations/          # Alembic migrations
├── requirements.txt
└── .env.example

frontend/
├── src/
│   ├── components/      # React components (CallInterface, AdminDashboard)
│   ├── hooks/           # Custom React hooks (WebSockets, Audio)
│   ├── services/        # API client services
│   ├── stores/          # Zustand state management
│   ├── App.tsx          # Main application routing
│   └── index.css        # Tailwind CSS and global styles
├── public/              # Static assets and audio processors
├── package.json
└── vite.config.ts
```

## 🔑 Test Credentials

After seeding, use these credentials for testing:

- **Customer ID**: `CUST00001`
- **PIN**: `1234`
- **Card**: Ending in `4521` (varies by seed)

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_agents/test_intent_router.py
```

## 📊 Development Progress

See [task.md](../../.gemini/antigravity/brain/4d03eaa6-2dbd-402f-8b0d-2f28fc7ca6ac/task.md) for detailed task tracking.

## 🚢 Deployment

### General Guidelines

The application is designed to be deployed as a standard full-stack application on any cloud provider capable of hosting containers or standard web services.

#### Backend Deployment

1. **Environment Setup**: Ensure your production environment has access to a PostgreSQL database and a Redis instance.
2. **Environment Variables**: Configure all required environment variables based on the `.env.example` file (OpenAI, Deepgram, ElevenLabs, Database URLs, etc.).
3. **Database Migrations**: Run the Alembic migrations (`alembic upgrade head`) before starting the application server.
4. **Server Startup**: Use a production-grade ASGI server like Uvicorn managed by Gunicorn.
   ```bash
   gunicorn src.api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

#### Frontend Deployment

1. **Build Process**: The frontend must be built for production use. Ensure your CI/CD pipeline installs Node dependencies and runs the build command.
   ```bash
   npm ci
   npm run build
   ```
2. **Environment Linking**: Ensure the `VITE_API_URL` and `VITE_WS_URL` environment variables are correctly injected during the build step to point to your deployed backend URL.
3. **Static Hosting**: The resulting output in the `dist` folder consists of static assets (HTML, JS, CSS) that can be served by any static file host, CDN, or web server (e.g., Nginx, S3 + CloudFront).
