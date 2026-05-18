from enum import StrEnum


class VegetationHealth(StrEnum):
    EXCELLENT = "EXCELLENT"  # NDVI >= 0.6
    GOOD = "GOOD"            # NDVI 0.4–0.6
    MODERATE = "MODERATE"    # NDVI 0.3–0.4
    POOR = "POOR"            # NDVI < 0.3

    @classmethod
    def from_ndvi(cls, ndvi: float) -> "VegetationHealth":
        if ndvi >= 0.6:
            return cls.EXCELLENT
        if ndvi >= 0.4:
            return cls.GOOD
        if ndvi >= 0.3:
            return cls.MODERATE
        return cls.POOR
