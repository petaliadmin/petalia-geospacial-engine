from typing import Any

import pyproj
from shapely.geometry import shape
from shapely.ops import transform


def compute_area_hectares(geojson: dict[str, Any]) -> float:
    """Compute area of a GeoJSON geometry in hectares using geodesic projection."""
    geom = shape(geojson)
    wgs84 = pyproj.CRS("EPSG:4326")
    # Use equal-area projection (Mollweide) for accurate area calculation
    equal_area = pyproj.CRS("ESRI:54009")
    project = pyproj.Transformer.from_crs(wgs84, equal_area, always_xy=True).transform
    projected = transform(project, geom)
    area_m2 = projected.area
    return round(area_m2 / 10_000, 4)


def validate_geojson_geometry(geojson: dict[str, Any]) -> None:
    """Validate GeoJSON geometry. Raises ValueError if invalid."""
    if "type" not in geojson:
        raise ValueError("Missing 'type' field in geometry")
    valid_types = {"Point", "MultiPoint", "LineString", "MultiLineString",
                   "Polygon", "MultiPolygon", "GeometryCollection"}
    if geojson["type"] not in valid_types:
        raise ValueError(f"Invalid geometry type: {geojson['type']}")
    try:
        geom = shape(geojson)
        if not geom.is_valid:
            raise ValueError(f"Geometry is not valid: {geom.is_valid_reason}")
    except Exception as exc:
        raise ValueError(str(exc)) from exc


def geojson_to_ee_geometry(geojson: dict[str, Any]) -> dict[str, Any]:
    """Convert GeoJSON dict to Earth Engine geometry dict."""
    return {
        "type": geojson["type"],
        "coordinates": geojson.get("coordinates"),
    }


def bbox_from_geojson(geojson: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) bounding box."""
    geom = shape(geojson)
    return geom.bounds


def centroid_from_geojson(geojson: dict[str, Any]) -> tuple[float, float]:
    """Return (lon, lat) centroid of geometry."""
    geom = shape(geojson)
    centroid = geom.centroid
    return (centroid.x, centroid.y)
