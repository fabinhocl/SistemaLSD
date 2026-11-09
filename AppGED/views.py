from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from AppLSD.permissoes import require_any_perfil
from AppLSD.utils import usuario_tem_perfil
from .models import (
    Setor, Categoria, Documento, TipoDocumento, CampoMetadado,
    Documento, MetadadoValor, VersaoDocumento, Tag,
    PermissaoSetor, LogAuditoria
)
from .forms import DocumentoForm, DocumentoFilterForm, SetorForm, CategoriaForm, TipoDocumentoForm, CampoMetadadoForm
from .permissions import usuario_pode_administrar_ged


@login_required 
@user_passes_test(usuario_pode_administrar_ged)
def administracao_ged(request):
    context = {
        'total_setores': Setor.objects.filter(ativo=True).count(),
        'total_categorias': Categoria.objects.filter(ativo=True).count(),
        'total_tipos': TipoDocumento.objects.filter(ativo=True).count(),
        'total_campos': CampoMetadado.objects.filter(ativo=True).count(),
    }

    return render(
        request,
        'AppGED/administracao/dashboard.html',
        context
    )

@require_any_perfil('admin', 'administrativo', 'diretoria', 'financeiro')
def dashboard(request):
    """Dashboard do GED"""
    context = {
        'total_documentos': Documento.objects.count(),
        'documentos_recentes': Documento.objects.all()[:10],
        'setores': Setor.objects.filter(ativo=True),
    }
    return render(request, 'AppGED/dashboard.html', context)

@require_any_perfil('admin', 'administrativo')
def configuracao_dashboard(request):
    return render(
        request,
        'AppGED/configuracao/dashboard.html'
    )


def documentos_acessiveis(user):
    if user.is_superuser:
        return Documento.objects.all()

    setores_ids = PermissaoSetor.objects.filter(
        user=user,
        pode_visualizar=True
    ).values_list('setor_id', flat=True)

    categorias_ids = PermissaoCategoria.objects.filter(
        user=user,
        pode_visualizar=True
    ).values_list('categoria_id', flat=True)

    return Documento.objects.filter(
        Q(setor_id__in=setores_ids) |
        Q(categoria_id__in=categorias_ids)
    ).distinct()

@login_required
def lista_documentos(request):
    """Lista de documentos com filtros"""
    documentos = documentos_acessiveis(request.user).select_related(
        'setor', 'categoria', 'tipo_documento', 'criado_por'
    ).prefetch_related('tags', 'versoes')

    # Filtros
    form = DocumentoFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data.get('setor'):
            documentos = documentos.filter(setor=form.cleaned_data['setor'])
        if form.cleaned_data.get('categoria'):
            documentos = documentos.filter(categoria=form.cleaned_data['categoria'])
        if form.cleaned_data.get('status'):
            documentos = documentos.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('nivel_sigilo'):
            documentos = documentos.filter(nivel_sigilo=form.cleaned_data['nivel_sigilo'])
        if form.cleaned_data.get('search'):
            search = form.cleaned_data['search']
            documentos = documentos.filter(
                Q(titulo__icontains=search) |
                Q(codigo_registro__icontains=search) |
                Q(descricao__icontains=search)
            )

    # Paginaco
    paginator = Paginator(documentos, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'form': form,
        'setores': Setor.objects.filter(ativo=True),
    }
    return render(request, 'AppGED/documentos/lista.html', context)


@login_required
def detalhe_documento(request, pk):
    """Detalhe de um documento"""
    documento = get_object_or_404(
        Documento.objects.select_related(
            'setor', 'categoria', 'tipo_documento'
        ).prefetch_related('tags', 'versoes', 'metadados_valores__campo'),
        pk=pk
    )

    # Log de visualizaco
    LogAuditoria.objects.create(
        user=request.user,
        documento=documento,
        acao='visualizou',
        ip=request.META.get('REMOTE_ADDR')
    )

    context = {
        'documento': documento,
        'versoes': documento.versoes.all(),
        'metadados': documento.metadados_valores.all(),
    }
    return render(request, 'AppGED/documentos/detalhe.html', context)


@require_any_perfil('admin', 'administrativo')
def criar_documento(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)

        if form.is_valid():
            documento = form.save(commit=False)
            documento.criado_por = request.user
            documento.save()
            form.save_m2m()

            messages.success(
                request,
                'Documento criado com sucesso.'
            )

            return redirect(
                'ged:detalhe_documento',
                pk=documento.pk
            )
    else:
        form = DocumentoForm()

    return render(
        request,
        'AppGED/documentos/formulario.html',
        {'form': form}
    )

@login_required
def editar_documento(request, pk):
    """Editar documento"""
    documento = get_object_or_404(Documento, pk=pk)

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, instance=documento)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.save()
            form.save_m2m()

            # Log de edico
            LogAuditoria.objects.create(
                user=request.user,
                documento=documento,
                acao='editou',
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, 'Documento atualizado com sucesso!')
            return redirect('ged:detalhe_documento', pk=documento.pk)
    else:
        form = DocumentoForm(instance=documento)

    context = {'form': form, 'documento': documento}
    return render(request, 'AppGED/documentos/formulario.html', context)


@login_required
def upload_versao(request, pk):
    """Upload de nova versio do documento"""
    documento = get_object_or_404(Documento, pk=pk)

    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        if arquivo:
            # Criar nova versio
            versao = VersaoDocumento.objects.create(
                documento=documento,
                arquivo=arquivo,
                tamanho=arquivo.size,
                # hash_sha256 seria calculado aqui
                criado_por=request.user
            )

            # Log
            LogAuditoria.objects.create(
                user=request.user,
                documento=documento,
                acao='criou_versao',
                detalhes=f'Versio {versao.numero_versao}',
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, f'Versio {versao.numero_versao} criada com sucesso!')
            return redirect('ged:detalhe_documento', pk=documento.pk)

    context = {'documento': documento}
    return render(request, 'AppGED/documentos/upload_versao.html', context)


@login_required
def baixar_documento(request, versao_pk):
    """Baixar arquivo do documento"""
    versao = get_object_or_404(VersaoDocumento, pk=versao_pk)

    # Log de download
    LogAuditoria.objects.create(
        user=request.user,
        documento=versao.documento,
        acao='baixou',
        ip=request.META.get('REMOTE_ADDR')
    )

    from django.http import FileResponse
    response = FileResponse(versao.arquivo)
    response['Content-Disposition'] = f'attachment; filename="{versao.arquivo.name.split("/")[-1]}"'
    return response


@require_any_perfil('admin', 'administrativo')
def configurar_tipos_documento(request):
    tipos = TipoDocumento.objects.select_related(
        'categoria',
        'categoria__setor',
    ).order_by(
        'categoria__setor__nome',
        'categoria__nome',
        'nome',
    )

    return render(
        request,
        'AppGED/configuracao/tipos_lista.html',
        {
            'tipos': tipos,
        },
    )


@require_any_perfil('admin', 'administrativo')
def criar_tipo_documento(request):
    if request.method == 'POST':
        form = TipoDocumentoForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Tipo de documento cadastrado com sucesso.'
            )

            return redirect(
                'ged:configurar_tipos_documento'
            )
    else:
        form = TipoDocumentoForm()

    return render(
        request,
        'AppGED/configuracao/tipo_form.html',
        {
            'form': form,
            'titulo_pagina': 'Novo tipo de documento',
            'texto_botao': 'Salvar tipo',
        },
    )


@require_any_perfil('admin', 'administrativo')
def editar_tipo_documento(request, pk):
    tipo = get_object_or_404(
        TipoDocumento,
        pk=pk
    )

    if request.method == 'POST':
        form = TipoDocumentoForm(
            request.POST,
            instance=tipo
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Tipo de documento atualizado com sucesso.'
            )

            return redirect(
                'ged:configurar_tipos_documento'
            )
    else:
        form = TipoDocumentoForm(
            instance=tipo
        )

    return render(
        request,
        'AppGED/configuracao/tipo_form.html',
        {
            'form': form,
            'tipo': tipo,
            'titulo_pagina': 'Editar tipo de documento',
            'texto_botao': 'Salvar alterações',
        },
    )


@require_any_perfil(
    'admin',
    'administrativo',
    'diretoria',
    'financeiro',
)
def lista_setores(request):
    """Lista de setores"""
    setores = Setor.objects.filter(ativo=True).prefetch_related('categorias')
    context = {'setores': setores}
    return render(request, 'AppGED/setores/lista.html', context)

@login_required
@user_passes_test(usuario_pode_administrar_ged)
def lista_setores_admin(request):
    setores = Setor.objects.all()

    return render(
        request,
        'AppGED/administracao/setores_lista.html',
        {'setores': setores}
    )


@require_any_perfil('admin', 'administrativo')
def configurar_setores(request):
    setores = Setor.objects.all().order_by('nome')

    return render(
        request,
        'AppGED/configuracao/setores_lista.html',
        {
            'setores': setores,
        },
    )


@require_any_perfil('admin', 'administrativo')
def criar_setor(request):
    if request.method == 'POST':
        form = SetorForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Setor cadastrado com sucesso.'
            )

            return redirect('ged:configurar_setores')
    else:
        form = SetorForm()

    return render(
        request,
        'AppGED/configuracao/setor_form.html',
        {
            'form': form,
            'titulo_pagina': 'Novo setor',
            'texto_botao': 'Salvar setor',
        },
    )


@require_any_perfil('admin', 'administrativo')
def editar_setor(request, pk):
    setor = get_object_or_404(Setor, pk=pk)

    if request.method == 'POST':
        form = SetorForm(request.POST, instance=setor)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Setor atualizado com sucesso.'
            )

            return redirect('ged:configurar_setores')
    else:
        form = SetorForm(instance=setor)

    return render(
        request,
        'AppGED/configuracao/setor_form.html',
        {
            'form': form,
            'setor': setor,
            'titulo_pagina': 'Editar setor',
            'texto_botao': 'Salvar alterações',
        },
    )

@require_any_perfil('admin', 'administrativo')
def lista_categorias(request, setor_pk):
    """Lista de categorias de um setor"""
    setor = get_object_or_404(Setor, pk=setor_pk)
    categorias = Categoria.objects.filter(setor=setor, ativo=True).select_related('pai')
    context = {'setor': setor, 'categorias': categorias}
    return render(request, 'AppGED/categorias/lista.html', context)

@require_any_perfil('admin', 'administrativo')
def configurar_categorias(request):
    categorias = Categoria.objects.select_related(
        'setor',
        'pai',
    ).order_by(
        'setor__nome',
        'nivel',
        'nome',
    )

    return render(
        request,
        'AppGED/configuracao/categorias_lista.html',
        {
            'categorias': categorias,
        },
    )


@require_any_perfil('admin', 'administrativo')
def criar_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Categoria cadastrada com sucesso.'
            )

            return redirect(
                'ged:configurar_categorias'
            )
    else:
        form = CategoriaForm()

    return render(
        request,
        'AppGED/configuracao/categoria_form.html',
        {
            'form': form,
            'titulo_pagina': 'Nova categoria',
            'texto_botao': 'Salvar categoria',
        },
    )


@require_any_perfil('admin', 'administrativo')
def editar_categoria(request, pk):
    categoria = get_object_or_404(
        Categoria,
        pk=pk
    )

    if request.method == 'POST':
        form = CategoriaForm(
            request.POST,
            instance=categoria
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Categoria atualizada com sucesso.'
            )

            return redirect(
                'ged:configurar_categorias'
            )
    else:
        form = CategoriaForm(
            instance=categoria
        )

    return render(
        request,
        'AppGED/configuracao/categoria_form.html',
        {
            'form': form,
            'categoria': categoria,
            'titulo_pagina': 'Editar categoria',
            'texto_botao': 'Salvar alterações',
        },
    )


@require_any_perfil('admin', 'administrativo')
def configurar_campos_metadado(request):
    campos = CampoMetadado.objects.select_related(
        'tipo_documento',
        'tipo_documento__categoria',
        'tipo_documento__categoria__setor',
    ).order_by(
        'tipo_documento__categoria__setor__nome',
        'tipo_documento__categoria__nome',
        'tipo_documento__nome',
        'ordem',
        'nome',
    )

    return render(
        request,
        'AppGED/configuracao/campos_lista.html',
        {
            'campos': campos,
        },
    )


@require_any_perfil('admin', 'administrativo')
def criar_campo_metadado(request):
    if request.method == 'POST':
        form = CampoMetadadoForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Campo de metadado cadastrado com sucesso.'
            )

            return redirect(
                'ged:configurar_campos_metadado'
            )
    else:
        form = CampoMetadadoForm()

    return render(
        request,
        'AppGED/configuracao/campo_form.html',
        {
            'form': form,
            'titulo_pagina': 'Novo campo de metadado',
            'texto_botao': 'Salvar campo',
        },
    )


@require_any_perfil('admin', 'administrativo')
def editar_campo_metadado(request, pk):
    campo = get_object_or_404(
        CampoMetadado,
        pk=pk
    )

    if request.method == 'POST':
        form = CampoMetadadoForm(
            request.POST,
            instance=campo
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                'Campo de metadado atualizado com sucesso.'
            )

            return redirect(
                'ged:configurar_campos_metadado'
            )
    else:
        form = CampoMetadadoForm(
            instance=campo
        )

    return render(
        request,
        'AppGED/configuracao/campo_form.html',
        {
            'form': form,
            'campo': campo,
            'titulo_pagina': 'Editar campo de metadado',
            'texto_botao': 'Salvar alterações',
        },
    )

@login_required
def categorias_por_setor(request):
    setor_id = request.GET.get('setor_id')

    if not setor_id:
        return JsonResponse({
            'categorias': [],
        })

    categorias = Categoria.objects.filter(
        setor_id=setor_id,
        ativo=True,
    ).order_by(
        'nivel',
        'nome',
    )

    dados = [
        {
            'id': categoria.pk,
            'nome': str(categoria),
        }
        for categoria in categorias
    ]

    return JsonResponse({
        'categorias': dados,
    })

@login_required
def tipos_por_categoria(request):
    categoria_id = request.GET.get('categoria_id')

    if not categoria_id:
        return JsonResponse({
            'tipos': [],
        })

    tipos = TipoDocumento.objects.filter(
        categoria_id=categoria_id,
        ativo=True,
    ).order_by('nome')

    dados = [
        {
            'id': tipo.pk,
            'nome': tipo.nome,
        }
        for tipo in tipos
    ]

    return JsonResponse({
        'tipos': dados,
    })