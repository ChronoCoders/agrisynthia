# -*- coding: utf-8 -*-
import json

import django.contrib.gis.db.models.fields
from django.db import migrations


def convert_polygon_json_to_geom(apps, schema_editor):
    """Copy [[lng,lat],...] rings from the old JSONField into the new PolygonField."""
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
    Projects = apps.get_model("dron_map", "Projects")
    for project in Projects.objects.exclude(field_polygon_geom__isnull=True):
        try:
            import json as _json
            geom = project.field_polygon_geom
            # geom.coords[0] is the exterior ring as a tuple of (lng, lat) tuples
            ring = [list(c) for c in geom.coords[0]]
            project.field_polygon = ring
            project.save(update_fields=["field_polygon"])
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ("dron_map", "0007_add_field_polygon_satellite_ndvi"),
    ]

    operations = [
        # Step 1: add temporary geometry column (nullable)
        migrations.AddField(
            model_name="projects",
            name="field_polygon_geom",
            field=django.contrib.gis.db.models.fields.PolygonField(
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
