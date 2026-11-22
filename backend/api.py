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
    job = db.enqueue_delivery_job(
        lead_id, dry_run=request.dry_run, variation=request.variation
    )
    if job.get("missing"):
        raise HTTPException(status_code=404, detail="Lead not found")
    if not job.get("created") and not job.get("job_id"):
        raise HTTPException(status_code=409, detail=f"Lead cannot be approved from status {job.get('status')}")
    return {"message": "Approved delivery queued", **job}


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


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8000))
    logger.info("starting API", extra={"port": port, "database": db.db_path})
    uvicorn.run(app, host="0.0.0.0", port=port)
