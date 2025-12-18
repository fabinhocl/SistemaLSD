from django import template
from AppLSD.models import PerfilUsuario

register = template.Library()

@register.filter
def is_admin(user):
    """
    Verifica se o usuário é administrador
    """
    if user.is_superuser:
        return True
    
    return PerfilUsuario.objects.filter(
        user=user,
        tipo_perfil='admin'
    ).exists()
