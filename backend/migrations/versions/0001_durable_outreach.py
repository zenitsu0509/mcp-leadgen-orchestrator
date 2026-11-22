"""Add durable jobs, email audit fields, suppression, and idempotency."""

from alembic import op
from sqlalchemy import inspect, text

from database import metadata

revision = "0001_durable_outreach"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("leads"):
        metadata.create_all(bind)
    else:
        additive = {
            "leads": {
                "interest_area": "TEXT", "challenge": "TEXT", "company_size": "VARCHAR(100)",
                "idempotency_key": "VARCHAR(64)",
            },
            "messages": {"subject": "TEXT", "body": "TEXT", "html_body": "TEXT"},
            "outreach": {"provider_message_id": "VARCHAR(500)"},
        }
        for table, columns in additive.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    op.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}')

        # These are new tables, so create_all is safe after additive columns exist.
        metadata.create_all(bind)
        rows = bind.execute(text('SELECT id FROM "leads" WHERE idempotency_key IS NULL')).fetchall()
        for row in rows:
            bind.execute(
                text('UPDATE "leads" SET idempotency_key = :key WHERE id = :id'),
                {"key": f"legacy-{row[0]}", "id": row[0]},
            )

    op.create_index(
        "uq_leads_idempotency_key", "leads", ["idempotency_key"],
        unique=True, if_not_exists=True,
    )


def downgrade():
    # Data-safe downgrade is intentionally manual; dropping audit/job tables loses history.
    raise RuntimeError("This migration is irreversible because it contains delivery audit history")
