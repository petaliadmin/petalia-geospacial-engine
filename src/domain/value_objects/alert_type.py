from enum import StrEnum


class AlertType(StrEnum):
    # Existing
    NDVI_LOW = "NDVI_LOW"
    NDVI_DROP = "NDVI_DROP"
    HIGH_CLOUD_COVER = "HIGH_CLOUD_COVER"
    # S2-2: New agronomic alert types
    WATER_STRESS = "WATER_STRESS"         # NDMI below threshold → irrigation recommended
    NITROGEN_STRESS = "NITROGEN_STRESS"   # NDRE below threshold → foliar analysis recommended
    HIGH_VARIABILITY = "HIGH_VARIABILITY"  # High intra-field heterogeneity → zone mapping
