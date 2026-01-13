"""
Funções auxiliares e decorators para controle de permissões
"""
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from AppLSD.models import AppLog
from functools import wraps


def get_tipo_perfil(user):
    """
    Retorna o tipo de perfil do usuário
    """
    if user.is_superuser:
        return 'admin'
    
    perfis = user.perfis.all()
    if perfis.exists():
        return perfis.first().tipo_perfil  # ✅ Campo correto
    
    return None


def usuario_tem_perfil(user, tipo_perfil):
    """
    Verifica se o usuário tem um perfil específico
    
    Args:
        user: Objeto User
        tipo_perfil: String com o tipo de perfil ('coordenacao', 'educadora', etc.)
    
    Returns:
        Boolean
    """
    if user.is_superuser and tipo_perfil == 'admin':
        return True
    
    perfis = user.perfis.all()
    return perfis.filter(tipo_perfil=tipo_perfil).exists()  # ✅ Usando tipo_perfil

def is_coordenacao(user):
    """
    Verifica se o usuário é coordenação
    """
    tipo = get_tipo_perfil(user)
    return tipo == 'coordenacao' or user.is_superuser  # ✅ Sem acento


def is_educadora(user):
    """
    Verifica se o usuário é educadora
    """
    tipo = get_tipo_perfil(user)
    return tipo == 'educadora'

def is_servicosocial(user):
    """
    Verifica se o usuário é serviço social
    """
    tipo = get_tipo_perfil(user)
    return tipo == 'servicosocial'


def coordenacao_required(function):
    """
    Decorator para exigir que o usuário seja coordenação.
    Uso: @coordenacao_required
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if is_coordenacao(request.user):
            return function(request, *args, **kwargs)
        else:
            raise PermissionDenied("Acesso permitido apenas para coordenação.")
    return wrap


def educadora_ou_coordenacao_required(function):
    """
    Decorator para exigir que o usuário seja educadora ou coordenação.
    Uso: @educadora_ou_coordenacao_required
    """
    @wraps(function)
    def wrap(request, *args, **kwargs):
        if is_educadora(request.user) or is_coordenacao(request.user):
            return function(request, *args, **kwargs)
        else:
            raise PermissionDenied("Acesso permitido apenas para educadoras e coordenação.")
    return wrap

def registrar_log(user, objeto, acao, descricao):
    AppLog.objects.create(
        content_type=ContentType.objects.get_for_model(objeto.__class__),
        object_id=objeto.pk,
        objeto=objeto,
        acao=acao,
        descricao=descricao,
        criado_por=user,
    )
