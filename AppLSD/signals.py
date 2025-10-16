from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Group
from .models import PerfilUsuario

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        tipo = 'colaborador' # default
        if instance.is_superuser:
            tipo = 'admin'
        elif instance.groups.filter(name='Coordenador').exists():
            tipo = 'coordenador'
        elif instance.groups.filter(name='Supervisor').exists():
            tipo = 'supervisor'
        elif instance.groups.filter(name='Professor').exists():
            tipo = 'professor'
        elif instance.groups.filter(name='Administrativo').exists():
            tipo = 'administrativo'
        PerfilUsuario.objects.create(user=instance, tipo=tipo)
        print(f'PerfilUsuario ({tipo}) criado para o usuário {instance.username}')
