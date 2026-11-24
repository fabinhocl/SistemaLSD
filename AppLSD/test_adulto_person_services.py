"""Testes do servico interno. Nao altera URLs, templates ou views."""
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from AppLSD import test_person_lote_v2 as fixtures
from AppLSD import adulto_person_services as servico
from AppLSD.models import Adult, Person, AppLog
from AppLSD.management.commands import aplicar_lote_person_v2 as lote


class EdicaoAdultoPersonTests(TestCase):
    proximo_cpf = fixtures.LotePersonV2Tests.proximo_cpf
    criar_familia = fixtures.LotePersonV2Tests.criar_familia

    def setUp(self):
        from AppLSD.models import PerfilUsuario
        fixtures.LotePersonV2Tests.setUp(self)
        lote.aplicar_plano(lote.novo_plano())
        self.adulto.refresh_from_db()
        self.usuario = get_user_model().objects.create_user(
            username='operador_person_sintetico', password=None)
        PerfilUsuario.objects.create(user=self.usuario, tipo_perfil='servicosocial')
        _, self.token = servico.criar_token_edicao_adulto(
            usuario=self.usuario, adulto_id=self.adulto.pk)

    def salvar(self, alteracoes, token=None, usuario=None):
        return servico.salvar_edicao_adulto(
            usuario=usuario if usuario is not None else self.usuario,
            adulto_id=self.adulto.pk, alteracoes=alteracoes,
            token=self.token if token is None else token)

    def test_nome_gravado_nas_duas_pontas_e_auditado(self):
        resultado = self.salvar({'name': 'Nome corrigido sintetico'})
        self.adulto.refresh_from_db()
        pessoa = Person.objects.get(pk=self.adulto.person_id)
        self.assertEqual(self.adulto.name, 'Nome corrigido sintetico')
        self.assertEqual(pessoa.full_name, self.adulto.name)
        self.assertEqual(self.adulto.editado_por_id, self.usuario.pk)
        self.assertTrue(resultado['alterado'])
        self.assertEqual(AppLog.objects.filter(acao='adulto_editado').count(), 1)
        self.assertEqual(AppLog.objects.filter(acao='person_identificacao_atualizada').count(), 1)

    def test_nascimento_e_sexo_sincronizados(self):
        self.salvar({'birth_date': date(1984, 3, 2), 'sex': 'Feminino'})
        pessoa = Person.objects.get(pk=self.adulto.person_id)
        self.adulto.refresh_from_db()
        self.assertEqual(pessoa.birth_date, self.adulto.birth_date)
        self.assertEqual(pessoa.gender, 'F')

    def test_telefone_nao_e_copiado_para_person_nesta_etapa(self):
        telefone_person = Person.objects.get(pk=self.adulto.person_id).phone
        resultado = self.salvar({'telephone': '000000000'})
        self.adulto.refresh_from_db()
        self.assertEqual(self.adulto.telephone, '000000000')
        self.assertEqual(Person.objects.get(pk=self.adulto.person_id).phone, telefone_person)
        self.assertEqual(resultado['campos_person'], [])

    def test_sem_alteracao_nao_grava_nem_cria_log(self):
        antes = lote.snapshot()
        resultado = self.salvar({})
        self.assertFalse(resultado['alterado'])
        self.assertEqual(lote.snapshot(), antes)

    def test_troca_de_cpf_reverte_tudo(self):
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.salvar({'name': 'Nao persistir', 'cpf': self.proximo_cpf()})
        self.assertEqual(lote.snapshot(), antes)

    def test_falha_no_save_adulto_reverte_person(self):
        antes = lote.snapshot()
        with patch.object(Adult, 'save', side_effect=RuntimeError('Falha sintetica')):
            with self.assertRaises(RuntimeError):
                self.salvar({'name': 'Nao persistir'})
        self.assertEqual(lote.snapshot(), antes)

    def test_falha_no_log_reverte_as_duas_pontas(self):
        antes = lote.snapshot()
        with patch.object(servico, 'registrar_log', side_effect=RuntimeError('Falha sintetica')):
            with self.assertRaises(RuntimeError):
                self.salvar({'name': 'Nao persistir'})
        self.assertEqual(lote.snapshot(), antes)

    def test_formulario_antigo_detecta_mudanca_no_adulto(self):
        self.adulto.telephone = '000000000'
        self.adulto.save(update_fields=['telephone'])
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.salvar({'name': 'Nao persistir'})
        self.assertEqual(lote.snapshot(), antes)

    def test_formulario_antigo_detecta_mudanca_no_person(self):
        pessoa = Person.objects.get(pk=self.adulto.person_id)
        pessoa.notes = 'Alteracao sintetica concorrente'
        pessoa.save(update_fields=['notes'])
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.salvar({'name': 'Nao persistir'})
        self.assertEqual(lote.snapshot(), antes)

    def test_token_adulterado_e_recusado(self):
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.salvar({'name': 'Nao persistir'}, token='adulterado')
        self.assertEqual(lote.snapshot(), antes)

    def test_token_de_outro_operador_e_recusado(self):
        from AppLSD.models import PerfilUsuario
        outro = get_user_model().objects.create_user(username='outro_sintetico', password=None)
        PerfilUsuario.objects.create(user=outro, tipo_perfil='admin')
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.salvar({'name': 'Nao persistir'}, usuario=outro)
        self.assertEqual(lote.snapshot(), antes)

    def test_usuario_sem_permissao_e_recusado(self):
        outro = get_user_model().objects.create_user(username='sem_permissao_sintetico', password=None)
        outro.user_permissions.add(Permission.objects.get(
            content_type__app_label='AppLSD', codename='change_adult'))
        antes = lote.snapshot()
        with self.assertRaises(PermissionDenied):
            self.salvar({'name': 'Nao persistir'}, usuario=outro)
        self.assertEqual(lote.snapshot(), antes)

    def test_usuario_inativo_ou_anonimo_e_recusado(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=['is_active'])
        antes = lote.snapshot()
        for usuario in (self.usuario, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                self.salvar({'name': 'Nao persistir'}, usuario=usuario)
        self.assertEqual(lote.snapshot(), antes)

    def test_campos_protegidos_e_cadastro_sem_person_nao_sao_aproveitados(self):
        antes = lote.snapshot()
        for alteracoes in ({'family_id': self.familia.pk}, {'person_id': self.adulto.person_id}):
            with self.assertRaises(ValidationError):
                self.salvar(alteracoes)
        self.assertEqual(lote.snapshot(), antes)
        self.adulto.person = None
        self.adulto.save(update_fields=['person'])
        _, token = servico.criar_token_edicao_adulto(usuario=self.usuario, adulto_id=self.adulto.pk)
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.salvar({'name': 'Nao persistir'}, token=token)
        self.assertEqual(lote.snapshot(), antes)
