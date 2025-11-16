# AppLSD/templatetags/perfil_tags.py
from django import template

register = template.Library()

@register.filter
def has_perfil(user, tipo):
    """
    Uso: {% if user|has_perfil:"admin" %}
    """
    return hasattr(user, 'perfis') and user.perfis.filter(tipo=tipo).exists()

"""@register.filter
def perfil_count(user, tipo):
    """
"""Uso: {{ user|perfil_count:"admin" }}
    """
""" if hasattr(user, 'perfis'):
        return user.perfis.filter(tipo=tipo).count()
    return 0  """