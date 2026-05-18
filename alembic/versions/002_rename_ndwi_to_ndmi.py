"""S1-3 — Rename ndwi_mean → ndmi_mean in vegetation_metrics

(B8 - B11) / (B8 + B11) is the NDMI (Gao 1996, Normalized Difference
Moisture Index), NOT the NDWI (McFeeters 1996, open water detection).
This rename corrects the misleading column name without data loss.

Revision ID: 002
Revises: 001
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "vegetation_metrics",
        "ndwi_mean",
        new_column_name="ndmi_mean",
    )


def downgrade() -> None:
    op.alter_column(
        "vegetation_metrics",
        "ndmi_mean",
        new_column_name="ndwi_mean",
    )
