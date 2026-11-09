from django.core.exceptions import PermissionDenied


PERFIS_ADMIN_GED = {
    'Admin',
    'Administrativo',
    'Diretoria',
}


def usuario_pode_administrar_ged(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    # Ajuste conforme o nome do relacionamento real do seu projeto.
    perfis = getattr(user, 'perfis', None)

    if perfis is None:
        return False

    nomes = perfis.values_list('nome', flat=True)

    return any(nome in PERFIS_ADMIN_GED for nome in nomes)


def exigir_admin_ged(user):
    if not usuario_pode_administrar_ged(user):
        raise PermissionDenied