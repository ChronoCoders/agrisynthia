from django.urls import path
from django.utils.translation import gettext_lazy as _

from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path(_("urun/"), views.product, name="product"),
    path(_("fiyatlandirma/"), views.pricing, name="pricing"),
    path(_("hakkimizda/"), views.about, name="about"),
    path(_("blog/"), views.blog, name="blog"),
    path(_("blog/<slug:slug>/"), views.blog_detail, name="blog_detail"),
    path(_("iletisim/"), views.contact, name="contact"),
    path(_("gizlilik-politikasi/"), views.privacy, name="privacy"),
    path(_("kullanim-kosullari/"), views.terms, name="terms"),
    path(_("kvkk/"), views.kvkk, name="kvkk"),
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
    path("chat/", views.chatbot_chat, name="chatbot_chat"),
    path("chat/lead/", views.chat_lead, name="chat_lead"),
]
