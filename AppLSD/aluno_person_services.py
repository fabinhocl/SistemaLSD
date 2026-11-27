"""Criacao/edicao Aluno + Person. Nao regulariza legados nem executa desligamentos."""
import re
import unicodedata
from collections.abc import Mapping
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from AppLSD.models import Family, Adult, Aluno, Person
from AppLSD.adulto_person_services import _estado, _hash
from AppLSD.aluno_person_permissoes import validar_operador_aluno
from AppLSD.utils import registrar_log

CAMPOS_ALUNO = frozenset({
    "name", "cpf", "nis", "parentesco", "birth_date", "sex", "school", "rede_ensino",
    "ensino", "serie", "turno", "health_problem", "special_need", "uso_medicacao",
    "qual_medicacao", "frequencia_tipo", "dias_semana", "possui_sisc",
    "justificativa_sisc", "justificativa_sisc_outros", "status_lsd",
})
STATUS_DEFINIDOS = frozenset({"Frequentando", "desligado", "nao_frequenta"})
SALT = "AppLSD.aluno_person.edicao.v1"
TOKEN_MAX_AGE = 3600


def _cpf(valor):
    return re.sub(r"[^0-9]", "", str(valor or ""))


def _nome(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def bloquear_identidades_aluno():
    if connection.vendor != "postgresql" or connection.alias != "default":
        raise ValidationError("Este fluxo exige PostgreSQL no banco default.")
    tabelas = sorted(m._meta.db_table for m in (Family, Adult, Aluno, Person))
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '5s'")
        cursor.execute("LOCK TABLE " + ", ".join(connection.ops.quote_name(t) for t in tabelas)
                       + " IN SHARE ROW EXCLUSIVE MODE")


def _dados(dados):
    if not isinstance(dados, Mapping) or set(dados) - CAMPOS_ALUNO:
        raise ValidationError("Dados contem campos fora do escopo cadastral.")


def _ler(aluno_id, *, bloquear=False):
    qs = Aluno.objects.select_for_update() if bloquear else Aluno.objects
    fid = Aluno.objects.values_list("family_id", flat=True).get(pk=aluno_id)
    fs = Family.objects.select_for_update() if bloquear else Family.objects
    familia = fs.get(pk=fid)
    aluno = qs.get(pk=aluno_id)
    if aluno.family_id != fid:
        raise ValidationError("Familia alterada durante a leitura. Reabra o cadastro.")
    if aluno.excluido or familia.excluido:
        raise ValidationError("Cadastro ou familia excluidos: fluxo indisponivel.")
    ps = Person.objects.select_for_update() if bloquear else Person.objects
    pessoa = ps.filter(pk=aluno.person_id).first() if aluno.person_id else None
    return aluno, pessoa, familia


def _assinatura(aluno, pessoa, familia):
    return _hash({"Aluno": _estado(aluno), "Person": _estado(pessoa) if pessoa else None,
                  "Family": _estado(familia)})


def criar_token_edicao_aluno(*, usuario, aluno_id):
    operador = validar_operador_aluno(usuario)
    aluno, pessoa, familia = _ler(aluno_id)
    token = signing.dumps({"aluno_id": aluno.pk, "usuario_id": operador.pk,
        "estado": _assinatura(aluno, pessoa, familia)}, salt=SALT, compress=True)
    return aluno, token


def validar_token_aluno(*, usuario, aluno, pessoa, familia, token):
    try:
        dados = signing.loads(token or "", salt=SALT, max_age=TOKEN_MAX_AGE)
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError("Formulario invalido ou expirado. Reabra a edicao.") from None
    if not isinstance(dados, dict) or dados.get("aluno_id") != aluno.pk or dados.get("usuario_id") != usuario.pk:
        raise ValidationError("Formulario nao corresponde ao cadastro ou ao operador.")
    if dados.get("estado") != _assinatura(aluno, pessoa, familia):
        raise ValidationError("Cadastro alterado desde a abertura. Reabra antes de salvar.")


def _genero(aluno):
    genero = {"Feminino": "F", "Masculino": "M"}.get(aluno.sex)
    if genero is None:
        raise ValidationError({"sex": "Informe o sexo para identificar a pessoa."})
    return genero


def _conflitos(aluno, *, nova):
    documento, nome = _cpf(aluno.cpf), _nome(aluno.name)
    for modelo, campo in ((Family, "responsible_name"), (Adult, "name"),
                          (Aluno, "name"), (Person, "full_name")):
        for pk, cpf, outro_nome, data in modelo._base_manager.values_list("pk", "cpf", campo, "birth_date").iterator():
            if not nova and ((modelo is Aluno and pk == aluno.pk)
                             or (modelo is Person and pk == aluno.person_id)):
                continue
            if documento and documento == _cpf(cpf):
                raise ValidationError({"cpf": "CPF presente em outro cadastro. Revisar identidade; nenhuma associacao automatica sera feita."})
            if (nova or not documento) and nome == _nome(outro_nome) and (
                    data is None or aluno.birth_date is None or data == aluno.birth_date):
                raise ValidationError({"name": "Possivel identidade existente por nome/nascimento. Requer revisao; nao sera fundida ou reutilizada automaticamente."})


def _validar_cadastro(aluno):
    if not str(aluno.name or "").strip():
        raise ValidationError({"name": "Informe o nome."})
    if aluno.health_problem == "sim" and not str(aluno.special_need or "").strip():
        raise ValidationError({"special_need": "Informe o problema de saude."})
    if aluno.uso_medicacao == "sim" and not str(aluno.qual_medicacao or "").strip():
        raise ValidationError({"qual_medicacao": "Informe a medicacao."})
    if aluno.frequencia_tipo == "especificos" and not aluno.dias_semana:
        raise ValidationError({"dias_semana": "Selecione pelo menos um dia da semana."})
    permitidos = {"segunda", "terca", "quarta", "quinta", "sexta"}
    if not isinstance(aluno.dias_semana, list) or any(d not in permitidos for d in aluno.dias_semana):
        raise ValidationError({"dias_semana": "Dias da semana invalidos."})
    aluno.full_clean()


def _relacionados(aluno):
    """Fotografia dos relacionamentos reversos deste assistido, sem AppLog generico."""
    resultado = {}
    for rel in Aluno._meta.related_objects:
        if rel.many_to_many:
            modelo = rel.through
            for campo in modelo._meta.concrete_fields:
                if campo.is_relation and campo.related_model is Aluno:
                    resultado[modelo._meta.label] = list(modelo._base_manager.filter(
                        **{campo.attname: aluno.pk}).order_by("pk").values())
        elif rel.one_to_many or rel.one_to_one:
            modelo = rel.related_model
            resultado[modelo._meta.label + ":" + rel.field.attname] = list(
                modelo._base_manager.filter(**{rel.field.attname: aluno.pk}).order_by("pk").values())
    return _hash(resultado)


def criar_aluno_com_person(*, usuario, familia_id, dados):
    operador = validar_operador_aluno(usuario, criar=True)
    _dados(dados)
    with transaction.atomic():
        bloquear_identidades_aluno()
        operador = validar_operador_aluno(operador, criar=True)
        familia = Family.objects.select_for_update().get(pk=familia_id)
        if familia.excluido:
            raise ValidationError("Familia excluida nao pode receber cadastro.")
        antes_f = _hash(_estado(familia))
        aluno = Aluno(family=familia, criado_por=operador, **dict(dados))
        aluno.name = str(aluno.name or "").strip()
        if not str(aluno.cpf or "").strip():
            aluno.cpf = None
        if aluno.status_lsd == "desligado":
            raise ValidationError({"status_lsd": "Novo cadastro nao realiza desligamento. Use o fluxo especifico apos cadastrar."})
        genero = _genero(aluno)
        _validar_cadastro(aluno)
        _conflitos(aluno, nova=True)
        pessoa = Person(family=familia, full_name=aluno.name, birth_date=aluno.birth_date,
                        gender=genero, cpf=_cpf(aluno.cpf) or None)
        pessoa.full_clean()
        esperado_p = _estado(pessoa)
        pessoa.save()
        esperado_p[Person._meta.pk.attname] = pessoa.pk
        aluno.person = pessoa
        _validar_cadastro(aluno)
        esperado_a = _estado(aluno)
        aluno.save()
        esperado_a.update({Aluno._meta.pk.attname: aluno.pk, "criado_em": aluno.criado_em, "editado_em": aluno.editado_em})
        relacionados = _relacionados(aluno)
        # Nenhum relacionamento operacional e criado pelo servico cadastral.
        for rel in Aluno._meta.related_objects:
            if rel.many_to_many:
                modelo = rel.through
                campos = [c for c in modelo._meta.concrete_fields if c.is_relation and c.related_model is Aluno]
                if any(modelo._base_manager.filter(**{c.attname: aluno.pk}).exists() for c in campos):
                    raise ValidationError("Vinculo operacional inesperado na criacao.")
            elif (rel.one_to_many or rel.one_to_one) and rel.related_model._base_manager.filter(**{rel.field.attname: aluno.pk}).exists():
                raise ValidationError("Registro relacionado inesperado na criacao.")
        registrar_log(operador, pessoa, "person_criada", f"Identidade criada pelo cadastro Aluno#{aluno.pk}.")
        registrar_log(operador, aluno, "aluno_criado", f"Cadastro criado com Person#{pessoa.pk}.")
        if (_hash(_estado(Aluno.objects.get(pk=aluno.pk))) != _hash(esperado_a)
                or _hash(_estado(Person.objects.get(pk=pessoa.pk))) != _hash(esperado_p)
                or _hash(_estado(Family.objects.get(pk=familia.pk))) != antes_f
                or _relacionados(aluno) != relacionados):
            raise ValidationError("Alteracao inesperada na criacao. Operacao cancelada.")
        return {"aluno": aluno, "person_id": pessoa.pk}

def _exigir_cpf_livre(aluno):
    documento = _cpf(aluno.cpf)
    if not documento:
        return
    for modelo in (Family, Adult, Aluno, Person):
        for pk, cpf in modelo._base_manager.values_list("pk", "cpf").iterator():
            if modelo is Aluno and pk == aluno.pk:
                continue
            if documento == _cpf(cpf):
                raise ValidationError({"cpf": "CPF presente em outro cadastro. Revisar identidade; nenhuma associacao automatica sera feita."})


def _salvar_edicao_legado(operador, aluno, familia, alteracoes):
    """Assistido sem Person: salva so o cadastro; nao cria nem altera identidade."""
    antes_a = _estado(aluno)
    antes_f, relacionados = _hash(_estado(familia)), _relacionados(aluno)
    cpf_original = _cpf(aluno.cpf)
    for campo, valor in alteracoes.items():
        setattr(aluno, campo, valor)
    if not cpf_original and not str(aluno.cpf or "").strip():
        aluno.cpf = antes_a["cpf"]
    if aluno.status_lsd == "desligado" and antes_a["status_lsd"] != "desligado":
        raise ValidationError({"status_lsd": "Use a confirmacao especifica de desligamento. A edicao cadastral nao desliga assistidos."})
    if antes_a["status_lsd"] in STATUS_DEFINIDOS and aluno.status_lsd not in STATUS_DEFINIDOS:
        raise ValidationError({"status_lsd": "Nao e permitido apagar a situacao atual."})
    _validar_cadastro(aluno)
    if _cpf(aluno.cpf) != cpf_original:
        _exigir_cpf_livre(aluno)
    permitidos = set(alteracoes)
    if "possui_sisc" in permitidos:
        permitidos.update({"justificativa_sisc", "justificativa_sisc_outros"})
    depois_a = _estado(aluno)
    campos_a = sorted(k for k in antes_a if antes_a[k] != depois_a[k])
    if set(campos_a) - permitidos:
        raise ValidationError("Validacao alterou campo nao solicitado. Revisar cadastro.")
    if campos_a:
        aluno.editado_por = operador
        aluno.save(update_fields=campos_a + ["editado_por", "editado_em"])
        registrar_log(operador, aluno, "aluno_editado",
                      f"Cadastro sem Person atualizado. Campos: {', '.join(campos_a)}.")
    esperado_a = dict(depois_a)
    if campos_a:
        esperado_a.update(editado_por_id=operador.pk, editado_em=aluno.editado_em)
    if (_hash(_estado(Aluno.objects.get(pk=aluno.pk))) != _hash(esperado_a)
            or _hash(_estado(Family.objects.get(pk=familia.pk))) != antes_f
            or _relacionados(aluno) != relacionados):
        raise ValidationError("Alteracao fora do escopo cadastral. Edicao cancelada.")
    return {"aluno": aluno, "person_id": None, "alterado": bool(campos_a)}


def salvar_edicao_aluno(*, usuario, aluno_id, alteracoes, token):
    operador = validar_operador_aluno(usuario)
    _dados(alteracoes)
    with transaction.atomic():
        bloquear_identidades_aluno()
        operador = validar_operador_aluno(operador)
        aluno, pessoa, familia = _ler(aluno_id, bloquear=True)
        validar_token_aluno(usuario=operador, aluno=aluno, pessoa=pessoa, familia=familia, token=token)
        if pessoa is None:
            return _salvar_edicao_legado(operador, aluno, familia, alteracoes)
        if pessoa.family_id != aluno.family_id:
            raise ValidationError("Person e assistido possuem familias divergentes.")
        referencias = (Family._base_manager.filter(responsible_id=pessoa.pk).count()
            + Adult._base_manager.filter(person_id=pessoa.pk).count()
            + Aluno._base_manager.filter(person_id=pessoa.pk).count())
        if referencias != 1:
            raise ValidationError("Person compartilhada exige edicao coordenada.")
        antes_a, antes_p = _estado(aluno), _estado(pessoa)
        antes_f, relacionados = _hash(_estado(familia)), _relacionados(aluno)
        cpf_original = _cpf(aluno.cpf)
        if cpf_original != _cpf(pessoa.cpf):
            raise ValidationError({"cpf": "CPF divergente entre as pontas. Requer fluxo proprio."})
        for campo, valor in alteracoes.items():
            setattr(aluno, campo, valor)
        if _cpf(aluno.cpf) != cpf_original:
            raise ValidationError({"cpf": "Inclusao, remocao ou troca de CPF exige fluxo proprio."})
        if not cpf_original and not str(aluno.cpf or "").strip():
            aluno.cpf = antes_a["cpf"]
        if aluno.status_lsd == "desligado" and antes_a["status_lsd"] != "desligado":
            raise ValidationError({"status_lsd": "Use a confirmacao especifica de desligamento. A edicao cadastral nao desliga assistidos."})
        if antes_a["status_lsd"] in STATUS_DEFINIDOS and aluno.status_lsd not in STATUS_DEFINIDOS:
            raise ValidationError({"status_lsd": "Nao e permitido apagar a situacao atual."})
        _validar_cadastro(aluno)
        permitidos = set(alteracoes)
        if "possui_sisc" in permitidos:
            permitidos.update({"justificativa_sisc", "justificativa_sisc_outros"})
        depois_a = _estado(aluno)
        campos_a = sorted(k for k in antes_a if antes_a[k] != depois_a[k])
        if set(campos_a) - permitidos:
            raise ValidationError("Validacao alterou campo nao solicitado. Revisar cadastro.")
        _conflitos(aluno, nova=False)
        novos_p = {"full_name": aluno.name, "birth_date": aluno.birth_date, "gender": _genero(aluno)}
        campos_p = sorted(k for k, valor in novos_p.items() if getattr(pessoa, k) != valor)
        for campo, valor in novos_p.items():
            setattr(pessoa, campo, valor)
        esperado_p = dict(antes_p, **novos_p)
        pessoa.full_clean()
        if _hash(_estado(pessoa)) != _hash(esperado_p):
            raise ValidationError("Validacao alterou campo de Person fora do escopo.")
        if campos_p:
            pessoa.save(update_fields=campos_p)
        if campos_a:
            aluno.editado_por = operador
            aluno.save(update_fields=campos_a + ["editado_por", "editado_em"])
        if campos_p:
            registrar_log(operador, pessoa, "person_identificacao_atualizada",
                          f"Identificacao sincronizada por Aluno#{aluno.pk}. Campos: {', '.join(campos_p)}.")
        if campos_a:
            registrar_log(operador, aluno, "aluno_editado",
                          f"Cadastro atualizado com Person#{pessoa.pk}. Campos: {', '.join(campos_a)}.")
        esperado_a = dict(depois_a)
        if campos_a:
            esperado_a.update(editado_por_id=operador.pk, editado_em=aluno.editado_em)
        if (_hash(_estado(Aluno.objects.get(pk=aluno.pk))) != _hash(esperado_a)
                or _hash(_estado(Person.objects.get(pk=pessoa.pk))) != _hash(esperado_p)
                or _hash(_estado(Family.objects.get(pk=familia.pk))) != antes_f
                or _relacionados(aluno) != relacionados):
            raise ValidationError("Alteracao fora do escopo cadastral. Edicao cancelada.")
        return {"aluno": aluno, "person_id": pessoa.pk, "alterado": bool(campos_a or campos_p)}
