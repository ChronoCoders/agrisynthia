# -*- coding: utf-8 -*-
from django import forms

from dron_map.models import Projects


class Projects_Form(forms.ModelForm):
    class Meta:
        model = Projects
        fields = "__all__"
