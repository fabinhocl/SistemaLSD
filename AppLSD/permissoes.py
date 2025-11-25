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
