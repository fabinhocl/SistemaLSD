def usuario_tem_perfil(user, tipo):
    return hasattr(user, 'perfis') and user.perfis.filter(tipo=tipo).exists()