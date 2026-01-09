# MCP-Powered Lead Gen + Enrichment + Outreach System

A full-stack lead generation and outreach automation system built with Model Context Protocol (MCP), n8n orchestration, Groq AI, and a real-time monitoring dashboard.

## 🎯 Features

- **Lead Generation**: Generate 200+ realistic leads with valid contact information
- **AI Enrichment**: Enrich leads with company insights, personas, and pain points using Groq LLM
- **Message Personalization**: Create personalized emails and LinkedIn DMs with A/B variations
- **Smart Outreach**: Send messages with retry logic, rate limiting, and error handling
- **Real-time Monitoring**: Track pipeline progress with a modern React dashboard
- **MCP Integration**: Orchestrate workflow through Model Context Protocol
- **n8n Workflow**: Visual workflow automation and orchestration

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   n8n       │─────▶│  MCP Server  │─────▶│   Backend   │
│  Workflow   │      │   (Tools)    │      │  Services   │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                      │
                            │                      ▼
                            │               ┌─────────────┐
                            │               │   SQLite    │
                            │               │   Database  │
                            │               └─────────────┘
                            ▼
                     ┌──────────────┐
                     │   Frontend   │
                     │  Dashboard   │
                     └──────────────┘
```

## 📋 Prerequisites

- Python 3.10+
- Node.js 18+
- n8n (running on port 5678)
- Groq API key (free tier available at https://console.groq.com)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd e:\intern-assigment\linkind-mcp
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your Groq API key
# GROQ_API_KEY=your_key_here
```

### 3. Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
npm install
```

### 5. Initialize Database

```bash
python backend/database.py
```

### 6. Start the Services

**Terminal 1 - MCP Server:**
```bash
python mcp_server/server.py
```

**Terminal 2 - API Backend:**
```bash
python backend/api.py
```

**Terminal 3 - Frontend:**
```bash
npm run dev
```

### 7. Access the Applications

- **Frontend Dashboard**: http://localhost:3000
- **API Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **n8n Editor**: http://localhost:5678

## 📁 Project Structure

```
linkind-mcp/
├── backend/              # Python backend services
│   ├── api.py           # FastAPI application
│   ├── database.py      # SQLite database setup
│   ├── lead_generator.py # Lead generation logic
│   ├── enrichment.py    # Lead enrichment service
│   ├── messaging.py     # Message generation
│   └── outreach.py      # Message sending
├── mcp_server/          # MCP server implementation
│   ├── server.py        # MCP server main
│   └── tools.py         # MCP tool definitions
├── frontend/            # Next.js React frontend
│   ├── pages/          # Next.js pages
│   ├── components/     # React components
│   └── styles/         # CSS styles
├── data/               # SQLite database storage
├── .env.example        # Environment template
└── README.md           # This file
```

## 🔧 Configuration

### Dry Run vs Live Run

Toggle between modes in the frontend or set in `.env`:

```bash
DRY_RUN_MODE=true   # Logs messages without sending
DRY_RUN_MODE=false  # Actually sends messages
```

### Rate Limiting

Configure in `.env`:

```bash
RATE_LIMIT_PER_MINUTE=10  # Max messages per minute
MAX_RETRIES=2             # Retry attempts for failed sends
```

### Email Configuration

For live email sending, configure SMTP:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password  # Use Gmail App Password
```

## 🎮 Usage

### Running the Pipeline

1. Open the frontend dashboard at http://localhost:3000
2. Toggle "Dry Run" mode if you want to test without sending
3. Click "Run Pipeline" button
4. Monitor progress in real-time

### Pipeline Stages

1. **Generate Leads** → Creates 200+ realistic leads
2. **Enrich Leads** → Adds company insights and personas
3. **Generate Messages** → Creates personalized email + LinkedIn DM
4. **Send Outreach** → Delivers messages (or logs in dry-run)

### n8n Workflow

Access n8n at http://localhost:5678 to view and modify the orchestration workflow.

## 🧪 Testing

### Generate Sample Leads Only

```bash
python backend/lead_generator.py
```

### Test Enrichment

```bash
python backend/enrichment.py
```

### Test Message Generation

```bash
python backend/messaging.py
```

## 📊 Database Schema

Leads are tracked through these statuses:

- `NEW` → Lead created
- `ENRICHED` → Lead enriched with insights
- `MESSAGED` → Messages generated
- `SENT` → Outreach sent successfully
- `FAILED` → Process failed

## 🆓 Free Resources Used

- **Groq**: Free tier LLM API (100 requests/minute)
- **SQLite**: Local database (no limits)
- **n8n**: Self-hosted open-source (free)
- **Faker**: Python library for realistic data generation
- **FastAPI**: Python web framework
- **Next.js**: React framework
- **Mailhog** (optional): Local SMTP testing server
