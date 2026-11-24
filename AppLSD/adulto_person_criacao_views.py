"""Entrada HTTP de criacao integrada. Nao regulariza adultos existentes."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from AppLSD.adulto_permissoes import validar_operador_adulto
from AppLSD.adulto_person_services import CAMPOS_EDICAO_ADULTO
from AppLSD.adulto_person_criacao_services import criar_adulto_com_person
from AppLSD.adulto_person_views import _adicionar_erros
from AppLSD.forms import AdultForm
from AppLSD.models import Family


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def adult_create(request):
    operador = validar_operador_adulto(request.user)
    valor = request.GET.get("family_id")
    if not valor:
        return redirect("family_list")
    try:
        familia_id = int(valor)
        if familia_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise Http404("Familia nao encontrada.") from None
    familia = get_object_or_404(Family, pk=familia_id, excluido=False)
    form = AdultForm(request.POST if request.method == "POST" else None,
                     initial={"family": familia.pk})
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            enviada = form.cleaned_data.get("family")
            if enviada is None or enviada.pk != familia.pk:
                form.add_error("family", "Familia enviada difere da familia da pagina. Reabra o cadastro.")
                form.add_error(None, "Familia divergente: nenhum cadastro foi criado.")
            else:
                dados = {campo: form.cleaned_data[campo] for campo in CAMPOS_EDICAO_ADULTO
                         if campo in form.cleaned_data}
                try:
                    resultado = criar_adulto_com_person(
                        usuario=operador, familia_id=familia.pk, dados=dados)
                except ValidationError as exc:
                    _adicionar_erros(form, exc)
                except Family.DoesNotExist:
                    form.add_error(None, "Familia removida. Reabra o cadastro.")
                except IntegrityError:
                    form.add_error(None, "Conflito de cadastro. Reabra e confira antes de tentar novamente.")
                except OperationalError:
                    form.add_error(None, "Banco indisponivel ou ocupado. Reabra o cadastro e confira antes de tentar novamente.")
                else:
                    messages.success(request, "Adulto cadastrado com identificacao Person vinculada.")
                    return redirect("family_detail", pk=resultado["adulto"].family_id)
    return render(request, "AppLSD/adult_form.html", {
        "form": form, "family": familia, "criacao_person_integrada": True,
    }, status=status)
