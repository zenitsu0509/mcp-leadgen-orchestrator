# Complete Setup Guide

This guide will walk you through setting up the entire Lead Generation Pipeline system.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.10 or higher** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18 or higher** - [Download Node.js](https://nodejs.org/)
- **Git** (optional) - [Download Git](https://git-scm.com/downloads/)
- **n8n** - Remote self-hosted instance at https://92e249f97c50.ngrok-free.app

## Step 1: Get a Groq API Key

1. Visit [Groq Console](https://console.groq.com)
2. Sign up for a free account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the API key (you'll need it in Step 3)

The free tier provides:
- 100 requests per minute
- Sufficient for this project

## Step 2: Project Setup

### Windows

1. Open Command Prompt or PowerShell
2. Navigate to the project directory:
   ```cmd
   cd e:\intern-assigment\linkind-mcp
   ```

3. Run the setup script:
   ```cmd
   setup.bat
   ```

### Linux/Mac

1. Open Terminal
2. Navigate to the project directory:
   ```bash
   cd /path/to/linkind-mcp
   ```

3. Make scripts executable:
   ```bash
   chmod +x setup.sh start.sh
   ```

4. Run the setup script:
   ```bash
   ./setup.sh
   ```

The setup script will:
- Create a Python virtual environment
- Install all Python dependencies
- Create the data directory
- Initialize the SQLite database
- Install Node.js dependencies

## Step 3: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   # Windows
   copy .env.example .env
   
   # Linux/Mac
   cp .env.example .env
   ```

2. Edit the `.env` file with your preferred text editor

3. **Required:** Add your Groq API key:
   ```bash
   GROQ_API_KEY=your_actual_groq_api_key_here
   ```

4. **Optional:** Configure email settings (for live email sending):
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@gmail.com
   SMTP_PASSWORD=your_gmail_app_password
   SMTP_FROM_EMAIL=your_email@gmail.com
   ```

   **Gmail App Password Setup:**
   - Enable 2-factor authentication on your Google account
   - Go to Google Account Settings > Security
   - Select "App passwords"
   - Generate a new app password for "Mail"
   - Use this password (not your regular Gmail password)

5. **Optional:** Adjust other settings:
   ```bash
   DRY_RUN_MODE=true              # true for testing, false for live sending
   RATE_LIMIT_PER_MINUTE=10       # Max messages per minute
   MAX_RETRIES=2                  # Retry attempts for failed sends
   ```

## Step 4: Verify Installation

1. Activate the virtual environment:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. Test the database:
   ```bash
   python backend/database.py
   ```
   
   You should see: `✅ Database initialized successfully!`

3. Test lead generation:
   ```bash
   python backend/lead_generator.py
   ```
   
   You should see 200 leads generated with validation summary

4. Test enrichment (requires Groq API key):
   ```bash
   python backend/enrichment.py
   ```

## Step 5: Import n8n Workflow

1. Open n8n at http://localhost:5678

2. Click the "+" button or "Add workflow"

3. Click the "Import from File" button (or use menu)

4. Select the file: `n8n/n8n-workflow.json`

5. The workflow should appear with all nodes connected

6. **Optional:** Customize the workflow
   - Click on "Manual Trigger" node to configure input parameters
   - Adjust the "Run Pipeline" node to change default settings
   - Modify wait times if needed

7. Save the workflow

## Step 6: Start the Services

### Option A: Using Start Script (Recommended)

**Windows:**
```cmd
start.bat
```

**Linux/Mac:**
```bash
./start.sh
```

This will start:
- API Backend on port 8000
- Frontend Dashboard on port 3000

### Option B: Manual Start (for debugging)

**Terminal 1 - API Backend:**
```bash
# Activate venv first
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Start API
python backend/api.py
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

## Step 7: Access the Applications

Once all services are running, access:

- **Frontend Dashboard:** http://localhost:3000
- **API Documentation:** http://localhost:8000/docs
- **API Backend:** http://localhost:8000
- **n8n Editor:** http://localhost:5678

## Step 8: Run Your First Pipeline

### Method 1: Using Frontend Dashboard

1. Go to http://localhost:3000
2. Configure pipeline settings:
   - Lead Count: 200
   - Enrichment Mode: Offline or AI
   - Run Mode: Dry Run (recommended for first test)
3. Click "Run Pipeline"
4. Watch the progress bar and metrics update in real-time

### Method 2: Using n8n Workflow

1. Go to http://localhost:5678
2. Open the imported workflow
3. Click "Execute Workflow" button
4. Watch the execution progress
5. Check the frontend dashboard for results

### Method 3: Using API Directly

```bash
curl -X POST "http://localhost:8000/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run": true,
    "enrichment_mode": "offline",
    "lead_count": 200,
    "channel": "both"
  }'
```

## Verification Checklist

After running your first pipeline, verify:

- [ ] Leads are visible in the frontend dashboard table
- [ ] Metrics show correct counts (200 leads, enriched, messaged, sent)
- [ ] Lead statuses progress through: NEW → ENRICHED → MESSAGED → SENT
- [ ] No errors in the console/terminal
- [ ] Database file created at `data/leads.db`

## Common Issues & Solutions

### Issue: "Module not found" errors

**Solution:**
```bash
# Ensure virtual environment is activated
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "GROQ_API_KEY not found"

**Solution:**
- Verify `.env` file exists in the root directory
- Check that `GROQ_API_KEY=your_key` is set correctly
- Ensure no extra spaces or quotes around the key
- Restart the API server after changing `.env`

### Issue: Frontend won't load

**Solution:**
```bash
# Clear node modules and reinstall
rm -rf node_modules
npm install

# Or on Windows
rmdir /s /q node_modules
npm install
```

### Issue: Port already in use

**Solution:**
```bash
# Windows - Kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <process_id> /F

# Linux/Mac - Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Issue: Database locked error

**Solution:**
```bash
# Close all connections to database
# Delete and reinitialize database
rm data/leads.db
python backend/database.py
```

## Testing Different Modes

### 1. Dry Run Mode (Safe Testing)
```bash
DRY_RUN_MODE=true
```
- Messages are logged but not sent
- Perfect for testing without actual outreach
- Recommended for development

### 2. Offline Enrichment Mode
```bash
ENRICHMENT_MODE=offline
```
- Uses rule-based enrichment
- No API calls to Groq
- Faster processing
- Good for testing pipeline flow

### 3. AI Enrichment Mode
```bash
ENRICHMENT_MODE=ai
```
- Uses Groq LLM for enrichment
- More realistic and personalized data
- Requires valid API key
- Slower but higher quality

### 4. Live Run Mode (Production)
```bash
DRY_RUN_MODE=false
```
- Actually sends emails (requires SMTP config)
- LinkedIn DMs are still simulated
- Use with caution!

## Next Steps

1. **Explore the Frontend:**
   - View lead details
   - Monitor pipeline progress
   - Check metrics and status breakdown

2. **Customize the Workflow:**
   - Edit n8n workflow nodes
   - Add error handling
   - Implement notifications

3. **Review Generated Data:**
   - Check SQLite database with DB Browser
   - Export leads to CSV
   - Analyze message variations

4. **Optimize Settings:**
   - Adjust rate limiting
   - Configure retry logic
   - Tune enrichment prompts

## Production Deployment

For production use:

1. **Security:**
   - Never commit `.env` file to git
   - Use environment variables in production
   - Enable authentication on APIs

2. **Scaling:**
   - Use PostgreSQL instead of SQLite
   - Implement job queues (Celery, RQ)
   - Add caching (Redis)

3. **Monitoring:**
   - Set up logging (ELK stack, CloudWatch)
   - Add metrics (Prometheus, Grafana)
   - Configure alerts (PagerDuty, Slack)

4. **Email Deliverability:**
   - Use transactional email service (SendGrid, Mailgun)
   - Implement proper SPF, DKIM, DMARC
   - Monitor bounce and spam rates

## Support & Resources

- **Documentation:** README.md in root directory
- **API Docs:** http://localhost:8000/docs (when API is running)
- **n8n Docs:** https://docs.n8n.io
- **Groq API Docs:** https://console.groq.com/docs

## Maintenance

### Regular Tasks

1. **Clear old data:**
   ```bash
   # Via API
   curl -X DELETE http://localhost:8000/leads
   
   # Or via frontend "Clear Data" button
   ```

2. **Backup database:**
   ```bash
   # Windows
   copy data\leads.db data\leads_backup.db
   
   # Linux/Mac
   cp data/leads.db data/leads_backup.db
   ```

3. **Update dependencies:**
   ```bash
   # Python
   pip install --upgrade -r requirements.txt
   
   # Node.js
   npm update
   ```

## Troubleshooting

If you encounter any issues:

1. Check all services are running
2. Review console/terminal logs for errors
3. Verify `.env` configuration
4. Ensure database is initialized
5. Clear browser cache
6. Restart all services

For persistent issues, check the logs in:
- API Backend: Console output
- Frontend: Browser console (F12)
- n8n: Execution logs in n8n interface

---

**Congratulations!** Your Lead Generation Pipeline is now fully set up and ready to use. 🎉
