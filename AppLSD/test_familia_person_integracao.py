from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from . import familia_person_services
from .forms import AlunoInlineFormSet, FamilyForm
from .models import Aluno, AppLog, Family, Person


class FamiliaPersonIntegracaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operador = get_user_model().objects.create_superuser(
            username="super_familia_person_sintetico", password=None
        )

    def setUp(self):
        self.client.force_login(self.operador)
        self.url = reverse("family_create")
        opcoes_form = {valor for valor, _ in FamilyForm.base_fields["education"].choices}
        escolaridade = next(
            (
                valor
                for valor, _ in Family._meta.get_field("education").flatchoices
                if valor and valor in opcoes_form
            ),
            None,
        )
        self.assertIsNotNone(
            escolaridade, "FamilyForm e Family não têm opção de escolaridade em comum."
        )
        self.dados = {
            "registration_number": "T81001",
            "responsible_name": "Responsável sintético integração",
            "social_name": "Responsável sintético",
            "cpf": "529.982.247-25",
            "birth_date": "1980-01-02",
            "sex": "Feminino",
            "mae_solo": "Não",
            "marital_status": "solteira",
            "education": escolaridade,
            "race": "Pardo",
            "religion": "Não possui religião",
            "cep": "57000-000",
            "address": "Rua fictícia",
            "neighborhood": "Bairro fictício",
            "is_benefits": "Não",
            "is_working": "Não",
            "has_proven_income": "Não",
            "others_contribute": "Não",
            "num_residents": "1",
            "has_adult": "1",
            "has_elderly": "0",
            "has_pcd": "0",
            "has_adolescent": "0",
            "has_child": "0",
            "has_pregnant": "0",
            "status": "ativo",
        }
        formulario_base = FamilyForm(data=self.dados)
        self.assertTrue(formulario_base.is_valid(), formulario_base.errors.as_json())

    def _contagens(self):
        return tuple(m.objects.count() for m in (Family, Person, Aluno, AppLog))

    def _criar(self):
        resposta = self.client.post(self.url, self.dados)
        erros = (
            resposta.context["form"].errors.as_json()
            if resposta.context and "form" in resposta.context else ""
        )
        self.assertEqual(resposta.status_code, 302, erros)
        familia = Family.objects.get(registration_number=self.dados["registration_number"])
        self.assertRedirects(
            resposta, reverse("family_detail", args=[familia.pk]),
            fetch_redirect_response=False,
        )
        return familia

    def test_cria_familia_pessoa_vinculos_e_auditoria(self):
        antes = self._contagens()
        familia = self._criar()
        pessoa = familia.responsible
        self.assertIsNotNone(pessoa)
        self.assertEqual(pessoa.family_id, familia.pk)
        self.assertEqual(pessoa.full_name, familia.responsible_name)
        self.assertEqual(pessoa.birth_date, date(1980, 1, 2))
        self.assertEqual(pessoa.gender, "F")
        self.assertEqual(pessoa.cpf, familia.cpf)
        self.assertEqual(familia.criado_por_id, self.operador.pk)
        self.assertEqual(self._contagens(), tuple(a + b for a, b in zip(antes, (1, 1, 0, 2))))
        for objeto, acao in ((familia, "familia_criada"), (pessoa, "person_criada")):
            self.assertEqual(AppLog.objects.filter(
                content_type=ContentType.objects.get_for_model(objeto),
                object_id=objeto.pk, acao=acao, criado_por=self.operador,
            ).count(), 1)

    def test_cpf_sem_mascara_em_person_bloqueia_sem_reaproveitamento(self):
        Person.objects.create(full_name="Pessoa sintética anterior", gender="M", cpf="52998224725")
        antes = self._contagens()
        resposta = self.client.post(self.url, self.dados)
        self.assertContains(resposta, "CPF já utilizado", status_code=400)
        self.assertEqual(self._contagens(), antes)

    def test_sexo_vazio_recusado_sem_gravar(self):
        antes = self._contagens()
        resposta = self.client.post(self.url, {**self.dados, "sex": ""})
        self.assertContains(resposta, "Informe nome, sexo e CPF", status_code=400)
        self.assertEqual(self._contagens(), antes)

    def test_formset_legado_recusado_sem_gravar(self):
        antes = self._contagens()
        prefixo = AlunoInlineFormSet.get_default_prefix()
        resposta = self.client.post(self.url, {**self.dados, f"{prefixo}-TOTAL_FORMS": "0"})
        self.assertContains(resposta, "Nenhum cadastro foi salvo", status_code=400)
        self.assertEqual(self._contagens(), antes)

    def test_falha_na_segunda_auditoria_desfaz_as_duas_gravacoes_e_o_primeiro_log(self):
        antes = self._contagens()
        registrar_log = familia_person_services.registrar_log

        def falhar_no_log_da_familia(operador, objeto, acao, descricao):
            if acao == "familia_criada":
                raise ValidationError("Falha de auditoria simulada.")
            registrar_log(operador, objeto, acao, descricao)

        with patch.object(familia_person_services, "registrar_log", falhar_no_log_da_familia):
            resposta = self.client.post(self.url, self.dados)
        self.assertContains(resposta, "Falha de auditoria simulada", status_code=400)
        self.assertEqual(self._contagens(), antes)

    def test_edicao_comum_bloqueia_nome_mas_preserva_edicao_social(self):
        familia = self._criar()
        url = reverse("family_edit", args=[familia.pk])
        resposta = self.client.post(url, {**self.dados, "responsible_name": "Nome diferente"})
        self.assertContains(resposta, "não podem ser alterados nesta tela")
        familia.refresh_from_db()
        self.assertEqual(familia.responsible_name, self.dados["responsible_name"])
        resposta = self.client.post(url, {**self.dados, "address": "Novo endereço fictício"})
        self.assertEqual(resposta.status_code, 302)
        familia.refresh_from_db()
        self.assertEqual(familia.address, "Novo endereço fictício")
        self.assertEqual(familia.responsible.full_name, familia.responsible_name)
