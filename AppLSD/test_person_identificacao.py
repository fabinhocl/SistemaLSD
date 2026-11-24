"""Testes de preparacao; nenhuma integracao com views neste passo."""
from datetime import date
from django.core.exceptions import ValidationError
from django.test import TestCase
from AppLSD import test_person_lote_v2 as fixtures
from AppLSD.models import Family, Adult, Aluno, Person
from AppLSD.management.commands import aplicar_lote_person_v2 as lote
from AppLSD.person_identificacao import preparar_identificacao_person


class PreparacaoIdentificacaoTests(TestCase):
    # Reutiliza somente as fixtures ja corrigidas e aprovadas da suite anterior.
    proximo_cpf = fixtures.LotePersonV2Tests.proximo_cpf
    criar_familia = fixtures.LotePersonV2Tests.criar_familia

    def setUp(self):
        fixtures.LotePersonV2Tests.setUp(self)
        lote.aplicar_plano(lote.novo_plano())
        for obj in (self.familia, self.adulto, self.aluno):
            obj.refresh_from_db()

    def test_nome_adulto_preparado_sem_gravar(self):
        antes = lote.snapshot()
        self.adulto.name = 'Nome corrigido sintetico'
        pessoa, campos = preparar_identificacao_person(self.adulto)
        self.assertEqual(pessoa.full_name, self.adulto.name)
        self.assertEqual(campos, ['full_name'])
        self.assertEqual(lote.snapshot(), antes)

    def test_nome_responsavel_preparado_sem_gravar(self):
        antes = lote.snapshot()
        self.familia.responsible_name = 'Nome corrigido sintetico'
        pessoa, campos = preparar_identificacao_person(self.familia)
        self.assertEqual(pessoa.full_name, self.familia.responsible_name)
        self.assertEqual(campos, ['full_name'])
        self.assertEqual(lote.snapshot(), antes)

    def test_nascimento_e_sexo_aluno_preservam_outros_campos(self):
        antes = lote.snapshot()
        pessoa_original = Person.objects.get(pk=self.aluno.person_id)
        self.aluno.birth_date = date(2017, 3, 2)
        self.aluno.sex = 'Feminino'
        pessoa, campos = preparar_identificacao_person(self.aluno)
        self.assertEqual(set(campos), {'birth_date', 'gender'})
        self.assertEqual(pessoa.gender, 'F')
        for campo in ('cpf', 'phone', 'address', 'notes', 'family_id'):
            self.assertEqual(getattr(pessoa, campo), getattr(pessoa_original, campo))
        self.assertEqual(lote.snapshot(), antes)

    def test_cpf_diferente_e_bloqueado(self):
        self.adulto.cpf = self.proximo_cpf()
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.adulto)
        self.assertEqual(lote.snapshot(), antes)

    def test_formatacao_do_mesmo_cpf_nao_troca_identidade(self):
        d = lote.montar_person(self.adulto).cpf
        self.adulto.cpf = f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
        pessoa, campos = preparar_identificacao_person(self.adulto)
        self.assertEqual(pessoa.pk, self.adulto.person_id)
        self.assertEqual(campos, [])

    def test_nascimento_desconhecido_continua_opcional(self):
        self.aluno.birth_date = None
        pessoa, campos = preparar_identificacao_person(self.aluno)
        self.assertIsNone(pessoa.birth_date)
        self.assertEqual(campos, ['birth_date'])

    def test_sem_alteracao_retorna_lista_vazia(self):
        pessoa, campos = preparar_identificacao_person(self.aluno)
        self.assertEqual(pessoa.pk, self.aluno.person_id)
        self.assertEqual(campos, [])

    def test_nome_e_sexo_invalidos_nao_gravam(self):
        antes = lote.snapshot()
        self.aluno.name = '   '
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.aluno)
        self.aluno.name = 'Nome valido'
        self.aluno.sex = 'invalido'
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.aluno)
        self.assertEqual(lote.snapshot(), antes)

    def test_troca_de_familia_ou_identidade_e_bloqueada(self):
        outra = self.criar_familia()
        self.adulto.family = outra
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.adulto)
        self.adulto.refresh_from_db()
        self.adulto.person_id = self.aluno.person_id
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.adulto)

    def test_cadastro_novo_nao_e_regularizado_implicitamente(self):
        novo = Adult(family=self.familia, name='Novo sintetico')
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(novo)

    def test_cadastro_persistido_sem_person_e_bloqueado(self):
        outro = Adult.objects.create(
            family=self.familia, name='Outro sintetico', social_name='Outro sintetico',
            cpf=self.proximo_cpf(), sex='Masculino', education='med_comp',
        )
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(outro)
        self.assertEqual(lote.snapshot(), antes)

    def test_person_compartilhada_exige_fluxo_coordenado(self):
        # Somente fixture sintetica: reproduz outra origem com a mesma identidade.
        outra = self.criar_familia()
        outra.responsible_id = self.adulto.person_id
        outra.save(update_fields=['responsible'])
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.adulto)
        self.assertEqual(lote.snapshot(), antes)

    def test_cpf_em_outra_origem_e_bloqueado(self):
        duplicado = Aluno(
            pk=2005, family=self.familia, name='Duplicado sintetico',
            cpf=self.adulto.cpf, sex='Masculino', status_lsd='',
        )
        duplicado.save()
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.adulto)

    def test_cpf_em_outro_person_e_bloqueado(self):
        Person.objects.create(full_name='Outra identidade sintetica', gender='M',
                              cpf=self.adulto.cpf, family=self.familia)
        with self.assertRaises(ValidationError):
            preparar_identificacao_person(self.adulto)
