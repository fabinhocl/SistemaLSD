"""Criacao conservadora de Adult + Person, sem reutilizacao automatica."""
from collections.abc import Mapping
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from AppLSD.models import Family, Adult, Aluno, Person
from AppLSD.adulto_permissoes import validar_operador_adulto
from AppLSD.adulto_person_services import CAMPOS_EDICAO_ADULTO, _estado, _hash
from AppLSD.adulto_person_identidade import cpf_digitos, validar_identidade_adulto
from AppLSD.utils import registrar_log


def _bloquear_identidades():
    # Person.cpf nao e unico; serializa pesquisas de ausencia e insercoes.
    # Bloqueio conservador temporario das quatro tabelas, nao apenas da familia.
    tabelas = sorted(m._meta.db_table for m in (Family, Adult, Aluno, Person))
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '5s'")
        cursor.execute("LOCK TABLE " + ", ".join(connection.ops.quote_name(t) for t in tabelas)
                       + " IN SHARE ROW EXCLUSIVE MODE")


def criar_adulto_com_person(*, usuario, familia_id, dados):
    operador = validar_operador_adulto(usuario)
    if connection.vendor != "postgresql" or connection.alias != "default":
        raise ValidationError("Este fluxo exige PostgreSQL no banco default.")
    if not isinstance(dados, Mapping) or set(dados) - CAMPOS_EDICAO_ADULTO:
        raise ValidationError("Dados de criacao contem campos nao permitidos.")
    with transaction.atomic():
        _bloquear_identidades()
        get_user_model().objects.select_for_update().get(pk=operador.pk)
        operador = validar_operador_adulto(operador)
        familia = Family.objects.select_for_update().get(pk=familia_id)
        if familia.excluido:
            raise ValidationError("Familia excluida nao pode receber cadastro por este fluxo.")
        familia_antes = _hash(_estado(familia))
        adulto = Adult(family=familia, **dict(dados))
        adulto.name = str(adulto.name or "").strip()
        valor = adulto.cpf
        if valor is None or not str(valor).strip():
            adulto.cpf = None
        else:
            digitos = cpf_digitos(valor)
            if len(digitos) != 11:
                raise ValidationError({"cpf": "CPF invalido."})
            adulto.cpf = f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
        genero = {"Feminino": "F", "Masculino": "M"}.get(adulto.sex)
        if genero is None:
            raise ValidationError({"sex": "Informe o sexo para identificar a pessoa."})
        adulto.criado_por = operador
        adulto.full_clean()
        validar_identidade_adulto(adulto)
        pessoa = Person(family=familia, full_name=adulto.name,
                        birth_date=adulto.birth_date, gender=genero,
                        cpf=cpf_digitos(adulto.cpf) or None)
        pessoa.full_clean()
        esperado_p = _estado(pessoa)
        pessoa.save()
        esperado_p[Person._meta.pk.attname] = pessoa.pk
        adulto.person = pessoa
        adulto.full_clean()
        esperado_a = _estado(adulto)
        adulto.save()
        esperado_a.update({Adult._meta.pk.attname: adulto.pk,
                           "criado_em": adulto.criado_em, "editado_em": adulto.editado_em})
        registrar_log(operador, pessoa, "person_criada",
                      f"Identidade criada pelo cadastro Adult#{adulto.pk}.")
        registrar_log(operador, adulto, "adulto_criado",
                      f"Cadastro criado com Person#{pessoa.pk}. CPF informado: {'sim' if adulto.cpf else 'nao'}.")
        if _hash(_estado(Person.objects.get(pk=pessoa.pk))) != _hash(esperado_p):
            raise ValidationError("Person sofreu alteracao inesperada; criacao cancelada.")
        if _hash(_estado(Adult.objects.get(pk=adulto.pk))) != _hash(esperado_a):
            raise ValidationError("Adult sofreu alteracao inesperada; criacao cancelada.")
        if _hash(_estado(Family.objects.get(pk=familia.pk))) != familia_antes:
            raise ValidationError("Familia sofreu alteracao inesperada; criacao cancelada.")
        return {"adulto": adulto, "person_id": pessoa.pk}
