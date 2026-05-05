"""
Funções auxiliares e decorators para controle de permissões
"""
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from functools import wraps


PERFIL_TO_GROUP = {
    'admin': 'Admin',
    'coordenacao': 'Coordenação',
    'servicosocial': 'Serviço Social',
    'educadora': 'Educadora',
    'facilitador': 'Facilitador',
    'administrativo': 'Administrativo',
    'diretoria': 'Diretoria',
    'colaborador': 'Colaborador',
    'financeiro': 'Financeiro',
    'nutricao': 'Nutrição',
}

# perfis válidos (em vez de lista “na mão”)
TIPOS_PERFIL_VALIDOS = list(PERFIL_TO_GROUP.keys())

def sincronizar_grupos_usuario(usuario):
    from AppLSD.models import PerfilUsuario
    # remove de todos os grupos gerenciados
    for _, nome_grupo in PERFIL_TO_GROUP.items():
        try:
            grp = Group.objects.get(name=nome_grupo)
            usuario.groups.remove(grp)
        except Group.DoesNotExist:
            continue

    # adiciona grupos conforme perfis atuais
    tipos = PerfilUsuario.objects.filter(user=usuario).values_list('tipo_perfil', flat=True)
    for tipo in tipos:
        nome_grupo = PERFIL_TO_GROUP.get(tipo)
        if nome_grupo:
            grp, _ = Group.objects.get_or_create(name=nome_grupo)
            usuario.groups.add(grp)


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
    from AppLSD.models import AppLog
    AppLog.objects.create(
        content_type=ContentType.objects.get_for_model(objeto.__class__),
        object_id=objeto.pk,
        objeto=objeto,
        acao=acao,
        descricao=descricao,
        criado_por=user,
    )


def pode_editar_frequencia_turma(user, turma):
    """
    Coordenação pode editar qualquer frequência.
    Educadora pode editar frequência apenas da própria turma.
    """
    if is_coordenacao(user):
        return True

    if is_educadora(user) and turma.educadora == user:
        return True

    return False