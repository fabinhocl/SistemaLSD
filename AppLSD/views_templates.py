from pyexpat.errors import messages
from dal import autocomplete
from AppLSD.models import Family, Aluno, Turma, Activity, FrequenciaTurma, FrequenciaAluno, FrequenciaAtividade, MovimentacaoTurmaAluno, OcorrenciaAluno, Adult, AppLog, PerfilUsuario, DocumentoFamilia    
from AppLSD.utils import is_coordenacao, is_educadora, coordenacao_required, usuario_tem_perfil, get_tipo_perfil, registrar_log, TIPOS_PERFIL_VALIDOS, sincronizar_grupos_usuario # ✅ Importar as funções
from AppLSD.templatetags.perfil_tags import has_perfil
from .forms import FamilyForm, AlunoForm, TurmaForm, ActivityForm, AddAlunosToTurmaForm, AlunoFiltroForm, AlunoInlineFormSet, MoverAlunoForm, OcorrenciaAlunoForm, AdultFormSet, AdultForm, UsuarioForm, RemoverAlunoAtividadeForm
from calendar import monthrange
from django import forms
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth import authenticate 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db import transaction
from django.db.models import Count, Q, Avg, Value, CharField, Exists, OuterRef, IntegerField
from django.db.models.functions import Cast
from django.forms.models import inlineformset_factory
from django.template.loader import render_to_string
from django.views.generic import ListView
from django_xhtml2pdf.utils import generate_pdf
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
    usuarios = User.objects.all().prefetch_related('perfis').order_by('username')
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
        return redirect('home_diretoria')  # ou o nome correto do path para dashboard
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
    weekday = hoje.weekday()

    # ====== TURMAS COM STATUS DE FREQUÊNCIA ======
    turmas = Turma.objects.filter(educadora=educadora)
    
    turmas_com_status = []
    for turma in turmas:
        frequencia_turma_hoje = FrequenciaTurma.objects.filter(
            turma=turma,
            data=hoje
        ).first()

         # ✅ Usando Aluno.objects.filter em vez de turma.aluno_set
        total_alunos = Aluno.objects.filter(turma=turma).count()
        
        # DEBUG: Verificar se FrequenciaAluno existe
        freq_alunos = FrequenciaAluno.objects.filter(
            chamada__turma=turma,
            chamada__data=hoje
        )
        
        alunos_presentes_hoje = freq_alunos.filter(presente=True).count()

       
        
        turmas_com_status.append({
            'turma': turma,
            'total_alunos': total_alunos,
            'alunos_presentes': alunos_presentes_hoje,
            'frequencia_existe': frequencia_turma_hoje is not None,
            'frequencia': frequencia_turma_hoje,
            'pode_editar': is_coordenacao(educadora),
            'pode_visualizar': is_educadora(educadora) and frequencia_turma_hoje is not None,
        })
    
     # ====== ATIVIDADES COM STATUS DE FREQUÊNCIA ======
    alunos_da_educadora = Aluno.objects.filter(turma__educadora=educadora)
    
    atividades_com_alunos_da_educadora = Activity.objects.filter(
        Exists(
            alunos_da_educadora.filter(atividades=OuterRef('pk'))
        )
    )
    
    mapa_weekday = {0: 'segunda', 1: 'terca', 2: 'quarta', 3: 'quinta', 4: 'sexta'}
    valor_dia = mapa_weekday.get(weekday)


    if valor_dia:
        atividades_com_alunos_da_educadora = atividades_com_alunos_da_educadora.filter(
            dia_semana__icontains=valor_dia
        )

    # CRIAR LISTA COM STATUS DE FREQUÊNCIA ✅
    atividades_com_status = []
    for atividade in atividades_com_alunos_da_educadora:
        # Verifica se já existe pelo menos um registro de frequência hoje para esta atividade
        # e para os alunos desta educadora
        frequencia_existe = FrequenciaAtividade.objects.filter(
            atividade=atividade,
            data=hoje,
            aluno__in=alunos_da_educadora
        ).exists()

        atividades_com_status.append({
            'obj': atividade,
            'frequencia_existe': frequencia_existe
        })
    

    context = {
        'turmas_com_status': turmas_com_status,  # ✅ Com este nome
        'atividades_do_dia': atividades_com_status,
        'is_coordenacao': is_coordenacao(educadora),
        'is_educadora': is_educadora(educadora),
        'total_alunos': total_alunos,
        'alunos_presentes_hoje': alunos_presentes_hoje,
    }
    return render(request, 'AppLSD/home_educadora.html', context)

    
@login_required
def home_facilitador(request):
    facilitador_atividades = Activity.objects.filter(facilitador=request.user)
    return render(request, 'AppLSD/home_facilitador.html', {'atividades': facilitador_atividades})

@login_required
def home_assist(request):
    #print(">>> ENTROU NA HOME_ASSIST")
    servicosocial = request.user
    hoje = timezone.now().date()
    data_corte = date(hoje.year - 60, hoje.month, hoje.day)
    contexto = {
        "total_assistidos": Aluno.objects.filter(status_lsd="Frequentando").count(),
        "total_familias": Family.objects.count(),
        "total_familias_ativas": Family.objects.filter(status="ativo").count(),
        "total_adultos": Adult.objects.count(),
        "total_idosos": Adult.objects.filter(birth_date__lte=data_corte).count(),
        # "percentual_presenca": calcular_presenca_hoje(),
        "hoje": timezone.now().strftime("%d/%m/%Y"),
    }
    #hoje = timezone.now().date()
    return render(request, 'AppLSD/home_assist.html', contexto)

@login_required
def home_escola(request):

    hoje = date.today()

    # todos aniversariantes do mês (todas as turmas)
    aniversariantes_mes = (
        Aluno.objects.select_related('turma').filter(birth_date__month=hoje.month, status_lsd="Frequentando")
        .order_by('birth_date__day', 'name')
    )

    # aniversariantes do dia (subset do anterior)
    aniversariantes_dia = aniversariantes_mes.filter(birth_date__day=hoje.day)

    context = {
        'aniversariantes_mes': aniversariantes_mes,
        'aniversariantes_dia': aniversariantes_dia,
    }
    return render(request, 'AppLSD/home_escola.html', context)

@login_required
def home_diretoria(request):
    diretoria = request.user
    hoje = timezone.now().date()
    data_corte = date(hoje.year - 60, hoje.month, hoje.day)
    contexto = {
        "total_assistidos": Aluno.objects.filter(status_lsd="Frequentando").count(),
        "total_familias": Family.objects.count(),
        "total_familias_ativas": Family.objects.filter(status="ativo").count(),
        "total_adultos": Adult.objects.count(),
        "total_idosos": Adult.objects.filter(birth_date__lte=data_corte).count(),
        # "percentual_presenca": calcular_presenca_hoje(),
        "hoje": timezone.now().strftime("%d/%m/%Y"),
    }
    #hoje = timezone.now().date()
    return render(request, 'AppLSD/home_diretoria.html', contexto)
       
@login_required
def home_adm(request):
    return render(request, 'AppLSD/home_adm.html')

#Mesclagem das views de dashboard de presença e relatórios
@login_required
def dashboard_completo(request):
    today = timezone.now().date()

    turmas = Turma.objects.all()
    atividades = Activity.objects.all()
    alunos = Aluno.objects.all()

    total_alunos = Aluno.objects.filter(status_lsd='Frequentando').count()

    presentes_hoje_manha = FrequenciaAluno.objects.filter(
        aluno__turma__turno='Matutino',
        chamada__data=today,
        presente=True
    ).count()

    presentes_hoje_tarde = FrequenciaAluno.objects.filter(
        aluno__turma__turno='Vespertino',
        chamada__data=today,
        presente=True
    ).count()

    faltas_hoje = FrequenciaAluno.objects.filter(
        chamada__data=today,
        presente=False
    ).count()

    turmas_ativas = Turma.objects.count()
    atividades_ativas = Activity.objects.count()

    # médias últimos 7 dias (se ainda quiser usar nos atalhos)
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

    context = {
        "total_alunos": total_alunos,
        "presentes_hoje_manha": presentes_hoje_manha,
        "presentes_hoje_tarde": presentes_hoje_tarde,
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

    total_alunos = Aluno.objects.filter(status_lsd='Frequentando').count()
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

    ano_atual = timezone.now().year
    doc_atual = DocumentoFamilia.objects.filter(family=family, ano=ano_atual).first()

    # todos os documentos da família, mais recentes primeiro
    documentos = family.documentos.all().order_by('-criado_em')

    context = {
        "family": family,
        "logs": logs,
        "doc_atual": doc_atual,
        "documentos": documentos,
    }

    return render(request, 'AppLSD/family_detail.html', context)


def upload_documento(request, pk):
    family = get_object_or_404(Family, pk=pk)

    if request.method == "POST":
        form = DocumentoFamiliaForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.family = family
            doc.ano = timezone.now().year
            doc.save()
            return redirect("family_detail", pk=family.pk)
    else:
        form = DocumentoFamiliaForm()

    return render(request, "AppLSD/upload_documento.html", {"family": family, "form": form})


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
    show_ativas = request.GET.get('show_ativas')  # 'on' se checkbox marcado
    # queryset base
    families_qs = Family.objects.all()

    # aplica filtro se houver busca
    if query:
        families_qs = families_qs.filter(
            Q(registration_number__icontains=query) |
            Q(responsible_name__icontains=query) |
            Q(cpf__icontains=query)
        )

    # filtro de status ativo
    if show_ativas == 'on':
        families_qs = families_qs.filter(status='ativo')

    # ordenação
    families_qs = families_qs.order_by('registration_number')

    # guarda total ANTES da paginação
    total = families_qs.count()
    total_ativas = families_qs.filter(status='ativo').count()

    # paginação
    paginator = Paginator(families_qs, 50)  # 50 por página
    page_number = request.GET.get('page')
    families_page = paginator.get_page(page_number)

    context = {
        'families': families_page,  # objeto de página
        'query': query,
        'show_ativas': show_ativas,
        'total': total,
        'total_ativas': total_ativas,
    }
    return render(request, 'AppLSD/family_list.html', context)

@login_required
def family_edit(request, pk):
    family = get_object_or_404(Family, pk=pk)

    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES, instance=family)

        if form.is_valid():
            family = form.save(commit=False)
            family.editado_por = request.user
            family.save()

            registrar_log(
                request.user,
                family,
                'familia_editada',
                f'Família {family.responsible_name} atualizada.'
            )

            # Campo de arquivo único (file_info) OU múltiplos (documentos)
            # 1) Se você mantiver um único input:
            arquivo_atual = request.FILES.get('file_info')
            if arquivo_atual:
                DocumentoFamilia.objects.create(
                    family=family,
                    ano=timezone.now().year,
                    tipo='geral',
                    arquivo=arquivo_atual,
                )

            # 2) Se usar <input type="file" name="documentos" multiple>:
           

            return redirect('family_detail', pk=family.pk)
    else:
        form = FamilyForm(instance=family)

    return render(
        request,
        'AppLSD/family_form.html',
        {'form': form, 'family': family},
    )

@login_required
def family_create(request):
    if request.method == 'POST':
        form = FamilyForm(request.POST, request.FILES or None)
        formset = AlunoInlineFormSet(request.POST, request.FILES or None)

        print("Family is_valid:", form.is_valid())
        print("Family errors:", form.errors)
        print("Family non_field_errors:", form.non_field_errors())
        print("Formset is_valid:", formset.is_valid())
        print("Formset errors:", formset.errors)
        print("Formset non_form_errors:", formset.non_form_errors())

        if form.is_valid() and formset.is_valid():
            family = form.save(commit=False)
            family.criado_por = request.user  # auditoria
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

    return render(
        request,
        'AppLSD/family_form.html',
        {'form': form, 'formset': formset}
    )

@login_required
def family_update(request, pk):
    family = get_object_or_404(Family, pk=pk)
    if request.method == 'POST':
        # guarda o valor antigo de file_info antes de processar o form
        file_info_antigo = family.file_info
        form = FamilyForm(request.POST, request.FILES, instance=family)
        formset = AlunoInlineFormSet(request.POST, request.FILES, instance=family)
        if form.is_valid() and formset.is_valid():
            family = form.save(commit=False) 
            family.editado_por = request.user           # auditoria
            family.save()
            formset.save()

            print("FILES:", request.FILES)  # DEBUG
            # arquivo do documento atual (campo EXTRA no template)
            arquivo_atual = request.FILES.get('file_info')

            print("ARQUIVO_ATUAL:", arquivo_atual)  # DEBUG

            if arquivo_atual:
                ano_atual = timezone.now().year
                DocumentoFamilia.objects.filter(family=family, ano=ano_atual).delete()
                DocumentoFamilia.objects.create(
                    family=family,
                    ano=ano_atual,
                    arquivo=arquivo_atual,
                )
                # restaura o file_info antigo para continuar sendo o "documento anterior"
                family.file_info = file_info_antigo
                family.save(update_fields=['file_info'])
            return redirect('family_detail', pk=family.pk)
    else:
        form = FamilyForm(instance=family)
        formset = AlunoInlineFormSet(instance=family)
    return render(request, 'families/family_form.html', {'form': form, 'formset': formset, 'family': family},)

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
    show_frequentando = request.GET.get('show_frequentando')
    
    print('DEBUG show_frequentando =', show_frequentando)  # aqui

    # Base queryset
    alunos_qs = Aluno.objects.select_related('family', 'turma').all()
    # Filtra os alunos
    if query:
        alunos_qs = alunos_qs.filter(
            Q(name__icontains=query) |
            Q(cpf__icontains=query) |
            Q(family__registration_number__icontains=query) |
            Q(family__responsible_name__icontains=query)  # Busca pelo responsável
        )
    
    if show_frequentando == 'on':
        alunos_qs = alunos_qs.filter(status_lsd='Frequentando')  # ajuste ao valor real
    
        print(show_frequentando)
    # Ordena
    alunos_qs = alunos_qs.order_by('name')
    # Conta total ANTES da paginação
    total = alunos_qs.count()
    total_ativos = alunos_qs.filter(status_lsd='Frequentando').count()

      # Paginação
    paginator = Paginator(alunos_qs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'alunos': page_obj,
        'query': query,
        'show_frequentando': show_frequentando,
        'total': total,
        'total_ativos': total_ativos,
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

    is_educadora = request.user.groups.filter(name='Educadora').exists()

    turma_atual = aluno.turma  # ajuste se o relacionamento for outro

    ct = ContentType.objects.get_for_model(Aluno)
    logs = AppLog.objects.filter(content_type=ct, object_id=aluno.pk)

    historico_turmas = MovimentacaoTurmaAluno.objects.filter(
        aluno=aluno
    ).order_by('-data')   # traz inclusive quando turma_destino é None

    context = {
        'aluno': aluno,
        'logs': logs,
        'historico_turmas': historico_turmas,
        'is_educadora': is_educadora,
        'turma_atual': turma_atual,
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

def desativar_familia(request, familia_id):
    """
    Desativa uma família e todos os seus assistidos.
    Remove alunos de turmas e atividades, registrando no histórico.
    """
    familia = get_object_or_404(Family, id=familia_id)
    
    if request.method == 'POST':
        with transaction.atomic():
            # 1. Buscar todos os alunos da família
            alunos = Aluno.objects.filter(family=familia)
            
            # 2. Para cada aluno
            for aluno in alunos:
                # Remover de todas as atividades
                atividades = Activity.objects.filter(alunos=aluno)
                for atividade in atividades:
                    atividade.alunos.remove(aluno)
                    
                    # Registrar no histórico da atividade
                    registrar_log(
                        request.user,
                        atividade,
                        'aluno_removido_familia_desativada',
                        f'Aluno {aluno.name} removido da atividade "{atividade.atividade}" '
                        f'por desativação da família {familia.name}.'
                    )
                
                # Registrar no histórico do aluno
                registrar_log(
                    request.user,
                    aluno,
                    'aluno_removido_atividade',
                    f'Removido de todas as atividades por desativação da família.'
                )
                
                # Remover de todas as turmas (se aplicável)
                turma_atual = aluno.turma
                if turma_atual:
                    aluno.turma = None
                    aluno.save()
                    
                    # Registrar no histórico da turma
                    registrar_log(
                        request.user,
                        turma_atual,
                        'aluno_removido_familia_desativada',
                        f'Aluno {aluno.name} removido por desativação da família {familia.name}.'
                    )
                
                # Desativar o aluno
                aluno.ativo = False
                aluno.save()
                
                # Registrar no histórico do aluno
                registrar_log(
                    request.user,
                    aluno,
                    'aluno_desativado',
                    f'Aluno desativado por desativação da família {familia.name}.'
                )
            
            # 3. Desativar a família
            familia.ativo = False
            familia.save()
            
            messages.success(
                request, 
                f'Família {familia.name} desativada. '
                f'{alunos.count()} aluno(s) removido(s) de turmas e atividades.'
            )
            
            return redirect('familia_list')
    
    return render(request, 'desativar_familia.html', {'familia': familia})

def _remover_aluno_da_atividade_logic(request, aluno, atividade):
    """
    Lógica comum para remover aluno de atividade com validação de senha.
    """
    if not (request.user.is_superuser or is_coordenacao(request.user)):
        return HttpResponseForbidden('Sem permissão')

    if request.method == 'POST':
        # ✅ Validar senha
        senha = request.POST.get('senha', '')
        if not senha:
            messages.error(request, 'Senha obrigatória!')
            return False
        
        if not check_password(senha, request.user.password):
            messages.error(request, 'Senha incorreta!')
            return False

        motivo = request.POST.get('motivo', '').strip()

        atividade.alunos.remove(aluno)

        # Log na atividade
        registrar_log(
            request.user,
            atividade,
            'aluno_removido_da_atividade',
            f'Aluno {aluno.name} removido da atividade '
            f'"{atividade.atividade}". Motivo: {motivo or "não informado"}.'
        )

        # Log no aluno
        registrar_log(
            request.user,
            aluno,
            'aluno_removido_atividade',
            f'Aluno removido da atividade "{atividade.atividade}". Motivo: {motivo or "não informado"}.'
        )

        messages.success(request, 'Aluno removido da atividade.')
        return True
    return False

@login_required
def remover_aluno_da_atividade(request, activity_id, aluno_id):
    """
    Remove aluno da atividade - chamada da tela de DETALHES DA ATIVIDADE
    """
    atividade = get_object_or_404(Activity, id=activity_id)
    aluno = get_object_or_404(Aluno, id=aluno_id)

    if _remover_aluno_da_atividade_logic(request, aluno, atividade):
        return redirect('activity_detail', activity_id=atividade.id)
    
    return redirect('activity_detail', activity_id=atividade.id)


@login_required
def remover_aluno_da_atividade_por_aluno(request, aluno_id, activity_id):
    """
    Remove aluno da atividade - chamada da tela de DETALHES DO ALUNO
    URL: /alunos/<aluno_id>/remover-da-atividade/<activity_id>/
    """
    aluno = get_object_or_404(Aluno, id=aluno_id)
    atividade = get_object_or_404(Activity, id=activity_id)

    if _remover_aluno_da_atividade_logic(request, aluno, atividade):
        return redirect('aluno_detail', pk=aluno.id)
    
    return redirect('aluno_detail', pk=aluno.id)


@login_required
def turma_detail(request, turma_id):
    turma = get_object_or_404(Turma, id=turma_id)
    alunos = Aluno.objects.filter(turma=turma).order_by('name')
    total_alunos_turma = alunos.count()

    coordenacao_status = is_coordenacao(request.user)
    educadora_status = is_educadora(request.user)

    # ✅ Educadora só pode mover se for a educadora DESTA turma
    is_educadora_desta_turma = (
        educadora_status and turma.educadora == request.user
    )

    today = timezone.now().date()

    aniversariantes_mes = alunos.filter(
        birth_date__month=today.month
    ).order_by('birth_date', 'name')

    aniversariantes_dia = aniversariantes_mes.filter(birth_date__day=today.day)

    frequencia_hoje = FrequenciaTurma.objects.filter(
        turma=turma,
        data=today
    ).first()

    pode_editar = False
    pode_visualizar = False
    pode_iniciar = False

    if frequencia_hoje:
        pode_iniciar = False
        if coordenacao_status:
            pode_editar = True
            pode_visualizar = True
        elif educadora_status:
            pode_visualizar = True
            pode_editar = False
    else:
        if educadora_status or coordenacao_status:
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
        'is_coordenacao': coordenacao_status,
        'is_educadora': educadora_status,
        'total_alunos_turma': total_alunos_turma,
        'pode_adicionar_alunos': coordenacao_status,
        'pode_editar_alunos': coordenacao_status,
        # ✅ Coordenação OU educadora desta turma podem mover
        'pode_mover_alunos': coordenacao_status or is_educadora_desta_turma,
        'aniversariantes_mes': aniversariantes_mes,
        'aniversariantes_dia': aniversariantes_dia,
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
        qs = Turma.objects.all().order_by('educadora', 'grupo', 'turno')

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
                f'Turma {turma.grupo} criada para o turno {turma.turno}.'
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
                f'Turma {turma.grupo} editada para o turno {turma.turno}.'
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
    Só cria/salva frequência no POST.
    """
    turma = get_object_or_404(Turma, id=turma_id)
    hoje = timezone.now().date()
    alunos = Aluno.objects.filter(turma=turma).order_by('name')

    if request.method == "POST":
        # cria/obtém a chamada SOMENTE aqui
        chamada, created = FrequenciaTurma.objects.get_or_create(
            turma=turma,
            data=hoje,
            defaults={
                'presente': True,      # se ainda usar esse campo
                'criado_por': request.user,
            }
        )

        for aluno in alunos:
            presente = f'presente_{aluno.id}' in request.POST
            motivo_falta = request.POST.get(f'motivo_{aluno.id}', '').strip()

            FrequenciaAluno.objects.update_or_create(
                chamada=chamada,
                aluno=aluno,
                defaults={
                    'presente': presente,
                    'motivo_falta': motivo_falta if not presente else '',
                }
            )

        messages.success(request, 'Frequência registrada com sucesso!')

        registrar_log(
            request.user,
            turma,
            'frequencia_criada',
            f'Frequência do dia {hoje.strftime("%d/%m/%Y")} registrada pela educadora '
            f'{request.user.get_full_name() or request.user.username}.',
        )
        return redirect('frequencia_visualizar', frequencia_id=chamada.id)

    # GET: apenas mostra o formulário, NÃO cria chamada nem registros
    return render(
        request,
        'AppLSD/frequencia_turma_iniciar.html',
        {
            'turma': turma,
            'alunos': alunos,
            'data_hoje': hoje,
        }
    )


def visualizar_frequencia_turma(request, frequencia_id):
    """
    Visualiza a frequência em modo somente leitura
    """
    chamada = get_object_or_404(FrequenciaTurma, id=frequencia_id)
    presencas = FrequenciaAluno.objects.filter(chamada=chamada).select_related('aluno').order_by('aluno__name')
    
    # Buscar alunos da turma
    alunos_turma = Aluno.objects.filter(turma=chamada.turma).order_by('name')
    
    
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
    presencas = FrequenciaAluno.objects.filter(chamada=chamada).select_related('aluno').order_by('aluno__name')
    alunos_turma = Aluno.objects.filter(turma=chamada.turma).order_by('name')
    
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

    # alunos vinculados à atividade em ordem alfabética
    alunos_atividade = Aluno.objects.filter(
        atividades=atividade
    ).order_by('name')  # ou 'nome', conforme o campo no model

    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Activity)
    logs = AppLog.objects.filter(content_type=ct, object_id=atividade.pk)

    context = {
        'atividade': atividade,
        'tem_frequencia_hoje': tem_frequencia_hoje,
        # se tiver controle de permissão, algo como:
        'logs': logs,
        'alunos_atividade': alunos_atividade,
        'is_coordenacao': is_coordenacao(request.user), 
        
    }
    return render(request, 'AppLSD/activity_detail.html', context)
    


@login_required
def activity_list(request):
    atividades = Activity.objects.all().select_related('facilitador')

    atividade_nome = request.GET.get("atividade") or ""
    facilitador_id = request.GET.get("facilitador") or ""
    dia_semana = request.GET.get("dia_semana") or ""
    turno = request.GET.get("turno") or ""
    tipo = request.GET.get("tipo") or ""

    if atividade_nome:
        atividades = atividades.filter(atividade__icontains=atividade_nome)
    if facilitador_id:
        atividades = atividades.filter(facilitador_id=facilitador_id)
    if dia_semana:
        # ✅ CORRIGIDO: Usar icontains sem as aspas
        atividades = atividades.filter(dia_semana__icontains=dia_semana)
    if turno:
        atividades = atividades.filter(turno=turno)
    if tipo:
        atividades = atividades.filter(tipo=tipo)

    atividades = atividades.order_by('atividade')

    # Listas para os selects
    facilitadores = User.objects.filter(
        id__in=Activity.objects.values('facilitador_id')
    ).order_by('first_name').distinct()

    nomes_atividades = (
        Activity.objects.order_by('atividade')
        .values_list('atividade', flat=True)
        .distinct()
    )

    tipos_atividades = Activity.TIPO_CHOICES
    dias_semana_choices = Activity.DIAS_SEMANAS_CHOICES

    turnos = (
        Activity.objects.order_by('turno')
        .values_list('turno', flat=True)
        .distinct()
    )

    paginator = Paginator(atividades, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'facilitadores': facilitadores,
        'nomes_atividades': nomes_atividades,
        'tipos_atividades': tipos_atividades,
        'dias_semana_choices': dias_semana_choices,
        'turnos': turnos,
        'filtro_atividade': atividade_nome,
        'filtro_facilitador': facilitador_id,
        'filtro_dia_semana': dia_semana,
        'filtro_turno': turno,
        'filtro_tipo': tipo,
        'is_coordenacao': is_coordenacao(request.user),  
        'is_educadora': is_educadora(request.user),
    }
    return render(request, 'AppLSD/activity_list.html', context)



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
        alunos = Aluno.objects.filter(atividades=atividade).order_by('name')
    else:
        # educadora vê só alunos de turmas dela
        alunos = Aluno.objects.filter(
            atividades=atividade,
            turma__educadora=request.user,
        ).order_by('name')
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

    # base: só alunos frequentando
    
    alunos_queryset = Aluno.objects.filter(
        status_lsd="Frequentando",
        turma__isnull=True,          # <--- só quem não está em nenhuma turma
    )

    # excluir quem já está na turma
    alunos_queryset = alunos_queryset.exclude(turma=turma)

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


@login_required
def mover_aluno(request, aluno_id):
    aluno = get_object_or_404(Aluno, pk=aluno_id)

    # ✅ Proteção real na view (independente do template)
    is_educadora_da_turma = (
        is_educadora(request.user)
        and aluno.turma is not None
        and aluno.turma.educadora == request.user
    )

    if not (is_coordenacao(request.user) or is_educadora_da_turma):
        raise PermissionDenied

    if request.method == "POST":
        form = MoverAlunoForm(request.POST)
        if form.is_valid():
            turma_antiga = aluno.turma
            turma_nova = form.cleaned_data.get('turma_destino')
            motivo = form.cleaned_data.get('motivo')

            aluno.turma = turma_nova
            aluno.save()

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

    # alunos que ainda não estão na atividade e estão frequentando
    alunos_queryset = Aluno.objects.exclude(atividades=atividade)
    alunos_queryset = alunos_queryset.filter(status_lsd="Frequentando")

    # Se quiser restringir pelo turno da própria atividade (opcional):
    if atividade.turno == 'Matutino':
       alunos_queryset = alunos_queryset.filter(turno='Vespertino')
    elif atividade.turno == 'Vespertino':
         alunos_queryset = alunos_queryset.filter(turno='Matutino')

    # filtros de busca
    filtro = AlunoFiltroForm(request.GET or None)
    if filtro.is_valid():
        nome = filtro.cleaned_data.get("nome")
        inscricao = filtro.cleaned_data.get("registration_number")
        faixa = filtro.cleaned_data.get("faixa_etaria")

        if nome:
            alunos_queryset = alunos_queryset.filter(name__icontains=nome)

        if inscricao:
            alunos_queryset = alunos_queryset.filter(
                family=inscricao
            )

        if faixa:
            hoje = date.today()

            def intervalo_idade(min_idade, max_idade):
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

    # Form dinâmico usando o queryset filtrado
    class DinamicoAddAlunosToAtividadeForm(AddAlunosToTurmaForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["alunos"].queryset = alunos_queryset

    if request.method == "POST":
        form = DinamicoAddAlunosToAtividadeForm(request.POST)
        if form.is_valid():
            for aluno in form.cleaned_data["alunos"]:
                atividade.alunos.add(aluno)
            return redirect("activity_detail", activity_id=atividade.id)
    else:
        form = DinamicoAddAlunosToAtividadeForm()

    return render(
        request,
        "AppLSD/activity_add_alunos.html",
        {"atividade": atividade, "form": form, "filtro": filtro},
    )


def get_contexto_relatorio_turma(request, turma_id, data=None):
    turma = Turma.objects.get(id=turma_id)
    alunos = Aluno.objects.filter(turma=turma).order_by('name')

    # data vinda por GET sobrescreve o parâmetro da URL
    data_get = request.GET.get('data')
    if data_get:
        data = data_get

    chamada = None
    presencas_dict = {}

    if data:
        chamada = FrequenciaTurma.objects.filter(turma=turma, data=data).first()
    else:
        chamada = (
            FrequenciaTurma.objects
            .filter(turma=turma)
            .order_by('-data')
            .first()
        )
        data = chamada.data if chamada else None

    if chamada:
        presencas = FrequenciaAluno.objects.filter(chamada=chamada)
        presencas_dict = {p.aluno_id: p for p in presencas}

    context = {
        'turma': turma,
        'alunos': alunos,
        'chamada': chamada,
        'data': data,
        'presencas_dict': presencas_dict,
    }
    return context

@login_required
def relatorio_presenca_turma(request, turma_id, data=None):
    context = get_contexto_relatorio_turma(request, turma_id, data)
    return render(request, 'AppLSD/relatorio_presenca_turma.html', context)


@login_required
def relatorio_presenca_turma_pdf(request, turma_id, data=None):
    context = get_contexto_relatorio_turma(request, turma_id, data)

    response = HttpResponse(content_type='application/pdf')
    # se quiser forçar download, use também:
    # response['Content-Disposition'] = f'attachment; filename="relatorio_turma_{turma_id}.pdf"'

    return generate_pdf(
        'AppLSD/relatorio_presenca_turma.html',
        file_object=response,
        context=context,
    )


def get_contexto_relatorio_turma_mensal(request, turma_id):
    turma = Turma.objects.get(id=turma_id)
    alunos = list(Aluno.objects.filter(turma=turma).order_by('name'))

    mes = request.GET.get('mes')
    if not mes:
        hoje = date.today()
        mes = f"{hoje.year}-{hoje.month:02d}"

    ano, mes_num = mes.split('-')
    ano = int(ano)
    mes_num = int(mes_num)

    primeiro_dia = date(ano, mes_num, 1)
    ultimo_dia_num = monthrange(ano, mes_num)[1]
    ultimo_dia = date(ano, mes_num, ultimo_dia_num)

    # todos os dias do mês
    todos_dias = [primeiro_dia + timedelta(days=i)
                  for i in range((ultimo_dia - primeiro_dia).days + 1)]
    # apenas dias úteis (segunda a sexta)
    dias_mes = [d for d in todos_dias if d.weekday() < 5]

    # chamadas e frequências no mês todo (não precisa filtrar aqui por dia útil)
    chamadas = (FrequenciaTurma.objects
                .filter(turma=turma, data__range=(primeiro_dia, ultimo_dia)))
    chamadas_por_data = {c.data: c for c in chamadas}

    frequencias = (FrequenciaAluno.objects
                   .filter(
                       aluno__turma=turma,
                       chamada__data__range=(primeiro_dia, ultimo_dia),
                   )
                   .select_related('aluno', 'chamada'))

    freq_dict = {
        (f.aluno_id, f.chamada.data): f
        for f in frequencias
    }

    linhas = []
    for aluno in alunos:
        linha_status = []
        faltas = 0

        # percorrendo apenas dias_mes (só dias úteis)
        for dia in dias_mes:
            f = freq_dict.get((aluno.id, dia))
            if f is None:
                status = ''
            else:
                if f.presente:
                    status = 'P'
                else:
                    status = 'F'
                    faltas += 1
            linha_status.append(status)

        linhas.append({
            'aluno': aluno,
            'status_por_dia': linha_status,
            'faltas': faltas,  # só conta F em dias úteis
        })

    return {
        'turma': turma,
        'mes': mes,
        'ano': ano,
        'mes_num': mes_num,
        'dias_mes': dias_mes,
        'linhas': linhas,
    }


@login_required
def relatorio_turma_mensal_html(request, turma_id):
    context = get_contexto_relatorio_turma_mensal(request, turma_id)
    return render(request, 'AppLSD/relatorio_turma_mensal.html', context)


@login_required
def relatorio_turma_mensal_pdf(request, turma_id):
    context = get_contexto_relatorio_turma_mensal(request, turma_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="relatorio_turma_mensal_{turma_id}.pdf"'
    return generate_pdf(
        'AppLSD/relatorio_turma_mensal_pdf.html',
        file_object=response,
        context=context,
    )

def get_contexto_relatorio_atividade(request, activity_id, data=None):
    activity = Activity.objects.get(id=activity_id)

    data_get = request.GET.get('data')
    if data_get:
        data = data_get

    chamada = None
    presencas = []

    if data:
        chamada = FrequenciaTurma.objects.filter(activity=activity, data=data).first()
    else:
        chamada = (
            FrequenciaTurma.objects
            .filter(activity=activity)
            .order_by('-data')
            .first()
        )
        data = chamada.data if chamada else None

    if chamada:
        presencas = FrequenciaAluno.objects.filter(chamada=chamada)

    context = {
        'activity': activity,
        'data': data,
        'chamada': chamada,
        'presencas': presencas,
    }
    return context

@login_required
def relatorio_presenca_activity(request, activity_id, data=None):
    context = get_contexto_relatorio_atividade(request, activity_id, data)
    return render(request, 'AppLSD/relatorio_presenca_activity.html', context)


@login_required
def relatorio_presenca_activity_pdf(request, activity_id, data=None):
    context = get_contexto_relatorio_atividade(request, activity_id, data)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="relatorio_atividade_{activity_id}.pdf"'
    return generate_pdf(
        'AppLSD/relatorio_presenca_activity.html',
        file_object=response,
        context=context,
    )

def get_contexto_relatorio_aluno_mensal(request):
    aluno_id = request.GET.get('aluno_id')
    mes = request.GET.get('mes')  # YYYY-MM

    aluno = get_object_or_404(Aluno, id=aluno_id)

    # se não vier mês, você pode defaultar para mês atual
    if not mes:
        hoje = date.today()
        mes = f"{hoje.year}-{hoje.month:02d}"

    ano, mes_num = mes.split('-')
    ano = int(ano)
    mes_num = int(mes_num)

    primeiro_dia = date(ano, mes_num, 1)
    ultimo_dia_num = monthrange(ano, mes_num)[1]
    ultimo_dia = date(ano, mes_num, ultimo_dia_num)

     # --------- DIAS ÚTEIS DO MÊS (segunda a sexta) ----------
    todos_dias = [primeiro_dia + timedelta(days=i)
                  for i in range((ultimo_dia - primeiro_dia).days + 1)]
    dias_mes = [d for d in todos_dias if d.weekday() < 5]

    # --------- FREQUÊNCIA EM TURMA (planilha P/F) ----------
    freq_qs = (FrequenciaAluno.objects
               .filter(
                   aluno=aluno,
                   chamada__data__range=(primeiro_dia, ultimo_dia),
               )
               .select_related('chamada'))

    # dict data -> registro de frequência
    freq_dict = {f.chamada.data: f for f in freq_qs}

    status_por_dia = []
    faltas = 0

    for dia in dias_mes:
        f = freq_dict.get(dia)
        if f is None:
            status = ''
        else:
            if f.presente:
                status = 'P'
            else:
                status = 'F'
                faltas += 1
        status_por_dia.append(status)

    # --------- FREQUÊNCIA EM ATIVIDADES ----------
    atividades_freq = (
        FrequenciaAtividade.objects
        .filter(
            aluno=aluno,
            data__range=(primeiro_dia, ultimo_dia),
        )
        .select_related('atividade')
        .order_by('data', 'atividade__atividade')
    )

    # --------- MOVIMENTAÇÕES ENTRE TURMAS ----------
    movs = MovimentacaoTurmaAluno.objects.filter(
        aluno=aluno,
        data__date__range=(primeiro_dia, ultimo_dia),
    ).select_related('turma_origem', 'turma_destino').order_by('data')

    # --------- OCORRÊNCIAS ----------
    ocorrencias = OcorrenciaAluno.objects.filter(
        aluno=aluno,
        data__range=(primeiro_dia, ultimo_dia),
    ).order_by('data')

    context = {
        'aluno': aluno,
        'mes': mes,
        'ano': ano,
        'mes_num': mes_num,
        'dias_mes': dias_mes,
        'status_por_dia': status_por_dia,
        'faltas': faltas,
        'atividades_freq': atividades_freq,
        'movimentacoes': movs,
        'ocorrencias': ocorrencias,
    }
    return context

 
@login_required
def relatorio_mensal_aluno(request):
    context = get_contexto_relatorio_aluno_mensal(request)
    return render(request, 'AppLSD/relatorio_mensal_aluno.html', context)


@login_required
def relatorio_mensal_aluno_pdf(request):
    context = get_contexto_relatorio_aluno_mensal(request)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="relatorio_aluno_{context["aluno"].id}.pdf"'
    return generate_pdf(
        'AppLSD/relatorio_mensal_aluno_pdf.html',  # <-- novo template
        file_object=response,
        context=context,
    )


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

def get_created_at_for_instance(instance, acao):
    """
    Retorna a data/hora do primeiro log da ação informada
    para a instância (por ex. 'familia_criada').
    """
    ct = ContentType.objects.get_for_model(instance.__class__)
    log = (
        AppLog.objects
        .filter(
            content_type=ct,
            object_id=instance.pk,
            acao=acao,
        )
        .order_by('criado_em')
        .first()
    )
    return log.criado_em if log else None

#Exportação em excel das listas Família, Aluno e Adulto
@login_required
def export_family_excel(request):
    campos = request.GET.getlist('campos')

    if not campos:
        campos = [
            'criado_em', 'registration_number', 'responsible_name', 'cpf',
            'telephone', 'address', 'neighborhood', 'status'
        ]

    families = Family.objects.all().order_by('registration_number')

    wb = Workbook()
    ws = wb.active
    ws.title = "Famílias"

    campos_info = {
        'criado_em': {'label': 'Criado em'},  # novo
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

    headers = [campos_info[c]['label'] for c in campos if c in campos_info]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")

    for family in families:
        row = []
        for campo in campos:
            if campo not in campos_info:
                continue

            valor = ''
            if campo == 'criado_em':
                dt = get_created_at_for_instance(family, 'familia_criada')
                valor = dt.strftime('%d/%m/%Y %H:%M') if dt else ''
            else:
                field_name = campos_info[campo]['field']
                v = getattr(family, field_name, '')
                if campo == 'birth_date' and v:
                    v = v.strftime('%d/%m/%Y')
                valor = v

            row.append(str(valor) if valor else '')

        ws.append(row)

    # (restante da função igual: ajustar colunas, salvar response)
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
    
       
    alunos = Aluno.objects.select_related('family', 'turma').all().order_by('name')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Alunos"
    
    # Dicionário com TODOS os campos possíveis
    campos_info = {
        'criado_em': {'label': 'Criado em'},  # novo
        'inscricao': {'label': 'Inscrição', 'field': 'family__registration_number'},
        'name': {'label': 'Nome', 'field': 'name'},
        'responsavel': {'label': 'Responsável', 'field': 'family__responsible_name'},
        'cpf': {'label': 'CPF', 'field': 'cpf'},
        'nis': {'label': 'NIS', 'field': 'nis'},
        'birth_date': {'label': 'Data de Nascimento', 'field': 'birth_date'},
        'idade': {'label': 'Idade', 'field': 'idade'},
        'sex': {'label': 'Sexo', 'field': 'sex'},
        'rede_ensino': {'label': 'Rede de Ensino', 'field': 'rede_ensino'},
        'school': {'label': 'Escola', 'field': 'school'},
        'ensino': {'label': 'Ensino', 'field': 'ensino'},
        'serie': {'label': 'Série', 'field': 'serie'},
        'turno': {'label': 'Turno', 'field': 'turno'},
        'health_problem': {'label': 'Tem Problema de Saúde?', 'field': 'health_problem'},
        'special_need': {'label': 'Qual problema de Saúde?', 'field': 'special_need'},
        'uso_medicacao': {'label': 'Faz uso de Medicação?', 'field': 'uso_medicacao'},
        'qual_medicacao': {'label': 'Qual Medicação?', 'field': 'qual_medicacao'},
        'frequencia_tipo': {'label': 'Tipo de Frequência', 'field': 'frequencia_tipo'},
        'dias_semana': {'label': 'Dias da Semana', 'field': 'dias_semana'},
        'status_lsd': {'label': 'Status LSD', 'field': 'status_lsd'},
        'turma': {'label': 'Turma', 'field': 'turma__name'},
    }

    if not campos:
        campos = list(campos_info.keys())  # se não vier campos, exporta todos os campos disponíveis
    
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
                    valor = aluno.idade if hasattr(aluno, 'idade') else ''
                elif campo == 'criado_em':
                    dt = get_created_at_for_instance(aluno, 'aluno_criado')
                    valor = dt.strftime('%d/%m/%Y %H:%M') if dt else ''
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
        campos = ['criado_em', 'inscricao', 'name', 'cpf', 'birth_date', 'parentesco', 'ocupacao']
    
    adults = Adult.objects.select_related('family').all().order_by('name')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Adultos"
    
    # Dicionário com TODOS os campos possíveis
    campos_info = {
        'criado_em': {'label': 'Criado em'},
        'inscricao': {'label': 'Inscrição', 'field': 'family__registration_number'},
        'name': {'label': 'Nome', 'field': 'name'},
        'cpf': {'label': 'CPF', 'field': 'cpf'},
        'birth_date': {'label': 'Data de Nascimento', 'field': 'birth_date'},
        'idade': {'label': 'Idade', 'field': 'idade'},
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
                    valor = adult.idade if hasattr(adult, 'idade') else ''
                elif campo == 'is_working':
                    valor = 'Sim' if adult.is_working == 'sim' else 'Não' if adult.is_working else ''
                elif campo == 'criado_em':
                    dt = get_created_at_for_instance(adult, 'adulto_criado')
                    valor = dt.strftime('%d/%m/%Y %H:%M') if dt else ''
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
