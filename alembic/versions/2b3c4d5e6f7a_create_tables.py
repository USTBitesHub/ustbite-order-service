"""create_order_tables

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-04-25 00:00:00
"""
from alembic import op

revision = '2b3c4d5e6f7a'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asyncpg requires ONE statement per op.execute() call

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE order_status_enum AS ENUM (
                'PENDING', 'CONFIRMED', 'PREPARING', 'READY',
                'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'PAYMENT_FAILED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            restaurant_id UUID NOT NULL,
            restaurant_name_snapshot VARCHAR NOT NULL,
            status order_status_enum DEFAULT 'PENDING',
            total_amount NUMERIC(10,2) NOT NULL,
            delivery_floor VARCHAR,
            delivery_wing VARCHAR,
            special_instructions VARCHAR,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_orders_user_id ON orders(user_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            menu_item_id UUID NOT NULL,
            item_name_snapshot VARCHAR NOT NULL,
            item_price_snapshot NUMERIC(10,2) NOT NULL,
            quantity INTEGER NOT NULL,
            subtotal NUMERIC(10,2) NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS order_items CASCADE")
    op.execute("DROP TABLE IF EXISTS orders CASCADE")
    op.execute("DROP TYPE IF EXISTS order_status_enum")
