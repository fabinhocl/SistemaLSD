# events/views.py
from django.contrib.auth import authenticate
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DetailView, ListView, TemplateView, DeleteView
from django.views.decorators.http import require_GET
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse, HttpResponse
from django.utils.html import escape
from requests import request
from AppLSD.models import Person

from .models import Event, EventParticipant
from .forms import EventForm, EventParticipantFormSet, PersonQuickForm


class EventCreateView(CreateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:event_list')  # ajuste para sua URL

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['participants_formset'] = EventParticipantFormSet(
                self.request.POST,
                instance=self.object if hasattr(self, 'object') else None,
            )
        else:
            context['participants_formset'] = EventParticipantFormSet(
                instance=self.object if hasattr(self, 'object') else None,
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        participants_formset = context['participants_formset']
        with transaction.atomic():
            self.object = form.save()

            # se for o evento mensal de responsáveis, pré-cria os participantes
            if self.object.event_type == 'RESPONSAVEIS':
                responsaveis = Person.objects.filter(
                    families_responsible__isnull=False
                ).distinct()
                for person in responsaveis:
                    EventParticipant.objects.get_or_create(
                        event=self.object,
                        person=person,
                        defaults={
                            'role': 'RESPONSAVEL',
                            'attendance_status': 'INSCRITO',
                            'group_label': 'Responsável',
                        },
                    )

            if participants_formset.is_valid():
                participants_formset.instance = self.object
                participants_formset.save()
            else:
                return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)


class EventUpdateView(UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('events:event_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            context["participants_formset"] = EventParticipantFormSet(
                self.request.POST,
                instance=self.object,
                prefix="participants",
            )
        else:
            context["participants_formset"] = EventParticipantFormSet(
                instance=self.object,
                prefix="participants",
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        participants_formset = context["participants_formset"]

        if participants_formset.is_valid():
            self.object = form.save()
            participants_formset.instance = self.object
            participants_formset.save()
            return redirect(self.get_success_url())
    
        return self.form_invalid(form)


class EventListView(ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'
    ordering = ['-date']


class EventDetailView(DetailView):
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'

class EventDeleteView(DeleteView):
    model = Event
    template_name = 'events/event_delete.html'
    context_object_name = 'event'
    success_url = reverse_lazy('events:event_list')
    
    def test_func(self):
        """
        Verifica se o usuário é administrador
        """
        # Verifica se é superuser
        if self.request.user.is_superuser:
            return True
        
        # Verifica se tem perfil de admin
        from AppLSD.models import PerfilUsuario
        return PerfilUsuario.objects.filter(
            user=self.request.user,
            tipo_perfil='admin'
        ).exists()
    
    def handle_no_permission(self):
        """
        Chamado quando test_func retorna False
        """
        messages.error(
            self.request, 
            'Você não tem permissão para excluir eventos. Apenas administradores podem realizar esta ação.'
        )
        return redirect('events:event_list')
    
    def get(self, request, *args, **kwargs):
        """
        Exibe o formulário de confirmação com senha
        """
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
    
    def post(self, request, *args, **kwargs):
        """
        Processa a exclusão com validação de senha
        """
        self.object = self.get_object()
        senha = request.POST.get('senha', '').strip()
        
        # Valida se a senha foi fornecida
        if not senha:
            messages.error(request, 'Por favor, digite sua senha para confirmar a exclusão.')
            return render(request, self.template_name, {
                'event': self.object,
                'error': 'Senha é obrigatória.',
            })
        
        # Autentica o usuário
        usuario = request.user
        user_autenticado = authenticate(username=usuario.username, password=senha)
        
        if user_autenticado is not None:
            # Salva informações antes de deletar
            event_title = self.object.title
            event_date = self.object.date
            
            # Registra log antes de deletar (opcional)
            from AppLSD.utils import registrar_log
            registrar_log(
                request.user,
                self.object,
                'evento_excluido',
                f'Evento "{event_title}" de {event_date} foi excluído pelo administrador {request.user.get_full_name() or request.user.username}.'
            )
            
            # Deleta o evento
            self.object.delete()
            
            # Mensagem de sucesso
            messages.success(
                request, 
                f'Evento "{event_title}" foi excluído com sucesso!'
            )
            
            return redirect(self.success_url)
        else:
            # Senha incorreta
            messages.error(request, 'Senha incorreta. Tente novamente.')
            return render(request, self.template_name, {
                'event': self.object,
                'error': 'Senha incorreta.',
            })


class PersonQuickCreateView(CreateView):
    model = Person
    form_class = PersonQuickForm
    template_name = 'events/person_quick_form.html'

    def form_valid(self, form):
        obj = form.save()
        # devolve JS que roda dentro do iframe
        html = f"""
        <script>
          window.parent.adicionarPessoaNoSelect("{escape(obj.pk)}", "{escape(str(obj))}");
        </script>
        """
        return HttpResponse(html)

    def get_success_url(self):
        return reverse_lazy("events:person_quick_success")
    
def person_quick_success(request):
    return HttpResponse("<h3>Salvo com sucesso.</h3>")


@require_GET
def person_search(request):
    term = request.GET.get("query", "").strip()
    if len(term) < 3:
        return JsonResponse([], safe=False)

    qs = Person.objects.filter(full_name__icontains=term).order_by("full_name")[:20]

    data = [
        {"id": p.id, "nome": p.full_name}
        for p in qs
    ]
    return JsonResponse(data, safe=False)

class RelatorioPresencaResponsaveisView(TemplateView):
    template_name = 'events/relatorio_responsaveis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ano = int(self.request.GET.get('ano', 2025))  # depois pode vir de um filtro

        presencas = (
            EventParticipant.objects
            .filter(
                event__event_type='RESPONSAVEIS',
                event__date__year=ano,
                attendance_status='PRESENTE',
            )
            .values('person__full_name')
            .annotate(qtd_presencas=Count('id'))
            .order_by('-qtd_presencas')
        )

        context['ano'] = ano
        context['presencas'] = presencas
        return context
        