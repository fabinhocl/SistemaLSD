from django.urls import path
from .import views

app_name = 'ged'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('administracao/', views.administracao_ged, name='administracao_ged'),
    path('administracao/setores/', views.lista_setores_admin, name='lista_setores_admin'),
    path('administracao/setores/novo/', views.criar_setor, name='criar_setor'),
    path('documentos/', views.lista_documentos, name='lista_documentos'),
    path('documentos/novo/', views.criar_documento, name='criar_documento'),
    path('documentos/<int:pk>/', views.detalhe_documento, name='detalhe_documento'),
    path('documentos/<int:pk>/editar/', views.editar_documento, name='editar_documento'),
    path('documentos/<int:pk>/upload/', views.upload_versao, name='upload_versao'),
    path('versoes/<int:versao_pk>/baixar/', views.baixar_documento, name='baixar_documento'),
    path('setores/', views.lista_setores, name='lista_setores'),
    path('setores/<int:setor_pk>/categorias/', views.lista_categorias, name='lista_categorias'),
    path('configuracao/setores/', views.configurar_setores, name='configurar_setores'),
    path('configuracao/setores/novo/', views.criar_setor, name='criar_setor'),
    path('configuracao/setores/<int:pk>/editar/', views.editar_setor, name='editar_setor'),
    path('configuracao/categorias/', views.configurar_categorias, name='configurar_categorias'),
    path('configuracao/categorias/novo/', views.criar_categoria, name='criar_categoria'),
    path('configuracao/categorias/<int:pk>/editar/', views.editar_categoria, name='editar_categoria'),
    path('configuracao/tipos-documento/', views.configurar_tipos_documento, name='configurar_tipos_documento'),
    path('configuracao/tipos-documento/novo/', views.criar_tipo_documento, name='criar_tipo_documento'),
    path('configuracao/tipos-documento/<int:pk>/editar/', views.editar_tipo_documento, name='editar_tipo_documento'),
    path('configuracao/campos-metadado/', views.configurar_campos_metadado, name='configurar_campos_metadado'),
    path('configuracao/campos-metadado/novo/', views.criar_campo_metadado, name='criar_campo_metadado'),
    path('configuracao/campos-metadado/<int:pk>/editar/', views.editar_campo_metadado, name='editar_campo_metadado'),
    path('configuracao/', views.configuracao_dashboard, name='configuracao_dashboard'),
    path('ajax/categorias-por-setor/', views.categorias_por_setor, name='categorias_por_setor'),
    path('ajax/tipos-por-categoria/', views.tipos_por_categoria, name='tipos_por_categoria'),
]
