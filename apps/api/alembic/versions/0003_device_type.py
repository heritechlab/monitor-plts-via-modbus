"""Add device_type to devices, so the web UI can list/select multiple BMS devices.

Revision ID: 0003_device_type
Revises: 0002_bms_telemetry
Create Date: 2026-08-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_device_type"
down_revision = "0002_bms_telemetry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "device_type", sa.String(length=20), nullable=False, server_default="inverter"
        ),
    )
    op.execute(
        "UPDATE devices SET device_type = 'bms' WHERE slug LIKE '%-bms'"
    )


def downgrade() -> None:
    op.drop_column("devices", "device_type")
