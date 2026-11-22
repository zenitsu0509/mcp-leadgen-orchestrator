"""FastAPI control plane for the lead research and outreach worker."""

import hmac
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import Config
from database import Database, LeadStatus
from lead_generator import LeadGenerator
from rag_engine import RAGEngine
from worker import PipelineWorker

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("leadgen.api")

db = Database()
rag = RAGEngine()
worker_thread = None
worker_instance = None


@asynccontextmanager
async def lifespan(_app):
    global worker_thread, worker_instance
    if Config.PIPELINE_WORKER_ENABLED:
        worker_instance = PipelineWorker(db, rag)
        worker_thread = threading.Thread(
            target=worker_instance.run_forever, name="leadgen-worker", daemon=True
        )
        worker_thread.start()
    yield
    if worker_instance:
        worker_instance.stop()
    if worker_thread and worker_thread.is_alive():
        worker_thread.join(timeout=5)


production = Config.APP_ENV.lower() == "production"
app = FastAPI(
    title="Lead Generation API", version="2.0.0", lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Admin-Token"],
)


def require_api_token(authorization: Optional[str] = Header(default=None)):
    if Config.APP_ENV.lower() == "production" and not Config.API_AUTH_TOKEN:
        raise HTTPException(status_code=503, detail="API_AUTH_TOKEN must be configured in production")
    if Config.API_AUTH_TOKEN:
        expected = f"Bearer {Config.API_AUTH_TOKEN}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Valid bearer token required")


def require_admin_token(x_admin_token: Optional[str] = Header(default=None)):
    if Config.APP_ENV.lower() == "production" and not Config.ADMIN_API_TOKEN:
        raise HTTPException(status_code=503, detail="ADMIN_API_TOKEN must be configured in production")
    if Config.ADMIN_API_TOKEN and (
        not x_admin_token or not hmac.compare_digest(x_admin_token, Config.ADMIN_API_TOKEN)
    ):
        raise HTTPException(status_code=401, detail="Valid admin token required")


class PipelineRequest(BaseModel):
    dry_run: bool = Config.DRY_RUN_MODE
    enrichment_mode: str = Field(default="offline", pattern="^(offline|ai)$")
    channel: str = Field(default="email", pattern="^(email)$")
    require_approval: bool = Config.REQUIRE_EMAIL_APPROVAL
    lead_data: dict


class ApprovalRequest(BaseModel):
    dry_run: bool = Config.DRY_RUN_MODE
    variation: str = Field(default="A", pattern="^[AB]$")
    scheduled_for: Optional[str] = None


class BulkApprovalRequest(BaseModel):
    lead_ids: list[int]
    variation: str = Field(default="A", pattern="^[AB]$")
    dry_run: bool = Config.DRY_RUN_MODE
    scheduled_for: Optional[str] = None


class ApproveAllRequest(BaseModel):
    variation: str = Field(default="A", pattern="^[AB]$")
    dry_run: bool = Config.DRY_RUN_MODE
    scheduled_for: Optional[str] = None


class RevisionRequest(BaseModel):
    variation: str = Field(pattern="^[AB]$")
    feedback: str = Field(min_length=3, max_length=2000)


@app.get("/")
async def root():
    return {"name": "Lead Generation API", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    try:
        db.get_metrics()
        return {"status": "healthy", "database": "reachable"}
    except Exception as exc:
        logger.exception("health check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@app.get("/metrics", dependencies=[Depends(require_api_token)])
async def get_metrics():
    metrics = db.get_metrics()
    return {**metrics, **db.get_pipeline_summary()}


@app.get("/leads")
async def get_leads(
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _auth: None = Depends(require_api_token),
):
    status_enum = None
    if status:
        try:
            status_enum = LeadStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
    return {
        "total": db.count_leads(status_enum), "limit": limit, "offset": offset,
        "leads": db.get_leads_by_status(status_enum, limit=limit, offset=offset),
    }


@app.get("/leads/{lead_id}", dependencies=[Depends(require_api_token)])
async def get_lead(lead_id: int):
    lead = db.get_lead_with_enrichment(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@app.get("/leads/{lead_id}/messages", dependencies=[Depends(require_api_token)])
async def get_lead_messages(lead_id: int):
    if not db.get_lead(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead_id": lead_id, "messages": db.get_lead_messages(lead_id)}


@app.post("/pipeline/run", status_code=202, dependencies=[Depends(require_api_token)])
async def run_pipeline(request: PipelineRequest):
    try:
        processed = LeadGenerator().process_external_lead(request.lead_data)
    except ValueError as exc:
        logger.info("pipeline input rejected: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = db.create_pipeline_job(processed, {
        "dry_run": request.dry_run,
        "enrichment_mode": request.enrichment_mode,
        "channel": request.channel,
        "require_approval": request.require_approval,
    })
    if job.get("suppressed"):
        return {"message": "Lead is on the suppression list", "status": "suppressed"}
    if not job["created"]:
        return {
            "message": "Duplicate lead ignored; this email has already been received",
            "status": "duplicate", "lead_id": job.get("lead_id"),
            "job_id": job.get("job_id"), "job_status": job.get("job_status"),
        }
    logger.info("pipeline job queued", extra={"job_id": job["job_id"], "lead_id": job["lead_id"]})
    return {"message": "Pipeline job queued", "status": "queued", **job}


@app.get("/jobs/{job_id}", dependencies=[Depends(require_api_token)])
async def get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/leads/{lead_id}/approve", status_code=202, dependencies=[Depends(require_api_token)])
async def approve_email(lead_id: int, request: ApprovalRequest):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    sched_time = None
    if request.scheduled_for:
        try:
            from datetime import datetime
            sched_time = datetime.fromisoformat(request.scheduled_for.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid scheduled_for timestamp: {e}")
    job = db.enqueue_delivery_job(
        lead_id, dry_run=request.dry_run, variation=request.variation, scheduled_for=sched_time,
    )
    if job.get("missing"):
        raise HTTPException(status_code=404, detail="Lead not found")
    if not job.get("created") and not job.get("job_id"):
        raise HTTPException(status_code=409, detail=f"Lead cannot be approved from status {job.get('status')}")
    return {"message": "Approved delivery queued", **job}


@app.post("/leads/{lead_id}/retry", status_code=202, dependencies=[Depends(require_api_token)])
async def retry_lead(lead_id: int):
    """Re-queue a failed or stuck lead for processing."""
    job = db.enqueue_retry_job(lead_id)
    if job.get("missing"):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"message": "Lead re-queued for processing", **job}


@app.post("/leads/bulk-approve", status_code=202, dependencies=[Depends(require_api_token)])
async def bulk_approve_leads(request: BulkApprovalRequest):
    """Bulk approve and send/schedule outreach emails to specifically selected leads."""
    if not request.lead_ids:
        raise HTTPException(status_code=422, detail="No lead IDs provided")

    sched_time = None
    if request.scheduled_for:
        try:
            from datetime import datetime
            sched_time = datetime.fromisoformat(request.scheduled_for.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid scheduled_for timestamp: {e}")

    result = db.enqueue_bulk_delivery_jobs(
        lead_ids=request.lead_ids,
        variation=request.variation,
        dry_run=request.dry_run,
        scheduled_for=sched_time,
    )
    return {"message": f"Queued {result['queued_count']} deliveries", **result}


@app.post("/leads/approve-all", status_code=202, dependencies=[Depends(require_api_token)])
async def approve_all_pending_leads(request: ApproveAllRequest):
    """Approve and send/schedule outreach emails to all leads currently awaiting review."""
    sched_time = None
    if request.scheduled_for:
        try:
            from datetime import datetime
            sched_time = datetime.fromisoformat(request.scheduled_for.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid scheduled_for timestamp: {e}")

    result = db.enqueue_all_pending_delivery(
        variation=request.variation,
        dry_run=request.dry_run,
        scheduled_for=sched_time,
    )
    return {"message": f"Queued {result['queued_count']} deliveries for all pending leads", **result}


@app.post("/leads/{lead_id}/revise", status_code=202, dependencies=[Depends(require_api_token)])
async def revise_email(lead_id: int, request: RevisionRequest,
                       idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    feedback = request.feedback.strip()
    if len(feedback) < 3:
        raise HTTPException(status_code=422, detail="Feedback must contain at least 3 non-space characters")
    job = db.enqueue_revision_job(
        lead_id, variation=request.variation, feedback=feedback,
        idempotency_key=idempotency_key,
    )
    if job.get("missing"):
        raise HTTPException(status_code=404, detail="Lead not found")
    if job.get("status") and not job.get("job_id"):
        raise HTTPException(status_code=409, detail=f"Lead cannot be revised from status {job['status']}")
    return {"message": "Email revision queued", **job}


@app.post("/pipeline/stop", dependencies=[Depends(require_api_token)])
async def stop_pipeline():
    # Persisted jobs are not silently discarded; this endpoint reports queued/running state.
    summary = db.get_pipeline_summary()
    return {"message": "Jobs remain durable; stop the worker to pause processing", **summary}


@app.delete("/leads")
async def clear_leads(x_admin_token: Optional[str] = Header(default=None)):
    if Config.APP_ENV.lower() == "production" and not Config.ADMIN_API_TOKEN:
        raise HTTPException(status_code=403, detail="Lead deletion is disabled in production")
    if Config.ADMIN_API_TOKEN and (
        not x_admin_token or not hmac.compare_digest(x_admin_token, Config.ADMIN_API_TOKEN)
    ):
        raise HTTPException(status_code=401, detail="Valid admin token required")
    db.clear_all_data()
    return {"message": "Lead data cleared"}


@app.post("/suppression", dependencies=[Depends(require_api_token), Depends(require_admin_token)])
async def suppress_email(payload: dict):
    email = str(payload.get("email", "")).strip()
    reason = str(payload.get("reason", "manual")).strip()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email is required")
    db.add_suppression(email, reason, source="api")
    return {"status": "suppressed"}


class InboundEmailPayload(BaseModel):
    email: Optional[str] = ""
    sender: Optional[str] = Field(default="", alias="from")
    recipient: Optional[str] = Field(default="", alias="to")
    subject: Optional[str] = ""
    body: Optional[str] = Field(default="", alias="text")
    message_id: Optional[str] = Field(default="", alias="Message-ID")
    in_reply_to: Optional[str] = Field(default="", alias="In-Reply-To")
    references: Optional[str] = Field(default="", alias="References")
    headers: Optional[dict] = Field(default_factory=dict)
    event_type: Optional[str] = None
    lead_id: Optional[int] = None

    class Config:
        populate_by_name = True


@app.post("/webhooks/inbound-email", status_code=200)
async def inbound_email_webhook(payload: dict):
    """
    Ingest inbound reply, bounce, or out-of-office message from mailboxes or ESP webhooks.
    Automatically classifies intent and updates lead state and suppression.
    """
    email = str(payload.get("email") or payload.get("from") or payload.get("sender") or "").strip()
    # Extract clean email if formatted as "Name <email@example.com>"
    if "<" in email and ">" in email:
        email = email.split("<")[1].split(">")[0].strip()

    subject = str(payload.get("subject") or "")
    body = str(payload.get("text") or payload.get("body") or payload.get("stripped-text") or "")
    in_reply_to = str(payload.get("In-Reply-To") or payload.get("in_reply_to") or "")
    references = str(payload.get("References") or payload.get("references") or "")
    provider_msg_id = str(payload.get("Message-ID") or payload.get("message_id") or "")
    headers = payload.get("headers") or {}
    lead_id = payload.get("lead_id")

    event_data = {
        "email": email,
        "lead_id": lead_id,
        "subject": subject,
        "body": body,
        "in_reply_to": in_reply_to,
        "references": references,
        "provider_message_id": provider_msg_id,
        "headers": headers,
        "event_type": payload.get("event_type") or payload.get("event"),
    }
    result = db.process_inbound_event(event_data)
    return {"message": "Inbound event processed", **result}


@app.post("/webhooks/events", status_code=200)
async def provider_event_webhook(payload: dict):
    """
    Ingest delivery/bounce/unsubscribe events from ESP providers (SendGrid, Mailgun, Postmark, SES).
    """
    email = str(payload.get("email") or payload.get("recipient") or "").strip()
    event_type = str(payload.get("event") or payload.get("event_type") or payload.get("RecordType") or "").lower()
    event_data = {
        "email": email,
        "lead_id": payload.get("lead_id"),
        "event_type": event_type,
        "subject": payload.get("subject", ""),
        "body": payload.get("reason", "") or payload.get("description", ""),
        "provider_message_id": payload.get("sg_message_id") or payload.get("message_id"),
        "headers": payload.get("headers") or {},
    }
    result = db.process_inbound_event(event_data)
    return {"message": "Provider event processed", **result}


@app.get("/inbound-events", dependencies=[Depends(require_api_token)])
async def list_inbound_events(lead_id: Optional[int] = Query(default=None), limit: int = Query(default=50, ge=1, le=200)):
    return {"events": db.get_inbound_events(lead_id=lead_id, limit=limit)}


class FollowupRequest(BaseModel):
    step: int = Field(default=1, ge=1, le=3)
    delay_days: int = Field(default=0, ge=0, le=30)
    dry_run: Optional[bool] = None


@app.post("/leads/{lead_id}/followup", status_code=202, dependencies=[Depends(require_api_token)])
async def trigger_followup(lead_id: int, request: FollowupRequest):
    """Schedule or immediately trigger a follow-up email for an outreach-completed lead."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    stopping = {LeadStatus.REPLIED.value, LeadStatus.BOUNCED.value, LeadStatus.UNSUBSCRIBED.value, LeadStatus.SUPPRESSED.value}
    if lead["status"] in stopping:
        raise HTTPException(status_code=409, detail=f"Cannot follow up with lead in status {lead['status']}")

    if db.is_suppressed(lead["email"]):
        raise HTTPException(status_code=409, detail="Lead email is in the suppression list")

    dry_run = request.dry_run if request.dry_run is not None else Config.DRY_RUN_MODE
    job = db.schedule_followup_job(
        lead_id=lead_id,
        step=request.step,
        delay_days=request.delay_days,
        dry_run=dry_run,
    )
    if not job.get("created"):
        raise HTTPException(status_code=409, detail=f"Follow-up not scheduled (status: {job.get('status') or 'already queued'})")
    return {"message": f"Follow-up #{request.step} queued", **job}


@app.post("/leads/{lead_id}/cancel-followup", dependencies=[Depends(require_api_token)])
async def cancel_followup(lead_id: int):
    """Cancel any pending follow-up jobs for a lead."""
    cancelled = db.cancel_pending_followup_jobs(lead_id, reason="Manual operator cancellation")
    return {"message": f"Cancelled {cancelled} follow-up jobs for lead {lead_id}", "cancelled_count": cancelled}


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8000))
    logger.info("starting API", extra={"port": port, "database": db.db_path})
    uvicorn.run(app, host="0.0.0.0", port=port)
