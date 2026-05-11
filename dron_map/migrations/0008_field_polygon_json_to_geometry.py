# -*- coding: utf-8 -*-
# This migration converts field_polygon from JSONField to PostGIS PolygonField.
# It only executes when GEODJANGO_ENABLED=True (GDAL available on the host).
# On systems without GDAL (e.g. Windows dev), it is registered as a no-op so
# the migration history stays consistent. The actual schema change happens on the
# first deploy to a PostGIS-enabled environment.
import json
import os

from django.db import migrations

_GEODJANGO_ENABLED = os.environ.get("GEODJANGO_ENABLED", "True") == "True"

# Guard the GDAL-dependent import — loading this module must not crash on systems
# where GDAL is not installed.
if _GEODJANGO_ENABLED:
    try:
        import django.contrib.gis.db.models.fields as _gis_fields
    except Exception:
        _GEODJANGO_ENABLED = False


def convert_polygon_json_to_geom(apps, schema_editor):
    """Copy [[lng,lat],...] rings from the old JSONField into the new PolygonField."""
    if not _GEODJANGO_ENABLED:
        return

    from django.contrib.gis.geos import GEOSGeometry

    Projects = apps.get_model("dron_map", "Projects")
    for project in Projects.objects.exclude(field_polygon__isnull=True):
        ring = project.field_polygon
        if not ring or not isinstance(ring, list):
            continue
        try:
            geojson = json.dumps({"type": "Polygon", "coordinates": [ring]})
            project.field_polygon_geom = GEOSGeometry(geojson, srid=4326)
            project.save(update_fields=["field_polygon_geom"])
        except Exception:
            pass


def reverse_geom_to_json(apps, schema_editor):
    """Reverse: copy coordinates back from PolygonField into a JSONField ring."""
    if not _GEODJANGO_ENABLED:
        return

    Projects = apps.get_model("dron_map", "Projects")
    for project in Projects.objects.exclude(field_polygon_geom__isnull=True):
        try:
            geom = project.field_polygon_geom
            ring = [list(c) for c in geom.coords[0]]
            project.field_polygon = ring
            project.save(update_fields=["field_polygon"])
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ("dron_map", "0007_add_field_polygon_satellite_ndvi"),
    ]

    if _GEODJANGO_ENABLED:
        operations = [
            # Step 1: add temporary geometry column (nullable)
            migrations.AddField(
                model_name="projects",
                name="field_polygon_geom",
                field=_gis_fields.PolygonField(
                    blank=True,
                    null=True,
                    srid=4326,
                    help_text="WGS-84 polygon defining the field boundary",
                ),
            ),
            # Step 2: populate geometry column from JSON ring data
            migrations.RunPython(
                convert_polygon_json_to_geom,
                reverse_code=reverse_geom_to_json,
            ),
            # Step 3: remove the old JSONField
            migrations.RemoveField(
                model_name="projects",
                name="field_polygon",
            ),
            # Step 4: rename geometry column to the canonical name
            migrations.RenameField(
                model_name="projects",
                old_name="field_polygon_geom",
                new_name="field_polygon",
            ),
        ]
    else:
        # No-op on systems without GDAL — keeps migration history consistent.
        # On first PostGIS deploy, ensure this runs against a DB at migration 0007.
        operations = []
