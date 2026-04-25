"""Convert orders.status from order_status_enum to TEXT

Reason: SQLAlchemy Column(String) is used in the model (no native PG enum).
This migration converts the existing enum column to plain TEXT so inserts
work without PostgreSQL complaining about unknown enum types.

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-04-25
"""
from alembic import op

revision = '3c4d5e6f7a8b'
down_revision = '2b3c4d5e6f7a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert the enum-typed column to plain TEXT
    op.execute("ALTER TABLE orders ALTER COLUMN status TYPE TEXT USING status::text")
    # Drop the now-unused PostgreSQL enum type
    op.execute("DROP TYPE IF EXISTS order_status_enum")
    op.execute("DROP TYPE IF EXISTS orderstatusenum")


def downgrade() -> None:
    # Recreate the enum type and cast back (best-effort)
    op.execute("""
        CREATE TYPE order_status_enum AS ENUM (
            'PENDING','CONFIRMED','PREPARING','READY',
            'OUT_FOR_DELIVERY','DELIVERED','CANCELLED','PAYMENT_FAILED'
        )
    """)
    op.execute(
        "ALTER TABLE orders ALTER COLUMN status TYPE order_status_enum "
        "USING status::order_status_enum"
    )
