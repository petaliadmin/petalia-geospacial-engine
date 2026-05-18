from enum import StrEnum


class AlertType(StrEnum):
    NDVI_LOW = "NDVI_LOW"
    NDVI_DROP = "NDVI_DROP"
    HIGH_CLOUD_COVER = "HIGH_CLOUD_COVER"
    WATER_STRESS = "WATER_STRESS"
