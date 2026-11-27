"""Edicao de adulto vinculada a Person; criacao existente recebe apenas a guarda de perfil."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from AppLSD.adulto_permissoes import validar_operador_adulto
from AppLSD.adulto_person_services import (
    CAMPOS_EDICAO_ADULTO, criar_token_edicao_adulto, salvar_edicao_adulto,
)
from AppLSD.forms import AdultForm
from AppLSD.models import Adult, Family, Person


def _adicionar_erros(form, exc):
    if hasattr(exc, 'message_dict'):
        for campo, erros in exc.message_dict.items():
            for erro in erros:
                form.add_error(campo if campo in form.fields else None, erro)
    else:
        for erro in exc.messages:
            form.add_error(None, erro)


@login_required
@require_http_methods(['GET', 'POST'])
@never_cache
def adult_edit(request, pk):
    operador = validar_operador_adulto(request.user)
    status = 200
    if request.method == 'GET':
        try:
            adulto, token = criar_token_edicao_adulto(usuario=operador, adulto_id=pk)
        except (Adult.DoesNotExist, Family.DoesNotExist, Person.DoesNotExist):
            raise Http404('Cadastro nao encontrado.') from None
        except ValidationError as exc:
            raise Http404('Cadastro indisponivel para edicao.') from exc
        familia = adulto.family
        form = AdultForm(instance=adulto)
    else:
        adulto = get_object_or_404(Adult, pk=pk, excluido=False)
        familia = adulto.family
        familia_id_original = adulto.family_id
        token = request.POST.get('token_identificacao', '')
        form = AdultForm(request.POST, instance=adulto)
        if form.is_valid():
            familia_enviada = form.cleaned_data.get('family')
            if familia_enviada is None or familia_enviada.pk != familia_id_original:
                form.add_error('family', 'Mudanca de familia exige fluxo proprio.')
                status = 400
            else:
                dados = {campo: form.cleaned_data[campo]
                         for campo in CAMPOS_EDICAO_ADULTO if campo in form.cleaned_data}
                try:
                    resultado = salvar_edicao_adulto(
                        usuario=operador, adulto_id=pk, alteracoes=dados, token=token)
                except ValidationError as exc:
                    _adicionar_erros(form, exc)
                    status = 400
                except (Adult.DoesNotExist, Family.DoesNotExist, Person.DoesNotExist):
                    form.add_error(None, 'Cadastro alterado ou removido. Reabra a pagina.')
                    status = 400
                else:
                    if resultado['alterado']:
                        messages.success(request, 'Adulto atualizado.' if resultado['person_id'] is None
                            else 'Adulto atualizado com identificacao sincronizada.')
                    return redirect('family_detail', pk=resultado['adulto'].family_id)
        else:
            status = 400
        # Em qualquer erro conserva o token recebido; nao renova a versao do POST.
    return render(request, 'AppLSD/adult_form.html', {
        'form': form, 'adult': adulto, 'family': familia,
        'token_identificacao': token,
        'identificacao_pendente': adulto.person_id is None,
        'edicao_person_integrada': True,
    }, status=status)
