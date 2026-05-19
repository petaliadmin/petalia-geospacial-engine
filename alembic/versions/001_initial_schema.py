"""Initial schema — fields, analyses, observations, metrics, alerts

Revision ID: 001
Revises:
Create Date: 2026-05-17 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # fields
    op.create_table(
        "fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(255), nullable=False, unique=True),
        sa.Column("geometry", sa.JSON, nullable=False),
        sa.Column("area_ha", sa.Float, nullable=False),
        sa.Column("geom", sa.Text, nullable=True),  # Stored as WKT, managed by PostGIS
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_fields_external_id", "fields", ["external_id"])

    # analyses
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_metrics", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("algorithm_version", sa.String(20), nullable=False, server_default="1.0.0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analyses_field_id", "analyses", ["field_id"])
    op.create_index("ix_analyses_status", "analyses", ["status"])

    # satellite_observations
    op.create_table(
        "satellite_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.String(50),
            sa.ForeignKey("analyses.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("acquisition_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloud_coverage", sa.Float, nullable=False),
        sa.Column("image_source", sa.String(255), nullable=False),
        sa.Column("scene_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_satellite_observations_analysis_id", "satellite_observations", ["analysis_id"]
    )

    # vegetation_metrics
    op.create_table(
        "vegetation_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.String(50),
            sa.ForeignKey("analyses.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ndvi_mean", sa.Float, nullable=False),
        sa.Column("ndvi_min", sa.Float, nullable=False),
        sa.Column("ndvi_max", sa.Float, nullable=False),
        sa.Column("ndvi_std", sa.Float, nullable=False),
        sa.Column("ndwi_mean", sa.Float, nullable=False),
        sa.Column("variability_index", sa.Float, nullable=False),
        sa.Column("trend", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_vegetation_metrics_analysis_id", "vegetation_metrics", ["analysis_id"]
    )

    # agronomic_alerts
    op.create_table(
        "agronomic_alerts",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id"), nullable=False),
        sa.Column("analysis_id", sa.String(50), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agronomic_alerts_field_id", "agronomic_alerts", ["field_id"])
    op.create_index("ix_agronomic_alerts_analysis_id", "agronomic_alerts", ["analysis_id"])
    op.create_index("ix_agronomic_alerts_severity", "agronomic_alerts", ["severity"])


def downgrade() -> None:
    op.drop_table("agronomic_alerts")
    op.drop_table("vegetation_metrics")
    op.drop_table("satellite_observations")
    op.drop_table("analyses")
    op.drop_table("fields")
