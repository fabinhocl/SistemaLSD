# events/urls.py
from django.urls import path
from .views import EventListView, EventCreateView, EventUpdateView, EventDetailView, EventDeleteView, RelatorioPresencaResponsaveisView, PersonQuickCreateView, person_quick_success, person_search

app_name = 'events'

urlpatterns = [
    path('', EventListView.as_view(), name='event_list'),
    path('novo/', EventCreateView.as_view(), name='event_create'),
    path('<int:pk>/editar/', EventUpdateView.as_view(), name='event_update'),
    path('<int:pk>/', EventDetailView.as_view(), name='event_detail'),
    path('<int:pk>/deletar/', EventDeleteView.as_view(), name='event_delete'),
    path('pessoas/novo-rapido/', PersonQuickCreateView.as_view(), name='person_quick_create'),
    path('pessoas/novo-rapido/sucesso/', person_quick_success, name='person_quick_success'),
    path('pessoas/buscar/', person_search, name='person_search'),
    path('relatorios/responsaveis/', RelatorioPresencaResponsaveisView.as_view(), name='relatorio_responsaveis'),
]
