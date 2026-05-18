"""S2-1 — Add ndre_mean, savi_mean, evi2_mean columns to vegetation_metrics

New precision agriculture indices:
  - NDRE (B8A - B5) / (B8A + B5): Red-Edge index — detects nitrogen/chlorophyll
    stress 2-3 weeks before NDVI
  - SAVI = 1.5*(NIR-RED)/(NIR+RED+0.5): Soil-Adjusted — corrects for bare soil
    effect in juvenile crop stages
  - EVI2 = 2.5*(NIR-RED)/(NIR+2.4*RED+1): Enhanced VI — avoids NDVI saturation
    on dense canopies (corn, sunflower) without needing the Blue band

All columns are nullable for backward compatibility with existing analyses.

Revision ID: 003
Revises: 002
Create Date: 2026-05-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vegetation_metrics",
        sa.Column("ndre_mean", sa.Float, nullable=True, comment="Red-Edge: nitrogen/chlorophyll stress"),
    )
    op.add_column(
        "vegetation_metrics",
        sa.Column("savi_mean", sa.Float, nullable=True, comment="Soil-Adjusted VI: bare soil correction"),
    )
    op.add_column(
        "vegetation_metrics",
        sa.Column("evi2_mean", sa.Float, nullable=True, comment="Enhanced VI 2-band: dense canopy"),
    )


def downgrade() -> None:
    op.drop_column("vegetation_metrics", "evi2_mean")
    op.drop_column("vegetation_metrics", "savi_mean")
    op.drop_column("vegetation_metrics", "ndre_mean")
