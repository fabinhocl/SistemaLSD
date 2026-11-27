"""Entrada HTTP integrada. Desligamento continua na view especifica existente."""
from copy import copy
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from AppLSD.forms import AlunoForm
from AppLSD.models import Aluno, Family, MotivoDesligamentoChoices
from AppLSD.utils import pode_desligar_assistido
from AppLSD.aluno_person_permissoes import validar_operador_aluno
from AppLSD.aluno_person_services import (
    CAMPOS_ALUNO, criar_aluno_com_person, salvar_edicao_aluno,
    criar_token_edicao_aluno, bloquear_identidades_aluno, validar_token_aluno, _ler,
)


def _erros(form, exc):
    if hasattr(exc, "message_dict"):
        for campo, erros in exc.message_dict.items():
            for erro in erros:
                form.add_error(campo if campo in form.fields else None, erro)
    else:
        for erro in exc.messages:
            form.add_error(None, erro)


def _configurar(form, familia, operador, *, novo):
    if familia:
        form.fields["family"].queryset = Family.objects.filter(pk=familia.pk, excluido=False)
        form.fields["family"].widget = forms.HiddenInput()
    else:
        form.fields["family"].queryset = Family.objects.filter(excluido=False)
    if novo or (form.instance.status_lsd != "desligado" and not pode_desligar_assistido(operador)):
        form.fields["status_lsd"].choices = [(v, r) for v, r in form.fields["status_lsd"].choices if v != "desligado"]


def _render(request, form, familia, operador, *, aluno=None, token="", status=200, abrir_modal=False):
    return render(request, "AppLSD/aluno_form.html", {
        "form": form, "family": familia, "aluno": aluno,
        "aluno_person_integrado": True, "token_aluno_person": token,
        "identificacao_pendente": bool(aluno and not aluno.person_id),
        "pode_desligar_aluno_person": bool(aluno and pode_desligar_assistido(operador)),
        "motivos_desligamento": MotivoDesligamentoChoices.choices,
        "abrir_modal_desligamento": abrir_modal,
    }, status=status)


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def aluno_create(request):
    operador = validar_operador_aluno(request.user, criar=True)
    valor = request.GET.get("family_id")
    familia = None
    if valor:
        try:
            fid = int(valor)
            if fid <= 0:
                raise ValueError
        except (ValueError, TypeError):
            raise Http404("Familia nao encontrada.") from None
        familia = get_object_or_404(Family, pk=fid, excluido=False)
    form = AlunoForm(request.POST if request.method == "POST" else None,
                     initial={"family": familia.pk} if familia else {})
    _configurar(form, familia, operador, novo=True)
    if request.method == "POST":
        if request.POST.get("acao"):
            form.is_valid()
            form.add_error(None, "Acao nao permitida na criacao.")
        elif form.is_valid():
            enviada = form.cleaned_data["family"]
            if familia and enviada.pk != familia.pk:
                form.add_error(None, "Familia enviada difere da pagina. Reabra o cadastro.")
            else:
                try:
                    resultado = criar_aluno_com_person(usuario=operador, familia_id=enviada.pk,
                        dados={c: form.cleaned_data[c] for c in CAMPOS_ALUNO if c in form.cleaned_data})
                except ValidationError as exc:
                    _erros(form, exc)
                except Family.DoesNotExist:
                    form.add_error(None, "Familia removida. Reabra o cadastro.")
                except (IntegrityError, OperationalError):
                    form.add_error(None, "Banco ocupado, indisponivel ou cadastro em conflito. Reabra e confira antes de tentar novamente.")
                else:
                    messages.success(request, "Assistido cadastrado com identificacao Person vinculada.")
                    return redirect("family_detail", pk=resultado["aluno"].family_id)
        return _render(request, form, familia, operador, status=400)
    return _render(request, form, familia, operador)


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def aluno_edit(request, pk):
    operador = validar_operador_aluno(request.user)
    if request.method == "GET":
        try:
            aluno, token = criar_token_edicao_aluno(usuario=operador, aluno_id=pk)
        except (Aluno.DoesNotExist, Family.DoesNotExist):
            raise Http404("Cadastro nao encontrado.") from None
        except ValidationError:
            raise Http404("Cadastro indisponivel para edicao.") from None
        familia = get_object_or_404(Family, pk=aluno.family_id)
        form = AlunoForm(instance=aluno)
        _configurar(form, familia, operador, novo=False)
        return _render(request, form, familia, operador, aluno=aluno, token=token)

    aluno = get_object_or_404(Aluno, pk=pk)
    familia = get_object_or_404(Family, pk=aluno.family_id)
    token = request.POST.get("token_aluno_person", "")
    acao = request.POST.get("acao", "")
    if acao == "confirmar_desligamento":
        # Nao salva os campos cadastrais do POST. Usa permissao/senha/motivo
        # e efeitos operacionais do endpoint canonico, sem duplicar o servico.
        try:
            with transaction.atomic():
                bloquear_identidades_aluno()
                atual, pessoa, fam = _ler(pk, bloquear=True)
                validar_token_aluno(usuario=operador, aluno=atual, pessoa=pessoa, familia=fam, token=token)
                operador = validar_operador_aluno(operador)
                if not pode_desligar_assistido(operador):
                    raise PermissionDenied(
                        "Desligamento individual é restrito ao Serviço Social, "
                        "à Coordenação e ao superusuário ativo."
                    )
                if not request.POST.get("senha") or not operador.check_password(request.POST["senha"]):
                    raise ValidationError("Informe corretamente sua senha para confirmar o desligamento.")
                if request.POST.get("motivo", "").strip() not in MotivoDesligamentoChoices.values:
                    raise ValidationError("Selecione um motivo valido de desligamento.")
                from AppLSD.views_templates import desativar_aluno
                request.user = operador
                resposta = desativar_aluno(request, aluno_id=pk)
                if resposta.status_code != 302:
                    raise ValidationError("Desligamento nao concluido. Confira os dados ou utilize a tela especifica.")
                return resposta
        except (Aluno.DoesNotExist, Family.DoesNotExist):
            raise Http404("Cadastro nao encontrado.") from None
        except ValidationError as exc:
            form = AlunoForm(instance=aluno)
            _configurar(form, familia, operador, novo=False)
            form.is_valid()
            # Unbound forms recebem ErrorDict vazio para mostrar erro global.
            from django.forms.utils import ErrorDict
            form._errors = ErrorDict()
            form.cleaned_data = {}
            _erros(form, exc)
            return _render(request, form, familia, operador, aluno=aluno, token=token, status=400, abrir_modal=True)
        except (IntegrityError, OperationalError):
            form = AlunoForm(instance=aluno)
            from django.forms.utils import ErrorDict
            form._errors = ErrorDict()
            form.cleaned_data = {}
            form.add_error(None, "Operacao indisponivel. Reabra e confira o cadastro.")
            _configurar(form, familia, operador, novo=False)
            return _render(request, form, familia, operador, aluno=aluno, token=token, status=400, abrir_modal=True)

    form = AlunoForm(request.POST, instance=copy(aluno))
    _configurar(form, familia, operador, novo=False)
    valido = form.is_valid()
    if acao:
        form.add_error(None, "Acao nao reconhecida.")
    elif valido:
        enviada = form.cleaned_data["family"]
        if enviada.pk != aluno.family_id:
            form.add_error(None, "Troca de familia exige fluxo proprio.")
        else:
            try:
                resultado = salvar_edicao_aluno(usuario=operador, aluno_id=pk, token=token,
                    alteracoes={c: form.cleaned_data[c] for c in CAMPOS_ALUNO if c in form.cleaned_data})
            except ValidationError as exc:
                _erros(form, exc)
            except (Aluno.DoesNotExist, Family.DoesNotExist):
                raise Http404("Cadastro nao encontrado.") from None
            except (IntegrityError, OperationalError):
                form.add_error(None, "Banco ocupado, indisponivel ou cadastro em conflito. Reabra e confira antes de tentar novamente.")
            else:
                if resultado["person_id"] is None:
                    messages.success(request, "Assistido atualizado. Cadastro ainda sem Person: identidade nao alterada.")
                else:
                    messages.success(request, "Assistido atualizado com identificacao sincronizada.")
                return redirect("aluno_detail", pk=pk)
    return _render(request, form, familia, operador, aluno=aluno, token=token, status=400)
