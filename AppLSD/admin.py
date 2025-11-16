from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Family, Aluno, Turma, Activity, PerfilUsuario, FrequenciaTurma, FrequenciaAtividade

class FamilyAdmin(admin.ModelAdmin):
    list_per_page = 300  # Define 300 famílias por página no admin
class AlunoAdmin(admin.ModelAdmin):
    list_per_page = 300  # Define 300 alunos por página no admin
    search_fields = ['name', 'family__responsible_name']
class TurmaAdmin(admin.ModelAdmin):
    list_per_page = 300  # Define 300 turmas por página no admin
    search_fields = ['name', 'responsible_name']
class ActivityAdmin(admin.ModelAdmin):
    list_per_page = 300  # Define 300 atividades por página no admin
    search_fields = ['atividade', 'tipo']
class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    extra = 0  # ou 0 para não exibir nenhum por padrão
    min_num = 0
    can_delete = True
    verbose_name_plural = 'Perfil Usuário'

@admin.register(FrequenciaTurma)
class FrequenciaTurmaAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'turma', 'data', 'presente')
    list_filter = ('turma', 'data', 'presente')
    search_fields = ('aluno__name',)

@admin.register(FrequenciaAtividade)
class FrequenciaAtividadeAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'atividade', 'data', 'presente')
    list_filter = ('atividade', 'data', 'presente')
    search_fields = ('aluno__name',)

class CustomUserAdmin(UserAdmin):
    inlines = (PerfilUsuarioInline,)

# Re-registrar o User admin com o inline do perfil
admin.site.unregister(User)
admin.site.register(User, type('UserAdmin', (UserAdmin,), {'inlines': (PerfilUsuarioInline,)}))
admin.site.register(Family, FamilyAdmin)
admin.site.register(Aluno, AlunoAdmin)
admin.site.register(Turma, TurmaAdmin)
admin.site.register(Activity, ActivityAdmin)
