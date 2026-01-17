from pyexpat.errors import messages
from dal import autocomplete
from AppLSD.models import Family, Aluno, Turma, Activity, FrequenciaTurma, FrequenciaAluno, FrequenciaAtividade, MovimentacaoTurmaAluno, OcorrenciaAluno, Adult, AppLog, PerfilUsuario
from AppLSD.utils import is_coordenacao, is_educadora, coordenacao_required, usuario_tem_perfil, get_tipo_perfil, registrar_log, TIPOS_PERFIL_VALIDOS, sincronizar_grupos_usuario # ✅ Importar as funções
from AppLSD.templatetags.perfil_tags import has_perfil
from .forms import FamilyForm, AlunoForm, TurmaForm, ActivityForm, AddAlunosToTurmaForm, AlunoFiltroForm, AlunoInlineFormSet, MoverAlunoForm, OcorrenciaAlunoForm, AdultFormSet, AdultForm, UsuarioForm
from django import forms
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.http import JsonResponse, HttpResponse 
from django.db.models import Count, Q, Avg, Value, CharField, Exists, OuterRef, IntegerField
from django.db.models.functions import Cast
from django.forms.models import inlineformset_factory
from django.template.loader import render_to_string
from django.views.generic import ListView
from datetime import date, timedelta, datetime
from .permissoes import require_perfil
# Concatena e ordena por data
from itertools import chain
from operator import itemgetter
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import os
os.environ['WEASYPRINT_DLL_DIRECTORIES'] = r"C:\Program Files\GTK3-Runtime Win64\bin"
from weasyprint import HTML, CSS
import plotly.graph_objs as go
import plotly.offline as opy
import io
import base64
import matplotlib.pyplot as plt
import unicodedata
import logging

logger = logging.getLogger(__name__)

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect('/home/')  # URL direta, não por nome
    else:
        return redirect('/accounts/login/')  # nome padrão da view de login
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
@require_perfil('servicosocial')
def view_servicosocial(request):
    # apenas serviço social acessa
    pass

@require_perfil('admin')
def view_admin(request):
    # apenas admin acessa
    pass

@require_perfil('educadora')
def registrar_frequencia(request, turma_id):
    perfil = request.user.perfis.get(tipo_perfil='educadora')
    turma = get_object_or_404(Turma, id=turma_id, educadora=perfil)
    # Resto da lógica

@require_perfil('servicosocial')
def registrar_frequencia(request):
    perfil = request.user.perfis.get(tipo_perfil='servicosocial')
    pass
    # Resto da lógica

@require_perfil('facilitador')
def registrar_frequencia(request, turma_id):
    perfil = request.user.perfis.get(tipo_perfil='facilitador')
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

    # processamento POST igual ao seu código
    if request.method == "POST":
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

    # Lista de tipos de perfil a partir do model
    #from AppLSD.models import PerfilUsuario
    tipos_perfil = [tp[0] for tp in PerfilUsuario._meta.get_field('tipo_perfil').choices]

    # Se estiver mostrando perfis de um único usuário (por exemplo, ao editar), passe assim:
    perfis_do_usuario = []
    usuario_id = request.GET.get("usuario_id")  # exemplo para edição de um usuário
    if usuario_id:
        usuario = get_object_or_404(User, id=usuario_id)
        perfis_do_usuario = [perfil.tipo_perfil for perfil in usuario.perfis.all()]

    return render(request, 'AppLSD/usuarios_gerenciar.html', {
        "usuarios": usuarios,
        "tipos_perfil": tipos_perfil,
        "perfis_do_usuario": perfis_do_usuario,
    })
    

@require_perfil('admin')
def editar_perfis_usuario(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)

    if request.method == "POST":
        novos_perfis = request.POST.getlist('tipo_perfil')

        # mantém só tipos válidos
        novos_perfis = [tp for tp in novos_perfis if tp in TIPOS_PERFIL_VALIDOS]

        # remove perfis não marcados
        usuario.perfis.exclude(tipo_perfil__in=novos_perfis).delete()

        # adiciona os novos perfis
        for tipo in novos_perfis:
            if not usuario.perfis.filter(tipo_perfil=tipo).exists():
                PerfilUsuario.objects.create(user=usuario, tipo_perfil=tipo)

        # se ficou sem nenhum, força colaborador
        if not usuario.perfis.exists():
            PerfilUsuario.objects.create(user=usuario, tipo_perfil='colaborador')

        sincronizar_grupos_usuario(usuario)
        return redirect('usuarios_gerenciar')

    perfis_do_usuario = list(usuario.perfis.values_list('tipo_perfil', flat=True))
    return render(
        request,
        'AppLSD/editar_perfis.html',
        {
            "usuario": usuario,
            "tipo_perfil": TIPOS_PERFIL_VALIDOS,
            "perfis_do_usuario": perfis_do_usuario,
        },
    )

@require_perfil('admin')
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)
    tipo_perfil_choices = TIPOS_PERFIL_VALIDOS
    perfis_do_usuario = list(usuario.perfis.values_list('tipo_perfil', flat=True))

    if request.method == "POST":
        usuario.first_name = request.POST.get('nome')
        usuario.email = request.POST.get('email')
        usuario.is_active = request.POST.get('is_active') == 'true'
        usuario.save()

        novos_perfis = request.POST.getlist('tipo_perfil')
        novos_perfis = [tp for tp in novos_perfis if tp in TIPOS_PERFIL_VALIDOS]

        usuario.perfis.exclude(tipo_perfil__in=novos_perfis).delete()

        for tipo in novos_perfis:
            if not usuario.perfis.filter(tipo_perfil=tipo).exists():
                PerfilUsuario.objects.create(user=usuario, tipo_perfil=tipo)

        if not usuario.perfis.exists():
            PerfilUsuario.objects.create(user=usuario, tipo_perfil='colaborador')

        sincronizar_grupos_usuario(usuario)
        return redirect('usuarios_gerenciar')

    return render(
        request,
        'AppLSD/editar_usuario.html',
        {
            'usuario': usuario,
            'tipo_perfil_choices': tipo_perfil_choices,
            'perfis_do_usuario': perfis_do_usuario,
        },
    )


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
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            user = form.save()
            perfis = request.POST.getlist("perfis")  # nomes do tipo_perfil
            for perfil in perfis:
                PerfilUsuario.objects.create(user=user, tipo_perfil=perfil)
            # se não marcou nada, cria padrão colaborador
            if not perfis:
                PerfilUsuario.objects.create(user=user, tipo_perfil='colaborador')
            sincronizar_grupos_usuario(user)
            return redirect('usuarios_gerenciar')
    else:
        form = UsuarioForm()
    return render(
        request,
        'AppLSD/cadastrar_usuario.html',
        {"form": form, "tipo_perfil": TIPOS_PERFIL_VALIDOS},
    )

@login_required
def home(request):
    if usuario_tem_perfil(request.user, "facilitador"):
        return redirect('home_facilitador')
    elif usuario_tem_perfil(request.user, "educadora"):
        return redirect('home_educadora')
    elif usuario_tem_perfil(request.user, "coordenacao"):
        return redirect('home_escola')
    elif usuario_tem_perfil(request.user, "servicosocial"):
        return redirect('home_assist')
    elif usuario_tem_perfil(request.user, "diretoria"):
        return redirect('lsd_dashboard/dashboard')  # ou o nome correto do path para dashboard
    return render(request, "AppLSD/home.html", {
        "usuario_admin": usuario_tem_perfil(request.user, "admin"),
        "usuario_coord": usuario_tem_perfil(request.user, "coordenacao"),
        "usuario_supervisor": usuario_tem_perfil(request.user, "supervisor"),
        "usuario_educadora": usuario_tem_perfil(request.user, "educadora"),
        "usuario_servicosocial": usuario_tem_perfil(request.user, "servicosocial"),
        "usuario_facilitador": usuario_tem_perfil(request.user, "facilitador"),
        "usuario_dir": usuario_tem_perfil(request.user, "diretoria"),
        "usuario_adm": usuario_tem_perfil(request.user, "administrativo"),
        "usuario_colab": usuario_tem_perfil(request.user, "colaborador"),
        "usuario_finan": usuario_tem_perfil(request.user, "financeiro"),
        "usuario_nutri": usuario_tem_perfil(request.user, "nutricao"),

    })
   
def remove_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

@login_required
def home_educadora(request):
    educadora = request.user
    hoje = timezone.now().date()
    weekday = hoje.weekday()  # 0=segunda, 6=domingo

     # alunos da educadora
    alunos_da_educadora = Aluno.objects.filter(turma__educadora=educadora)
    
    # atividades que têm pelo menos um desses alunos
    atividades_com_alunos_da_educadora = Activity.objects.filter(
        Exists(
            alunos_da_educadora.filter(atividades=OuterRef('pk'))
        )
    )
    # se você tem campo de dia da semana na Activity, aplique o filtro do dia aqui:
    # por exemplo, se get_dia_semana_display usa choices com 'SEG', 'TER'...:
    mapa_weekday = {
        0: 'segunda',
        1: 'terca',
        2: 'quarta',
        3: 'quinta',
        4: 'sexta',
    }

    valor_dia = mapa_weekday.get(weekday)
    if valor_dia:
        # se dia_semana guarda vários dias em uma string, usa contains
        atividades_com_alunos_da_educadora = atividades_com_alunos_da_educadora.filter(dia_semana__icontains=valor_dia)

    context = {
        'turmas': Turma.objects.filter(educadora=educadora),
        'atividades_do_dia': atividades_com_alunos_da_educadora,
        # outros dados que você já manda hoje (turmas do dia, etc.)
    }
    return render(request, 'AppLSD/home_educadora.html', context)
    
@login_required
def home_facilitador(request):
    facilitador_atividades = Activity.objects.filter(facilitador=request.user)
    return render(request, 'AppLSD/home_facilitador.html', {'atividades': facilitador_atividades})

@login_required
def home_assist(request):
    print(">>> ENTROU NA HOME_ASSIST")
    servicosocial = request.user
    hoje = timezone.now().date()
    data_corte = date(hoje.year - 60, hoje.month, hoje.day)
    contexto = {
        "total_assistidos": Aluno.objects.count(),
        "total_familias": Family.objects.count(),
        "total_adultos": Adult.objects.count(),
        "total_idosos": Adult.objects.filter(birth_date__lte=data_corte).count(),
        # "percentual_presenca": calcular_presenca_hoje(),
        "hoje": timezone.now().strftime("%d/%m/%Y"),
    }
    #hoje = timezone.now().date()
    return render(request, 'AppLSD/home_assist.html', contexto)

@login_required
def home_escola(request):
    return render(request, 'AppLSD/home_escola.html')

@login_required
def home_diretoria(request):
    return render(request, 'AppLSD/home_diretoria.html')
@login_required
def home_adm(request):
    return render(request, 'AppLSD/home_adm.html')

#Mesclagem das views de dashboard de presença e relatórios
@login_required
def dashboard_completo(request):
    today = timezone.now().date()

    # ===== DASHBOARD DE PRESENÇA =====
    total_alunos = Aluno.objects.count()

    presentes_hoje = FrequenciaAluno.objects.filter(
        chamada__data=today,
        presente=True
    ).count()

    faltas_hoje = FrequenciaAluno.objects.filter(
        chamada__data=today,
        presente=False
    ).count()

    turmas_ativas = Turma.objects.count()

    # ===== RELATÓRIOS =====
    turmas = Turma.objects.all()

    # Frequência por turma
    turmas_com_frequencia = []
    for turma in Turma.objects.annotate(total_alunos=Count("alunos")):
        if turma.total_alunos > 0:
            media_presenca = (
                FrequenciaAluno.objects
                .filter(
                    aluno__turma=turma,
                    chamada__data__gte=today - timezone.timedelta(days=7),
                )
                .annotate(presente_int=Cast("presente", IntegerField()))
                .aggregate(media=Avg("presente_int"))["media"] or 0
            )
            turma.media_presenca = media_presenca * 100
            turmas_com_frequencia.append(turma)

    # Atividades
    atividades_ativas = Activity.objects.count()
    atividades = Activity.objects.all()

    atividades_com_frequencia = []
    for atividade in Activity.objects.annotate(total_alunos=Count("alunos")):
        if atividade.total_alunos > 0:
            media_presenca = (
                FrequenciaAluno.objects
                .filter(
                    aluno__atividades=atividade,
                    chamada__data__gte=today - timezone.timedelta(days=7),
                )
                .annotate(presente_int=Cast("presente", IntegerField()))
                .aggregate(media=Avg("presente_int"))["media"] or 0
            )
            atividade.media_presenca = media_presenca * 100
            atividades_com_frequencia.append(atividade)

    alunos = Aluno.objects.all()

    context = {
        "total_alunos": total_alunos,
        "presentes_hoje": presentes_hoje,
        "faltas_hoje": faltas_hoje,
        "turmas_ativas": turmas_ativas,
        "atividades_ativas": atividades_ativas,
        "turmas_com_frequencia": turmas_com_frequencia,
        "atividades_com_frequencia": atividades_com_frequencia,
        "turmas": turmas,
        "atividades": atividades,
        "alunos": alunos,
    }
    return render(request, "AppLSD/home_relatorios.html", context)
    
#Tela para Educadora e Facilitador
@login_required
def dashboard_presenca(request):
    hoje = timezone.now().date()
    semana = hoje - timedelta(days=7)

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
            media_presenca = (
                FrequenciaAluno.objects
                .filter(
                    aluno__turma=turma,
                    chamada__data__gte=hoje - timezone.timedelta(days=7),
                )
                .annotate(presente_int=Cast("presente", IntegerField()))
                .aggregate(media=Avg("presente_int"))["media"] or 0
            )

            turma.media_presenca = media_presenca * 100
            turmas_com_frequencia.append(turma)

    # IDs das atividades com presenças registradas nos últimos 7 dias
    atividades_ids = FrequenciaAtividade.objects.filter(
        data__gte=semana
    ).values_list("atividade_id", flat=True).distinct()

    atividades_com_frequencia = []
    for atividade in Activity.objects.annotate(total_alunos=Count("alunos")).filter(
        id__in=atividades_ids
    ):
        if atividade.total_alunos > 0:
            presencas = FrequenciaAtividade.objects.filter(
                atividade=atividade,
                data__gte=semana,
                presente=True,
            ).count()
            media = (presencas / atividade.total_alunos * 100) if atividade.total_alunos else 0
            atividade.media_presenca = round(media, 1)
            atividades_com_frequencia.append(atividade)

    return render(
        request,
        "AppLSD/dashboard_presenca.html",
        {
            "total_alunos": total_alunos,
            "presentes_hoje": presentes_hoje,
            "faltas_hoje": faltas_hoje,
            "turmas_ativas": turmas_ativas,
            "turmas_com_frequencia": turmas_com_frequencia,
            "atividades_com_frequencia": atividades_com_frequencia,
        },
    )

#Métódos Familia
@login_required
def family_detail(request, pk):
    family = get_object_or_404(Family, pk=pk)

    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Family)
    logs = AppLog.objects.filter(content_type=ct, object_id=family.pk)

    context = {
        'family': family,
        'logs': logs,
    }
    return render(request, 'AppLSD/family_detail.html', context)

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

@login_required
def family_list(request):
    # termo vindo da URL ?q=...
    query = request.GET.get('q', '').strip()

    # queryset base
    families_qs = Family.objects.all()

    # aplica filtro se houver busca
    if query:
        families_qs = families_qs.filter(
            Q(registration_number__icontains=query) |
            Q(responsible_name__icontains=query) |
            Q(cpf__icontains=query)
        )

    # ordenação
    families_qs = families_qs.order_by('registration_number')

    # guarda total ANTES da paginação
    total = families_qs.count()

    # paginação
    paginator = Paginator(families_qs, 50)  # 50 por página
    page_number = request.GET.get('page')
    families_page = paginator.get_page(page_number)

    context = {
        'families': families_page,  # objeto de página
        'query': query,
        'total': total,
    }
    return render(request, 'AppLSD/family_list.html', context)

@login_required
def family_edit(request, pk):
    family = get_object_or_404(Family, pk=pk)

    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES, instance=family)
        if form.is_valid():
            family = form.save(commit=False)
            family.editado_por = request.user           # auditoria
            family.save()
            registrar_log(
                request.user,
                family,
                'familia_editada',
                f'Família {family.responsible_name} atualizada.'
            )
            return redirect('family_detail', pk=family.pk)
    else:
        form = FamilyForm(instance=family)
    
    context = {
        'form': form,
        'family': family,
    }
    return render(request, 'AppLSD/family_form.html', {'form': form, 'family': family})

@login_required
def family_create(request):
    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES)
        formset = AlunoInlineFormSet(request.POST, request.FILES)
        if form.is_valid() and formset.is_valid():
            family = form.save(commit=False)
            family.criado_por = request.user            # auditoria
            family.save()
            formset.instance = family
            formset.save()
            registrar_log(
                request.user,
                family,
                'familia_criada',
                f'Família {family.responsible_name} cadastrada.'
            )
            return redirect('family_detail', pk=family.pk)
    else:
        form = FamilyForm()
        formset = AlunoInlineFormSet()
    return render(request, 'AppLSD/family_form.html', {'form': form, 'formset': formset})

@login_required
def family_update(request, pk):
    family = get_object_or_404(Family, pk=pk)
    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES, instance=family)
        formset = AlunoInlineFormSet(request.POST, request.FILES, instance=family)
        if form.is_valid() and formset.is_valid():
            family = form.save(commit=False)
            family.editado_por = request.user           # auditoria
            family.save()
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

# Gerar PDF do termo de responsabilidade da família
def family_term_pdf(request, pk):
    family = get_object_or_404(Family, pk=pk)
    today = date.today()

    context = {
        'family': family,
        'city': 'Maceió',
        'today': today,
        'day': today.day,
        'month': today.strftime('%B'),   # ou em português manualmente
        'year': today.year,
    }

    html_string = render_to_string('terms/family_term.html', context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf_file = html.write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    # se quiser forçar download, use attachment:
    response['Content-Disposition'] = f'filename="termo_familia_{family.id}.pdf"'

    return response

@login_required
def adult_list(request):
    # Captura o termo de busca
    query = request.GET.get('q', '').strip()
    
    # Base queryset - ajuste o nome do modelo conforme seu código
    adultos = Adult.objects.select_related('family').all()  # ou Person, conforme seu modelo
    
    # Aplica filtro se houver busca
    if query:
        adultos = adultos.filter(
            Q(name__icontains=query) |
            Q(cpf__icontains=query) |
            Q(family__registration_number__icontains=query) |
            Q(family__responsible_name__icontains=query)
        )
    
    # Ordena por nome
    adultos = adultos.order_by('name')
    
    # Conta total
    total = adultos.count()
    
    # Paginação
    paginator = Paginator(adultos, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'adultos': page_obj,
        'query': query,
        'total': total,
    }
    
    return render(request, 'AppLSD/adult_list.html', context)

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
            adult.criado_por = request.user             # auditoria
            adult.save()
            registrar_log(
                request.user,
                adult,
                'adulto_criado',
                f'Adulto {adult.name} incluído na família {adult.family.responsible_name}.'
            )
            return redirect('family_detail', pk=family.pk)
    else:
        form = AdultForm()
        form.fields['family'].initial = family.pk  # mantém selecionado
        form.fields['family'].widget = forms.HiddenInput()   # campo bloqueado
    return render(request, 'AppLSD/adult_form.html', {'form': form, 'family': family})

@login_required
def adult_detail(request, pk):
    adult = get_object_or_404(Adult, pk=pk)

    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Adult)
    logs = AppLog.objects.filter(content_type=ct, object_id=adult.pk)
    
    context = {
        'adult': adult,
        'logs': logs,
    }
    return render(request, 'AppLSD/adult_detail.html', context)

@login_required
def adult_edit(request, pk):
    adult = get_object_or_404(Adult, pk=pk)
    if request.method == 'POST':
        form = AdultForm(request.POST, instance=adult)
        if form.is_valid():
            adult = form.save(commit=False)
            adult.editado_por = request.user            # auditoria
            adult.save()
            registrar_log(
                request.user,
                adult,
                'adulto_editado',
                f'Dados do adulto {adult.name} atualizados.'
            )
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




@login_required
def aluno_list(request):
    # Captura o termo de busca
    query = request.GET.get('q', '').strip()
    
    # Base queryset
    alunos = Aluno.objects.select_related('family', 'turma').all()
    # Filtra os alunos
    if query:
        alunos = alunos.filter(
            Q(name__icontains=query) |
            Q(cpf__icontains=query) |
            Q(family__registration_number__icontains=query) |
            Q(family__responsible_name__icontains=query)  # Busca pelo responsável
        )
    # Ordena
    alunos = alunos.order_by('name')
    # Conta total ANTES da paginação
    total = alunos.count()
    
      # Paginação
    paginator = Paginator(alunos, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'alunos': page_obj,
        'query': query,
        'total': total,
    }
    
    return render(request, 'AppLSD/aluno_list.html', context)

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
            try:
                aluno = form.save(commit=False)
                aluno.criado_por = request.user # registra quem criou
                # Associa família caso venha selecionada/fixa
                if family:
                    aluno.family = family
                aluno.save()
                if aluno.family:
                    family_name = aluno.family.responsible_name
                    registrar_log(
                        request.user,
                        aluno,
                        'aluno_criado',
                        f'Aluno {aluno.name} criado e vinculado à família {aluno.family.responsible_name}.'
                    )
                    logger.info(f"Aluno {aluno.name} (ID: {aluno.pk}) criado e vinculado à família {family_name}")
                    messages.success(request, f'Aluno {aluno.name} cadastrado com sucesso!')
            #return redirect('family_detail')  # Ou outro local desejado
                    return redirect('family_detail', pk=aluno.family.pk)
                else:
                    logger.info(f"Aluno {aluno.name} (ID: {aluno.pk}) criado sem família")
                    messages.success(request, f'Aluno {aluno.name} cadastrado com sucesso!')

                    return redirect('aluno_list')  # ajuste para sua view de lista de alunos
                    
            except Exception as e:
                logger.error(f"Erro ao criar aluno: {str(e)}")
                messages.error(request, f'Erro ao cadastrar aluno: {str(e)}')
        else:
            # Exibe erros do formulário
            logger.warning(f"Formulário inválido ao criar aluno: {form.errors}")
            messages.error(request, 'Por favor, corrija os erros no formulário.')
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

    ct = ContentType.objects.get_for_model(Aluno)
    logs = AppLog.objects.filter(content_type=ct, object_id=aluno.pk)

    historico_turmas = MovimentacaoTurmaAluno.objects.filter(
        aluno=aluno
    ).order_by('-data')   # traz inclusive quando turma_destino é None

    context = {
        'aluno': aluno,
        'logs': logs,
        'historico_turmas': historico_turmas,
    }
    return render(request, 'AppLSD/aluno_detail.html', context)

@login_required
def aluno_edit(request, pk):
    # bloqueia colaboradores
    if usuario_tem_perfil(request.user, "colaborador"):
        raise PermissionDenied("Colaborador não pode editar aluno.")
    aluno = get_object_or_404(Aluno, pk=pk)
    if request.method == 'POST':
        form = AlunoForm(request.POST, instance=aluno)
        if form.is_valid():
            aluno = form.save(commit=False)
            aluno.editado_por = request.user  # auditoria
            aluno.save()
            return redirect('aluno_detail', pk=aluno.pk)
    else:
        form = AlunoForm(instance=aluno)
    
    # Contexto com valores para carregar nos campos HTML puros
    context = {
        'form': form,
        'aluno': aluno,
        
    }
  
    # Log para debug
    logger.debug(f"Ensino: {aluno.ensino}, Série: {aluno.serie}")
    
    return render(request, 'AppLSD/aluno_form.html', context)

@login_required
def aluno_delete_confirm(request, pk):
    # bloqueia colaboradores
    if usuario_tem_perfil(request.user, "colaborador"):
        raise PermissionDenied("Colaborador não pode excluir aluno.")
    aluno = get_object_or_404(Aluno, pk=pk)
    error = None

    if request.method == 'POST':
        senha = request.POST.get('senha')
        usuario = request.user
        user_autenticado = authenticate(username=usuario.username, password=senha)
        if user_autenticado is not None:
            # se quiser manter delete “real”, só delete()
            # se quiser já usar auditoria no futuro: trocar por soft_delete
            # aluno.soft_delete(request.user)
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
    """
    Exibe detalhes da turma com verificação de frequência do dia
    """
    turma = get_object_or_404(Turma, id=turma_id)
    alunos = Aluno.objects.filter(turma=turma)
    today = timezone.now().date()
     # Verificar se já existe frequência para hoje
    frequencia_hoje = FrequenciaTurma.objects.filter(
        turma=turma,
        data=today
    ).first()
   # Verificar grupos do usuário =====
    user = request.user
    tipo_perfil = None

     # Buscar o perfil do usuário (pode ter múltiplos perfis)
    perfis = user.perfis.all()
    
    if perfis.exists():
        # Pegar o primeiro perfil (ou você pode implementar lógica para múltiplos)
        tipo_perfil = perfis.first().tipo_perfil
    # DEBUG: 
    print(f"===== DEBUG TURMA DETAIL =====")
    print(f"Usuário: {user.username}")
    print(f"Tipo de Perfil: {tipo_perfil}")
    print(f"Todos os perfis: {list(perfis.values_list('tipo_perfil', flat=True))}")
    print(f"É superuser: {user.is_superuser}")
    
    # Verificar permissão do usuário
    is_coordenacao = (tipo_perfil == 'coordenacao') or user.is_superuser
    is_educadora = (tipo_perfil == 'educadora')


    print(f"is_coordenacao: {is_coordenacao}")
    print(f"is_educadora: {is_educadora}")
    print(f"Frequência hoje existe: {frequencia_hoje is not None}")
    print(f"==============================\n")

    
    # Lógica de permissões
    pode_editar = False
    pode_visualizar = False
    pode_iniciar = True
    
    if frequencia_hoje:
        # Já existe frequência hoje
        pode_iniciar = False

        if is_coordenacao:
            pode_editar = True
            pode_visualizar = True
        elif is_educadora:
            pode_visualizar = True
            pode_editar = False  # Educadora não pode editar depois de criar
        else:
            # Não existe frequência - qualquer um pode iniciar
            pode_iniciar = True

    ct = ContentType.objects.get_for_model(Turma)
    logs = AppLog.objects.filter(content_type=ct, object_id=turma.id).order_by('-criado_em')
    context = {
        'turma': turma,
        'logs': logs,
        'alunos': alunos,
        'frequencia_hoje': frequencia_hoje,
        'ja_tem_frequencia': frequencia_hoje is not None,
        'pode_editar': pode_editar,
        'pode_visualizar': pode_visualizar,
        'pode_iniciar': pode_iniciar,
        'is_coordenacao': is_coordenacao,
        'is_educadora': is_educadora,
    }
    return render(request, 'AppLSD/turma_detail.html', context)

def get_tipo_perfil(user):
    """
    Retorna o tipo de perfil do usuário
    """
    if user.is_superuser:
        return 'admin'
    
    perfis = user.perfis.all()
    if perfis.exists():
        return perfis.first().tipo_perfil
    
    return None

"""
def is_coordenacao(user):
    
    #Verifica se o usuário é coordenação
        tipo_perfil = get_tipo_perfil(user)
    return tipo_perfil == 'coordenacao' or user.is_superuser
"""

def is_educadora(user):
    """
    Verifica se o usuário é educadora   
    """
    tipo_perfil = get_tipo_perfil(user)
    return tipo_perfil == 'educadora'


class TurmaListView(ListView):
    model = Turma
    template_name = "AppLSD/turma_list.html"   # use o seu template atual
    context_object_name = "page_obj"           # para reaproveitar o template
    paginate_by = 20                          # mesmo valor do Paginator

    def get_queryset(self):
        qs = Turma.objects.all().order_by('educadora', 'sala', 'turno')

        turno = self.request.GET.get("turno")
        ano = self.request.GET.get("ano")
        faixa = self.request.GET.get("faixa_etaria")
        educadora = self.request.GET.get("educadora")

        if turno:
            qs = qs.filter(turno=turno)
        if ano:
            qs = qs.filter(ano_letivo=ano)
        if faixa:
            qs = qs.filter(faixa_etaria=faixa)
        if educadora:
            qs = qs.filter(educadora__first_name__icontains=educadora)


        return qs

@login_required
def turma_create(request):
    if request.method == 'POST':
        form = TurmaForm(request.POST)
        if form.is_valid():
            turma = form.save(commit=False)
            turma.criado_por = request.user              # auditoria
            form.save()
            registrar_log(
                request.user,
                turma,
                'turma_criada',
                f'Turma {turma.sala} criada para o turno {turma.turno}.'
            )
            return redirect('turma_list')
    else:
        form = TurmaForm()
    return render(request, 'AppLSD/turma_form.html', {'form': form})

@login_required
def turma_edit(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    if request.method == 'POST':
        form = TurmaForm(request.POST, instance=turma)
        if form.is_valid():
            turma = form.save(commit=False)
            turma.editado_por = request.user            # auditoria
            form.save()
            registrar_log(
                request.user,
                turma,
                'turma_editada',
                f'Turma {turma.sala} editada para o turno {turma.turno}.'
            )
            return redirect('turma_list')
    else:
        form = TurmaForm(instance=turma)
    return render(request, 'AppLSD/turma_form.html', {'form': form})

@login_required
def turma_delete(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    if request.method == 'POST':
        #turma.soft_delete(request.user)               # Se quiser deletar turma usar soft delte
        turma.delete()
        return redirect('turma_list')
    return render(request, 'AppLSD/turma_confirm_delete.html', {'turma': turma})

@login_required
def iniciar_frequencia_turma(request, turma_id):
    """
    Inicia uma nova frequência para a turma.
    Educadora registra frequência se não existe, senão apenas visualiza.
    """
    turma = get_object_or_404(Turma, id=turma_id)
    hoje = timezone.now().date()
    alunos = Aluno.objects.filter(turma=turma) #inclui essa na criação da auditoria
    # se quiser impedir duplicada no mesmo dia:
    chamada, created = FrequenciaTurma.objects.get_or_create(
        turma=turma,
        data=hoje,
        defaults={
            'presente': True,          # valor padrão na chamada
            'criado_por': request.user
        }
    )
    #alunos = Aluno.objects.filter(turma=turma)
    # Verificar se já existe frequência hoje
    #frequencia_existente = FrequenciaTurma.objects.filter(turma=turma, data=timezone.now().date()).first()

    if request.method == "POST":
        # processamento da presença
        for aluno in alunos:
            presente = f'presente_{aluno.id}' in request.POST
            motivo_falta = request.POST.get(f'motivo_{aluno.id}', '').strip()
            
            # Aqui é o ponto crítico: SEMPRE passar chamada=chamada
            FrequenciaAluno.objects.update_or_create(
                chamada=chamada,
                aluno=aluno,
                defaults={'presente': presente, 'motivo_falta': motivo_falta if not presente else ''}
            )
        messages.success(request, 'Frequência registrada com sucesso!')

        # depois de criar/obter chamada e salvar presenças, antes do redirect
        registrar_log(
            request.user,
            turma,
            'frequencia_criada',
            f'Frequência do dia {hoje.strftime("%d/%m/%Y")} registrada pela educadora {request.user.get_full_name() or request.user.username}.',
        )
        return redirect('frequencia_visualizar', frequencia_id=chamada.id)

    # No GET, renderize o template de registro!
    return render(request, 'AppLSD/frequencia_turma_iniciar.html', {
        'turma': turma,
        'alunos': alunos,
        'chamada': chamada,
    })

    
    # Redirecionar para página de registro de presença
    #return redirect('frequencia_turma_iniciar', turma_id=chamada.turma.id)

def visualizar_frequencia_turma(request, frequencia_id):
    """
    Visualiza a frequência em modo somente leitura
    """
    chamada = get_object_or_404(FrequenciaTurma, id=frequencia_id)
    presencas = FrequenciaAluno.objects.filter(chamada=chamada).select_related('aluno')
    
    # Buscar alunos da turma
    alunos_turma = Aluno.objects.filter(turma=chamada.turma)
    
    # Verificar permissão
    is_coordenadora = request.user.groups.filter(name='Coordenadora').exists() or request.user.is_superuser
    
    context = {
        'chamada': chamada,
        'presencas': presencas,
        'alunos_turma': alunos_turma,
        'modo_visualizacao': True,
        'pode_editar': is_coordenadora,
    }
    
    return render(request, 'AppLSD/frequencia_turma_visualizar.html', context)
"""
def is_coordenacao(user):
    return user.groups.filter(name='Coordenacao').exists() or user.is_superuser
"""

@user_passes_test(is_coordenacao)  # ✅ Apenas coordenação pode acessar
def editar_frequencia_turma(request, frequencia_id):
    """
    Edita a frequência - apenas coordenadoras
    """
    chamada = get_object_or_404(FrequenciaTurma, id=frequencia_id)
    presencas = FrequenciaAluno.objects.filter(chamada=chamada).select_related('aluno')
    alunos_turma = Aluno.objects.filter(turma=chamada.turma)
    
    if request.method == 'POST':
        chamada.editado_por = request.user             # auditoria
        chamada.save()
        # Processar alterações
        for aluno in alunos_turma:
           # Mesmo padrão da view de iniciar: checkbox marcado = presente
            presente = f'presente_{aluno.id}' in request.POST
            motivo_falta = request.POST.get(f'motivo_{aluno.id}', '').strip()
            
            # Atualizar ou criar registro
            """ 
            try:
        # Buscar registro existente
                freq_aluno = FrequenciaAluno.objects.get(chamada=chamada, aluno=aluno)
                freq_aluno.presente = presente
                freq_aluno.motivo_falta = motivo_falta if not presente else ''
                freq_aluno.save()
            except FrequenciaAluno.DoesNotExist:
            """
                # Se não existe, cria novo registro
            FrequenciaAluno.objects.update_or_create(
                chamada=chamada,
                aluno=aluno,
                defaults={
                    'presente': presente,
                    'motivo_falta': motivo_falta if not presente else ''
                }
            )
        messages.success(request, 'Frequência atualizada com sucesso!')

        registrar_log(
            request.user,
            chamada.turma,
            'frequencia_editada',
            f'Frequência de {chamada.data.strftime("%d/%m/%Y")} editada pela coordenadora ({request.user.get_full_name() or request.user.username}).',
        )
        return redirect('turma_detail', turma_id=chamada.turma.id)
            
    # Criar dicionário de presenças para facilitar no template
    presencas_dict = {p.aluno.id: p for p in presencas}
    context = {
        'chamada': chamada,
        'presencas': presencas_dict,
        'alunos_turma': alunos_turma,
        'modo_edicao': True,
    }
    
    return render(request, 'AppLSD/frequencia_turma_editar.html', context)

@login_required
def activity_detail(request, activity_id):
    atividade = get_object_or_404(Activity, id=activity_id)
    
    hoje = timezone.now().date()
    tem_frequencia_hoje = FrequenciaAtividade.objects.filter(
        atividade=atividade,
        data=hoje,
    ).exists()

    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Activity)
    logs = AppLog.objects.filter(content_type=ct, object_id=atividade.pk)

    context = {
        'atividade': atividade,
        'tem_frequencia_hoje': tem_frequencia_hoje,
        # se tiver controle de permissão, algo como:
        'is_coordenacao': request.user.groups.filter(name='Coordenacao').exists(),
        'logs': logs,
    }
    return render(request, 'AppLSD/activity_detail.html', context)
    

def activity_list(request):
    activity_list = Activity.objects.all().order_by('atividade')
    paginator = Paginator(activity_list, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'AppLSD/activity_list.html', {'page_obj': page_obj})

@login_required
def activity_create(request):
    if request.method == 'POST':
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.criado_por = request.user          # auditoria
            activity.save()
            registrar_log(
                request.user,
                activity,
                'atividade_criada',
                f'Atividade {activity.atividade} criada para o turno {activity.turno}.'
            )
            form.save_m2m()
            return redirect('activity_list')
    else:
        form = ActivityForm()
    return render(request, 'AppLSD/activity_form.html', {'form': form})

def activity_edit(request, pk):
    atividade = get_object_or_404(Activity, pk=pk)
    if request.method == 'POST':
        form = ActivityForm(request.POST, instance=atividade)
        if form.is_valid():
            atividade = form.save(commit=False)
            atividade.editado_por = request.user        # auditoria
            atividade.save()
            registrar_log(
                request.user,
                atividade,
                'atividade_editada',
                f'Atividade {atividade.atividade} editada.'
            )
            form.save_m2m()
            return redirect('activity_list')
    else:
        form = ActivityForm(instance=atividade)
    return render(request, 'AppLSD/activity_form.html', {'form': form})

def activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    if request.method == 'POST':
        #activity.soft_delete(request.user)              # se quiser soft delete
        # ou activity.delete() se ainda preferir exclusão real
        activity.delete()
        return redirect('activity_list')
    return render(request, 'AppLSD/activity_confirm_delete.html', {'activity': activity})

@login_required
def iniciar_frequencia_activity(request, activity_id):
    """
    Inicia ou registra a frequência de uma atividade.
    Educadoras registram a presença dos alunos vinculados à atividade.
    """
    atividade = get_object_or_404(Activity, id=activity_id)
    if request.user.is_superuser or request.user.groups.filter(name='Coordenacao').exists():
        # coordenação pode ver todos os alunos da atividade
        alunos = Aluno.objects.filter(atividades=atividade)
    else:
        # educadora vê só alunos de turmas dela
        alunos = Aluno.objects.filter(
            atividades=atividade,
            turma__educadora=request.user,
        )
    # Data da chamada: se vier no POST usa, senão hoje
    if request.method == 'POST' and request.POST.get('data'):
        data_chamada = date.fromisoformat(request.POST['data'])
    else:
        data_chamada = timezone.now().date()

    if request.method == 'POST':

        # verifica se já existia frequência para essa atividade e data
        ja_existia = FrequenciaAtividade.objects.filter(
            atividade=atividade,
            data=data_chamada,
        ).exists()

        # Processamento da presença
        for aluno in alunos:
            # Checkbox marcado = presente
            presente = f'presente_{aluno.id}' in request.POST
            motivo_falta = request.POST.get(f'motivo_{aluno.id}', '').strip()

            FrequenciaAtividade.objects.update_or_create(
                atividade=atividade,
                aluno=aluno,
                data=data_chamada,
                defaults={
                    'presente': presente,
                    'motivo_falta': motivo_falta if not presente else '',
                    #'editado_por': request.user,
                    'criado_por': request.user,
                }
            )

        messages.success(request, 'Frequência da atividade registrada com sucesso!')

        # Log na atividade
        registrar_log(
            request.user,
            atividade,
            'frequencia_atividade_criada' if not ja_existia else 'frequencia_atividade_editada',
            (
                f'Frequência da atividade "{atividade.atividade}" em '
                f'{data_chamada.strftime("%d/%m/%Y")} registrada pela educadora '
                f'{request.user.get_full_name() or request.user.username}.'
            ),
        )

        return redirect('frequencia_activity_visualizar', activity_id=atividade.id)

    # GET: renderiza formulário de presença
    return render(request, 'AppLSD/frequencia_activity_iniciar.html', {
        'atividade': atividade,
        'alunos': alunos,
        'data': data_chamada,
    })


@login_required
def visualizar_frequencia_activity(request, activity_id):
    atividade = get_object_or_404(Activity, id=activity_id)
    data = request.GET.get('data')  # ou outra forma de escolher o dia
    if data:
        data_chamada = date.fromisoformat(data)
    else:
        data_chamada = timezone.now().date()

    # pega a "cabeça" da chamada (se você usa o mesmo model) apenas como referência
    chamada = FrequenciaAtividade.objects.filter(
        atividade=atividade,
        data=data_chamada,
    ).order_by('id').first()

    # lista de presenças por aluno (pode ser o mesmo queryset)
    presencas = FrequenciaAtividade.objects.filter(
        atividade=atividade,
        data=data_chamada,
    ).select_related('aluno').order_by('aluno__name')

    context = {
        'atividade': atividade,
        'data_chamada': data_chamada,
        'chamada': chamada,
        'presencas': presencas,
    }
    return render(request, 'AppLSD/frequencia_activity_visualizar.html', context)


@user_passes_test(is_coordenacao)  # ✅ Apenas coordenação pode acessar
def editar_frequencia_activity(request, activity_id):
    """
    Edita a frequência - apenas coordenadoras
    """
    atividade = get_object_or_404(Activity, id=activity_id)
    alunos_atividade = Aluno.objects.filter(atividade=atividade)        
    
    if request.method == 'POST' and request.POST.get('data'):
        data_chamada = date.fromisoformat(request.POST['data'])
    else:
        data_chamada = timezone.now().date()

    presencas = FrequenciaAtividade.objects.filter(
        atividade=atividade,
        data=data_chamada
    ).select_related('aluno')

        # Processar alterações
    if request.method == 'POST':
        for aluno in alunos_atividade:
           # Mesmo padrão da view de iniciar: checkbox marcado = presente
            presente = f'presente_{aluno.id}' in request.POST
            motivo_falta = request.POST.get(f'motivo_{aluno.id}', '').strip()
            
            
            # Se não existe, cria novo registro
            FrequenciaAtividade.objects.update_or_create(
                atividade=atividade,
                aluno=aluno,
                data=data_chamada,
                defaults={
                    'presente': presente,
                    'motivo_falta': motivo_falta if not presente else '',
                    'editado_por': request.user,
                }
            )
        messages.success(request, 'Frequência atualizada com sucesso!')

        registrar_log(
            request.user,
            atividade,
            'frequencia_atividade_editada',
            f'Frequência da atividade "{atividade.atividade}" em '
            f'{data_chamada.strftime("%d/%m/%Y")} editada pela coordenadora' 
            f' ({request.user.get_full_name() or request.user.username}).',
        )
        return redirect('activity_detail', atividade.id)
            
    # Criar dicionário de presenças para facilitar no template
    presencas_dict = {p.aluno.id: p for p in presencas}
    context = {
        'atividade': atividade,
        'data_chamada': data_chamada,
        'presencas': presencas_dict,
        'alunos_atividade': alunos_atividade,
        'modo_edicao': True,
    }
    
    return render(request, 'AppLSD/frequencia_activity_editar.html', context)
    

def turma_add_alunos(request, turma_id):
    turma = get_object_or_404(Turma, pk=turma_id)
    alunos_queryset = Aluno.objects.filter(turma__isnull=True)

    # turno_oposto: se turma é Matutino, pega alunos Vespertino; se é Vespertino, pega Matutino
    if turma.turno == 'Matutino':
        alunos_queryset = alunos_queryset.filter(turno='Vespertino')
    elif turma.turno == 'Vespertino':
        alunos_queryset = alunos_queryset.filter(turno='Matutino')

    filtro = AlunoFiltroForm(request.GET or None)
    if filtro.is_valid():
        if filtro.cleaned_data['nome']:
            alunos_queryset = alunos_queryset.filter(name__icontains=filtro.cleaned_data['nome'])
        if filtro.cleaned_data['registration_number']:
            alunos_queryset = alunos_queryset.filter(family=filtro.cleaned_data['registration_number'])
        faixa = filtro.cleaned_data.get('faixa_etaria')
        if faixa:
            hoje = date.today()

            def intervalo_idade(min_idade, max_idade):
                # pessoas com idade entre min e max nasceram entre estas datas:
                data_max = date(hoje.year - min_idade, hoje.month, hoje.day)
                data_min = date(hoje.year - max_idade - 1, hoje.month, hoje.day) + timedelta(days=1)
                return data_min, data_max

            if faixa == "06-07":
                data_min, data_max = intervalo_idade(6, 7)
            elif faixa == "08-09":
                data_min, data_max = intervalo_idade(8, 9)
            elif faixa == "10-12":
                data_min, data_max = intervalo_idade(10, 12)
            elif faixa == "13-17":
                data_min, data_max = intervalo_idade(13, 17)

            alunos_queryset = alunos_queryset.filter(
                birth_date__range=(data_min, data_max)
            )
            
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
            turma_nova = form.cleaned_data.get('turma_destino')  # pode ser None
            motivo = form.cleaned_data.get('motivo')

            # Atualiza a turma do aluno (None = remove da turma)
            aluno.turma = turma_nova
            aluno.save()

            # Cria registro no histórico (permite turma_nova ou None)
            MovimentacaoTurmaAluno.objects.create(
                aluno=aluno,
                turma_origem=turma_antiga,
                turma_destino=turma_nova,
                motivo=motivo
            )

            texto_destino = turma_nova if turma_nova else 'SEM TURMA'
            registrar_log(
                request.user,
                aluno,
                'aluno_movido',
                f'Aluno {aluno.name} movido da turma {turma_antiga} para {texto_destino}. Motivo: {motivo}'
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

    # Busca data filtrada via URL (GET)
    data_get = request.GET.get('data')
    if data_get:
        data = data_get

    chamada = None
    presencas_dict = {}
    if data:
        chamada = FrequenciaTurma.objects.filter(turma=turma, data=data).first()
    else:
        chamada = FrequenciaTurma.objects.filter(turma=turma).order_by('-data').first()
        data = chamada.data if chamada else None

    if chamada:
        presencas = FrequenciaAluno.objects.filter(chamada=chamada)
        presencas_dict = {p.aluno_id: p for p in presencas}

    return render(request, 'AppLSD/relatorio_presenca_turma.html', {
        'turma': turma,
        'alunos': alunos,
        'chamada': chamada,
        'data': data,
        'presencas_dict': presencas_dict,
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

""" 
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
"""

def registrar_faltas_automaticas(chamada):
    """
    Registra automaticamente como falta todos os alunos da turma
    que não foram marcados como presentes na chamada.
    
    Args:
        chamada: Objeto FrequenciaTurma
    """
        
    # Buscar todos os alunos da turma
    alunos_turma = Aluno.objects.filter(turma=chamada.turma)
    
    # Alunos que já têm registro nesta chamada
    alunos_com_registro = FrequenciaAluno.objects.filter(
        chamada=chamada
    ).values_list('aluno_id', flat=True)
    
    # Alunos sem registro = faltaram
    alunos_sem_registro = alunos_turma.exclude(id__in=alunos_com_registro)
    
    # Registrar as faltas
    faltas_criadas = 0
    for aluno in alunos_sem_registro:
        FrequenciaAluno.objects.create(
            chamada=chamada,
            aluno=aluno,
            presente=False
        )
        faltas_criadas += 1
    
    return faltas_criadas

def finalizar_chamada(request, chamada_id):
    chamada = FrequenciaTurma.objects.get(id=chamada_id)
    
    # Registrar faltas automaticamente
    faltas_criadas = registrar_faltas_automaticas(chamada)
    
    messages.success(request, f"Chamada finalizada! {faltas_criadas} faltas registradas automaticamente.")
    return redirect(request, 'AppLSD/home_relatorios.html')


#Exportação em excel das listas Família, Aluno e Adulto
@login_required
def export_family_excel(request):
    campos = request.GET.getlist('campos')
    
    # Se nenhum campo selecionado, usa padrão
    if not campos:
        campos = ['registration_number', 'responsible_name', 'cpf', 'telephone', 'address', 'neighborhood', 'status']
    
    # DEBUG - Ver quais campos foram selecionados
    print(f"Campos selecionados: {campos}")
    
    families = Family.objects.all().order_by('registration_number')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Famílias"
    
    # Dicionário com TODOS os campos possíveis
    campos_info = {
        'registration_number': {'label': 'Inscrição', 'field': 'registration_number'},
        'responsible_name': {'label': 'Responsável', 'field': 'responsible_name'},
        'cpf': {'label': 'CPF', 'field': 'cpf'},
        'rg': {'label': 'RG', 'field': 'rg'},
        'nis': {'label': 'NIS', 'field': 'nis'},
        'birth_date': {'label': 'Data de Nascimento', 'field': 'birth_date'},
        'sex': {'label': 'Sexo', 'field': 'sex'},
        'telephone': {'label': 'Telefone', 'field': 'telephone'},
        'telephone_2': {'label': 'Telefone 2', 'field': 'telephone_2'},
        'address': {'label': 'Endereço', 'field': 'address'},
        'number': {'label': 'Número', 'field': 'number'},
        'neighborhood': {'label': 'Bairro', 'field': 'neighborhood'},
        'cep': {'label': 'CEP', 'field': 'cep'},
        'reference_point': {'label': 'Ponto de Referência', 'field': 'reference_point'},
        'marital_status': {'label': 'Estado Civil', 'field': 'marital_status'},
        'education': {'label': 'Escolaridade', 'field': 'education'},
        'race': {'label': 'Raça', 'field': 'race'},
        'occupation': {'label': 'Ocupação', 'field': 'occupation'},
        'salary_range': {'label': 'Faixa Salarial', 'field': 'salary_range'},
        'num_residents': {'label': 'Nº de Moradores', 'field': 'num_residents'},
        'status': {'label': 'Status', 'field': 'status'},
    }
    
    # Cabeçalhos NA ORDEM dos campos selecionados
    headers = []
    for campo in campos:
        if campo in campos_info:
            headers.append(campos_info[campo]['label'])
    
    ws.append(headers)
    
    # Estilo do cabeçalho
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Dados NA ORDEM dos campos selecionados
    for family in families:
        row = []
        for campo in campos:
            if campo in campos_info:
                field_name = campos_info[campo]['field']
                valor = getattr(family, field_name, '')
                
                # Formata data se necessário
                if campo == 'birth_date' and valor:
                    valor = valor.strftime('%d/%m/%Y')
                
                row.append(str(valor) if valor else '')
        
        ws.append(row)
    
    # Ajusta largura das colunas
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = min((max_length + 2), 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Resposta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'familias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response


@login_required
def export_aluno_excel(request):
    campos = request.GET.getlist('campos')
    
    if not campos:
        campos = ['inscricao', 'name', 'cpf', 'birth_date', 'school', 'ensino', 'serie']
    
    alunos = Aluno.objects.select_related('family', 'turma').all().order_by('name')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Alunos"
    
    # Dicionário com TODOS os campos possíveis
    campos_info = {
        'inscricao': {'label': 'Inscrição', 'field': 'family__registration_number'},
        'name': {'label': 'Nome', 'field': 'name'},
        'cpf': {'label': 'CPF', 'field': 'cpf'},
        'nis': {'label': 'NIS', 'field': 'nis'},
        'birth_date': {'label': 'Data de Nascimento', 'field': 'birth_date'},
        'idade': {'label': 'Idade', 'field': 'age'},
        'sex': {'label': 'Sexo', 'field': 'sex'},
        'school': {'label': 'Escola', 'field': 'school'},
        'ensino': {'label': 'Ensino', 'field': 'ensino'},
        'serie': {'label': 'Série', 'field': 'serie'},
        'turno': {'label': 'Turno', 'field': 'turno'},
        'responsavel': {'label': 'Responsável', 'field': 'family__responsible_name'},
    }
    
    # Cabeçalhos NA ORDEM dos campos selecionados
    headers = []
    for campo in campos:
        if campo in campos_info:
            headers.append(campos_info[campo]['label'])
    
    ws.append(headers)
    
    # Estilo do cabeçalho
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Dados NA ORDEM dos campos selecionados
    for aluno in alunos:
        row = []
        for campo in campos:
            if campo in campos_info:
                valor = ''
                
                # Campos especiais
                if campo == 'inscricao':
                    valor = aluno.family.registration_number if aluno.family else ''
                elif campo == 'responsavel':
                    valor = aluno.family.responsible_name if aluno.family else ''
                elif campo == 'birth_date':
                    valor = aluno.birth_date.strftime('%d/%m/%Y') if aluno.birth_date else ''
                elif campo == 'idade':
                    valor = aluno.age if hasattr(aluno, 'age') else ''
                else:
                    valor = getattr(aluno, campo, '')
                
                row.append(str(valor) if valor else '')
        
        ws.append(row)
    
    # Ajusta largura das colunas
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = min((max_length + 2), 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'alunos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response

@login_required
def export_adult_excel(request):
     # DEBUG - Lista todos os campos do modelo
    adult = Adult.objects.first()
    if adult:
        print("===== CAMPOS DISPONÍVEIS NO MODELO ADULT =====")
        for field in adult._meta.get_fields():
            print(f"Campo: {field.name}")
        print("=" * 50)
    campos = request.GET.getlist('campos')
    
    if not campos:
        campos = ['inscricao', 'name', 'cpf', 'birth_date', 'parentesco', 'ocupacao']
    
    adults = Adult.objects.select_related('family').all().order_by('name')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Adultos"
    
    # Dicionário com TODOS os campos possíveis
    campos_info = {
        'inscricao': {'label': 'Inscrição', 'field': 'family__registration_number'},
        'name': {'label': 'Nome', 'field': 'name'},
        'cpf': {'label': 'CPF', 'field': 'cpf'},
        'birth_date': {'label': 'Data de Nascimento', 'field': 'birth_date'},
        'idade': {'label': 'Idade', 'field': 'age'},
        'sex': {'label': 'Sexo', 'field': 'sex'},
        'education': {'label': 'Escolaridade', 'field': 'education'},
        'parentesco': {'label': 'Parentesco', 'field': 'parentesco'},
        'ocupacao': {'label': 'Ocupação', 'field': 'ocupacao'},
        'renda': {'label': 'Renda', 'field': 'income'},
        'telephone': {'label': 'Telefone', 'field': 'telephone'},
        'responsavel': {'label': 'Responsável', 'field': 'family__responsible_name'},
    }
    
    # Cabeçalhos NA ORDEM dos campos selecionados
    headers = []
    for campo in campos:
        if campo in campos_info:
            headers.append(campos_info[campo]['label'])
    
    ws.append(headers)
    
    # Estilo do cabeçalho
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    # Dados NA ORDEM dos campos selecionados
    for adult in adults:
        row = []
        for campo in campos:
            if campo in campos_info:
                valor = ''
                
                # Campos especiais
                if campo == 'inscricao':
                    valor = adult.family.registration_number if adult.family else ''
                elif campo == 'responsavel':
                    valor = adult.family.responsible_name if adult.family else ''
                elif campo == 'birth_date':
                    valor = adult.birth_date.strftime('%d/%m/%Y') if adult.birth_date else ''
                elif campo == 'idade':
                    valor = adult.age if hasattr(adult, 'age') else ''
                elif campo == 'is_working':
                    valor = 'Sim' if adult.is_working == 'sim' else 'Não' if adult.is_working else ''
                else:
                    valor = getattr(adult, campo, '')
                
                row.append(str(valor) if valor else '')
        
        ws.append(row)
    
    # Ajusta largura das colunas
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = min((max_length + 2), 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'adultos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response
