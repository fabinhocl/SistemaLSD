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


