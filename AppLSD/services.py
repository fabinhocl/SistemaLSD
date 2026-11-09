"""
arquivo services.py
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .atividade_services import encerrar_participacao_atividade
from .models import (    
    Activity,
    Aluno,
    Family,
    HistoricoDesligamento,
    MotivoDesligamentoChoices,
    MovimentacaoTurmaAluno,
)
from .utils import registrar_log, is_coordenacao, pode_inativar_familia, pode_desligar_assistido

def inativar_familia(familia, user, motivo, observacao=''):
    """
    Ponte de compatibilidade para chamadas existentes.

    O parâmetro motivo deve receber um código válido de
    MotivoDesligamentoChoices.

    Mantém o retorno antigo: quantidade de assistidos desligados.
    """
    if familia.pk is None:
        raise ValidationError(
            'A família precisa estar cadastrada antes de ser inativada.'
        )

    resultado = inativar_familia_logic(
        request_user=user,
        familia_id=familia.pk,
        motivo_codigo=motivo,
        observacao=observacao,
        origem='manual',
    )

    familia.refresh_from_db()

    return resultado['total_desligados']


def _validar_operador_desligamento(user):
    if not user or not user.is_authenticated:
        raise PermissionDenied('Autenticação obrigatória.')

    if not pode_desligar_assistido(user):
        raise PermissionDenied(
            'O desligamento individual de assistidos é permitido '
            'somente à Coordenação.'
        )


def _validar_operador_inativacao_familia(user):
    if not user or not user.is_authenticated:
        raise PermissionDenied('Autenticação obrigatória.')

    if not pode_inativar_familia(user):
        raise PermissionDenied(
            'A inativação de famílias é permitida '
            'somente ao Serviço Social.'
        )

def _validar_motivo_padronizado(motivo_codigo):
    codigo = (motivo_codigo or '').strip()
    motivos = dict(MotivoDesligamentoChoices.choices)

    if codigo not in motivos:
        raise ValidationError({
            'motivo_codigo': 'Selecione um motivo válido.'
        })

    return codigo, motivos[codigo]


def _desligar_aluno_bloqueado(
    *,
    request_user,
    aluno,
    motivo_codigo,
    motivo_descricao,
    observacao,
    origem,
    evento_familia=None,
):
    """
    Uso interno.

    Deve ser chamada dentro de uma transação, com a família
    e o assistido previamente bloqueados.
    """
    if aluno.status_lsd == 'desligado':
        return None

    agora = timezone.now()

    turma_anterior = aluno.turma

    atividades = list(
        Activity.objects
        .filter(alunos=aluno)
        .order_by('pk')
    )

    dados_anteriores = {
        'status_lsd': aluno.status_lsd,
        'familia_id': aluno.family_id,
        'turma': (
            {
                'id': turma_anterior.pk,
                'grupo': turma_anterior.grupo,
                'turno': turma_anterior.turno,
            }
            if turma_anterior else None
        ),
        'atividades': [
            {
                'id': atividade.pk,
                'nome': atividade.atividade,
            }
            for atividade in atividades
        ],
        'motivo_desligamento': aluno.motivo_desligamento,
        'motivo_desligamento_codigo': (
            aluno.motivo_desligamento_codigo
        ),
        'observacao_desligamento': (
            aluno.observacao_desligamento
        ),
        'data_desligamento': (
            aluno.data_desligamento.isoformat()
            if aluno.data_desligamento else None
        ),
        'desligado_por_id': aluno.desligado_por_id,
    }

    descricao_completa = motivo_descricao

    if observacao:
        descricao_completa += f' — {observacao}'

    if turma_anterior:
        MovimentacaoTurmaAluno.objects.create(
            aluno=aluno,
            turma_origem=turma_anterior,
            turma_destino=None,
            data=agora,
            motivo=descricao_completa,
            criado_por=request_user,
        )

    for atividade in atividades:
        encerrar_participacao_atividade(
            usuario=request_user,
            aluno_id=aluno.pk,
            atividade=atividade,
            motivo=descricao_completa,
            origem=origem,
            instante=agora,
        )

    aluno.turma = None
    aluno.status_lsd = 'desligado'
    aluno.motivo_desligamento_codigo = motivo_codigo
    aluno.observacao_desligamento = observacao
    aluno.motivo_desligamento = descricao_completa
    aluno.data_desligamento = agora
    aluno.desligado_por = request_user
    aluno.editado_por = request_user
    aluno.save()

    evento = HistoricoDesligamento.objects.create(
        tipo_evento=(
            HistoricoDesligamento.TipoEvento.ALUNO_DESLIGADO
        ),
        origem=origem,
        familia_id=aluno.family_id,
        aluno=aluno,
        evento_familia=evento_familia,
        motivo_codigo=motivo_codigo,
        motivo_descricao=motivo_descricao,
        observacao=observacao,
        dados_anteriores=dados_anteriores,
        criado_por=request_user,
    )

    if turma_anterior:
        registrar_log(
            request_user,
            turma_anterior,
            'aluno_removido_turma',
            (
                f'Assistido {aluno.name} removido da turma '
                f'"{turma_anterior.grupo}" por desligamento. '
                f'Motivo: {descricao_completa}.'
            ),
        )

    registrar_log(
        request_user,
        aluno,
        'aluno_desligado',
        (
            f'Assistido {aluno.name} desligado. '
            f'Motivo: {descricao_completa}. '
            f'Origem: {origem}. '
            f'Histórico: {evento.pk}.'
        ),
    )

    return evento


@transaction.atomic
def desligar_aluno_padronizado(
    *,
    request_user,
    aluno_id,
    motivo_codigo,
    observacao='',
    origem='manual',
):
    """
    Desligamento individual com motivo padronizado.

    Retorna:
        HistoricoDesligamento: quando realiza o desligamento.
        None: quando o assistido já estava desligado.
    """
    _validar_operador_desligamento(request_user)

    motivo_codigo, motivo_descricao = (
        _validar_motivo_padronizado(motivo_codigo)
    )

    observacao = (observacao or '').strip()

    origens_permitidas = {
        HistoricoDesligamento.Origem.MANUAL,
        HistoricoDesligamento.Origem.EDICAO,
    }

    if origem not in origens_permitidas:
        raise ValidationError('Origem de desligamento inválida.')

    # A ordem de bloqueio é família e depois assistido.
    familia_id = (
        Aluno.objects
        .values_list('family_id', flat=True)
        .get(pk=aluno_id)
    )

    Family.objects.select_for_update().get(pk=familia_id)

    aluno = (
        Aluno.objects
        .select_for_update(of=('self',))
        .select_related('family', 'turma')
        .get(pk=aluno_id)
    )

    if aluno.family_id != familia_id:
        raise ValidationError(
            'A família do assistido foi alterada durante a operação. '
            'Atualize a página e tente novamente.'
        )

    return _desligar_aluno_bloqueado(
        request_user=request_user,
        aluno=aluno,
        motivo_codigo=motivo_codigo,
        motivo_descricao=motivo_descricao,
        observacao=observacao,
        origem=origem,
    )


@transaction.atomic
def inativar_familia_logic(
    *,
    request_user,
    familia_id,
    motivo_codigo,
    observacao='',
    origem='manual',
):
    """
    Inativa a família e desliga os assistidos ainda não desligados.

    Retorna um dicionário com:
        alterado
        evento
        total_desligados
    """
    _validar_operador_inativacao_familia(request_user)

    motivo_codigo, motivo_descricao = (
        _validar_motivo_padronizado(motivo_codigo)
    )

    observacao = (observacao or '').strip()

    origens_permitidas = {
        HistoricoDesligamento.Origem.MANUAL,
        HistoricoDesligamento.Origem.EDICAO,
    }

    if origem not in origens_permitidas:
        raise ValidationError('Origem de inativação inválida.')

    familia = (
        Family.objects
        .select_for_update()
        .get(pk=familia_id)
    )

    alunos = list(
        Aluno.objects
        .select_for_update(of=('self',))
        .filter(family=familia)
        .select_related('turma')
        .order_by('pk')
    )

    pendentes = [
        aluno
        for aluno in alunos
        if aluno.status_lsd != 'desligado'
    ]

    if familia.status == 'inativo':
        if pendentes:
            raise ValidationError(
                'Esta família já está inativa, mas possui assistidos '
                'que não estão desligados. A situação deve ser '
                'revisada antes de repetir a operação.'
            )

        return {
            'alterado': False,
            'evento': None,
            'total_desligados': 0,
        }

    dados_anteriores = {
        'status': familia.status,
        'motivo_inativacao': familia.motivo_inativacao,
        'observacao_inativacao': familia.observacao_inativacao,
        'data_inativacao': (
            familia.data_inativacao.isoformat()
            if familia.data_inativacao else None
        ),
        'inativado_por_id': familia.inativado_por_id,
        'assistidos_a_desligar': [
            aluno.pk for aluno in pendentes
        ],
    }

    evento_familia = HistoricoDesligamento.objects.create(
        tipo_evento=(
            HistoricoDesligamento.TipoEvento.FAMILIA_INATIVADA
        ),
        origem=origem,
        familia=familia,
        motivo_codigo=motivo_codigo,
        motivo_descricao=motivo_descricao,
        observacao=observacao,
        dados_anteriores=dados_anteriores,
        criado_por=request_user,
    )

    total_desligados = 0

    for aluno in pendentes:
        _desligar_aluno_bloqueado(
            request_user=request_user,
            aluno=aluno,
            motivo_codigo=motivo_codigo,
            motivo_descricao=motivo_descricao,
            observacao=observacao,
            origem=HistoricoDesligamento.Origem.FAMILIA,
            evento_familia=evento_familia,
        )
        total_desligados += 1

    familia.status = 'inativo'
    familia.motivo_inativacao = motivo_codigo
    familia.observacao_inativacao = observacao
    familia.data_inativacao = timezone.now()
    familia.inativado_por = request_user
    familia.editado_por = request_user
    familia.save()

    registrar_log(
        request_user,
        familia,
        'familia_inativada',
        (
            f'Família de {familia.responsible_name} inativada. '
            f'Motivo: {motivo_descricao}. '
            f'Observação: {observacao or "Não informada"}. '
            f'Assistidos desligados: {total_desligados}. '
            f'Histórico: {evento_familia.pk}.'
        ),
    )

    return {
        'alterado': True,
        'evento': evento_familia,
        'total_desligados': total_desligados,
    }


DIAS_SEMANA_CODIGOS = {
    0: 'segunda',
    1: 'terca',
    2: 'quarta',
    3: 'quinta',
    4: 'sexta',
    5: 'sabado',
    6: 'domingo',
}


def aluno_previsto_na_data(aluno, data):
    """
    Retorna True se o aluno deveria participar da turma naquela data,
    conforme frequencia_tipo e dias_semana.
    """
    if aluno.frequencia_tipo == 'diaria':
        return True

    dias = aluno.dias_semana or []
    codigo_dia = DIAS_SEMANA_CODIGOS.get(data.weekday(), '')
    return codigo_dia in dias