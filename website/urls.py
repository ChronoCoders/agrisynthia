# -*- coding: utf-8 -*-
from django.urls import path
from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("urun/", views.product, name="product"),
    path("fiyatlandirma/", views.pricing, name="pricing"),
    path("hakkimizda/", views.about, name="about"),
    path("blog/", views.blog, name="blog"),
    path("blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
    path("iletisim/", views.contact, name="contact"),
    path("gizlilik-politikasi/", views.privacy, name="privacy"),
    path("kullanim-kosullari/", views.terms, name="terms"),
    path("kvkk/", views.kvkk, name="kvkk"),
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
]
