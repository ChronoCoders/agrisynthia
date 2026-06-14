from django import template
from django.urls import translate_url

register = template.Library()


@register.simple_tag(takes_context=True)
def alt_url(context, lang_code):
    request = context.get("request")
    if request is None:
        return ""
    return translate_url(request.get_full_path(), lang_code)
