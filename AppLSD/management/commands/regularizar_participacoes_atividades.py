from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from AppLSD.models import (
    Activity,
    Aluno,
    Family,
    ParticipacaoAtividade,
)


class Command(BaseCommand):
    help = (
        'Regulariza o histórico dos vínculos atuais de atividades. '
        'Por padrão, apenas simula. Use --aplicar para gravar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Grava as participações abertas que estiverem faltando.',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']

        resumo = {
            'vinculos': 0,
            'existentes': 0,
            'faltantes': 0,
        }

        inconsistencias = []

        with transaction.atomic():
            alunos_com_vinculo = (
                Aluno.objects
                .filter(atividades__isnull=False)
                .values_list('pk', flat=True)
            )

            alunos_com_participacao = (
                ParticipacaoAtividade.objects
                .filter(saida_em__isnull=True)
                .values_list('aluno_id', flat=True)
            )

            alunos_em_familias_inativas = (
                Aluno.objects
                .filter(
                    status_lsd='Frequentando',
                    family__status='inativo',
                )
                .values_list('pk', flat=True)
            )

            alunos_ids = (
                set(alunos_com_vinculo)
                | set(alunos_com_participacao)
                | set(alunos_em_familias_inativas)
            )

            referencias = list(
                Aluno.objects
                .filter(pk__in=alunos_ids)
                .order_by('family_id', 'pk')
                .values_list('pk', 'family_id')
            )

            for aluno_id, familia_id in referencias:
                familias_qs = (
                    Family.objects
                    .select_related(None)
                )

                alunos_qs = (
                    Aluno.objects
                    .select_related(None)
                )

                if aplicar:
                    familias_qs = familias_qs.select_for_update(
                        of=('self',),
                    )

                    alunos_qs = alunos_qs.select_for_update(
                        of=('self',),
                    )

                familia = familias_qs.get(pk=familia_id)
                aluno = alunos_qs.get(pk=aluno_id)

                if aluno.family_id != familia.pk:
                    inconsistencias.append(
                        f'Assistido #{aluno.pk}: '
                        'família alterada durante a execução.'
                    )
                    continue

                atividades = list(
                    Activity.objects
                    .filter(alunos=aluno)
                    .order_by('pk')
                )

                atividades_por_id = {
                    atividade.pk: atividade
                    for atividade in atividades
                }

                participacoes = list(
                    ParticipacaoAtividade.objects
                    .filter(
                        aluno=aluno,
                        saida_em__isnull=True,
                    )
                    .order_by('pk')
                )

                abertas_por_atividade = {}

                for participacao in participacoes:
                    atividade_id = participacao.atividade_id

                    if atividade_id in abertas_por_atividade:
                        inconsistencias.append(
                            f'Assistido #{aluno.pk}, '
                            f'atividade #{atividade_id}: '
                            'mais de uma participação aberta.'
                        )
                    else:
                        abertas_por_atividade[atividade_id] = (
                            participacao
                        )

                    if atividade_id not in atividades_por_id:
                        inconsistencias.append(
                            f'Assistido #{aluno.pk}, '
                            f'atividade #{atividade_id}: '
                            'participação aberta sem vínculo atual.'
                        )

                resumo['vinculos'] += len(atividades)

                frequentando_em_familia_inativa = (
                    aluno.status_lsd == 'Frequentando'
                    and familia.status == 'inativo'
                )

                vinculos_em_situacao_invalida = (
                    bool(atividades)
                    and (
                        aluno.status_lsd != 'Frequentando'
                        or familia.status != 'ativo'
                    )
                )

                if (
                    frequentando_em_familia_inativa
                    or vinculos_em_situacao_invalida
                ):
                    inconsistencias.append(
                        f'Assistido #{aluno.pk}: '
                        f'situação "{aluno.status_lsd}", '
                        f'família #{familia.pk} '
                        f'com situação "{familia.status}", '
                        f'{len(atividades)} atividade(s) vinculada(s).'
                    )
                    continue

                for atividade in atividades:
                    if atividade.pk in abertas_por_atividade:
                        resumo['existentes'] += 1
                        continue

                    resumo['faltantes'] += 1

                    if aplicar:
                        ParticipacaoAtividade.objects.create(
                            aluno=aluno,
                            atividade=atividade,
                            nome_atividade=atividade.atividade,
                            turno_atividade=atividade.turno or '',
                            entrada_em=None,
                            entrada_registrada_por=None,
                            saida_em=None,
                        )

            if inconsistencias:
                for texto in inconsistencias:
                    self.stderr.write(texto)

                raise CommandError(
                    f'Encontradas {len(inconsistencias)} '
                    'inconsistência(s). '
                    'Nenhuma regularização foi confirmada. '
                    'Revise os casos antes de aplicar.'
                )

        self.stdout.write(
            f'Vínculos atuais verificados: {resumo["vinculos"]}'
        )

        self.stdout.write(
            'Participações abertas já existentes: '
            f'{resumo["existentes"]}'
        )

        if aplicar:
            self.stdout.write(
                self.style.SUCCESS(
                    'Participações criadas: '
                    f'{resumo["faltantes"]}'
                )
            )
        else:
            self.stdout.write(
                'Participações que seriam criadas: '
                f'{resumo["faltantes"]}'
            )

            self.stdout.write(
                self.style.WARNING(
                    'SIMULAÇÃO: nenhum registro foi gravado.'
                )
            )