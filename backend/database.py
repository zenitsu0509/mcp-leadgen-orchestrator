"""Persistence for leads, pipeline jobs, messages, and delivery audit records.

SQLAlchemy Core keeps local SQLite development and production PostgreSQL on the
same repository interface. Schema upgrades are additive for existing databases.
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, MetaData, String, Table, Text,
    and_, create_engine, func, inspect, select, update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool


class LeadStatus(str, Enum):
    NEW = "NEW"
    ENRICHED = "ENRICHED"
    MESSAGED = "MESSAGED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    SENT = "SENT"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


metadata = MetaData()

leads = Table(
    "leads", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("full_name", String(250), nullable=False),
    Column("company_name", String(250), nullable=False),
    Column("role_title", String(250), nullable=False),
    Column("industry", String(150), nullable=False),
    Column("company_website", String(500), nullable=False),
    Column("email", String(320), nullable=False),
    Column("phone", String(80)),
    Column("linkedin_url", String(500), nullable=False),
    Column("country", String(150), nullable=False),
    Column("comments", Text),
    Column("interest_area", Text),
    Column("challenge", Text),
    Column("company_size", String(100)),
    Column("source", String(100)),
    Column("idempotency_key", String(64)),
    Column("status", String(40), nullable=False, server_default="NEW"),
    Column("created_at", DateTime, server_default=func.current_timestamp()),
    Column("updated_at", DateTime, server_default=func.current_timestamp()),
)

enrichment = Table(
    "enrichment", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("lead_id", Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
    Column("company_size", String(100)),
    Column("persona_tag", String(200)),
    Column("pain_points", Text),
    Column("buying_triggers", Text),
    Column("confidence_score", Integer),
    Column("enrichment_mode", String(40)),
    Column("created_at", DateTime, server_default=func.current_timestamp()),
)

messages = Table(
    "messages", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("lead_id", Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
    Column("channel", String(40), nullable=False),
    Column("variation", String(20), nullable=False),
    Column("content", Text, nullable=False),
    Column("subject", Text),
    Column("body", Text),
    Column("html_body", Text),
    Column("revision", Integer, nullable=False, server_default="1"),
    Column("review_feedback", Text),
    Column("created_at", DateTime, server_default=func.current_timestamp()),
)

outreach = Table(
    "outreach", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("lead_id", Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
    Column("message_id", Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
    Column("channel", String(40), nullable=False),
    Column("status", String(40), server_default="PENDING"),
    Column("sent_at", DateTime),
    Column("error_message", Text),
    Column("provider_message_id", String(500)),
    Column("retry_count", Integer, server_default="0"),
    Column("created_at", DateTime, server_default=func.current_timestamp()),
)

pipeline_jobs = Table(
    "pipeline_jobs", metadata,
    Column("id", String(36), primary_key=True),
    Column("lead_id", Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
    Column("action", String(40), nullable=False, server_default="process"),
    Column("idempotency_key", String(100), nullable=False, unique=True),
    Column("status", String(40), nullable=False, server_default="PENDING"),
    Column("stage", String(150)),
    Column("progress", Integer, nullable=False, server_default="0"),
    Column("config", Text, nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("error_message", Text),
    Column("created_at", DateTime, server_default=func.current_timestamp()),
    Column("started_at", DateTime),
    Column("finished_at", DateTime),
    Column("updated_at", DateTime, server_default=func.current_timestamp()),
)
Index("ix_pipeline_jobs_status_created", pipeline_jobs.c.status, pipeline_jobs.c.created_at)

suppression = Table(
    "suppression", metadata,
    Column("email", String(320), primary_key=True),
    Column("reason", String(100), nullable=False),
    Column("source", String(100)),
    Column("created_at", DateTime, server_default=func.current_timestamp()),
)


class Database:
    def __init__(self, db_path: Optional[str] = None, engine: Optional[Engine] = None):
        database_url = db_path or os.getenv("DATABASE_URL") or os.getenv("DATABASE_PATH", "./data/leads.db")
        if database_url == ":memory:":
            database_url = "sqlite:///:memory:"
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://") and "+" not in database_url.split(":", 1)[0]:
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif "://" not in database_url:
            Path(database_url).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{Path(database_url).expanduser().resolve()}"

        engine_options = {"pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            engine_options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in database_url:
                engine_options["poolclass"] = StaticPool
        self.engine = engine or create_engine(database_url, **engine_options)
        self.db_path = database_url
        if self.engine.dialect.name == "sqlite":
            from sqlalchemy import event

            @event.listens_for(self.engine, "connect")
            def enable_sqlite_foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        if os.getenv("AUTO_MIGRATE", "true").lower() == "true":
            self.init_db()

    def init_db(self):
        metadata.create_all(self.engine)
        self._migrate_additive_columns()
        self._backfill_idempotency_keys()

    def _migrate_additive_columns(self):
        additions = {
            "leads": {
                "interest_area": "TEXT", "challenge": "TEXT", "company_size": "VARCHAR(100)",
                "idempotency_key": "VARCHAR(64)",
            },
            "messages": {
                "subject": "TEXT", "body": "TEXT", "html_body": "TEXT",
                "revision": "INTEGER NOT NULL DEFAULT 1", "review_feedback": "TEXT",
            },
            "outreach": {"provider_message_id": "VARCHAR(500)"},
        }
        inspector = inspect(self.engine)
        with self.engine.begin() as connection:
            for table_name, columns in additions.items():
                existing = {column["name"] for column in inspector.get_columns(table_name)}
                for name, sql_type in columns.items():
                    if name not in existing:
                        connection.exec_driver_sql(
                            f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {sql_type}'
                        )
        # Keep this index out of global SQLAlchemy metadata: the legacy schema
        # needs its column added before the index can be created.
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_idempotency_key "
                "ON leads (idempotency_key)"
            )

    def _backfill_idempotency_keys(self):
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(leads.c.id).where(leads.c.idempotency_key.is_(None))
            ).all()
            for row in rows:
                connection.execute(
                    update(leads).where(leads.c.id == row.id).values(
                        idempotency_key=f"legacy-{row.id}"
                    )
                )

    @staticmethod
    def _email_key(email: str) -> str:
        return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()

    @staticmethod
    def _lead_values(lead: Dict) -> Dict:
        return {
            "full_name": lead["full_name"], "company_name": lead["company_name"],
            "role_title": lead["role_title"], "industry": lead["industry"],
            "company_website": lead["company_website"], "email": lead["email"].strip(),
            "phone": lead.get("phone", ""), "linkedin_url": lead["linkedin_url"],
            "country": lead.get("country", "United States"), "comments": lead.get("comments", ""),
            "interest_area": lead.get("interest_area", ""), "challenge": lead.get("challenge", ""),
            "company_size": lead.get("company_size", ""), "source": lead.get("source", "external"),
        }

    def create_pipeline_job(self, lead_data: Dict, config: Dict) -> Dict:
        """Atomically deduplicate a lead and persist a durable queue item."""
        email_key = self._email_key(lead_data["email"])
        job_id = str(uuid.uuid4())
        config_json = json.dumps(config)
        try:
            with self.engine.begin() as connection:
                existing = connection.execute(
                    select(leads.c.id).where(
                        (leads.c.idempotency_key == email_key)
                        | (func.lower(leads.c.email) == lead_data["email"].strip().lower())
                    ).limit(1)
                ).first()
                if existing:
                    previous_job = connection.execute(
                        select(pipeline_jobs.c.id, pipeline_jobs.c.status)
                        .where(pipeline_jobs.c.lead_id == existing.id)
                        .order_by(pipeline_jobs.c.created_at.desc()).limit(1)
                    ).first()
                    return {
                        "created": False, "lead_id": existing.id,
                        "job_id": previous_job.id if previous_job else None,
                        "job_status": previous_job.status if previous_job else None,
                    }
                if connection.execute(
                    select(suppression.c.email).where(
                        func.lower(suppression.c.email) == lead_data["email"].strip().lower()
                    )
                ).first():
                    return {"created": False, "suppressed": True, "lead_id": None, "job_id": None}
                lead_id = connection.execute(
                    leads.insert().values(**self._lead_values(lead_data), idempotency_key=email_key)
                    .returning(leads.c.id)
                ).scalar_one()
                connection.execute(pipeline_jobs.insert().values(
                    id=job_id, lead_id=lead_id, action="process", idempotency_key=email_key,
                    status="PENDING", progress=0, config=config_json, attempts=0,
                ))
            return {"created": True, "lead_id": lead_id, "job_id": job_id, "job_status": "PENDING"}
        except IntegrityError:
            # Concurrent webhook deliveries can race on the unique email key.
            with self.engine.connect() as connection:
                existing = connection.execute(
                    select(leads.c.id).where(leads.c.idempotency_key == email_key)
                ).first()
                if existing:
                    return {"created": False, "lead_id": existing.id, "job_id": None, "job_status": None}
            raise

    def enqueue_delivery_job(self, lead_id: int, dry_run: bool = False,
                             variation: str = "A") -> Dict:
        job_id = str(uuid.uuid4())
        key = f"delivery:{lead_id}"
        with self.engine.begin() as connection:
            lead = connection.execute(select(leads.c.status).where(leads.c.id == lead_id)).first()
            if not lead:
                return {"created": False, "missing": True}
            if lead.status != LeadStatus.PENDING_APPROVAL.value:
                return {"created": False, "status": lead.status}
            existing = connection.execute(select(pipeline_jobs.c.id, pipeline_jobs.c.status)
                .where(pipeline_jobs.c.idempotency_key == key)).first()
            if existing:
                return {"created": False, "job_id": existing.id, "job_status": existing.status}
            connection.execute(pipeline_jobs.insert().values(
                id=job_id, lead_id=lead_id, action="deliver", idempotency_key=key,
                status="PENDING", progress=0,
                config=json.dumps({"dry_run": dry_run, "variation": variation}), attempts=0,
            ))
        return {"created": True, "job_id": job_id, "job_status": "PENDING"}

    def enqueue_revision_job(self, lead_id: int, variation: str, feedback: str,
                             idempotency_key: Optional[str] = None) -> Dict:
        """Queue one draft revision and coalesce duplicate active requests per lead."""
        request_key = (idempotency_key or str(uuid.uuid4())).strip()[:100]
        with self.engine.begin() as connection:
            lead = connection.execute(select(leads.c.status).where(leads.c.id == lead_id)).first()
            if not lead:
                return {"created": False, "missing": True}
            if lead.status != LeadStatus.PENDING_APPROVAL.value:
                return {"created": False, "status": lead.status}
            active = connection.execute(select(pipeline_jobs.c.id, pipeline_jobs.c.status)
                .where(and_(pipeline_jobs.c.lead_id == lead_id,
                            pipeline_jobs.c.action == "revise",
                            pipeline_jobs.c.status.in_(["PENDING", "RUNNING"])))
                .order_by(pipeline_jobs.c.created_at.desc()).limit(1)).first()
            if active:
                return {"created": False, "job_id": active.id, "job_status": active.status}
            existing = connection.execute(select(pipeline_jobs.c.id, pipeline_jobs.c.status)
                .where(pipeline_jobs.c.idempotency_key == request_key)).first()
            if existing:
                return {"created": False, "job_id": existing.id, "job_status": existing.status}
            job_id = str(uuid.uuid4())
            connection.execute(pipeline_jobs.insert().values(
                id=job_id, lead_id=lead_id, action="revise",
                idempotency_key=request_key, status="PENDING", progress=0,
                config=json.dumps({"variation": variation, "feedback": feedback}), attempts=0,
            ))
        return {"created": True, "job_id": job_id, "job_status": "PENDING"}

    def insert_lead(self, lead_data: Dict) -> int:
        """Insert a lead for seed/import tooling; return the existing ID on duplicate."""
        email_key = self._email_key(lead_data["email"])
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(leads.c.id).where(func.lower(leads.c.email) == lead_data["email"].strip().lower())
            ).first()
            if existing:
                return existing.id
            return connection.execute(
                leads.insert().values(**self._lead_values(lead_data), idempotency_key=email_key)
                .returning(leads.c.id)
            ).scalar_one()

    def insert_enrichment(self, lead_id: int, data: Dict):
        with self.engine.begin() as connection:
            connection.execute(enrichment.insert().values(
                lead_id=lead_id, company_size=data.get("company_size"),
                persona_tag=data.get("persona_tag"), pain_points=json.dumps(data.get("pain_points", [])),
                buying_triggers=json.dumps(data.get("buying_triggers", [])),
                confidence_score=data.get("confidence_score"), enrichment_mode=data.get("enrichment_mode", "offline"),
            ))

    def insert_message(self, lead_id: int, channel: str, variation: str, content: str,
                       subject: Optional[str] = None, body: Optional[str] = None,
                       html_body: Optional[str] = None, revision: int = 1,
                       review_feedback: Optional[str] = None) -> int:
        with self.engine.begin() as connection:
            return connection.execute(messages.insert().values(
                lead_id=lead_id, channel=channel, variation=variation, content=content,
                subject=subject, body=body, html_body=html_body, revision=revision,
                review_feedback=review_feedback,
            ).returning(messages.c.id)).scalar_one()

    def insert_outreach(self, lead_id: int, message_id: int, channel: str) -> int:
        with self.engine.begin() as connection:
            return connection.execute(outreach.insert().values(
                lead_id=lead_id, message_id=message_id, channel=channel, status="PENDING",
            ).returning(outreach.c.id)).scalar_one()

    def update_lead_status(self, lead_id: int, status: LeadStatus):
        with self.engine.begin() as connection:
            connection.execute(update(leads).where(leads.c.id == lead_id).values(
                status=status.value, updated_at=func.current_timestamp()
            ))

    def update_outreach_status(self, outreach_id: int, status: str,
                               error_message: Optional[str] = None,
                               provider_message_id: Optional[str] = None):
        values = {"status": status, "error_message": error_message}
        if status == "SENT":
            values["sent_at"] = func.current_timestamp()
        if provider_message_id:
            values["provider_message_id"] = provider_message_id
        if status == "FAILED":
            values["retry_count"] = outreach.c.retry_count + 1
        with self.engine.begin() as connection:
            connection.execute(update(outreach).where(outreach.c.id == outreach_id).values(**values))

    def get_latest_outreach_status(self, lead_id: int) -> Optional[str]:
        with self.engine.connect() as connection:
            row = connection.execute(select(outreach.c.status).where(
                outreach.c.lead_id == lead_id
            ).order_by(outreach.c.id.desc()).limit(1)).first()
            return row.status if row else None

    def recover_interrupted_jobs(self):
        """Fail jobs interrupted during a process restart; never blindly resend SMTP."""
        stale_before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        with self.engine.begin() as connection:
            connection.execute(update(pipeline_jobs).where(
                and_(pipeline_jobs.c.status == "RUNNING", pipeline_jobs.c.started_at < stale_before)
            ).values(
                status="FAILED", finished_at=func.current_timestamp(),
                updated_at=func.current_timestamp(),
                error_message="Worker stopped mid-job. Inspect delivery history before retrying.",
            ))

    def update_job(self, job_id: str, status: Optional[str] = None,
                   stage: Optional[str] = None, progress: Optional[int] = None,
                   error_message: Optional[str] = None):
        values = {"updated_at": func.current_timestamp()}
        if status:
            values["status"] = status
            if status == "RUNNING":
                values["started_at"] = func.current_timestamp()
                values["attempts"] = pipeline_jobs.c.attempts + 1
            elif status in {"COMPLETED", "FAILED", "AWAITING_APPROVAL", "SUPPRESSED"}:
                values["finished_at"] = func.current_timestamp()
        if stage is not None:
            values["stage"] = stage
        if progress is not None:
            values["progress"] = progress
        if error_message is not None:
            values["error_message"] = error_message[:2000]
        with self.engine.begin() as connection:
            connection.execute(update(pipeline_jobs).where(pipeline_jobs.c.id == job_id).values(**values))

    def claim_next_job(self) -> Optional[Dict]:
        """Claim one queued job safely across worker processes."""
        with self.engine.begin() as connection:
            query = select(pipeline_jobs).where(pipeline_jobs.c.status == "PENDING").order_by(
                pipeline_jobs.c.created_at, pipeline_jobs.c.id
            ).limit(1)
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            row = connection.execute(query).mappings().first()
            if not row:
                return None
            result = connection.execute(update(pipeline_jobs).where(and_(
                pipeline_jobs.c.id == row["id"], pipeline_jobs.c.status == "PENDING"
            )).values(status="RUNNING", started_at=func.current_timestamp(),
                      attempts=pipeline_jobs.c.attempts + 1,
                      updated_at=func.current_timestamp()))
            if result.rowcount != 1:
                return None
            job = dict(row)
            job["status"] = "RUNNING"
            job["attempts"] = (job.get("attempts") or 0) + 1
            job["config"] = json.loads(job["config"])
            return job

    def get_job(self, job_id: str) -> Optional[Dict]:
        with self.engine.connect() as connection:
            row = connection.execute(select(pipeline_jobs).where(pipeline_jobs.c.id == job_id)).mappings().first()
            if not row:
                return None
            result = dict(row)
            result["config"] = json.loads(result["config"])
            return result

    def get_lead(self, lead_id: int) -> Optional[Dict]:
        with self.engine.connect() as connection:
            row = connection.execute(select(leads).where(leads.c.id == lead_id)).mappings().first()
            return dict(row) if row else None

    def get_lead_by_email(self, email: str) -> Optional[Dict]:
        with self.engine.connect() as connection:
            row = connection.execute(select(leads).where(
                func.lower(leads.c.email) == email.strip().lower()
            ).limit(1)).mappings().first()
            return dict(row) if row else None

    def get_leads_by_status(self, status: Optional[LeadStatus] = None,
                            limit: int = 100, offset: int = 0) -> List[Dict]:
        query = select(leads).order_by(leads.c.created_at.desc(), leads.c.id.desc())
        if status:
            query = query.where(leads.c.status == status.value)
        query = query.limit(max(1, min(limit, 500))).offset(max(0, offset))
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(query).mappings().all()]

    def count_leads(self, status: Optional[LeadStatus] = None) -> int:
        query = select(func.count()).select_from(leads)
        if status:
            query = query.where(leads.c.status == status.value)
        with self.engine.connect() as connection:
            return int(connection.execute(query).scalar_one())

    def get_lead_with_enrichment(self, lead_id: int) -> Optional[Dict]:
        query = select(leads, enrichment.c.persona_tag, enrichment.c.pain_points,
                       enrichment.c.buying_triggers, enrichment.c.confidence_score,
                       enrichment.c.enrichment_mode).select_from(
            leads.outerjoin(enrichment, leads.c.id == enrichment.c.lead_id)
        ).where(leads.c.id == lead_id).order_by(enrichment.c.created_at.desc()).limit(1)
        with self.engine.connect() as connection:
            row = connection.execute(query).mappings().first()
        if not row:
            return None
        result = dict(row)
        for key in ("pain_points", "buying_triggers"):
            try:
                result[key] = json.loads(result[key]) if result.get(key) else []
            except (TypeError, json.JSONDecodeError):
                result[key] = []
        return result

    def get_lead_messages(self, lead_id: int) -> Dict:
        with self.engine.connect() as connection:
            rows = connection.execute(select(messages).where(messages.c.lead_id == lead_id)
                                      .order_by(messages.c.created_at.desc(), messages.c.id.desc())).mappings().all()
        result = {}
        for row in rows:
            key = f"{row['channel']}_{row['variation'].lower()}"
            if key in result:
                continue
            subject, body = row.get("subject"), row.get("body")
            if row["channel"] == "email" and (subject is None or body is None):
                parts = row["content"].split("\n\n", 1)
                subject = parts[0].removeprefix("Subject: ").strip()
                body = parts[1].strip() if len(parts) > 1 else row["content"]
            result[key] = ({"subject": subject, "body": body, "html_body": row.get("html_body"),
                            "revision": row.get("revision", 1),
                            "review_feedback": row.get("review_feedback")}
                           if row["channel"] == "email" else {"message": row["content"]})
        return result

    def get_message_record(self, lead_id: int, channel: str = "email", variation: str = "A") -> Optional[Dict]:
        with self.engine.connect() as connection:
            row = connection.execute(select(messages).where(and_(
                messages.c.lead_id == lead_id, messages.c.channel == channel,
                messages.c.variation == variation,
            )).order_by(messages.c.id.desc()).limit(1)).mappings().first()
            return dict(row) if row else None

    def add_suppression(self, email: str, reason: str, source: str = "manual"):
        normalized = email.strip().lower()
        with self.engine.begin() as connection:
            existing = connection.execute(select(suppression.c.email).where(suppression.c.email == normalized)).first()
            if existing:
                connection.execute(update(suppression).where(suppression.c.email == normalized).values(
                    reason=reason, source=source, created_at=func.current_timestamp()
                ))
            else:
                connection.execute(suppression.insert().values(email=normalized, reason=reason, source=source))

    def is_suppressed(self, email: str) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(select(suppression.c.email).where(
                func.lower(suppression.c.email) == email.strip().lower()
            )).first() is not None

    def get_pipeline_summary(self) -> Dict:
        with self.engine.connect() as connection:
            rows = connection.execute(select(pipeline_jobs.c.status, func.count()).group_by(pipeline_jobs.c.status)).all()
            active = connection.execute(select(pipeline_jobs.c.stage, pipeline_jobs.c.progress)
                .where(pipeline_jobs.c.status == "RUNNING")
                .order_by(pipeline_jobs.c.started_at.desc()).limit(1)).first()
        return {
            "pipeline_running": any(status in {"PENDING", "RUNNING"} and count > 0 for status, count in rows),
            "current_stage": active.stage if active else None,
            "progress": active.progress if active else 0,
            "jobs_by_status": {status: count for status, count in rows},
        }

    def get_metrics(self) -> Dict:
        with self.engine.connect() as connection:
            total = connection.execute(select(func.count()).select_from(leads)).scalar_one()
            status_counts = dict(connection.execute(select(leads.c.status, func.count()).group_by(leads.c.status)).all())
            message_count = connection.execute(select(func.count()).select_from(messages)).scalar_one()
            sent = connection.execute(select(func.count()).select_from(outreach).where(outreach.c.status == "SENT")).scalar_one()
            failed = connection.execute(select(func.count()).select_from(outreach).where(outreach.c.status == "FAILED")).scalar_one()
            active = connection.execute(select(func.count()).select_from(pipeline_jobs).where(
                pipeline_jobs.c.status.in_(["PENDING", "RUNNING"])
            )).scalar_one()
        return {
            "total_leads": int(total),
            "leads_enriched": sum(status_counts.get(s, 0) for s in ("ENRICHED", "MESSAGED", "PENDING_APPROVAL", "SENT")),
            "messages_generated": int(message_count), "messages_sent": int(sent),
            "messages_failed": int(failed), "status_breakdown": status_counts,
            "pipeline_running": active > 0,
        }

    def clear_all_data(self):
        with self.engine.begin() as connection:
            for table in (outreach, messages, enrichment, pipeline_jobs, suppression, leads):
                connection.execute(table.delete())
