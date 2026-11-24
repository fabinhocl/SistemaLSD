"""Integração da criação familiar com a identidade do responsável."""

import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection, transaction
from django.db.models import CharField, F, Func, Value

from .models import Adult, Aluno, Family, Person
from .utils import registrar_log, usuario_tem_perfil


_SEXO = {"Feminino": "F", "Masculino": "M"}


def exigir_permissao_cadastral_familia(operador):
    if operador.is_authenticated and operador.is_active and (
        usuario_tem_perfil(operador, "servicosocial")
        or usuario_tem_perfil(operador, "admin")
    ):
        return
    raise PermissionDenied(
        "Criar e editar famílias é permitido somente ao Serviço Social e Admin."
    )


def _cpf(valor):
    return re.sub(r"[^0-9]", "", valor or "")


def _bloquear_tabelas():
    if connection.vendor != "postgresql":
        raise ValidationError("O cadastro integrado de família exige PostgreSQL.")
    tabelas = ", ".join(
        connection.ops.quote_name(nome)
        for nome in sorted({m._meta.db_table for m in (Family, Person, Adult, Aluno)})
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"LOCK TABLE {tabelas} IN SHARE ROW EXCLUSIVE MODE NOWAIT")
    except OperationalError as erro:
        causa = erro.__cause__
        if (getattr(causa, "sqlstate", None) or getattr(causa, "pgcode", None)) == "55P03":
            raise ValidationError(
                "Há outro cadastro em gravação. Aguarde e tente salvar novamente."
            ) from erro
        raise


def _cpf_ja_cadastrado(cpf):
    for modelo in (Family, Person, Adult, Aluno):
        digitos = Func(
            F("cpf"), Value("[^0-9]"), Value(""), Value("g"),
            function="REGEXP_REPLACE", output_field=CharField(),
        )
        # Inclui registros excluídos quando o gerente padrão os oculta.
        if modelo._base_manager.alias(cpf_identidade=digitos).filter(
            cpf_identidade=cpf
        ).exists():
            return True
    return False


def criar_familia_com_responsavel(form, operador):
    """Recebe FamilyForm válido; não reaproveita Person nem regulariza o legado."""
    exigir_permissao_cadastral_familia(operador)
    if not form.is_valid() or form.instance.pk is not None:
        raise ValidationError("Use um formulário válido de cadastro de nova família.")

    familia = form.save(commit=False)
    nome = familia.responsible_name.strip()
    cpf = _cpf(familia.cpf)
    genero = _SEXO.get(familia.sex)
    if not nome or genero is None or len(cpf) != 11:
        raise ValidationError("Informe nome, sexo e CPF válidos para o responsável.")

    with transaction.atomic():
        _bloquear_tabelas()
        if _cpf_ja_cadastrado(cpf):
            raise ValidationError(
                "CPF já utilizado em outro cadastro. "
                "Solicite a conferência da identidade antes de prosseguir."
            )
        # Revalida a inscrição sob bloqueio: o formulário foi validado antes.
        if Family._base_manager.filter(registration_number=familia.registration_number).exists():
            raise ValidationError("A inscrição já foi utilizada. Revise o cadastro.")

        pessoa = Person(
            full_name=nome,
            birth_date=familia.birth_date,
            gender=genero,
            cpf=familia.cpf,
        )
        pessoa.full_clean()
        familia.criado_por = operador
        familia.save()
        form.save_m2m()

        pessoa.family = familia
        pessoa.save()
        familia.responsible = pessoa
        familia.save(update_fields=["responsible"])
        registrar_log(operador, pessoa, "person_criada", "Identidade do responsável criada.")
        registrar_log(operador, familia, "familia_criada", "Família cadastrada com responsável vinculado.")

    return familia


def proteger_identificacao_responsavel(familia_banco, familia_editada):
    """Chamar depois de bloquear Family, antes de salvar a edição comum."""
    if familia_banco.responsible_id != familia_editada.responsible_id:
        raise ValidationError(
            "O vínculo do responsável mudou. Reabra a família antes de editar."
        )
    if familia_banco.responsible_id is None:
        return  # A edição cadastral não cria identidade para famílias legadas.

    identidade_anterior = (
        familia_banco.responsible_name, familia_banco.birth_date,
        familia_banco.sex, _cpf(familia_banco.cpf),
    )
    identidade_proposta = (
        familia_editada.responsible_name, familia_editada.birth_date,
        familia_editada.sex, _cpf(familia_editada.cpf),
    )
    if identidade_anterior != identidade_proposta:
        raise ValidationError(
            "Nome, nascimento, sexo e CPF do responsável vinculado não podem "
            "ser alterados nesta tela. Solicite a revisão da identificação."
        )
