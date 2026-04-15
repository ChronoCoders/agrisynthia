# -*- coding: utf-8 -*-
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


def register(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            logger.info("New user registered: %s", user.username)
            return redirect("/")
        else:
            logger.warning("Registration failed for: %s", request.POST.get("username"))
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})
