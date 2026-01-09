# Project Architecture & Implementation Details

## System Overview

This is a complete MCP-powered lead generation and outreach system with the following components:

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│                   (Next.js Dashboard)                        │
│                  http://localhost:3000                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ REST API
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│                  http://localhost:8000                      │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ Generate │ Enrich   │ Generate │  Send    │  Get     │   │
│  │  Leads   │  Leads   │ Messages │ Outreach │  Metrics │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Layer                         │
│              (Model Context Protocol)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tools: generate_leads, enrich_leads,                │   │
│  │         generate_messages, send_outreach,            │   │
│  │         get_status, get_metrics                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
            ┌─────────────┼─────────────┐
            │             │             │
            ▼             ▼             ▼
    ┌──────────────┬──────────────┬──────────────┐
    │   SQLite DB  │   Groq API   │  SMTP Server │
    │  (Leads &    │  (AI Engine) │  (Outreach)  │
    │   State)     │              │              │
    └──────────────┴──────────────┴──────────────┘
                          │
                          │ Orchestration
                          ▼
                    ┌──────────┐
                    │   n8n    │
                    │ Workflow │
                    │ :5678    │
                    └──────────┘
```

## Component Details

### 1. Frontend (Next.js + React + Tailwind)

**Location:** `/pages`, `/styles`

**Features:**
- Real-time dashboard with metrics
- Lead table with status tracking
- Pipeline controls (run, stop, configure)
- Progress monitoring
- Dry run toggle
- Enrichment mode selection

**Key Files:**
- `pages/index.tsx` - Main dashboard
- `pages/_app.tsx` - App wrapper
- `styles/globals.css` - Global styles

**Technologies:**
- Next.js 14
- React 18
- Tailwind CSS
- Axios for API calls
- Lucide React for icons

### 2. Backend API (FastAPI)

**Location:** `/backend/api.py`

**Endpoints:**
- `GET /` - API info
- `GET /health` - Health check
- `GET /metrics` - Pipeline metrics
- `GET /leads` - List leads with filtering
- `GET /leads/{id}` - Get specific lead
- `POST /pipeline/run` - Run pipeline
- `POST /pipeline/stop` - Stop pipeline
- `DELETE /leads` - Clear all data

**Features:**
- Background task execution
- CORS enabled for frontend
- Real-time progress tracking
- Comprehensive error handling

### 3. MCP Server

**Location:** `/mcp_server/server.py`

**MCP Tools:**

1. **generate_leads**
   - Generates realistic leads using Faker
   - Validates email, website, LinkedIn URLs
   - Inserts into database
   - Returns validation summary

2. **enrich_leads**
   - Enriches leads with company insights
   - Supports offline (rule-based) and AI (Groq) modes
   - Adds persona, pain points, triggers
   - Updates lead status to ENRICHED

3. **generate_messages**
   - Creates personalized emails and LinkedIn DMs
   - Generates A/B variations
   - Uses Groq LLM for personalization
   - Stores messages in database

4. **send_outreach**
   - Sends via email and/or LinkedIn
   - Supports dry-run mode
   - Implements retry logic
   - Rate limiting (10/min default)

5. **get_status**
   - Returns current pipeline status
   - Lead counts by status
   - Message statistics

6. **get_metrics**
   - Detailed pipeline metrics
   - Percentage calculations
   - Health indicators

### 4. Lead Generator

**Location:** `/backend/lead_generator.py`

**Features:**
- Generates 200+ realistic leads
- Industry-specific data
- Role-appropriate titles
- Valid email formats
- Valid company websites
- Valid LinkedIn URLs
- Reproducible with seed

**Industries Supported:**
- Technology
- Manufacturing
- Healthcare
- Retail
- Finance
- Logistics

**Validation:**
- Email regex validation
- URL format checking
- Industry-role consistency
- Company naming rules

### 5. Enrichment Service

**Location:** `/backend/enrichment.py`

**Modes:**

**Offline Mode (Rule-based):**
- Company size from role keywords
- Industry-specific personas
- Predefined pain points
- Standard buying triggers
- Confidence scoring

**AI Mode (Groq LLM):**
- Context-aware enrichment
- Dynamic persona generation
- Specific pain points
- Realistic buying triggers
- Higher confidence scores

**Model Used:** llama-3.3-70b-versatile

### 6. Message Personalization

**Location:** `/backend/messaging.py`

**Capabilities:**
- Email generation (max 120 words)
- LinkedIn DM generation (max 60 words)
- A/B variations
- Context-aware personalization
- Industry-specific language
- Clear CTAs

**Prompting Strategy:**
- System role: Expert B2B copywriter
- Context injection: Lead + enrichment data
- Style variants for A/B testing
- Word count enforcement

### 7. Outreach Service

**Location:** `/backend/outreach.py`

**Features:**
- SMTP email sending
- LinkedIn DM simulation
- Dry-run mode
- Rate limiting (configurable)
- Retry logic with exponential backoff
- Error tracking
- Status updates

**Configuration:**
- SMTP host/port
- Authentication
- Rate limits
- Retry attempts

### 8. Database Layer

**Location:** `/backend/database.py`

**Schema:**

**Leads Table:**
- id, full_name, company_name
- role_title, industry
- company_website, email, linkedin_url
- country, status, timestamps

**Enrichment Table:**
- lead_id (FK)
- company_size, persona_tag
- pain_points (JSON), buying_triggers (JSON)
- confidence_score, enrichment_mode

**Messages Table:**
- lead_id (FK), channel, variation
- content, timestamp

**Outreach Table:**
- lead_id (FK), message_id (FK)
- channel, status, sent_at
- error_message, retry_count

**Status Flow:**
```
NEW → ENRICHED → MESSAGED → SENT
                           ↓
                         FAILED
```

### 9. n8n Workflow

**Location:** `/n8n/n8n-workflow.json`

**Workflow Steps:**
1. Manual Trigger
2. Run Pipeline via API
3. Wait for initialization
4. Poll metrics
5. Check if running
6. Wait for completion (if running)
7. Get final metrics
8. Retrieve leads

**Features:**
- Visual workflow editing
- Error handling nodes
- Retry logic
- Status monitoring
- Result collection

## Data Flow

### Complete Pipeline Execution

```
1. User clicks "Run Pipeline" in Dashboard
   ↓
2. Frontend sends POST to /pipeline/run
   ↓
3. FastAPI creates background task
   ↓
4. Background task executes pipeline:
   
   a) Generate Leads
      - LeadGenerator creates 200 leads
      - Validates all fields
      - Inserts into leads table
      - Status: NEW
   
   b) Enrich Leads
      - Fetches NEW leads from DB
      - LeadEnricher processes each
      - Calls Groq API (if AI mode)
      - Inserts enrichment data
      - Updates status: ENRICHED
   
   c) Generate Messages
      - Fetches ENRICHED leads
      - MessagePersonalizer creates emails + DMs
      - Generates A/B variations
      - Stores in messages table
      - Updates status: MESSAGED
   
   d) Send Outreach
      - Fetches MESSAGED leads
      - OutreachService sends messages
      - Applies rate limiting
      - Retries on failures
      - Updates status: SENT or FAILED
   ↓
5. Frontend polls /metrics every 2 seconds
   ↓
6. Dashboard updates in real-time
```

## Technology Stack

### Backend
- **Python 3.10+**
- **FastAPI** - Modern web framework
- **SQLAlchemy** - ORM (though we use raw SQL here)
- **Faker** - Realistic data generation
- **Groq** - LLM API client
- **python-dotenv** - Environment management
- **uvicorn** - ASGI server
- **MCP SDK** - Model Context Protocol

### Frontend
- **Next.js 14** - React framework
- **React 18** - UI library
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **Lucide React** - Icons

### Database
- **SQLite** - Lightweight SQL database
- Perfect for development and demos
- Easy to backup and share

### AI/LLM
- **Groq** - Fast inference API
- **llama-3.3-70b-versatile** - Large language model
- Free tier: 100 req/min

### Orchestration
- **n8n** - Visual workflow automation
- Self-hosted, open-source
- Drag-and-drop workflow builder

## Free Resources Utilized

1. **Groq API** - Free tier (100 req/min)
2. **SQLite** - Free, embedded database
3. **n8n** - Open-source, self-hosted
4. **Faker** - Free Python library
5. **FastAPI** - Open-source framework
6. **Next.js** - Open-source React framework
7. **Tailwind CSS** - Open-source CSS framework

## Configuration Options

### Environment Variables

```bash
# AI Configuration
GROQ_API_KEY=your_key_here

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@gmail.com

# Application Settings
DRY_RUN_MODE=true
RATE_LIMIT_PER_MINUTE=10
MAX_RETRIES=2

# Database
DATABASE_PATH=./data/leads.db

# Ports
API_PORT=8000
FRONTEND_PORT=3000
```

## Development Workflow

### Adding New Features

1. **New Lead Field:**
   - Update `database.py` schema
   - Modify `lead_generator.py` logic
   - Update frontend display

2. **New Enrichment Source:**
   - Add to `enrichment.py`
   - Create new enrichment mode
   - Update API parameters

3. **New Message Channel:**
   - Extend `messaging.py`
   - Add to `outreach.py`
   - Update UI controls

4. **New MCP Tool:**
   - Define in `mcp_server/server.py`
   - Add to `list_tools()`
   - Implement in `call_tool()`

## Testing Strategy

### Unit Testing (Recommended additions)

```python
# test_lead_generator.py
def test_lead_generation():
    generator = LeadGenerator(seed=42)
    leads = generator.generate_leads(10)
    assert len(leads) == 10
    assert all('@' in lead['email'] for lead in leads)

# test_enrichment.py
def test_offline_enrichment():
    enricher = LeadEnricher(mode='offline')
    # ... test enrichment logic

# test_messaging.py
def test_message_generation():
    # ... test message creation
```

### Integration Testing

- Test complete pipeline flow
- Verify database state transitions
- Check API endpoint responses
- Validate n8n workflow execution

## Security Considerations

### Current Implementation
- No authentication (local dev only)
- Environment variables for secrets
- .gitignore includes .env
- CORS restricted to localhost

### Production Recommendations
1. Add API authentication (JWT, API keys)
2. Use HTTPS/TLS
3. Implement rate limiting on API
4. Use secrets management (AWS Secrets Manager, Vault)
5. Add input validation and sanitization
6. Implement audit logging
7. Use database connection pooling
8. Add SQL injection protection

## Performance Optimization

### Current Performance
- SQLite: Fast for < 100K leads
- Groq API: ~100 req/min
- Rate limiting: 10 msg/min
- Background processing: Non-blocking

### Scaling Recommendations
1. **Database:** Switch to PostgreSQL
2. **Caching:** Add Redis for metrics
3. **Queue:** Use Celery for async tasks
4. **Load Balancing:** Add nginx
5. **Containerization:** Docker/Kubernetes
6. **CDN:** For frontend assets

## Monitoring & Logging

### Current Logging
- Console output for all services
- Database tracks all status changes
- Frontend displays real-time metrics

### Recommended Additions
1. **Structured logging** (JSON logs)
2. **Log aggregation** (ELK stack)
3. **Metrics collection** (Prometheus)
4. **Dashboards** (Grafana)
5. **Error tracking** (Sentry)
6. **Uptime monitoring** (UptimeRobot)

## Deployment Options

### Development (Current)
- Local SQLite
- Python venv
- npm dev server
- Manual start scripts

### Production Options

**Option 1: Single Server**
- DigitalOcean Droplet
- Docker Compose
- Nginx reverse proxy
- Let's Encrypt SSL

**Option 2: Cloud Native**
- AWS ECS/Fargate
- RDS for database
- CloudFront CDN
- AWS Secrets Manager

**Option 3: Serverless**
- Vercel (frontend)
- AWS Lambda (backend)
- DynamoDB (database)
- API Gateway

## Future Enhancements

### High Priority
- [ ] WebSocket for real-time updates
- [ ] Export leads to CSV
- [ ] Unit test coverage
- [ ] Docker containerization

### Medium Priority
- [ ] Multi-tenant support
- [ ] Advanced filtering/search
- [ ] Email template editor
- [ ] Analytics dashboard
- [ ] Scheduled pipeline runs

### Low Priority
- [ ] LinkedIn OAuth integration
- [ ] CRM integrations (Salesforce, HubSpot)
- [ ] A/B test results tracking
- [ ] Machine learning for optimization
- [ ] Mobile app

## License

MIT License - Free to use and modify

## Support

For issues or questions:
1. Check SETUP.md
2. Review API docs at /docs
3. Examine console logs
4. Verify .env configuration
