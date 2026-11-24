from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    Family,
    Aluno,
    Turma,
    Activity,
    PerfilUsuario,
    FrequenciaTurma,
    FrequenciaAtividade,
    MovimentacaoTurmaAluno,
)


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_per_page = 300
    list_display = ['responsible_name', 'registration_number', 'status']
    search_fields = ['responsible_name', 'social_name']

    def has_add_permission(self, request):
        # O cadastro é feito na tela integrada, inclusive por superusuários.
        return False

    def has_change_permission(self, request, obj=None):
        # A consulta e as regras de exclusão existentes não são alteradas.
        return False


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_per_page = 300
    search_fields = ['name', 'family__responsible_name']
    list_display = ['name', 'get_frequencia_display', 'birth_date']
    list_filter = ['frequencia_tipo', 'status_lsd']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return {}

    def get_frequencia_display(self, obj):
        if obj.frequencia_tipo == 'diaria':
            return 'Diariamente'
        elif obj.dias_semana:
            dias = ', '.join(obj.dias_semana)
            return f'Dias específicos: {dias}'
        return 'Não definido'

    get_frequencia_display.short_description = 'Frequência'

    fieldsets = (
        ('Dados básicos', {
            'fields': ('name', 'birth_date', 'frequencia_tipo')
        }),
        ('Frequência', {
            'fields': ('dias_semana',),
            'classes': ('collapse',)
        }),
        ('Saúde', {
            'fields': ('health_problem', 'special_need'),
        }),
    )


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_per_page = 300
    search_fields = ['name', 'responsible_name']


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_per_page = 300
    search_fields = ['atividade', 'tipo']


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    extra = 0
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


@admin.register(MovimentacaoTurmaAluno)
class MovimentacaoTurmaAlunoAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'turma_origem', 'turma_destino', 'data', 'motivo')
    search_fields = ('aluno__name', 'motivo')
    list_filter = ('data', 'turma_origem', 'turma_destino')


class CustomUserAdmin(UserAdmin):
    inlines = (PerfilUsuarioInline,)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)
admin.site.register(PerfilUsuario)