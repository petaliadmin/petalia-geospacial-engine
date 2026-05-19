from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.vegetation_metrics import VegetationMetrics
from src.domain.repositories.metrics_repository import AbstractMetricsRepository
from src.domain.value_objects.vegetation_trend import VegetationTrend
from src.infrastructure.database.models import AnalysisModel, VegetationMetricsModel


class SQLMetricsRepository(AbstractMetricsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_analysis_id(self, analysis_id: str) -> VegetationMetrics | None:
        result = await self._session.execute(
            select(VegetationMetricsModel).where(VegetationMetricsModel.analysis_id == analysis_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_timeseries_for_field(
        self, field_id: str, limit: int = 30
    ) -> list[VegetationMetrics]:
        result = await self._session.execute(
            select(VegetationMetricsModel)
            .join(AnalysisModel, AnalysisModel.id == VegetationMetricsModel.analysis_id)
            .where(AnalysisModel.field_id == field_id)
            .order_by(AnalysisModel.completed_at.desc())
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def save(self, metrics: VegetationMetrics) -> VegetationMetrics:
        model = VegetationMetricsModel(
            id=metrics.id,
            analysis_id=metrics.analysis_id,
            ndvi_mean=metrics.ndvi_mean,
            ndvi_min=metrics.ndvi_min,
            ndvi_max=metrics.ndvi_max,
            ndvi_std=metrics.ndvi_std,
            ndmi_mean=metrics.ndmi_mean,
            ndre_mean=metrics.ndre_mean,
            savi_mean=metrics.savi_mean,
            evi2_mean=metrics.evi2_mean,
            variability_index=metrics.variability_index,
            trend=metrics.trend.value,
            created_at=metrics.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return metrics

    @staticmethod
    def _to_entity(model: VegetationMetricsModel) -> VegetationMetrics:
        return VegetationMetrics(
            id=model.id,
            analysis_id=model.analysis_id,
            ndvi_mean=model.ndvi_mean,
            ndvi_min=model.ndvi_min,
            ndvi_max=model.ndvi_max,
            ndvi_std=model.ndvi_std,
            ndmi_mean=model.ndmi_mean,
            ndre_mean=model.ndre_mean,
            savi_mean=model.savi_mean,
            evi2_mean=model.evi2_mean,
            variability_index=model.variability_index,
            trend=VegetationTrend(model.trend),
            created_at=model.created_at,
        )
