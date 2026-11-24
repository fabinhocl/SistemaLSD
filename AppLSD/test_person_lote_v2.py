"""Testes isolados da regularizacao. Executar exclusivamente com manage.py test."""
import io
import json
import tempfile
from datetime import date, time
from pathlib import Path
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models.signals import post_save
from django.test import TestCase

from AppLSD.models import (
    Family, Adult, Aluno, Person, Turma, Activity, HistoricoDesligamento,
    MotivoDesligamentoChoices,
)
from AppLSD.management.commands import aplicar_lote_person_v2 as lote


def cpf_teste(numero):
    texto = f'{numero:09d}'
    for n in (9, 10):
        digito = (sum(int(texto[i]) * (n + 1 - i) for i in range(n)) * 10 % 11) % 10
        texto += str(digito)
    return texto


class LotePersonV2Tests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql',
                         'Esta suite exige banco de testes PostgreSQL.')
        self.seq = 0
        self.familia = self.criar_familia()
        self.adulto = Adult(
            pk=1001, family=self.familia, name='Adulto sintetico',
            social_name='Adulto sintetico', cpf=self.proximo_cpf(),
            birth_date=date(1985, 2, 3), sex='Masculino',
            education='med_comp', status='trabalha',
        )
        self.adulto.full_clean()
        self.adulto.save()
        self.turma = Turma.objects.create(
            faixa_etaria='06-07 anos', grupo='Grupo Crianca Feliz',
            turno='Matutino', ano_letivo=2026, educadora=None,
        )
        self.aluno = Aluno(
            pk=1001, family=self.familia, name='Aluno sintetico',
            cpf=self.proximo_cpf(), birth_date=date(2018, 4, 5), sex='Masculino',
            status_lsd='Frequentando', turma=self.turma,
            possui_sisc='nao', justificativa_sisc='outros',
            justificativa_sisc_outros='Dado sintetico preservado',
        )
        self.aluno.save()
        self.atividade = Activity.objects.create(
            atividade='Atividade sintetica',
            facilitador=None,
            tipo='educativa',
            turno='Vespertino',
            horario_inicio=time(14, 0),
            horario_fim=time(15, 0),
        )
        self.atividade.alunos.add(self.aluno)

    def proximo_cpf(self):
        self.seq += 1
        return cpf_teste(123450000 + self.seq)

    def criar_familia(self):
        cpf = self.proximo_cpf()
        f = Family(
            pk=1000 + self.seq, registration_number=f'T{self.seq:05d}',
            responsible_name='Responsavel sintetica', social_name='Nome sintetico',
            cpf=cpf, birth_date=date(1980, 1, 2), sex='Feminino',
            mae_solo='Nao', marital_status='solteira', education='Ens. Med. Comp.',
            race='Pardo', religion='Nao possui religiao', cep='57000-000',
            address='Endereco sintetico', neighborhood='Bairro sintetico',
            num_residents=3, has_adult=2, has_child=1, status='ativo', location='',
        )
        # Utiliza os rotulos exatamente como definidos no modelo atual.
        f.mae_solo = 'Não'
        f.religion = 'Não possui religião'
        f.full_clean()
        f.save()
        return f

    def test_planejamento_nao_grava_no_banco(self):
        antes = lote.snapshot()
        plano = lote.novo_plano()
        self.assertEqual(plano['resumo']['selecionados'], 3)
        self.assertEqual(lote.snapshot(), antes)

    def test_cli_padrao_apenas_gera_arquivo(self):
        antes = lote.snapshot()
        with tempfile.TemporaryDirectory() as pasta:
            p = Path(pasta) / 'plano.json'
            call_command('aplicar_lote_person_v2', plano=str(p), stdout=io.StringIO())
            plano = json.loads(p.read_text(encoding='utf-8'))
            self.assertEqual(plano['versao'], 2)
            with self.assertRaises(CommandError):
                call_command('aplicar_lote_person_v2', plano=str(p), stdout=io.StringIO())
        self.assertEqual(lote.snapshot(), antes)

    def test_vincula_tres_origens_preservando_todos_os_outros_campos(self):
        origens = (self.familia, self.adulto, self.aluno)
        antes = {type(o): lote.estado(o) for o in origens}
        resultado = lote.aplicar_plano(lote.novo_plano())
        self.assertEqual(len(resultado), 3)
        self.assertEqual(Person.objects.count(), 3)
        for obj in origens:
            obj.refresh_from_db()
            campo = 'responsible_id' if isinstance(obj, Family) else 'person_id'
            esperado = dict(antes[type(obj)])
            esperado[campo] = getattr(obj, campo)
            self.assertIsNotNone(esperado[campo])
            self.assertEqual(lote.json_canonico(lote.estado(obj)), lote.json_canonico(esperado))
        self.assertEqual(HistoricoDesligamento.objects.count(), 0)
        self.assertTrue(self.atividade.alunos.filter(pk=self.aluno.pk).exists())

    def test_segunda_execucao_do_mesmo_plano_e_recusada_sem_duplicar(self):
        plano = lote.novo_plano()
        lote.aplicar_plano(plano)
        antes = lote.snapshot()
        with self.assertRaises(CommandError):
            lote.aplicar_plano(plano)
        self.assertEqual(lote.snapshot(), antes)
        self.assertEqual(lote.novo_plano()['resumo']['selecionados'], 0)

    def test_falha_no_ultimo_registro_reverte_todo_o_lote(self):
        plano = lote.novo_plano()
        antes = lote.snapshot()
        # Family e processada depois de Adult e Aluno na ordenacao do lote.
        with patch.object(Family, 'save', side_effect=RuntimeError('Falha sintetica')):
            with self.assertRaises(RuntimeError):
                lote.aplicar_plano(plano)
        self.assertEqual(lote.snapshot(), antes)

    def test_alteracao_da_base_invalida_plano(self):
        plano = lote.novo_plano()
        self.adulto.telephone = '000000000'
        self.adulto.save(update_fields=['telephone'])
        antes = lote.snapshot()
        with self.assertRaises(CommandError):
            lote.aplicar_plano(plano)
        self.assertEqual(lote.snapshot(), antes)

    def test_edicao_manual_do_plano_e_recusada(self):
        plano = lote.novo_plano()
        plano['selecionados'] = []
        with self.assertRaises(CommandError):
            lote.aplicar_plano(plano)
        self.assertEqual(Person.objects.count(), 0)

    def test_alteracao_de_assinatura_do_codigo_bloqueia(self):
        plano = lote.novo_plano()
        with patch.object(lote, 'assinatura_codigo', return_value='codigo_alterado'):
            with self.assertRaises(CommandError):
                lote.aplicar_plano(plano)
        self.assertEqual(Person.objects.count(), 0)

    def test_aluno_legado_sem_motivo_e_excluido_do_lote(self):
        legado = Aluno(
            pk=2001, family=self.familia, name='Legado sintetico',
            cpf=self.proximo_cpf(), sex='Feminino', birth_date=date(2010, 1, 1),
            status_lsd='desligado', motivo_desligamento_codigo='',
        )
        # Somente fixture no banco de testes: reproduz um registro historico invalido.
        Aluno.objects.bulk_create([legado])
        plano = lote.novo_plano()
        self.assertNotIn({'origem': 'Aluno', 'id': legado.pk}, plano['selecionados'])
        bloqueio = next(x for x in plano['bloqueados'] if x['origem'] == 'Aluno' and x['id'] == legado.pk)
        self.assertIn('motivo_desligamento_codigo', bloqueio['Origem'])
        lote.aplicar_plano(plano)
        legado.refresh_from_db()
        self.assertIsNone(legado.person_id)
        self.assertEqual(legado.status_lsd, 'desligado')
        self.assertEqual(legado.motivo_desligamento_codigo, '')

    def test_origem_sem_cpf_permanece_pendente(self):
        outro = Adult.objects.create(
            pk=2002, family=self.familia, name='Sem CPF sintetico',
            social_name='Nome sintetico', sex='Masculino',
            education='med_comp', cpf=None, birth_date=date(1970, 1, 1),
        )
        plano = lote.novo_plano()
        self.assertNotIn({'origem': 'Adult', 'id': outro.pk}, plano['selecionados'])
        lote.aplicar_plano(plano)
        outro.refresh_from_db()
        self.assertIsNone(outro.person_id)

    def test_endereco_longo_nao_e_truncado(self):
        self.familia.address = 'X' * 256
        self.familia.save(update_fields=['address'])
        plano = lote.novo_plano()
        item = next(x for x in plano['bloqueados'] if x['origem'] == 'Family')
        self.assertIn('address', item['Person'])
        lote.aplicar_plano(plano)
        self.familia.refresh_from_db()
        self.assertEqual(self.familia.address, 'X' * 256)
        self.assertIsNone(self.familia.responsible_id)

    def test_historico_criado_por_signal_cancela_e_reverte_lote(self):
        plano = lote.novo_plano()
        antes = lote.snapshot()
        def criar_evento(sender, instance, created, **kwargs):
            if created:
                HistoricoDesligamento.objects.create(
                    tipo_evento='familia_inativada', origem='manual', familia=self.familia,
                    motivo_codigo=MotivoDesligamentoChoices.choices[0][0],
                    motivo_descricao='Evento sintetico indevido',
                )
        post_save.connect(criar_evento, sender=Person, weak=False)
        try:
            with self.assertRaises(CommandError):
                lote.aplicar_plano(plano)
        finally:
            post_save.disconnect(criar_evento, sender=Person)
        self.assertEqual(lote.snapshot(), antes)

    def test_mudanca_m2m_por_signal_cancela_e_reverte_lote(self):
        plano = lote.novo_plano()
        antes = lote.snapshot()
        def remover_vinculo(sender, instance, created, **kwargs):
            if created:
                self.atividade.alunos.remove(self.aluno)
        post_save.connect(remover_vinculo, sender=Person, weak=False)
        try:
            with self.assertRaises(CommandError):
                lote.aplicar_plano(plano)
        finally:
            post_save.disconnect(remover_vinculo, sender=Person)
        self.assertEqual(lote.snapshot(), antes)

    def test_falta_de_confirmacoes_impede_aplicacao_cli(self):
        with tempfile.TemporaryDirectory() as pasta:
            p = Path(pasta) / 'plano.json'
            lote.gravar_exclusivo(p, lote.novo_plano())
            with self.assertRaises(CommandError):
                call_command('aplicar_lote_person_v2', plano=str(p), aplicar=True,
                             stdout=io.StringIO())
        self.assertEqual(Person.objects.count(), 0)
