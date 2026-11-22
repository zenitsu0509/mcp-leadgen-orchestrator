"""Track reviewer notes and revision numbers for saved email drafts."""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0002_email_review_revisions"
down_revision = "0001_durable_outreach"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in inspect(op.get_bind()).get_columns("messages")}
    if "revision" not in existing:
        op.add_column("messages", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    if "review_feedback" not in existing:
        op.add_column("messages", sa.Column("review_feedback", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("review_feedback")
        batch.drop_column("revision")
