from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Aluno, AppLog, Family, Person


class ApiAlunoSomenteConsultaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_superuser(
            username="super_teste_api_aluno", password=None,
        )
        familia = Family.objects.create(
            registration_number="T80003", responsible_name="Responsavel sintetico API",
            birth_date=date(1980, 1, 2), sex="Feminino", status="ativo",
            num_residents=2, has_adult=1, has_child=1,
        )
        cls.aluno = Aluno.objects.create(
            family=familia, name="Assistido sintetico API",
            birth_date=date(2018, 4, 5), sex="Masculino",
            status_lsd="Frequentando", possui_sisc="nao",
            justificativa_sisc="outros", justificativa_sisc_outros="Fixture de teste",
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        self.lista = reverse("aluno-list")
        self.detalhe = reverse("aluno-detail", args=[self.aluno.pk])

    def test_lista_e_detalhe_continuam_disponiveis(self):
        self.assertEqual(self.client.get(self.lista).status_code, 200)
        self.assertEqual(self.client.get(self.detalhe).status_code, 200)

    def test_escrita_recusada_sem_alterar_registros(self):
        def snapshot():
            return tuple(list(m.objects.order_by("pk").values()) for m in (Aluno, Person, AppLog))

        antes = snapshot()
        for metodo, url in (("post", self.lista), ("put", self.detalhe),
                            ("patch", self.detalhe), ("delete", self.detalhe)):
            with self.subTest(metodo=metodo):
                resposta = getattr(self.client, metodo)(
                    url, data='{"name":"Nao gravar"}', content_type="application/json",
                )
                self.assertEqual(resposta.status_code, 405)
                self.assertEqual(snapshot(), antes)
