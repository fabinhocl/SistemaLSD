from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from .models import PerfilUsuario
from AppLSD.models import Family, Aluno, Activity, Turma, AppLog
from AppLSD.utils import registrar_log
from AppLSD.middleware import get_current_user

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        tipo_perfil = 'colaborador' # default
        if instance.is_superuser:
            tipo_perfil = 'admin'
        elif instance.groups.filter(name='Coordenador').exists():
            tipo_perfil = 'coordenador'
        elif instance.groups.filter(name='Serviço Social').exists():
            tipo_perfil  = 'servicosocial'
        elif instance.groups.filter(name='Educadora').exists():
            tipo_perfil = 'educadora'
        elif instance.groups.filter(name='Facilitador').exists():
            tipo_perfil = 'facilitador'
        elif instance.groups.filter(name='Administrativo').exists():
            tipo_perfil = 'administrativo'
        elif instance.groups.filter(name='Financeiro').exists():
            tipo_perfil = 'financeiro'
        elif instance.groups.filter(name='Nutrição').exists():
            tipo_perfil = 'nutricao'
        PerfilUsuario.objects.create(user=instance, tipo_perfil=tipo_perfil)
        print(f'PerfilUsuario ({tipo_perfil}) criado para o usuário {instance.username}')


@receiver(post_save, sender=Family)
def desativar_alunos_ao_desativar_familia(sender, instance, created, update_fields, **kwargs):
    """
    Signal que dispara quando uma Família é salva.
    Se o status mudar para 'inativo', desativa todos os alunos 
    e remove das turmas e atividades.
    """
    
    # ✅ Se a família está sendo criada, ignora
    if created:
        return
    
    # ✅ Se o status NÃO mudou para 'inativo', ignora
    if instance.status != 'inativo':
        return
    
    # ✅ Buscar o usuário que fez a alteração
    usuario = get_current_user()
    
    # Se não tem usuário, usa um usuário padrão (Sistema)
    if not usuario:
        from django.contrib.auth.models import User
        usuario = User.objects.filter(username='system').first()
    
    alunos = Aluno.objects.filter(family=instance)
    
    for aluno in alunos:
        # 1. Remover de todas as atividades
        atividades = Activity.objects.filter(alunos=aluno)
        for atividade in atividades:
            atividade.alunos.remove(aluno)
            
            # ✅ Registrar no histórico da atividade COM MOTIVO
            if usuario:
                registrar_log(
                    usuario,
                    atividade,
                    'aluno_removido_familia_inativa',
                    f'Aluno {aluno.name} removido da atividade "{atividade.atividade}" '
                    f'por inativação da família {instance.responsible_name}. Status alterado para "inativo".'
                )
        
        # 2. Remover da turma
        turma_atual = aluno.turma
        if turma_atual:
            aluno.turma = None
            
            # ✅ Registrar no histórico da turma COM MOTIVO
            if usuario:
                registrar_log(
                    usuario,
                    turma_atual,
                    'aluno_removido_familia_inativa',
                    f'Aluno {aluno.name} removido por inativação da família {instance.responsible_name}. '
                    f'Motivo: Família alterada para status "inativo".'
                )
        
        # 3. Desativar o aluno
        aluno.status_lsd = 'desligado'
        aluno.save()
        
        # ✅ Registrar no histórico do aluno
        if usuario:
            registrar_log(
                usuario,
                aluno,
                'aluno_desligado_familia_inativa',
                f'Aluno desligado. Motivo: Família {instance.responsible_name} inativada pelo usuário {usuario.username}.'
            )
    
    # ✅ Registrar no histórico da FAMÍLIA COM MOTIVO
    if usuario:
        registrar_log(
            usuario,
            instance,
            'familia_inativada',
            f'Família inativada. Motivo: Status alterado para "inativo" pelo usuário {usuario.username}. '
            f'{alunos.count()} aluno(s) desligado(s) e removido(s) de turmas e atividades.'
        )