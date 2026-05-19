from src.domain.entities.field import Field

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-1.5, 47.5], [-1.4, 47.5], [-1.4, 47.6], [-1.5, 47.6], [-1.5, 47.5]]],
}


def test_field_create_generates_uuid():
    field = Field.create(external_id="field_001", geometry=GEOMETRY, area_ha=10.5)
    assert field.id is not None
    assert len(field.id) == 36


def test_field_create_sets_attributes():
    field = Field.create(external_id="field_001", geometry=GEOMETRY, area_ha=10.5)
    assert field.external_id == "field_001"
    assert field.geometry == GEOMETRY
    assert field.area_ha == 10.5


def test_field_update_geometry():
    field = Field.create(external_id="field_001", geometry=GEOMETRY, area_ha=10.5)
    original_created_at = field.created_at
    new_geom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    field.update_geometry(new_geom, 20.0)
    assert field.geometry == new_geom
    assert field.area_ha == 20.0
    # updated_at must be >= created_at (can be equal on fast machines in same microsecond)
    assert field.updated_at >= original_created_at
    # geometry and area were actually changed
    assert field.geometry != GEOMETRY
