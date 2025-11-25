from AppLSD.models import PerfilUsuario
from django.contrib.auth import get_user_model

User = get_user_model()

# 1. LIMPAR DUPLICATAS
print("===== LIMPANDO PERFIS DUPLICADOS =====")
for user in User.objects.all():
    perfis = user.perfis.all()
    if perfis.count() > 1:
        print(f"⚠️ {user.username} tem {perfis.count()} perfis")
        perfil_principal = perfis.first()
        perfis.exclude(id=perfil_principal.id).delete()
        print(f"✅ Mantido apenas 1 perfil")

# 2. ATUALIZAR PERFIS
print("\n===== ATUALIZANDO PERFIS =====")

# Admin
try:
    admin = User.objects.get(username='admin')
    perfil = admin.perfis.first()
    perfil.tipo_perfil = 'admin'
    perfil.save()
    print(f"✅ admin -> admin")
except:
    print("❌ Erro ao atualizar admin")

# Cristina - Coordenação
try:
    cristina = User.objects.get(username='cristina')
    perfil = cristina.perfis.first()
    perfil.tipo_perfil = 'coordenacao'
    perfil.save()
    print(f"✅ cristina -> coordenacao")
except:
    print("❌ Erro ao atualizar cristina")

# Rafaela - Educadora
try:
    rafaela = User.objects.get(username='rafaela')
    perfil = rafaela.perfis.first()
    perfil.tipo_perfil = 'educadora'
    perfil.save()
    print(f"✅ rafaela -> educadora")
except:
    print("❌ Erro ao atualizar rafaela")

# Marili - Educadora
try:
    marili = User.objects.get(username='marili')
    perfil = marili.perfis.first()
    perfil.tipo_perfil = 'educadora'
    perfil.save()
    print(f"✅ marili -> educadora")
except:
    print("❌ Erro ao atualizar marili")

# Solange - Educadora
try:
    solange = User.objects.get(username='solange')
    perfil = solange.perfis.first()
    perfil.tipo_perfil = 'educadora'
    perfil.save()
    print(f"✅ solange -> educadora")
except:
    print("❌ Erro ao atualizar solange")

# 3. VERIFICAÇÃO FINAL
print("\n===== RESULTADO FINAL =====")
for user in User.objects.all():
    perfil = user.perfis.first()
    if perfil:
        print(f"{user.username}: {perfil.tipo_perfil}")
    else:
        print(f"{user.username}: SEM PERFIL")
