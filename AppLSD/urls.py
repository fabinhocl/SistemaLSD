from rest_framework.routers import DefaultRouter
from AppLSD.views import FamilyViewSet, AlunoViewSet, TurmaViewSet, ActivityViewSet, FamilyAutocomplete 
from .import views_templates # importa as views para templates
from .import views
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from dal import autocomplete



router = DefaultRouter()
router.register(r'families', FamilyViewSet)
router.register(r'aluno', AlunoViewSet)
router.register(r'turmas', TurmaViewSet)
router.register(r'activities', ActivityViewSet)
#AppLSD/urls.py
urlpatterns = [
        
    # rotas para views com templates (front-end simples)
    path('', views_templates.root_redirect, name='root_redirect'),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('home/', views_templates.home, name='home'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('dashboard/', include('dashboard_lsd.urls')), # dashboard integrado
    path('events/', include('events.urls', namespace='events')),
    path('assistencia/', views_templates.home_assist, name='home_assist'),
    #path('assistencia/', views_templates.dashboard_assist, name='dashboard_assist'),
    path('escola/', views_templates.home_escola, name='home_escola'),
    path('diretoria/', views_templates.home_diretoria, name='home_diretoria'),
    path('administracao/', views_templates.home_adm, name='home_adm'),
    #path('events/', views.EventListView.as_view(), name='event_list'),    
    
    #Famílias
    path('families/', views_templates.family_list, name='family_list'),
    path('families/new/', views_templates.family_create, name='family_create'),
    path('families/edit/<int:pk>/', views_templates.family_edit, name='family_edit'),
    #path('families/delete/<int:pk>/', views_templates.family_delete, name='family_delete'),
    path('families/<int:pk>/', views_templates.family_detail, name='family_detail'),
    path('families/<int:pk>/delete/', views_templates.family_delete_confirm, name='family_delete_confirm'),
    path('families/buscar_family/', views_templates.buscar_family, name='buscar_family'),
    path('families/<int:pk>/termo/', views_templates.family_term_pdf, name='family_term_pdf'),
    path("families/<int:pk>/upload-documento/", views_templates.upload_documento, name="upload_documento"),
    
    #Adultos
    path('adults/', views_templates.adult_list, name='adult_list'),
    path('adult/new/', views_templates.adult_create, name='adult_create'),
    path('adult/edit/<int:pk>/', views_templates.adult_edit, name='adult_edit'),
    path('adult/delete/<int:pk>/', views_templates.adult_delete_confirm, name='adult_delete_confirm'),
    path('adult/<int:pk>/', views_templates.adult_detail, name='adult_detail'),
    
    #Alunos/assistidos
    path('alunos/', views_templates.aluno_list, name='aluno_list'),  # criar essa view para listar
    path('alunos/new/', views_templates.aluno_create, name='aluno_create'),
    path('alunos/edit/<int:pk>/', views_templates.aluno_edit, name='aluno_edit'),
    path('alunos/delete/<int:pk>/', views_templates.aluno_delete_confirm, name='aluno_delete_confirm'),
    path('alunos/<int:pk>/', views_templates.aluno_detail, name='aluno_detail'),
    path('alunos/<int:aluno_id>/mover/', views_templates.mover_aluno, name='mover_aluno'),
    path('alunos/<int:aluno_id>/ocorrencia/', views_templates.adicionar_ocorrencia, name='adicionar_ocorrencia'),
    path('atividades/<int:activity_id>/remover-aluno/<int:aluno_id>/', views_templates.remover_aluno_da_atividade, name='remover_aluno_da_atividade'),
    path('alunos/<int:aluno_id>/remover-da-atividade/<int:activity_id>/', views_templates.remover_aluno_da_atividade_por_aluno, name='remover_aluno_por_aluno'),


    #Turmas
    path('turma/', views_templates.TurmaListView.as_view(), name='turma_list'),
    path('turma/new/', views_templates.turma_create, name='turma_create'),
    path('turma/edit/<int:pk>/', views_templates.turma_edit, name='turma_edit'),
    path('turma/delete/<int:pk>/', views_templates.turma_delete, name='turma_delete'),
    path('turma/<int:turma_id>/', views_templates.turma_detail, name='turma_detail'),
    path('turmas/<int:turma_id>/adicionar-alunos/', views_templates.turma_add_alunos, name='turma_add_alunos'),
    path('turma/<int:turma_id>/relatorio-presenca/', views_templates.relatorio_presenca_turma, name='relatorio_presenca_turma'),

    #Atividades
    path('activities/', views_templates.activity_list, name='activity_list'),
    path('activities/new/', views_templates.activity_create, name='activity_create'),
    path('activities/edit/<int:pk>/', views_templates.activity_edit, name='activity_edit'),
    path('activities/delete/<int:pk>/', views_templates.activity_delete, name='activity_delete'),
    path('activities/<int:activity_id>/', views_templates.activity_detail, name='activity_detail'),
    path('activities/<int:activity_id>/adicionar-alunos/', views_templates.activity_add_alunos, name='activity_add_alunos'),
    path('activities/<int:activity_id>/relatorio-presenca/', views_templates.relatorio_presenca_activity, name='relatorio_presenca_activity'),
    
    path('family-autocomplete/', views.FamilyAutocomplete.as_view(), name='family-autocomplete'),
    path('educadora/turmas/', views_templates.home_educadora, name='home_educadora'),
    path('educadora/dashboard/', views_templates.dashboard_presenca, name='dashboard_presenca'),
    path('facilitador/atividades/', views_templates.home_facilitador, name='home_facilitador'),
    path('facilitador/dashboard/', views_templates.dashboard_presenca, name='dashboard_presenca'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/presenca/', views_templates.dashboard_presenca, name='dashboard_presenca'),

    #Gerenciamento de Usuários (Admin)
    path('usuarios/gerenciar/', views_templates.usuarios_gerenciar, name='usuarios_gerenciar'),
    path('usuarios/cadastrar/', views_templates.cadastrar_usuario, name='cadastrar_usuario'),
    path('usuarios/editar/<int:usuario_id>/', views_templates.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:usuario_id>/editar_perfis/', views_templates.editar_perfis_usuario, name='editar_perfis_usuario'),
    path('usuarios/<int:usuario_id>/resetar_senha/', views_templates.resetar_senha_usuario, name='resetar_senha_usuario'),
    
    #Frequência de Turmas e Atividades
    path('frequencia/turma/<int:turma_id>/', views_templates.iniciar_frequencia_turma, name='frequencia_turma_iniciar'),
    path('frequencia/<int:frequencia_id>/editar/', views_templates.editar_frequencia_turma, name='frequencia_editar'),
    path('frequencia/<int:frequencia_id>/visualizar/', views_templates.visualizar_frequencia_turma, name='frequencia_visualizar'),
    path('frequencia/activity/<int:activity_id>/', views_templates.iniciar_frequencia_activity, name='frequencia_activity_iniciar'),
    path('frequencia/activity/<int:activity_id>/editar/', views_templates.editar_frequencia_activity, name='frequencia_activity_editar'),
    path('frequencia/activity/<int:activity_id>/visualizar/', views_templates.visualizar_frequencia_activity, name='frequencia_activity_visualizar'),
    
    #Relatórios
    path('relatorios/', views_templates.dashboard_completo, name='home_relatorios'),
    path('relatorio/aluno/grafico/', views_templates.relatorio_grafico_mensal_aluno, name='relatorio_grafico_mensal_aluno'),
    path('relatorio/aluno/export_excel/', views_templates.exportar_frequencia_mensal_aluno_excel, name='exportar_frequencia_mensal_aluno_excel'),
    path('relatorio/aluno/mensal/', views_templates.relatorio_mensal_aluno, name='relatorio_mensal_aluno'),
    path('relatorio/aluno/busca/', views_templates.relatorio_busca_aluno, name='relatorio_busca_aluno'),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    path('families/export/', views_templates.export_family_excel, name='export_family_excel'),
    path('alunos/export/', views_templates.export_aluno_excel, name='export_aluno_excel'),
    path('adults/export/', views_templates.export_adult_excel, name='export_adult_excel'),

    
    
   #path('families/autocomplete/', views_templates.family_autocomplete, name="family_autocomplete"),


    # se desejar, adicione outras rotas para Child, Turma e Activity em views_templates.py aqui
    
    path('api/', include(router.urls)),  # rotas da API REST prefixadas com api/
    path('django_plotly_dash/', include('django_plotly_dash.urls')),   # necessário para Dash funcionar
    #path('', include('AppLSD.urls')),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
