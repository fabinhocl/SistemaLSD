"""Politica cadastral de assistidos, independente das operacoes escolares."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


def validar_operador_aluno(usuario, *, criar=False):
    if not usuario or not usuario.is_authenticated or not getattr(usuario, "pk", None):
        raise PermissionDenied("Autenticacao obrigatoria.")
    operador = get_user_model().objects.filter(pk=usuario.pk, is_active=True).first()
    if operador is None:
        raise PermissionDenied("Usuario inativo ou inexistente.")
    permitidos = {"servicosocial", "admin"}
    if not criar:
        permitidos.add("coordenacao")
    if not operador.is_superuser and not operador.perfis.filter(tipo_perfil__in=permitidos).exists():
        raise PermissionDenied("Sem perfil autorizado para esta operacao cadastral de assistidos.")
    return operador
