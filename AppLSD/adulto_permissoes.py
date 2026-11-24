"""Politica de criacao/edicao de adultos: Servico Social e Admin."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


def validar_operador_adulto(usuario):
    if (not usuario or not getattr(usuario, 'is_authenticated', False)
            or not getattr(usuario, 'pk', None)):
        raise PermissionDenied('Autenticacao obrigatoria.')
    try:
        atual = get_user_model().objects.get(pk=usuario.pk)
    except get_user_model().DoesNotExist:
        raise PermissionDenied('Operador nao encontrado.') from None
    if not atual.is_active:
        raise PermissionDenied('Usuario inativo.')
    # Mantem superusuario como administrador da instalacao.
    autorizado = atual.is_superuser or atual.perfis.filter(
        tipo_perfil__in=('admin', 'servicosocial')
    ).exists()
    if not autorizado:
        raise PermissionDenied('Criar e editar adultos e permitido somente ao Servico Social e Admin.')
    return atual


def pode_gerenciar_adulto(usuario):
    try:
        validar_operador_adulto(usuario)
    except PermissionDenied:
        return False
    return True
