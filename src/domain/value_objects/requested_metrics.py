from enum import StrEnum


class RequestedMetric(StrEnum):
    NDVI = "NDVI"
    NDWI = "NDWI"
    CLOUD = "CLOUD"
    TILES = "TILES"
    ALERTS = "ALERTS"
