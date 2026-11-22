"""Add scheduled_for to pipeline_jobs and create inbound_events table."""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0003_followup_and_inbound_events"
down_revision = "0002_email_review_revisions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. Add scheduled_for column to pipeline_jobs if missing
    columns = {col["name"] for col in inspector.get_columns("pipeline_jobs")}
    if "scheduled_for" not in columns:
        op.add_column("pipeline_jobs", sa.Column("scheduled_for", sa.DateTime(), nullable=True))

    indices = {idx["name"] for idx in inspector.get_indexes("pipeline_jobs")}
    if "ix_pipeline_jobs_status_scheduled" not in indices:
        op.create_index("ix_pipeline_jobs_status_scheduled", "pipeline_jobs", ["status", "scheduled_for"])

    # 2. Create inbound_events table if missing
    tables = inspector.get_table_names()
    if "inbound_events" not in tables:
        op.create_table(
            "inbound_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("provider_message_id", sa.String(length=500), nullable=True),
            sa.Column("in_reply_to", sa.String(length=500), nullable=True),
            sa.Column("references_header", sa.Text(), nullable=True),
            sa.Column("subject", sa.Text(), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("headers", sa.Text(), nullable=True),
            sa.Column("classified_intent", sa.String(length=150), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        )
        op.create_index("ix_inbound_events_email", "inbound_events", ["email"])
        op.create_index("ix_inbound_events_lead_id", "inbound_events", ["lead_id"])
        op.create_index("ix_inbound_events_event_type", "inbound_events", ["event_type"])


def downgrade():
    op.drop_table("inbound_events")
    with op.batch_alter_table("pipeline_jobs") as batch:
        batch.drop_index("ix_pipeline_jobs_status_scheduled")
        batch.drop_column("scheduled_for")
