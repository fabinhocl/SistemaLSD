"""Servico interno de edicao de Adult + Person. Ainda sem ligacao com views.

Banco default PostgreSQL. Politica: Servico Social e Admin (inclui superusuario ativo).
Nao cria identidades nem troca CPF, familia ou Person.
"""
import hashlib
import json
import re
from collections.abc import Mapping

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction

from AppLSD.models import Adult, Aluno, Family, Person
from AppLSD.person_identificacao import preparar_identificacao_person
from AppLSD.utils import registrar_log

CAMPOS_EDICAO_ADULTO = frozenset({
    'name', 'cpf', 'social_name', 'sex', 'parentesco', 'birth_date',
    'education', 'ocupacao', 'renda', 'status', 'telephone',
})
SALT = 'AppLSD.adulto_person.edicao.v1'
TOKEN_MAX_AGE = 3600


def _estado(obj):
    return {f.attname: getattr(obj, f.attname) for f in obj._meta.concrete_fields}


def _hash(valor):
    texto = json.dumps(valor, cls=DjangoJSONEncoder, sort_keys=True,
                       ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def _operador(usuario):
    from AppLSD.adulto_permissoes import validar_operador_adulto
    return validar_operador_adulto(usuario)


def _assinatura(adulto, pessoa):
    return _hash({'Adult': _estado(adulto),
                  'Person': _estado(pessoa) if pessoa is not None else None})


def criar_token_edicao_adulto(*, usuario, adulto_id):
    """Somente leitura. O futuro GET deve montar o formulario com a versao retornada.

    Retorna (adulto_lido, token). A view deve usar ESTE adulto para exibir o form,
    evitando gerar token novo para dados antigos recebidos em POST.
    """
    operador = _operador(usuario)
    with transaction.atomic():
        familia_id = Adult.objects.values_list('family_id', flat=True).get(pk=adulto_id)
        familia = Family.objects.select_for_update().get(pk=familia_id)
        adulto = Adult.objects.select_for_update().get(pk=adulto_id)
        if adulto.family_id != familia_id:
            raise ValidationError('Familia alterada durante a leitura. Reabra o cadastro.')
        if adulto.excluido or familia.excluido:
            raise ValidationError('Cadastro excluido nao pode ser editado por este fluxo.')
        pessoa = (Person.objects.select_for_update().get(pk=adulto.person_id)
                  if adulto.person_id is not None else None)
        token = signing.dumps({
            'adulto_id': adulto.pk,
            'usuario_id': operador.pk,
            'estado': _assinatura(adulto, pessoa),
        }, salt=SALT, compress=True)
    return adulto, token


def _digitos(valor):
    return re.sub(r'[^0-9]', '', str(valor or ''))


def _exigir_cpf_livre_adulto(adulto):
    documento = _digitos(adulto.cpf)
    if not documento:
        return
    for modelo in (Family, Adult, Aluno, Person):
        for pk, cpf in modelo._base_manager.values_list('pk', 'cpf').iterator():
            if modelo is Adult and pk == adulto.pk:
                continue
            if _digitos(cpf) == documento:
                raise ValidationError({'cpf': 'CPF presente em outro cadastro; revisar identidade.'})


def _salvar_edicao_adulto_legado(operador, adulto, alteracoes):
    """Adulto sem Person: salva so o cadastro; nao cria nem altera identidade."""
    antes = _estado(adulto)
    cpf_antes = _digitos(adulto.cpf)
    for campo, valor in alteracoes.items():
        setattr(adulto, campo, valor)
    adulto.full_clean()
    depois = _estado(adulto)
    campos_adulto = sorted(k for k in antes if antes[k] != depois[k])
    if set(campos_adulto) - set(alteracoes):
        raise ValidationError('Validacao alterou campo nao solicitado; revisar cadastro.')
    if _digitos(adulto.cpf) != cpf_antes:
        _exigir_cpf_livre_adulto(adulto)
    if campos_adulto:
        adulto.editado_por = operador
        adulto.save(update_fields=campos_adulto + ['editado_por', 'editado_em'])
        registrar_log(operador, adulto, 'adulto_editado',
                      f'Cadastro sem Person atualizado. Campos: {", ".join(campos_adulto)}.')
    return {'adulto': adulto, 'person_id': None, 'campos_adulto': campos_adulto,
            'campos_person': [], 'alterado': bool(campos_adulto)}

def salvar_edicao_adulto(*, usuario, adulto_id, alteracoes, token):
    """Salva as duas pontas e logs numa transacao, ou nao salva nenhuma.

    alteracoes deve conter valores limpos pelo formulario, sem family/person.
    A politica de perfis e compartilhada com a view.
    Bloqueios protegem estas linhas; nao substituem constraints nem a revisao
    de outros caminhos concorrentes que criem vinculos/identidades.
    """
    operador = _operador(usuario)
    if connection.vendor != 'postgresql':
        raise ValidationError('Este fluxo exige PostgreSQL.')
    if not isinstance(alteracoes, Mapping):
        raise ValidationError('Alteracoes devem ser um mapeamento de campos.')
    proibidos = set(alteracoes) - CAMPOS_EDICAO_ADULTO
    if proibidos:
        raise ValidationError('Ha campos fora do escopo desta edicao.')
    try:
        dados_token = signing.loads(token or '', salt=SALT, max_age=TOKEN_MAX_AGE)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('Formulario invalido ou expirado. Reabra o cadastro.') from None
    if (not isinstance(dados_token, dict)
            or dados_token.get('adulto_id') != adulto_id
            or dados_token.get('usuario_id') != operador.pk):
        raise ValidationError('Formulario nao corresponde ao cadastro ou ao operador.')

    with transaction.atomic():
        familia_id = Adult.objects.values_list('family_id', flat=True).get(pk=adulto_id)
        familia = Family.objects.select_for_update().get(pk=familia_id)
        adulto = Adult.objects.select_for_update().get(pk=adulto_id)
        if adulto.family_id != familia_id:
            raise ValidationError('Familia alterada durante a operacao. Reabra o cadastro.')
        if adulto.excluido or familia.excluido:
            raise ValidationError('Cadastro excluido nao pode ser editado por este fluxo.')
        pessoa_anterior = (Person.objects.select_for_update().get(pk=adulto.person_id)
                           if adulto.person_id is not None else None)
        if dados_token.get('estado') != _assinatura(adulto, pessoa_anterior):
            raise ValidationError('Cadastro alterado desde a abertura. Reabra antes de salvar.')
        if pessoa_anterior is None:
            return _salvar_edicao_adulto_legado(operador, adulto, alteracoes)

        antes = _estado(adulto)
        for campo, valor in alteracoes.items():
            setattr(adulto, campo, valor)
        adulto.full_clean()
        depois = _estado(adulto)
        campos_adulto = sorted(k for k in antes if antes[k] != depois[k])
        if set(campos_adulto) - set(alteracoes):
            raise ValidationError('Validacao alterou campo nao solicitado; revisar cadastro.')

        pessoa, campos_person = preparar_identificacao_person(adulto)
        anterior_p = _estado(pessoa_anterior)
        esperado_p = dict(anterior_p)
        for campo in campos_person:
            esperado_p[campo] = getattr(pessoa, campo)
        if _hash(_estado(pessoa)) != _hash(esperado_p):
            raise ValidationError('Validacao de Person alterou campo fora do escopo.')

        if campos_person:
            pessoa.save(update_fields=campos_person)
        if campos_adulto:
            adulto.editado_por = operador
            adulto.save(update_fields=campos_adulto + ['editado_por', 'editado_em'])
        if campos_person:
            registrar_log(operador, pessoa, 'person_identificacao_atualizada',
                          'Identificacao sincronizada pelo cadastro Adult#'
                          f'{adulto.pk}. Campos: {", ".join(sorted(campos_person))}.')
        if campos_adulto:
            registrar_log(operador, adulto, 'adulto_editado',
                          f'Cadastro atualizado com Person#{pessoa.pk}. '
                          f'Campos: {", ".join(campos_adulto)}.')

        origem_esperada = dict(depois)
        if campos_adulto:
            origem_esperada['editado_por_id'] = operador.pk
            origem_esperada['editado_em'] = adulto.editado_em
        if _hash(_estado(Adult.objects.get(pk=adulto.pk))) != _hash(origem_esperada):
            raise ValidationError('Adult sofreu alteracao inesperada; edicao cancelada.')
        if _hash(_estado(Person.objects.get(pk=pessoa.pk))) != _hash(esperado_p):
            raise ValidationError('Person sofreu alteracao inesperada; edicao cancelada.')
        return {
            'adulto': adulto, 'person_id': pessoa.pk,
            'campos_adulto': campos_adulto, 'campos_person': sorted(campos_person),
            'alterado': bool(campos_adulto or campos_person),
        }
