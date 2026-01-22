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
- n8n (remote self-hosted instance)
- Groq API key (free tier available at https://console.groq.com)
- ngrok account (free tier available at https://ngrok.com)

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
- **n8n Editor**: Your remote n8n instance URL

### 8. Setup ngrok Tunnel

To connect your local API with the remote n8n instance:

```bash
# In a new terminal, start ngrok
ngrok http 8000
```

Copy the ngrok URL (e.g., `https://abc123.ngrok-free.app`) and update your n8n workflow nodes to use this URL.

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

### How the System Works

The system now operates through automated triggers from external sources:

1. **Lead Capture**:
   - **Google Sheets**: Add a new row with lead information
   - **Facebook Lead Ads**: User submits an instant form
   
2. **Automatic Processing**:
   - n8n detects the new lead from trigger
   - Processes and normalizes the lead data
   - Sends to your local API via ngrok
   - API enriches the lead with AI insights
   - Generates personalized messages
   - Sends outreach (email/LinkedIn)

3. **Monitor Progress**:
   - Open frontend dashboard at http://localhost:3000
   - View real-time metrics and lead status
   - Check enrichment data and generated messages

### Pipeline Stages

1. **Process Lead** → Receives and validates external lead data
2. **Enrich Lead** → Adds AI-generated company insights and personas
3. **Generate Messages** → Creates personalized email + LinkedIn DM
4. **Send Outreach** → Delivers messages (or logs in dry-run mode)

### Testing with Sample Data

Add a test lead to your Google Sheet with:
- **Name**: John Smith
- **Email**: john.smith@company.com
- **Phone**: +1-555-0123
- **Job Title**: VP of Sales
- **Company**: TechCorp Solutions

The n8n workflow will automatically detect and process it.

### n8n Workflow Setup

1. **Access your n8n instance** (remote self-hosted)
2. **Import the workflow**: Navigate to n8n and import `n8n/n8n-workflow.json`
3. **Configure triggers**:
   - **Google Sheets Trigger**: Connect your Google account and select the spreadsheet with lead data
     - Required columns: name, email, phone, job_title, company
   - **Facebook Lead Ads Trigger**: Connect your Facebook account and select the form
4. **Update API endpoints**: Replace placeholder URLs in all HTTP Request nodes with your ngrok URL:
   - Run Pipeline: `https://YOUR-NGROK-URL.ngrok-free.app/pipeline/run`
   - Get Metrics: `https://YOUR-NGROK-URL.ngrok-free.app/metrics`
   - Get Leads: `https://YOUR-NGROK-URL.ngrok-free.app/leads`
5. **Activate the workflow**

## 🧪 Testing

### Test Lead Processing

```bash
python backend/lead_generator.py
```

### Test API Endpoint

```bash
curl -X POST http://localhost:8000/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": true,
    "enrichment_mode": "offline",
    "lead_count": 200,
    "channel": "both",
    "lead_data": {
      "name": "Jane Doe",
      "email": "jane@example.com",
      "phone": "+1-555-0199",
      "job_title": "CTO",
      "company": "Innovation Labs",
      "source": "test"
    }
  }'
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
- **ngrok**: Free tier for tunneling (https://ngrok.com)
- **External Lead Sources**: Facebook Lead Ads, Google Sheets
- **FastAPI**: Python web framework
- **Next.js**: React framework

## 🔐 Security Notes

- Keep your ngrok URL private - it exposes your local API
- Rotate ngrok URLs regularly (free tier URLs change on restart)
- Use environment variables for sensitive data
- Enable authentication on n8n in production
- Never commit `.env` files to version control

## 📝 License

MIT

## 🤝 Contributing

This is a take-home assignment project. For production use, consider adding:
- Unit tests
- WebSocket/SSE for real-time updates
- Multi-tenant support
- Export functionality
- Advanced targeting rules
