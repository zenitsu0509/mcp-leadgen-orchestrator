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
from rag_engine import RAGEngine

load_dotenv()

app = FastAPI(title="Lead Generation API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://92e249f97c50.ngrok-free.app",
        "http://n8nhim002.eastus.azurecontainer.io:5678",
        "http://n8nhim002.eastus.azurecontainer.io",
        "*"  # Allow all origins since n8n makes server-side HTTP calls (not browser CORS)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = Database()

# Initialize RAG engine (loads product knowledge base + embeddings at startup)
rag = RAGEngine()

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
    lead_data: Optional[dict] = None  # External lead data from Facebook/Google Forms


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


@app.get("/leads/{lead_id}/messages")
async def get_lead_messages(lead_id: int):
    """Get generated messages for a specific lead"""
    # First check if lead exists
    lead = db.get_lead_with_enrichment(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    messages = db.get_lead_messages(lead_id)
    
    return {
        "lead_id": lead_id,
        "messages": messages
    }


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
        request.channel,
        request.lead_data
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
    channel: str,
    lead_data: Optional[dict] = None
):
    """Execute the complete pipeline"""
    print(f"\n🚀 Starting pipeline execution...")
    print(f"  Lead Count: {lead_count}")
    print(f"  Enrichment Mode: {enrichment_mode}")
    print(f"  Dry Run: {dry_run}")
    print(f"  Channel: {channel}")
    print(f"  External Lead: {bool(lead_data)}\n")
    
    pipeline_state["running"] = True
    pipeline_state["progress"] = 0
    
    try:
        # Stage 1: Process lead data
        print("📝 Stage 1: Processing lead data...")
        pipeline_state["current_stage"] = "Processing leads"
        pipeline_state["progress"] = 10
        
        generator = LeadGenerator()
        
        if lead_data:
            # Process single external lead from Facebook/Google Forms
            print(f"  Processing external lead from {lead_data.get('source', 'external')}...")
            try:
                processed_lead = generator.process_external_lead(lead_data)
                lead_id = db.insert_lead(processed_lead)
                processed_lead['id'] = lead_id
                print(f"  ✅ Processed and inserted lead: {processed_lead['full_name']} (ID: {lead_id})")
            except ValueError as e:
                print(f"  ❌ Error processing lead: {e}")
                pipeline_state["running"] = False
                return
        else:
            print("  ⚠️  No lead data provided - pipeline requires external lead data")
            print("  Pipeline expects lead data from Facebook Lead Ads or Google Forms\n")
            pipeline_state["running"] = False
            return
        
        pipeline_state["progress"] = 25
        
        # Get the lead ID of the just-inserted lead
        current_lead_id = processed_lead['id']
        print(f"  ✅ Lead processing complete (ID: {current_lead_id})\n")
        
        # Stage 2: Enrich the single lead
        print("🔍 Stage 2: Enriching lead...")
        pipeline_state["current_stage"] = "Enriching lead"
        
        enricher = LeadEnricher(mode=enrichment_mode)
        new_leads = db.get_leads_by_status(LeadStatus.NEW)
        
        # Find the specific lead we just inserted
        current_lead = next((lead for lead in new_leads if lead['id'] == current_lead_id), None)
        
        if current_lead:
            print(f"  Enriching lead: {current_lead['full_name']}...")
            enrichment = enricher.enrich_lead(current_lead)
            db.insert_enrichment(current_lead['id'], enrichment)
            db.update_lead_status(current_lead['id'], LeadStatus.ENRICHED)
            pipeline_state["progress"] = 50
            print(f"  ✅ Enriched lead\n")
        else:
            print(f"  ❌ Could not find lead to enrich")
            pipeline_state["running"] = False
            return
        
        # Stage 2.5: RAG — find most relevant products for this lead
        print("🔍 Stage 2.5: Searching product database (RAG)...")
        enrichment_data = db.get_lead_with_enrichment(current_lead['id'])
        rag_query = rag.build_query_from_lead(current_lead, enrichment_data)
        print(f"  RAG query: \"{rag_query[:80]}...\"")
        rag_results = rag.search(rag_query, top_k=4)
        product_context = rag.build_short_context(rag_results)
        matched_products = [r['name'] for r in rag_results]
        print(f"  ✅ Matched products: {matched_products}\n")

        # Stage 3: Generate messages for the single lead
        print("✉️ Stage 3: Generating messages...")
        pipeline_state["current_stage"] = "Generating messages"

        personalizer = MessagePersonalizer()
        print(f"  Generating messages for {current_lead['full_name']}...")

        enrichment = db.get_lead_with_enrichment(current_lead['id'])
        messages = personalizer.generate_all_messages(current_lead, enrichment, product_context)
        
        # Store messages
        db.insert_message(current_lead['id'], 'email', 'A', 
                        f"{messages['email_a']['subject']}\n\n{messages['email_a']['body']}")
        db.insert_message(current_lead['id'], 'email', 'B', 
                        f"{messages['email_b']['subject']}\n\n{messages['email_b']['body']}")
        
        db.update_lead_status(current_lead['id'], LeadStatus.MESSAGED)
        pipeline_state["progress"] = 75
        print(f"  ✅ Generated messages\n")
        
        # Stage 4: Send outreach for the single lead
        print("📤 Stage 4: Sending outreach...")
        pipeline_state["current_stage"] = "Sending outreach"
        
        outreach = OutreachService(dry_run=dry_run)
        print(f"  Sending to {current_lead['full_name']}...")
        
        # Retrieve the AI-generated messages from database
        messages = db.get_lead_messages(current_lead['id'])
        
        if not messages:
            print(f"  ⚠️ No messages found in database, using fallback")
            messages = {
                'email_a': {
                    'subject': f"Question about {current_lead['industry']}",
                    'body': f"Hi {current_lead['full_name'].split()[0]},\n\nWould you be open to a 15-minute call?\n\nBest regards"
                }
            }
        
        results = outreach.send_outreach(current_lead, messages, channel)
        
        # Update status
        all_success = all(r['status'] == 'success' for r in results.values())
        if all_success:
            db.update_lead_status(current_lead['id'], LeadStatus.SENT)
            print(f"  ✅ Successfully sent outreach")
        else:
            db.update_lead_status(current_lead['id'], LeadStatus.FAILED)
            print(f"  ❌ Failed to send outreach")
        
        pipeline_state["progress"] = 100
        pipeline_state["current_stage"] = "Complete"
        print(f"  ✅ Outreach complete\n")
        
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
