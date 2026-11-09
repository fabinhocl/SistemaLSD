from django.contrib import admin
from .models import (
    Setor, Categoria, TipoDocumento, CampoMetadado,
    Documento, MetadadoValor, VersaoDocumento, Tag,
    PermissaoSetor, PermissaoCategoria, LogAuditoria
)


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'criado_em']
    list_filter = ['ativo']
    search_fields = ['nome', 'descricao']


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'setor', 'nivel', 'pai', 'ativo']
    list_filter = ['setor', 'ativo', 'nivel']
    search_fields = ['nome', 'descricao']
    ordering = ['setor', 'nivel', 'nome']


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'categoria', 'ativo']
    list_filter = ['categoria', 'ativo']
    search_fields = ['nome', 'descricao']


@admin.register(CampoMetadado)
class CampoMetadadoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo_documento', 'tipo', 'obrigatorio', 'ordem']
    list_filter = ['tipo', 'obrigatorio', 'ativo']
    search_fields = ['nome']
    ordering = ['tipo_documento', 'ordem']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cor']
    search_fields = ['nome']


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = [
        'codigo_registro', 'titulo', 'setor', 'categoria',
        'status', 'nivel_sigilo', 'criado_por', 'criado_em'
    ]
    list_filter = ['setor', 'categoria', 'status', 'nivel_sigilo']
    search_fields = ['titulo', 'codigo_registro', 'descricao']
    date_hierarchy = 'criado_em'
    raw_id_fields = ['criado_por']
    filter_horizontal = ['tags']


@admin.register(MetadadoValor)
class MetadadoValorAdmin(admin.ModelAdmin):
    list_display = ['documento', 'campo', 'get_valor']
    list_filter = ['campo__tipo']
    search_fields = ['documento__titulo', 'valor_texto']

    def get_valor(self, obj):
        return obj.get_valor()
    get_valor.short_description = 'Valor'


@admin.register(VersaoDocumento)
class VersaoDocumentoAdmin(admin.ModelAdmin):
    list_display = [
        'documento', 'numero_versao', 'tamanho',
        'idioma_detectado', 'criado_em'
    ]
    list_filter = ['idioma_detectado']
    search_fields = ['documento__titulo', 'texto_extraido']
    raw_id_fields = ['documento', 'criado_por']


@admin.register(PermissaoSetor)
class PermissaoSetorAdmin(admin.ModelAdmin):
    list_display = ['user', 'setor', 'pode_visualizar', 'pode_editar', 'pode_excluir']
    list_filter = ['pode_visualizar', 'pode_editar', 'pode_excluir']
    search_fields = ['user__username', 'setor__nome']


@admin.register(PermissaoCategoria)
class PermissaoCategoriaAdmin(admin.ModelAdmin):
    list_display = ['user', 'categoria', 'pode_visualizar', 'pode_editar']
    list_filter = ['pode_visualizar', 'pode_editar']
    search_fields = ['user__username', 'categoria__nome']


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ['user', 'documento', 'acao', 'ip', 'criado_em']
    list_filter = ['acao']
    search_fields = ['user__username', 'documento__titulo']
    date_hierarchy = 'criado_em'
    raw_id_fields = ['user', 'documento']
