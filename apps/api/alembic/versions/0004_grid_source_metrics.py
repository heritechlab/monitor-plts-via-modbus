"""Add grid/source metrics decoded from newly identified inverter registers.

Revision ID: 0004_grid_source_metrics
Revises: 0003_device_type
Create Date: 2026-08-21
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_grid_source_metrics"
down_revision = "0003_device_type"
branch_labels = None
depends_on = None

COLUMNS = (
    "grid_active",
    "grid_voltage_v",
    "grid_frequency_hz",
    "inverter_soc_percent",
)


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column("inverter_telemetry", sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    for name in reversed(COLUMNS):
        op.drop_column("inverter_telemetry", name)
