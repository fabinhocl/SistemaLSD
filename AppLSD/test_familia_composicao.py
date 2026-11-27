from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Aluno, Family


class FamiliaComposicaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="super_composicao", password=None)
        cls.familia = Family.objects.create(
            registration_number="T80010", responsible_name="Responsavel sintetico",
            birth_date=date(1980, 1, 2), sex="Feminino", status="ativo",
            num_residents=5, has_adult=1, has_child=4)

        def novo(nome, status, **extra):
            return Aluno.objects.create(
                family=cls.familia, name=nome, birth_date=date(2016, 3, 4),
                sex="Masculino", status_lsd=status, possui_sisc="nao",
                justificativa_sisc="outros", justificativa_sisc_outros="Fixture",
                **extra)

        cls.freq = novo("Freq sintetico", "Frequentando")
        cls.nao = novo("Nao freq sintetico", "nao_frequenta")
        cls.desl = novo("Desligado sintetico", "desligado",
                        motivo_desligamento_codigo="mudanca_endereco")
        cls.branco = novo("Branco sintetico", "")
        cls.legado = novo("Legado sintetico", "desligado",
                          motivo_desligamento_codigo="mudanca_endereco")
        Aluno.objects.filter(pk=cls.legado.pk).update(status_lsd="Desligado")

    def test_composicao_separa_as_tabelas(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse("family_detail", args=[self.familia.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([a.pk for a in resposta.context["assistidos_frequentando"]],
                         [self.freq.pk])
        self.assertEqual([a.pk for a in resposta.context["assistidos_nao_frequentam"]],
                         [self.branco.pk, self.nao.pk, self.desl.pk, self.legado.pk])
        self.assertEqual([a.pk for a in resposta.context["assistidos_a_classificar"]],
                         [self.branco.pk])