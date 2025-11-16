from dal import autocomplete
from .models import Family, Aluno, Turma, Activity, FrequenciaTurma, FrequenciaAluno, FrequenciaAtividade, MovimentacaoTurmaAluno, OcorrenciaAluno, Adult, PerfilUsuario
from .forms import FamilyForm, AlunoForm, TurmaForm, ActivityForm, AddAlunosToTurmaForm, AlunoFiltroForm, AlunoInlineFormSet, MoverAlunoForm, OcorrenciaAlunoForm, AdultFormSet, AdultForm, UsuarioForm
from django import forms
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import JsonResponse, HttpResponse 
from django.db.models import Count, Q, Avg, Value, CharField
from django.forms.models import inlineformset_factory
from datetime import date
from .permissoes import require_perfil
from .utils import usuario_tem_perfil
from AppLSD.templatetags.perfil_tags import has_perfil
# Concatena e ordena por data
from itertools import chain
from operator import itemgetter
from openpyxl import Workbook
import plotly.graph_objs as go
import plotly.offline as opy
import io
import base64
import matplotlib.pyplot as plt
import unicodedata


def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('home')  # nome da sua view home
    else:
        return redirect('login')  # nome padrão da view de login
"""   
def require_perfil(perfil_tipo):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Não autenticado.")
            if not request.user.perfis.filter(tipo=perfil_tipo).exists():
                return HttpResponseForbidden("Você não possui permissão para esta página.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
"""   
@require_perfil('educadora')
def view_educadora(request):
    # apenas educadora acessa
    pass

@require_perfil('facilitador')
def view_facilitador(request):
    # apenas facilitador acessa
    pass

@require_perfil('admin')
def view_admin(request):
    # apenas admin acessa
    pass

@require_perfil('educadora')
def registrar_frequencia(request, turma_id):
    perfil = request.user.perfis.get(tipo='educadora')
    turma = get_object_or_404(Turma, id=turma_id, educadora=perfil)
    # Resto da lógica

@require_perfil('facilitador')
def registrar_frequencia(request, turma_id):
    perfil = request.user.perfis.get(tipo='facilitador')
    turma = get_object_or_404(Turma, id=turma_id, facilitador=perfil)
    # Resto da lógica

@require_perfil('coordenacao')
def dashboard_coordenador(request):
    # Coordenação pode acessar dashboards/admin de turmas
    pass

@require_perfil('diretoria')
def dashboard_diretoria(request):
    # Diretoria pode acessar dashboards/admin de turmas
    pass

@require_perfil('admin')
def usuarios_gerenciar(request):
     # Lista todos os usuários do sistema, com seus perfis associados
    termo = request.GET.get("busca", "")
    usuarios = User.objects.all().prefetch_related('perfis')
    if termo:
        usuarios = usuarios.filter(username__icontains=termo) | usuarios.filter(first_name__icontains=termo)
    if request.method == "POST":
        # Exemplo: desativar usuário
        user_id = request.POST.get("desativar_id")
        if user_id:
            usuario = get_object_or_404(User, id=user_id)
            usuario.is_active = False
            usuario.save()
            return redirect('usuarios_gerenciar')
        user_id = request.POST.get("ativar_id")
        if user_id:
            usuario = get_object_or_404(User, id=user_id)
            usuario.is_active = True
            usuario.save()
            return redirect('usuarios_gerenciar')

    # Você pode adicionar filtros por busca, etc.
    return render(request, 'AppLSD/usuarios_gerenciar.html', {
        "usuarios": usuarios,
    })
    


@require_perfil('admin')
def editar_perfis_usuario(request, usuario_id):
    usuario = User.objects.get(id=usuario_id)
    tipos_perfil = ["admin", "administrativo", "coordenacao", "colaborador", "diretoria", "educadora", "facilitador", "supervisor"]
    if request.method == "POST":
        novos_perfis = request.POST.getlist('tipos_perfil')
        # Remove perfis não marcados
        usuario.perfis.exclude(tipo__in=novos_perfis).delete()
        # Adiciona os novos perfis
        for tipo in novos_perfis:
            if not usuario.perfis.filter(tipo=tipo).exists():
                PerfilUsuario.objects.create(user=usuario, tipo=tipo)
        return redirect('usuarios_gerenciar')
    return render(request, 'AppLSD/editar_perfis.html', {"usuario": usuario, "tipos_perfil": tipos_perfil})

@require_perfil('admin')
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)
    tipos_perfil = ["admin", "administrativo", "coordenacao", "colaborador", "diretoria", "educadora", "facilitador", "supervisor"]
    perfis_do_usuario = list(usuario.perfis.values_list('tipo', flat=True))
    if request.method == "POST":
        usuario.first_name = request.POST.get('nome')
        usuario.email = request.POST.get('email')
        usuario.is_active = True if request.POST.get('is_active') == 'on' else False
        usuario.save()
        # Atualiza perfis
        novos_perfis = request.POST.getlist('tipos_perfil')
        # Remove perfis não marcados
        usuario.perfis.exclude(tipo__in=novos_perfis).delete()
        # Adiciona perfis marcados
        for tipo in novos_perfis:
           if tipo not in perfis_do_usuario:
                PerfilUsuario.objects.create(user=usuario, tipo=tipo)
        return redirect('usuarios_gerenciar')
    return render(request, 'AppLSD/editar_usuario.html', {
        'usuario': usuario,
        'tipos_perfil': tipos_perfil,
        'perfis_do_usuario': perfis_do_usuario,
    })

@require_perfil('admin')
def resetar_senha_usuario(request, usuario_id):
    usuario = User.objects.get(id=usuario_id)
    if request.method == "POST":
        nova_senha = request.POST.get("nova_senha")
        usuario.set_password(nova_senha)
        usuario.save()
        return redirect('usuarios_gerenciar')
    return render(request, 'AppLSD/resetar_senha.html', {"usuario": usuario})

@require_perfil('admin')
def cadastrar_usuario(request):
    tipos_perfil = ["admin", "administrativo", "coordenacao", "colaborador", "diretoria", "educadora", "facilitador", "supervisor"]
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Perfis enviados como lista
            perfis = request.POST.getlist("perfis")
            for perfil in perfis:
                PerfilUsuario.objects.create(user=user, tipo=perfil)
            return redirect('usuarios_gerenciar')
    else:
        form = UsuarioForm()
    return render(request, 'AppLSD/cadastrar_usuario.html', {"form": form, "tipos_perfil": tipos_perfil})

@login_required
def home(request):
    if usuario_tem_perfil(request.user, "facilitador"):
        return redirect('home_facilitador')
    elif usuario_tem_perfil(request.user, "educadora"):
        return redirect('home_educadora')
    elif usuario_tem_perfil(request.user, "diretoria"):
        return redirect('lsd_dashboard/dashboard')  # ou o nome correto do path para dashboard
    return render(request, "AppLSD/home.html", {
        "usuario_admin": usuario_tem_perfil(request.user, "admin"),
        "usuario_coord": usuario_tem_perfil(request.user, "coordenacao"),
        "usuario_supervisor": usuario_tem_perfil(request.user, "supervisor"),
        "usuario_educadora": usuario_tem_perfil(request.user, "educadora"),
        "usuario_facilitador": usuario_tem_perfil(request.user, "facilitador"),
        "usuario_dir": usuario_tem_perfil(request.user, "diretoria"),
        "usuario_adm": usuario_tem_perfil(request.user, "administrativo"),
        "usuario_colab": usuario_tem_perfil(request.user, "colaborador"),
    })
   
def remove_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

@login_required
def home_educadora(request):
    educadora_turmas = Turma.objects.filter(educadora=request.user)
    return render(request, 'AppLSD/home_educadora.html', {'turmas': educadora_turmas})

@login_required
def home_facilitador(request):
    facilitador_atividades = Activity.objects.filter(facilitador=request.user)
    return render(request, 'AppLSD/home_facilitador.html', {'atividades': facilitador_atividades})

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
    atividades_ativas = Activity.objects.filter(alunos__isnull=False).distinct().count()
    
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
      

 # Frequência por Atividade
    atividades_com_frequencia = []
    for atividade in Activity.objects.annotate(total_alunos=Count('alunos')):
        if atividade.total_alunos > 0:
            media_presenca = FrequenciaAluno.objects.filter(
                aluno__atividades=atividade,
                chamada__data__gte=hoje - timezone.timedelta(days=7)
            ).aggregate(Avg('presente'))['presente__avg'] or 0
            
            atividade.media_presenca = media_presenca * 100
            atividades_com_frequencia.append(atividade)
    
    
    return render(request, 'AppLSD/dashboard_presenca.html', {
        'total_alunos': total_alunos,
        'presentes_hoje': presentes_hoje,
        'faltas_hoje': faltas_hoje,
        'turmas_ativas': turmas_ativas,
        'turmas_com_frequencia': turmas_com_frequencia,
        'atividades_com_frequencia': atividades_com_frequencia
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
    families_all = Family.objects.all().order_by('responsible_name')

    if search_query:
        search_query_norm = remove_accents(search_query.lower())
        families_list = [
            f for f in families_all
            if search_query_norm in remove_accents(f.responsible_name.lower())
            or search_query_norm in remove_accents(f.registration_number.lower())
            or search_query_norm in remove_accents(f.cpf.lower())
            # Adicione outros campos se quiser
        ]
    else:
        families_list = list(families_all)

    paginator = Paginator(families_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'AppLSD/family_list.html', {
        'page_obj': page_obj,
        'request': request,
        'search': search_query,
    })


def family_edit(request, pk):
    family = get_object_or_404(Family, pk=pk)

    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES, instance=family)
        if form.is_valid():
            form.save()
            return redirect('family_detail', pk=family.pk)
    else:
        form = FamilyForm(instance=family)
    return render(request, 'AppLSD/family_form.html', {'form': form, 'family': family})

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

def buscar_family(request):
    query = request.GET.get('query', '')
    families = Family.objects.filter(
        Q(responsible_name__icontains=query) | Q(registration_number__icontains=query) | Q(cpf__icontains=query)
    )[:10]
    results = [{
        'id': f.pk,
        'responsible_name': f.responsible_name,
        'cpf': f.cpf,
        'registration_number': f.registration_number
    } for f in families]
    return JsonResponse(results, safe=False)

@login_required
def adult_create(request):
    family_id = request.GET.get('family_id')
    if not family_id:
        # Redirecione para a lista de famílias ou exiba uma mensagem de erro amigável
        return redirect('family_list')

    family = Family.objects.get(pk=family_id)
    
    if request.method == 'POST':
        form = AdultForm(request.POST)
        if form.is_valid():
            adult = form.save(commit=False)
            adult.family = family
            adult.save()
            return redirect('family_detail', pk=family.pk)
    else:
        form = AdultForm()
        if family:
            form.fields['family'].initial = family.pk  # mantém selecionado
            form.fields['family'].widget = forms.HiddenInput()   # campo bloqueado
    return render(request, 'AppLSD/adult_form.html', {'form': form, 'family': family})

@login_required
def adult_detail(request, pk):
    adult = get_object_or_404(Adult, pk=pk)
    return render(request, 'AppLSD/adult_detail.html', {'adult': adult})

def adult_edit(request, pk):
    adult = get_object_or_404(Adult, pk=pk)
    if request.method == 'POST':
        form = AdultForm(request.POST, instance=adult)
        if form.is_valid():
            form.save()
            return redirect('family_detail', pk=adult.family.pk)
    else:
        form = AdultForm(instance=adult)
    return render(request, 'AppLSD/adult_form.html', {'form': form, 'family': adult.family, 'adult': adult})

@login_required
def adult_delete_confirm(request, pk):
    adult = get_object_or_404(Adult, pk=pk)
    family_pk = adult.family.pk
    error = None  # Inicializa a variável error

    if request.method == 'POST':
        senha = request.POST.get('senha')
        usuario = request.user
        user_autenticado = authenticate(username=usuario.username, password=senha)
        if user_autenticado is not None:
            adult.delete()
            return redirect('family_detail', pk=family_pk)  # Redireciona para detalhes da família
        else:
            error = "Senha incorreta."

    return render(request, 'AppLSD/adult_confirm_delete.html', {
        'adult': adult,
        'error': error,
    })


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

@login_required
def aluno_create(request):
    family_id = request.GET.get('family_id')
    family = get_object_or_404(Family, pk=family_id) if family_id else None
    #if not family_id:
        # Redirecione para a lista de famílias ou exiba uma mensagem de erro amigável
     #   return redirect('family_list')

    #family = Family.objects.get(pk=family_id)
    if request.method == 'POST':
        form = AlunoForm(request.POST)
        if form.is_valid():
            aluno = form.save(commit=False)
            # Associa família caso venha selecionada/fixa
            if family:
                aluno.family = family
            aluno.save()
            return redirect('aluno_list')  # Ou outro local desejado
            #return redirect('family_detail', pk=family.pk)
    else:
        # Se veio a família, preenche campo oculto. Senão, deixa campo visível
        initial_data = {'family': family} if family else {}
        form = AlunoForm(initial=initial_data)
        #form = AlunoForm()
        if family:
            #form.fields['family'].initial = family.pk  # mantém selecionado
            form.fields['family'].widget = forms.HiddenInput()   # campo bloqueado
    return render(request, 'AppLSD/aluno_form.html', {'form': form, 'family': family})

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
    class_list = Turma.objects.all().order_by('educadora', 'sala', 'turno')
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
    activity_list = Activity.objects.all().order_by('atividade')
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
        'tipo': f"Atividade: {reg.atividade.atividade}" if reg.atividade else "Atividade",
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
