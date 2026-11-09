"""
Arquivo permissoes.py
Funções auxiliares e decorators para controle de permissões
"""
from functools import wraps
from django.http import HttpResponseForbidden

def require_perfil(perfil_tipo):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Não autenticado.")
            if not request.user.perfis.filter(tipo_perfil=perfil_tipo).exists():
                return HttpResponseForbidden("Você não possui permissão para esta página.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def require_any_perfil(*perfis_permitidos):
    """
    Permite acesso quando o usuário possui ao menos um dos perfis informados.

    Exemplo:
    @require_any_perfil('admin', 'administrativo', 'diretoria')
    def minha_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden('Não autenticado.')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            possui_perfil = request.user.perfis.filter(
                tipo_perfil__in=perfis_permitidos
            ).exists()

            if not possui_perfil:
                return HttpResponseForbidden(
                    'Você não possui permissão para esta página.'
                )

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
