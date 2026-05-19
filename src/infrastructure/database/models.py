import uuid
from datetime import datetime

from geoalchemy2 import Geometry as GeoAlchemyGeometry
from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FieldModel(Base):
    __tablename__ = "fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    geometry: Mapped[dict] = mapped_column(JSON, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    # S2-4: geom is the native PostGIS geometry — populated by field_repository_impl.
    geom: Mapped[str | None] = mapped_column(
        GeoAlchemyGeometry("GEOMETRY", srid=4326), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    analyses: Mapped[list["AnalysisModel"]] = relationship(
        "AnalysisModel", back_populates="field", lazy="noload"
    )
    alerts: Mapped[list["AgronomicAlertModel"]] = relationship(
        "AgronomicAlertModel", back_populates="field", lazy="noload"
    )


class AnalysisModel(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    field_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    requested_metrics: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False, default="2.0.0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    field: Mapped["FieldModel"] = relationship("FieldModel", back_populates="analyses")
    observation: Mapped["SatelliteObservationModel | None"] = relationship(
        "SatelliteObservationModel", back_populates="analysis", uselist=False, lazy="noload"
    )
    metrics: Mapped["VegetationMetricsModel | None"] = relationship(
        "VegetationMetricsModel", back_populates="analysis", uselist=False, lazy="noload"
    )
    alerts: Mapped[list["AgronomicAlertModel"]] = relationship(
        "AgronomicAlertModel", back_populates="analysis", lazy="noload"
    )


class SatelliteObservationModel(Base):
    __tablename__ = "satellite_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    acquisition_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cloud_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    image_source: Mapped[str] = mapped_column(String(255), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped["AnalysisModel"] = relationship("AnalysisModel", back_populates="observation")


class VegetationMetricsModel(Base):
    __tablename__ = "vegetation_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ndvi_mean: Mapped[float] = mapped_column(Float, nullable=False)
    ndvi_min: Mapped[float] = mapped_column(Float, nullable=False)
    ndvi_max: Mapped[float] = mapped_column(Float, nullable=False)
    ndvi_std: Mapped[float] = mapped_column(Float, nullable=False)
    # S1-3: Renamed from ndwi_mean — formula (B8-B11)/(B8+B11) = NDMI, not NDWI
    ndmi_mean: Mapped[float] = mapped_column(Float, nullable=False)
    # S2-1: New precision agriculture indices — nullable for backward compat
    ndre_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    savi_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    evi2_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    variability_index: Mapped[float] = mapped_column(Float, nullable=False)
    trend: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped["AnalysisModel"] = relationship("AnalysisModel", back_populates="metrics")


class AgronomicAlertModel(Base):
    __tablename__ = "agronomic_alerts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    field_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    field: Mapped["FieldModel"] = relationship("FieldModel", back_populates="alerts")
    analysis: Mapped["AnalysisModel"] = relationship("AnalysisModel", back_populates="alerts")
