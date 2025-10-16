from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from dal import autocomplete
from .models import Family, Aluno, Turma, Activity, FrequenciaTurma, FrequenciaAluno, FrequenciaAtividade, MovimentacaoTurmaAluno, OcorrenciaAluno
from .forms import FamilyForm, AlunoForm, TurmaForm, ActivityForm, AddAlunosToTurmaForm, AlunoFiltroForm, AlunoInlineFormSet, MoverAlunoForm, OcorrenciaAlunoForm
from django import forms
from django.contrib.auth import authenticate 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse, HttpResponse  
from django.db.models import Count, Q, Avg
from datetime import date
# Concatena e ordena por data
from itertools import chain
from operator import itemgetter
from openpyxl import Workbook
from django.db.models import Value, CharField
import plotly.graph_objs as go
import plotly.offline as opy
import io
import base64
import matplotlib.pyplot as plt

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('home')  # nome da sua view home
    else:
        return redirect('login')  # nome padrão da view de login
    
@login_required
def home(request):
    return render(request, 'AppLSD/home.html')
   


@login_required
def professor_turmas(request):
    turmas = Turma.objects.filter(professor=request.user)
    return render(request, 'AppLSD/professor_turmas.html', {'turmas': turmas})

@login_required
def dashboard_presenca(request):
    hoje = timezone.now().date()
    
    total_alunos = Aluno.objects.count()
    presentes_hoje = FrequenciaAluno.objects.filter(
        chamada__data=hoje, presente=True
    ).count()
    faltas_hoje = FrequenciaAluno.objects.filter(
        chamada__data=hoje, presente=False
    ).count()
    turmas_ativas = Turma.objects.filter(alunos__isnull=False).distinct().count()
    
    # Frequência por turma
    turmas_com_frequencia = []
    for turma in Turma.objects.annotate(total_alunos=Count('alunos')):
        if turma.total_alunos > 0:
            media_presenca = FrequenciaAluno.objects.filter(
                aluno__turma=turma,
                chamada__data__gte=hoje - timezone.timedelta(days=7)
            ).aggregate(Avg('presente'))['presente__avg'] or 0
            
            turma.media_presenca = media_presenca * 100
            turmas_com_frequencia.append(turma)
    
    return render(request, 'AppLSD/dashboard_presenca.html', {
        'total_alunos': total_alunos,
        'presentes_hoje': presentes_hoje,
        'faltas_hoje': faltas_hoje,
        'turmas_ativas': turmas_ativas,
        'turmas_com_frequencia': turmas_com_frequencia
    })

@login_required
def family_detail(request, pk):
    family = get_object_or_404(Family, pk=pk)
    return render(request, 'AppLSD/family_detail.html', {'family': family})

@login_required
def family_delete_confirm(request, pk):
    family = get_object_or_404(Family, pk=pk)
    error = None

    if request.method == 'POST':
        senha = request.POST.get('senha')
        usuario = request.user
        user_autenticado = authenticate(username=usuario.username, password=senha)
        if user_autenticado is not None:
            family.delete()
            return redirect('family_list')
        else:
            error = "Senha incorreta."

    return render(request, 'AppLSD/family_confirm_delete.html', {
        'family': family,
        'error': error,
    })

def family_list(request):
    search_query = request.GET.get('search', '').strip()
    
    if search_query:
        families_list = Family.objects.filter(responsible_name__icontains=search_query).order_by('responsible_name')
    else:
        families_list = Family.objects.all().order_by('responsible_name')

    paginator = Paginator(families_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'AppLSD/family_list.html', {
        'page_obj': page_obj,
        'request': request,
    })

def family_edit(request, pk):
    family = get_object_or_404(Family, pk=pk)
    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES, instance=family)
        if form.is_valid():
            form.save()
            return redirect('family_list')
    else:
        form = FamilyForm(instance=family)
    return render(request, 'AppLSD/family_form.html', {'form': form})

def family_create(request):
    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES)
        formset = AlunoInlineFormSet(request.POST, request.FILES)
        if form.is_valid() and formset.is_valid():
            family = form.save()
            formset.instance = family
            formset.save()
            return redirect('family_detail', pk=family.pk)
    else:
        form = FamilyForm()
        formset = AlunoInlineFormSet()
    return render(request, 'AppLSD/family_form.html', {'form': form, 'formset': formset})

def family_update(request, pk):
    family = get_object_or_404(Family, pk=pk)
    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES, instance=family)
        formset = AlunoInlineFormSet(request.POST, request.FILES, instance=family)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('family_detail', pk=family.pk)
    else:
        form = FamilyForm(instance=family)
        formset = AlunoInlineFormSet(instance=family)
    return render(request, 'families/family_form.html', {'form': form, 'formset': formset})

def family_autocomplete(request):
    term = request.GET.get("q", "")
    familias = Family.objects.filter(responsible_name__icontains=term).order_by("responsible_name")[:20]
    results = [{"id": f.id, "text": f.responsible_name} for f in familias]
    return JsonResponse({"results": results})


def aluno_list(request):
    alunos_list = Aluno.objects.select_related('family').all().order_by('name')

    paginator = Paginator(alunos_list, 100)  # paginar 100 por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'AppLSD/aluno_list.html', {'page_obj': page_obj})

def aluno_create(request):
    family_id = request.GET.get('family_id')
    family = Family.objects.get(pk=family_id) if family_id else None
    
    if request.method == "POST":
        form = AlunoForm(request.POST)
        if form.is_valid():
            aluno = form.save(commit=False)
            if family:
                aluno.family = family
            elif not aluno.family:
                # Não foi informado nem pelo formulário
                return HttpResponse("É obrigatório informar a família ao cadastrar um aluno.", status=400)
            aluno.save()
            # redirecionar para a lista de alunos ou detalhes da família
            if family:
                return redirect('family_detail', pk=family.pk)
            return redirect('aluno_list')
    else:
        form = AlunoForm()
    return render(request, "AppLSD/aluno_form.html", {"form": form})

@login_required
def aluno_detail(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return render(request, 'AppLSD/aluno_detail.html', {'aluno': aluno})

def aluno_edit(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    if request.method == 'POST':
        form = AlunoForm(request.POST, instance=aluno)
        if form.is_valid():
            form.save()
            return redirect('aluno_list')
    else:
        form = AlunoForm(instance=aluno)
    return render(request, 'AppLSD/aluno_form.html', {'form': form})

@login_required
def aluno_delete_confirm(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    error = None

    if request.method == 'POST':
        senha = request.POST.get('senha')
        usuario = request.user
        user_autenticado = authenticate(username=usuario.username, password=senha)
        if user_autenticado is not None:
            aluno.delete()
            return redirect('aluno_list')
        else:
            error = "Senha incorreta."

    return render(request, 'AppLSD/aluno_confirm_delete.html', {
        'aluno': aluno,
        'error': error,
    })

@login_required
def turma_detail(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    return render(request, 'AppLSD/turma_detail.html', {'turma': turma})

def turma_list(request):
    class_list = Turma.objects.all().order_by('professor', 'sala', 'turno')
    paginator = Paginator(class_list, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'AppLSD/turma_list.html', {'page_obj': page_obj})

def turma_create(request):
    if request.method == 'POST':
        form = TurmaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('turma_list')
    else:
        form = TurmaForm()
    return render(request, 'AppLSD/turma_form.html', {'form': form})

def turma_edit(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    if request.method == 'POST':
        form = TurmaForm(request.POST, instance=turma)
        if form.is_valid():
            form.save()
            return redirect('turma_list')
    else:
        form = TurmaForm(instance=turma)
    return render(request, 'AppLSD/turma_form.html', {'form': form})

def turma_delete(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    if request.method == 'POST':
        turma.delete()
        return redirect('turma_list')
    return render(request, 'AppLSD/turma_confirm_delete.html', {'turma': turma})

@login_required
def iniciar_chamada_turma(request, turma_id):
    turma = Turma.objects.get(id=turma_id)
    alunos = Aluno.objects.filter(turma=turma)
    data_chamada = request.POST.get('data', date.today())

    if request.method == 'POST':
        for aluno in alunos:
            presente = bool(request.POST.get(f'presente_{aluno.id}'))
            freq, created = FrequenciaTurma.objects.update_or_create(
                aluno=aluno, turma=turma, data=data_chamada,
                defaults={'presente': presente}
            )
        return render(request, 'AppLSD/sucesso_turma.html', {'turma': turma, 'data': data_chamada})

    return render(request, 'AppLSD/turma_presenca.html', {
        'turma': turma,
        'alunos': alunos,
        'data': request.POST.get('data') or date.today().isoformat()
    })

@login_required
def activity_detail(request, activity_id):
    atividade = Activity.objects.get(id=activity_id)
    contexto = {'atividade': atividade}
    return render(request, 'AppLSD/activity_detail.html', contexto)
    

def activity_list(request):
    activity_list = Activity.objects.all().order_by('descricao')
    paginator = Paginator(activity_list, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'AppLSD/activity_list.html', {'page_obj': page_obj})

def activity_create(request):
    if request.method == 'POST':
        form = ActivityForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('activity_list')
    else:
        form = ActivityForm()
    return render(request, 'AppLSD/activity_form.html', {'form': form})

def activity_edit(request, pk):
    atividade = get_object_or_404(Activity, pk=pk)
    if request.method == 'POST':
        form = ActivityForm(request.POST, instance=atividade)
        if form.is_valid():
            form.save()
            return redirect('activity_list')
    else:
        form = ActivityForm(instance=atividade)
    return render(request, 'AppLSD/activity_form.html', {'form': form})

def activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    if request.method == 'POST':
        activity.delete()
        return redirect('activity_list')
    return render(request, 'AppLSD/activity_confirm_delete.html', {'activity': activity})

@login_required
def iniciar_chamada_activity(request, activity_id):
    atividade = Activity.objects.get(id=activity_id)
    alunos = Aluno.objects.filter(atividades=atividade)
    data_chamada = request.POST.get('data', date.today())

    if request.method == 'POST':
        for aluno in alunos:
            presente = bool(request.POST.get(f'presente_{aluno.id}'))
            freq, created = FrequenciaAtividade.objects.update_or_create(
                aluno=aluno, atividade=atividade, data=data_chamada,
                defaults={'presente': presente}
            )
        return render(request, 'AppLSD/sucesso_activity.html', {'atividade': atividade, 'data': data_chamada})

    return render(request, 'AppLSD/activity_presenca.html', {
        'atividade': atividade,
        'alunos': alunos,
        'data': request.POST.get('data') or date.today().isoformat()
    })

    

def turma_add_alunos(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    alunos_queryset = Aluno.objects.filter(turma__isnull=True)

    filtro = AlunoFiltroForm(request.GET or None)
    if filtro.is_valid():
        if filtro.cleaned_data['nome']:
            alunos_queryset = alunos_queryset.filter(name__icontains=filtro.cleaned_data['nome'])
        if filtro.cleaned_data['familia']:
            alunos_queryset = alunos_queryset.filter(family=filtro.cleaned_data['familia'])
        if filtro.cleaned_data['escola']:
            alunos_queryset = alunos_queryset.filter(school__icontains=filtro.cleaned_data['escola'])

    class DinamicoAddAlunosToTurmaForm(AddAlunosToTurmaForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['alunos'].queryset = alunos_queryset

    if request.method == 'POST':
        form = DinamicoAddAlunosToTurmaForm(request.POST)
        if form.is_valid():
            for aluno in form.cleaned_data['alunos']:
                aluno.turma = turma
                aluno.save()
            return redirect('turma_detail', turma_id=turma.id)
    else:
        form = DinamicoAddAlunosToTurmaForm()

    return render(
        request, 
        'AppLSD/turma_add_alunos.html', 
        {'turma': turma, 'form': form, 'filtro': filtro}
    )


def mover_aluno(request, aluno_id):
    aluno = Aluno.objects.get(pk=aluno_id)
    if request.method == "POST":
        form = MoverAlunoForm(request.POST)
        if form.is_valid():
            turma_antiga = aluno.turma
            turma_nova = form.cleaned_data['turma_destino']
            motivo = form.cleaned_data['motivo']

            # Atualiza a turma do aluno
            aluno.turma = turma_nova
            aluno.save()

            # Cria registro no histórico
            MovimentacaoTurmaAluno.objects.create(
                aluno=aluno,
                turma_origem=turma_antiga,
                turma_destino=turma_nova,
                motivo=motivo
            )
            return redirect('aluno_detail', pk=aluno.pk)
    else:
        form = MoverAlunoForm(initial={'turma_destino': aluno.turma})
    return render(request, "AppLSD/mover_aluno.html", {"form": form, "aluno": aluno})

def adicionar_ocorrencia(request, aluno_id):
    aluno = Aluno.objects.get(pk=aluno_id)
    if request.method == 'POST':
        form = OcorrenciaAlunoForm(request.POST)
        if form.is_valid():
            ocorrencia = form.save(commit=False)
            ocorrencia.aluno = aluno
            ocorrencia.save()
            return redirect('aluno_detail', pk=aluno.pk)
    else:
        form = OcorrenciaAlunoForm()
    return render(request, 'AppLSD/adicionar_ocorrencia.html', {'form': form, 'aluno': aluno})

def activity_add_alunos(request, activity_id):
    atividade = Activity.objects.get(id=activity_id)
    alunos_queryset = Aluno.objects.exclude(atividades=atividade)  # alunos que ainda não estão na atividade

    filtro = AlunoFiltroForm(request.GET or None)
    if filtro.is_valid():
        if filtro.cleaned_data['nome']:
            alunos_queryset = alunos_queryset.filter(name__icontains=filtro.cleaned_data['nome'])
        if filtro.cleaned_data['familia']:
            alunos_queryset = alunos_queryset.filter(family=filtro.cleaned_data['familia'])
        if filtro.cleaned_data['escola']:
            alunos_queryset = alunos_queryset.filter(school__icontains=filtro.cleaned_data['escola'])

    class DinamicoAddAlunosToTurmaForm(AddAlunosToTurmaForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['alunos'].queryset = alunos_queryset

    if request.method == 'POST':
        form = DinamicoAddAlunosToTurmaForm(request.POST)
        if form.is_valid():
            for aluno in form.cleaned_data['alunos']:
                atividade.alunos.add(aluno)  # adiciona aluno à atividade corretamente
            return redirect('activity_detail', activity_id=atividade.id)
    else:
        form = DinamicoAddAlunosToTurmaForm()

    return render(
        request, 
        'AppLSD/activity_add_alunos.html', 
        {'atividade': atividade, 'form': form, 'filtro': filtro}
    )

@login_required
def relatorio_presenca_turma(request, turma_id, data=None):
    turma = Turma.objects.get(id=turma_id)
    alunos = Aluno.objects.filter(turma=turma)

    # Primeiro verifica se há data passada por URL (GET)
    data_get = request.GET.get('data')
    if data_get:
        data = data_get

    if data:
        chamadas = FrequenciaTurma.objects.filter(turma=turma, data=data)
    else:
        chamada_recente = FrequenciaTurma.objects.filter(turma=turma).order_by('-data').first()
        data = chamada_recente.data if chamada_recente else None
        chamadas = FrequenciaTurma.objects.filter(turma=turma, data=data) if data else []

    return render(request, 'AppLSD/relatorio_presenca_turma.html', {
        'turma': turma,
        'alunos': alunos,
        'chamadas': chamadas,
        'data': data,
    })

@login_required
def relatorio_presenca_activity(request, activity_id, data=None):
    atividade = Activity.objects.get(id=activity_id)
    alunos = Aluno.objects.filter(atividades=atividade)

    # Primeiro verifica se há data passada por URL (GET)
    data_get = request.GET.get('data')
    if data_get:
        data = data_get

    if data:
        chamadas = FrequenciaAtividade.objects.filter(atividade=atividade, data=data)
    else:
        chamada_recente = FrequenciaAtividade.objects.filter(atividade=atividade).order_by('-data').first()
        data = chamada_recente.data if chamada_recente else None
        chamadas = FrequenciaAtividade.objects.filter(atividade=atividade, data=data) if data else []

    return render(request, 'AppLSD/relatorio_presenca_activity.html', {
        'atividade': atividade,
        'alunos': alunos,
        'chamadas': chamadas,
        'data': data,
    })

@login_required
def relatorio_mensal_aluno(request):
    aluno_id = request.GET.get('aluno_id')
    mes = request.GET.get('mes')  # formato "YYYY-MM"
    if not aluno_id:
        alunos = Aluno.objects.all()
        return render(request, 'AppLSD/relatorio_busca_aluno.html', {'alunos': alunos, 'erro': 'Selecione um aluno.'})
    tipo = request.GET.get('tipo', 'analitico')
    aluno = get_object_or_404(Aluno, pk=aluno_id)
    ano, mes_val = (int(x) for x in mes.split('-'))

    registros_turma = FrequenciaTurma.objects.filter(
    aluno=aluno, data__year=ano, data__month=mes_val)
    registros_turma_lista = [
        {
            'data': reg.data,
            'presente': reg.presente,
            'tipo': "Turma",
        }
        for reg in registros_turma
    ]
    
    registros_atividade = FrequenciaAtividade.objects.filter(
    aluno=aluno, data__year=ano, data__month=mes_val).select_related('atividade')

# Monte a lista anotando o nome da atividade em cada registro
    registros_atividade_lista = [
    {
        'data': reg.data,
        'presente': reg.presente,
        'tipo': f"Atividade: {reg.atividade.descricao}" if reg.atividade else "Atividade",
    }
    for reg in registros_atividade
    ]
    
    registros = sorted(registros_turma_lista + registros_atividade_lista, key=lambda x: x['data'])

    return render(request, 'AppLSD/relatorio_mensal_aluno.html', {
        'aluno': aluno,
        'mes': mes,
        'registros': registros,
        'tipo': tipo,
    })



#@login_required
def relatorio_busca_aluno(request):
    alunos = Aluno.objects.order_by('name')
    return render(request, 'AppLSD/relatorio_busca_aluno.html', {'alunos': alunos})

def relatorio_grafico_mensal_aluno(request):
    aluno_id = request.GET.get('aluno_id')
    mes_ano = request.GET.get('mes')  # formato "YYYY-MM"
    aluno = get_object_or_404(Aluno, pk=aluno_id)

    ano, mes = (int(x) for x in mes_ano.split('-'))
    chamadas = FrequenciaTurma.objects.filter(aluno=aluno, data__year=ano, data__month=mes)

    presencas = sum(1 for c in chamadas if c.presente)
    faltas = sum(1 for c in chamadas if not c.presente)

    # Criar gráfico
    labels = ['Presenças', 'Faltas']
    values = [presencas, faltas]
    fig, ax = plt.subplots()
    ax.bar(labels, values, color=['green', 'red'])
    ax.set_title(f'Frequência de {aluno.name} - {mes_ano}')

    # Convertendo gráfico para imagem no formato base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_png = buf.getvalue()
    graph = base64.b64encode(image_png).decode('utf-8')
    buf.close()

    return render(request, 'AppLSD/relatorio_grafico_aluno.html', {
        'graph': graph,
        'aluno': aluno,
        'mes_ano': mes_ano,
        'presencas': presencas,
        'faltas': faltas,
    })

@login_required
def exportar_frequencia_mensal_aluno_excel(request):
    aluno_id = request.GET.get('aluno_id')
    mes_ano = request.GET.get('mes')
    aluno = get_object_or_404(Aluno, pk=aluno_id)
    ano, mes = (int(x) for x in mes_ano.split('-'))
    chamadas = FrequenciaTurma.objects.filter(aluno=aluno, data__year=ano, data__month=mes)

    wb = Workbook()
    ws = wb.active
    ws.title = "Frequência"

    ws.append(["Data", "Presente", "Observação"])

    for c in chamadas:
        ws.append([c.data.strftime('%d/%m/%Y'), "Sim" if c.presente else "Não", c.observacao or ""])

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = f"attachment; filename=frequencia_{aluno.name}_{mes_ano}.xlsx"
    wb.save(response)
    return response


@login_required
def home_relatorios(request):
    turmas = Turma.objects.all()
    atividades = Activity.objects.all()
    alunos = Aluno.objects.all()  # Incluído para o relatório de aluno
    return render(request, 'AppLSD/home_relatorios.html', {
        'turmas': turmas,
        'atividades': atividades,
        'alunos': alunos,
    })
