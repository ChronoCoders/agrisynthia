# -*- coding: utf-8 -*-
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Projects


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer for drone mapping projects"""

    picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Projects
        fields = [
            "id",
            "Farm",
            "Field",
            "Title",
            "State",
            "Data_time",
            "picture",
            "picture_url",
            "hashing_path",
        ]
        read_only_fields = ["id", "Data_time", "hashing_path"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_picture_url(self, obj) -> str | None:
        """Get full URL for project picture"""
        if obj.picture:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.picture.url)
        return None

    def validate_Farm(self, value):
        """Ensure farm name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Farm name cannot be empty")
        return value.strip()

    def validate_Field(self, value):
        """Ensure field name is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Field name cannot be empty")
        return value.strip()


class ProjectSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for project listings"""

    class Meta:
        model = Projects
        fields = ["id", "Farm", "Field", "Title", "State", "Data_time"]
