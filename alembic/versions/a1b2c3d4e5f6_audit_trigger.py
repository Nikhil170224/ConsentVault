"""append-only trigger on consent_events

Revision ID: a1b2c3d4e5f6
Revises: 6fea9f722727
"""
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "6fea9f722727"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION consent_events_append_only()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'consent_events is append-only: % not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_consent_events_no_update
        BEFORE UPDATE ON consent_events
        FOR EACH ROW EXECUTE FUNCTION consent_events_append_only();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_consent_events_no_delete
        BEFORE DELETE ON consent_events
        FOR EACH ROW EXECUTE FUNCTION consent_events_append_only();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_consent_events_no_delete ON consent_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_consent_events_no_update ON consent_events;")
    op.execute("DROP FUNCTION IF EXISTS consent_events_append_only();")
