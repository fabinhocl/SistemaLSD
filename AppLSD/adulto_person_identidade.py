"""Guardas conservadoras. Nao salva nem reutiliza identidades."""
import re
import unicodedata
from django.core.exceptions import ValidationError
from AppLSD.models import Family, Adult, Aluno, Person


def cpf_digitos(valor):
    return re.sub(r"[^0-9]", "", str(valor or ""))


def nome_normalizado(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def validar_identidade_adulto(adulto, *, excluir_origem_id=None, excluir_person_id=None):
    """Coincidencia apenas bloqueia para revisao; nunca associa cadastros.

    Nome igual com data igual ou desconhecida e considerado ambiguo.
    Inclui legados e excluidos na pesquisa, independentemente de familia.
    """
    chave = nome_normalizado(adulto.name)
    documento = cpf_digitos(adulto.cpf)
    if not chave:
        raise ValidationError({"name": "Informe o nome."})
    for modelo, campo_nome in ((Family, "responsible_name"), (Adult, "name"),
                                (Aluno, "name"), (Person, "full_name")):
        for pk, nome, data, cpf in modelo._base_manager.values_list(
                "pk", campo_nome, "birth_date", "cpf").iterator():
            if modelo is Adult and pk == excluir_origem_id:
                continue
            if modelo is Person and pk == excluir_person_id:
                continue
            if documento and cpf_digitos(cpf) == documento:
                raise ValidationError({"cpf": "CPF ja localizado em outro cadastro. Requer revisao de identidade; nenhuma associacao automatica foi feita."})
            if nome_normalizado(nome) == chave and (
                    data is None or adulto.birth_date is None or data == adulto.birth_date):
                raise ValidationError({"name": "Possivel identidade ja cadastrada (nome e nascimento igual ou desconhecido). Requer revisao; nao sera criada outra Person automaticamente."})
