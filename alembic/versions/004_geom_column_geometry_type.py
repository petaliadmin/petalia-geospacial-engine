"""S2-4 — Convert fields.geom from Text to PostGIS Geometry + GIST index

The `geom` column was created as Text (WKT string) in the initial schema.
This migration converts it to a native PostGIS geometry(Geometry, 4326)
column and adds a GIST spatial index, enabling:

  - ST_Within, ST_Intersects, ST_DWithin spatial queries
  - Bounding box filtering at the database level
  - Future features: field overlap detection, zone intersection

Existing rows with a valid WKT string are migrated in-place via
ST_GeomFromText. Rows with NULL or invalid geom remain NULL (safe).

Revision ID: 004
Revises: 003
Create Date: 2026-05-18
"""
from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: Add a temporary geometry column
    op.execute("""
        ALTER TABLE fields
        ADD COLUMN geom_new geometry(Geometry, 4326)
    """)

    # Step 2: Migrate existing WKT data (handle SRID= prefix from Shapely)
    op.execute("""
        UPDATE fields
        SET geom_new = CASE
            WHEN geom IS NULL OR geom = '' THEN NULL
            WHEN geom LIKE 'SRID=%' THEN ST_GeomFromEWKT(geom)
            ELSE ST_GeomFromText(geom, 4326)
        END
        WHERE geom IS NOT NULL AND geom != ''
    """)

    # Step 3: Drop old text column and rename new one
    op.execute("ALTER TABLE fields DROP COLUMN geom")
    op.execute("ALTER TABLE fields RENAME COLUMN geom_new TO geom")

    # Step 4: Create GIST spatial index for fast spatial queries
    op.execute("""
        CREATE INDEX ix_fields_geom ON fields USING GIST (geom)
        WHERE geom IS NOT NULL
    """)


def downgrade() -> None:
    import sqlalchemy as sa

    op.execute("DROP INDEX IF EXISTS ix_fields_geom")
    op.execute("ALTER TABLE fields DROP COLUMN IF EXISTS geom")
    # Recreate original text column (data is lost — geom must be re-populated)
    op.add_column("fields", sa.Column("geom", sa.Text, nullable=True))
