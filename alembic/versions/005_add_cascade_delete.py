"""S3-5 — Add CASCADE DELETE to all foreign keys

Without CASCADE DELETE, deleting a field leaves orphan rows in:
  analyses, vegetation_metrics, satellite_observations, agronomic_alerts

This migration recreates all foreign keys with ondelete="CASCADE" to
enforce referential integrity and prevent zombie data accumulation.

Cascade chain:
  fields → analyses → satellite_observations
                    → vegetation_metrics
                    → agronomic_alerts (also directly to fields)

Revision ID: 005
Revises: 004
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # analyses.field_id → fields.id CASCADE
    op.drop_constraint("analyses_field_id_fkey", "analyses", type_="foreignkey")
    op.create_foreign_key(
        "analyses_field_id_fkey", "analyses", "fields",
        ["field_id"], ["id"], ondelete="CASCADE",
    )

    # agronomic_alerts.field_id → fields.id CASCADE
    op.drop_constraint("agronomic_alerts_field_id_fkey", "agronomic_alerts", type_="foreignkey")
    op.create_foreign_key(
        "agronomic_alerts_field_id_fkey", "agronomic_alerts", "fields",
        ["field_id"], ["id"], ondelete="CASCADE",
    )

    # agronomic_alerts.analysis_id → analyses.id CASCADE
    op.drop_constraint("agronomic_alerts_analysis_id_fkey", "agronomic_alerts", type_="foreignkey")
    op.create_foreign_key(
        "agronomic_alerts_analysis_id_fkey", "agronomic_alerts", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )

    # satellite_observations.analysis_id → analyses.id CASCADE
    op.drop_constraint(
        "satellite_observations_analysis_id_fkey", "satellite_observations", type_="foreignkey"
    )
    op.create_foreign_key(
        "satellite_observations_analysis_id_fkey", "satellite_observations", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )

    # vegetation_metrics.analysis_id → analyses.id CASCADE
    op.drop_constraint(
        "vegetation_metrics_analysis_id_fkey", "vegetation_metrics", type_="foreignkey"
    )
    op.create_foreign_key(
        "vegetation_metrics_analysis_id_fkey", "vegetation_metrics", "analyses",
        ["analysis_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    # Recreate all FKs without CASCADE (original state)
    op.drop_constraint("vegetation_metrics_analysis_id_fkey", "vegetation_metrics", type_="foreignkey")
    op.create_foreign_key(
        "vegetation_metrics_analysis_id_fkey", "vegetation_metrics", "analyses",
        ["analysis_id"], ["id"],
    )

    op.drop_constraint("satellite_observations_analysis_id_fkey", "satellite_observations", type_="foreignkey")
    op.create_foreign_key(
        "satellite_observations_analysis_id_fkey", "satellite_observations", "analyses",
        ["analysis_id"], ["id"],
    )

    op.drop_constraint("agronomic_alerts_analysis_id_fkey", "agronomic_alerts", type_="foreignkey")
    op.create_foreign_key(
        "agronomic_alerts_analysis_id_fkey", "agronomic_alerts", "analyses",
        ["analysis_id"], ["id"],
    )

    op.drop_constraint("agronomic_alerts_field_id_fkey", "agronomic_alerts", type_="foreignkey")
    op.create_foreign_key(
        "agronomic_alerts_field_id_fkey", "agronomic_alerts", "fields",
        ["field_id"], ["id"],
    )

    op.drop_constraint("analyses_field_id_fkey", "analyses", type_="foreignkey")
    op.create_foreign_key(
        "analyses_field_id_fkey", "analyses", "fields",
        ["field_id"], ["id"],
    )
