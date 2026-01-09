"""
FastAPI backend for the lead generation system.
Provides REST API for frontend monitoring and pipeline execution.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv
import uvicorn

from database import Database, LeadStatus
from lead_generator import LeadGenerator
from enrichment import LeadEnricher
from messaging import MessagePersonalizer
from outreach import OutreachService

load_dotenv()

app = FastAPI(title="Lead Generation API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5678"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = Database()

# Pipeline state
pipeline_state = {
    "running": False,
    "current_stage": None,
    "progress": 0
}


# Request models
class PipelineRequest(BaseModel):
    dry_run: bool = True
    enrichment_mode: str = "offline"
    lead_count: int = 200
    channel: str = "both"


class LeadResponse(BaseModel):
    id: int
    full_name: str
    company_name: str
    role_title: str
    industry: str
    email: str
    status: str


# Routes
@app.get("/")
async def root():
    """API root"""
    return {
        "name": "Lead Generation API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/metrics")
async def get_metrics():
    """Get pipeline metrics"""
    metrics = db.get_metrics()
    return {
        "total_leads": metrics["total_leads"],
        "leads_enriched": metrics["leads_enriched"],
        "messages_generated": metrics["messages_generated"],
        "messages_sent": metrics["messages_sent"],
        "messages_failed": metrics["messages_failed"],
        "status_breakdown": metrics["status_breakdown"],
        "pipeline_running": pipeline_state["running"],
        "current_stage": pipeline_state["current_stage"],
        "progress": pipeline_state["progress"]
    }


@app.get("/leads")
async def get_leads(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get leads with optional status filter"""
    if status:
        try:
            status_enum = LeadStatus(status)
            leads = db.get_leads_by_status(status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    else:
        leads = db.get_leads_by_status()
    
    # Apply pagination
    paginated_leads = leads[offset:offset + limit]
    
    return {
        "total": len(leads),
        "limit": limit,
        "offset": offset,
        "leads": paginated_leads
    }


@app.get("/leads/{lead_id}")
async def get_lead(lead_id: int):
    """Get a specific lead with enrichment data"""
    lead = db.get_lead_with_enrichment(lead_id)
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return lead


@app.post("/pipeline/run")
async def run_pipeline(
    request: PipelineRequest,
    background_tasks: BackgroundTasks
):
    """Run the complete pipeline"""
    if pipeline_state["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    
    # Run pipeline in background
    background_tasks.add_task(
        execute_pipeline,
        request.lead_count,
        request.enrichment_mode,
        request.dry_run,
        request.channel
    )
    
    return {
        "message": "Pipeline started",
        "config": {
            "lead_count": request.lead_count,
            "enrichment_mode": request.enrichment_mode,
            "dry_run": request.dry_run,
            "channel": request.channel
        }
    }


@app.post("/pipeline/stop")
async def stop_pipeline():
    """Stop the pipeline"""
    pipeline_state["running"] = False
    pipeline_state["current_stage"] = None
    
    return {"message": "Pipeline stopped"}


@app.delete("/leads")
async def clear_leads():
    """Clear all leads (for testing)"""
    db.clear_all_data()
    pipeline_state["running"] = False
    pipeline_state["current_stage"] = None
    pipeline_state["progress"] = 0
    return {"message": "All leads cleared"}


@app.get("/pipeline/status")
async def get_pipeline_status():
    """Get current pipeline state (for debugging)"""
    return {
        "running": pipeline_state["running"],
        "current_stage": pipeline_state["current_stage"],
        "progress": pipeline_state["progress"]
    }


# Pipeline execution
def execute_pipeline(
    lead_count: int,
    enrichment_mode: str,
    dry_run: bool,
    channel: str
):
    """Execute the complete pipeline"""
    print(f"\n🚀 Starting pipeline execution...")
    print(f"  Lead Count: {lead_count}")
    print(f"  Enrichment Mode: {enrichment_mode}")
    print(f"  Dry Run: {dry_run}")
    print(f"  Channel: {channel}\n")
    
    pipeline_state["running"] = True
    pipeline_state["progress"] = 0
    
    try:
        # Clear old data before starting new pipeline run
        print("🧹 Clearing old data...")
        db.clear_all_data()
        print(f"  ✅ Database cleared\n")
        
        # Stage 1: Generate leads
        print("📝 Stage 1: Generating leads...")
        pipeline_state["current_stage"] = "Generating leads"
        pipeline_state["progress"] = 10
        
        generator = LeadGenerator(seed=42)
        leads = generator.generate_leads(lead_count)
        print(f"  ✅ Generated {len(leads)} leads")
        
        for lead in leads:
            db.insert_lead(lead)
        
        pipeline_state["progress"] = 25
        print(f"  ✅ Inserted {len(leads)} leads into database\n")
        
        # Stage 2: Enrich leads
        print("🔍 Stage 2: Enriching leads...")
        pipeline_state["current_stage"] = "Enriching leads"
        
        enricher = LeadEnricher(mode=enrichment_mode)
        new_leads = db.get_leads_by_status(LeadStatus.NEW)
        print(f"  Found {len(new_leads)} leads to enrich")
        
        for i, lead in enumerate(new_leads):
            if i % 50 == 0:
                print(f"  Enriching lead {i+1}/{len(new_leads)}...")
            enrichment = enricher.enrich_lead(lead)
            db.insert_enrichment(lead['id'], enrichment)
            db.update_lead_status(lead['id'], LeadStatus.ENRICHED)
            pipeline_state["progress"] = 25 + int((i / len(new_leads)) * 25)
        
        pipeline_state["progress"] = 50
        print(f"  ✅ Enriched {len(new_leads)} leads\n")
        
        # Stage 3: Generate messages
        print("✉️ Stage 3: Generating messages...")
        pipeline_state["current_stage"] = "Generating messages"
        
        personalizer = MessagePersonalizer()
        enriched_leads = db.get_leads_by_status(LeadStatus.ENRICHED)
        print(f"  Found {len(enriched_leads)} leads to generate messages for")
        
        for i, lead in enumerate(enriched_leads):
            if i % 50 == 0:
                print(f"  Generating messages {i+1}/{len(enriched_leads)}...")
            enrichment = db.get_lead_with_enrichment(lead['id'])
            messages = personalizer.generate_all_messages(lead, enrichment)
            
            # Store messages
            db.insert_message(lead['id'], 'email', 'A', 
                            f"{messages['email_a']['subject']}\n\n{messages['email_a']['body']}")
            db.insert_message(lead['id'], 'linkedin', 'A', messages['linkedin_a']['message'])
            
            db.update_lead_status(lead['id'], LeadStatus.MESSAGED)
            pipeline_state["progress"] = 50 + int((i / len(enriched_leads)) * 25)
        
        pipeline_state["progress"] = 75
        print(f"  ✅ Generated messages for {len(enriched_leads)} leads\n")
        
        # Stage 4: Send outreach
        print("📤 Stage 4: Sending outreach...")
        pipeline_state["current_stage"] = "Sending outreach"
        
        outreach = OutreachService(dry_run=dry_run)
        messaged_leads = db.get_leads_by_status(LeadStatus.MESSAGED)
        print(f"  Found {len(messaged_leads)} leads to send to")
        
        for i, lead in enumerate(messaged_leads):
            if i % 50 == 0:
                print(f"  Sending to lead {i+1}/{len(messaged_leads)}...")
            enriched_lead = db.get_lead_with_enrichment(lead['id'])
            
            # Simple messages for sending
            messages = {
                'email_a': {
                    'subject': f"Question about {lead['industry']}",
                    'body': f"Hi {lead['full_name'].split()[0]},\n\nWould you be open to a 15-minute call?\n\nBest regards"
                },
                'linkedin_a': {
                    'message': f"Hi {lead['full_name'].split()[0]}, would love to connect!"
                }
            }
            
            results = outreach.send_outreach(lead, messages, channel)
            
            # Update status
            all_success = all(r['status'] == 'success' for r in results.values())
            if all_success:
                db.update_lead_status(lead['id'], LeadStatus.SENT)
            else:
                db.update_lead_status(lead['id'], LeadStatus.FAILED)
            
            pipeline_state["progress"] = 75 + int((i / len(messaged_leads)) * 25)
        
        pipeline_state["progress"] = 100
        pipeline_state["current_stage"] = "Complete"
        print(f"  ✅ Sent to {len(messaged_leads)} leads\n")
        
        print("🎉 Pipeline execution complete!")
        print(f"  Final Status: {pipeline_state['current_stage']}")
        print(f"  Progress: {pipeline_state['progress']}%\n")
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        pipeline_state["current_stage"] = error_msg
        print(f"\n❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        pipeline_state["running"] = False
        print(f"Pipeline state: running={pipeline_state['running']}, stage={pipeline_state['current_stage']}\n")


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8000))
    print(f"\n{'='*60}")
    print(f"🚀 Starting Lead Generation API")
    print(f"{'='*60}")
    print(f"📍 Server: http://localhost:{port}")
    print(f"📚 API Docs: http://localhost:{port}/docs")
    print(f"🔧 Database: {db.db_path}")
    print(f"{'='*60}\n")
    
    # Check Groq API key
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key or groq_key == "your_groq_api_key_here":
        print("⚠️  WARNING: GROQ_API_KEY not configured!")
        print("   AI enrichment and message generation will fail.")
        print("   Set GROQ_API_KEY in .env file\n")
    else:
        print(f"✅ Groq API key configured\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
