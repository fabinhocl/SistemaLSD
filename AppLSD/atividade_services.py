from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Aluno, Family, ParticipacaoAtividade, HistoricoDesligamento
from .utils import registrar_log


def _bloquear_aluno_atividade(aluno_id):
    familia_id = (
        Aluno.objects
        .values_list('family_id', flat=True)
        .get(pk=aluno_id)
    )

    familia = (
        Family.objects
        .select_related(None)
        .select_for_update(of=('self',))
        .get(pk=familia_id)
    )

    aluno = (
        Aluno.objects
        .select_related(None)
        .select_for_update(of=('self',))
        .get(pk=aluno_id)
    )

    if aluno.family_id != familia.pk:
        raise ValidationError(
            'A família do assistido foi alterada. '
            'Atualize a página e tente novamente.'
        )

    return aluno, familia


@transaction.atomic
def adicionar_participacao_atividade(
    *,
    usuario,
    aluno_id,
    atividade,
):
    aluno, familia = _bloquear_aluno_atividade(aluno_id)

    if aluno.status_lsd != 'Frequentando':
        raise ValidationError(
            'Somente assistidos com situação Frequentando '
            'podem ser inseridos em atividades.'
        )

    if familia.status == 'inativo':
        raise ValidationError(
            'Não é possível inserir em atividades um assistido '
            'de família inativa.'
        )

    if atividade.alunos.filter(pk=aluno.pk).exists():
        return False

    participacao_aberta = (
        ParticipacaoAtividade.objects
        .filter(
            aluno=aluno,
            atividade=atividade,
            saida_em__isnull=True,
        )
        .exists()
    )

    if participacao_aberta:
        raise ValidationError(
            'Existe uma participação aberta sem vínculo atual. '
            'Confira o histórico antes de reinserir o assistido.'
        )

    atividade.alunos.add(aluno)

    ParticipacaoAtividade.objects.create(
        aluno=aluno,
        atividade=atividade,
        nome_atividade=atividade.atividade,
        turno_atividade=atividade.turno or '',
        entrada_em=timezone.now(),
        entrada_registrada_por=usuario,
    )

    registrar_log(
        usuario,
        atividade,
        'aluno_adicionado_atividade',
        (
            f'Assistido {aluno.name} adicionado à atividade '
            f'"{atividade.atividade}".'
        ),
    )

    registrar_log(
        usuario,
        aluno,
        'atividade_adicionada_aluno',
        (
            f'Assistido inserido na atividade '
            f'"{atividade.atividade}" (ID {atividade.pk}).'
        ),
    )

    return True


@transaction.atomic
def encerrar_participacao_atividade(
    *,
    usuario,
    aluno_id,
    atividade,
    motivo,
    origem='remocao_individual',
    instante=None,
):
    aluno, _ = _bloquear_aluno_atividade(aluno_id)

    motivo = (motivo or '').strip()

    if not motivo:
        raise ValidationError('O motivo da remoção é obrigatório.')

    if not atividade.alunos.filter(pk=aluno.pk).exists():
        return False

    instante = instante or timezone.now()

    participacao = (
        ParticipacaoAtividade.objects
        .select_for_update()
        .filter(
            aluno=aluno,
            atividade=atividade,
            saida_em__isnull=True,
        )
        .first()
    )

    if participacao is None:
        participacao = ParticipacaoAtividade(
            aluno=aluno,
            atividade=atividade,
            nome_atividade=atividade.atividade,
            turno_atividade=atividade.turno or '',
            entrada_em=None,
            entrada_registrada_por=None,
        )

    participacao.saida_em = instante
    participacao.saida_registrada_por = usuario
    participacao.motivo_saida = motivo
    participacao.origem_saida = origem
    participacao.save()

    atividade.alunos.remove(aluno)

    registrar_log(
        usuario,
        atividade,
        'aluno_removido_da_atividade',
        (
            f'Assistido {aluno.name} removido da atividade '
            f'"{atividade.atividade}". '
            f'Motivo: {motivo}. Origem: {origem}.'
        ),
    )

    registrar_log(
        usuario,
        aluno,
        'aluno_removido_atividade',
        (
            f'Assistido removido da atividade '
            f'"{atividade.atividade}" (ID {atividade.pk}). '
            f'Motivo: {motivo}. Origem: {origem}.'
        ),
    )

    return True

def consultar_atividades_em_desligamentos(aluno_id):
    """
    Retorna as atividades preservadas nos snapshots
    dos desligamentos do assistido.

    Não altera vínculos, frequências ou participações.
    """
    eventos = (
        HistoricoDesligamento.objects
        .filter(
            aluno_id=aluno_id,
            tipo_evento=(
                HistoricoDesligamento
                .TipoEvento
                .ALUNO_DESLIGADO
            ),
        )
        .select_related('criado_por')
        .order_by('-criado_em', '-pk')
    )

    linhas = []

    for evento in eventos:
        dados = evento.dados_anteriores

        if not isinstance(dados, dict):
            continue

        atividades = dados.get('atividades', [])

        if not isinstance(atividades, list):
            continue

        atividades_vistas = set()

        for atividade in atividades:
            if not isinstance(atividade, dict):
                continue

            atividade_id = atividade.get('id')

            nome = str(
                atividade.get('nome') or ''
            ).strip()

            if not nome and atividade_id is None:
                continue

            chave = (
                str(atividade_id),
                nome,
            )

            if chave in atividades_vistas:
                continue

            atividades_vistas.add(chave)

            linhas.append({
                'evento_id': evento.pk,
                'atividade_id': atividade_id,
                'nome_atividade': (
                    nome or 'Nome não preservado no registro'
                ),
                'registrado_em': evento.criado_em,
                'motivo': evento.motivo_descricao,
                'observacao': evento.observacao,
                'origem': evento.get_origem_display(),
                'registrado_por': evento.criado_por,
            })

    return linhas