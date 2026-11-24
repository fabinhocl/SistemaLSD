from datetime import date
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from .familia_person_services import criar_familia_com_responsavel
from .forms import AlunoInlineFormSet
from .models import AppLog, Family, PerfilUsuario, Person


class FamiliaPermissoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.usuarios = {}
        for perfil in ("servicosocial", "admin", "coordenacao", "colaborador"):
            usuario = user_model.objects.create_user(username=f"familia_teste_{perfil}")
            PerfilUsuario.objects.get_or_create(user=usuario, tipo_perfil=perfil)
            cls.usuarios[perfil] = usuario
        cls.superusuario = user_model.objects.create_superuser(
            username="familia_teste_super", password=None,
        )
        cls.inativo = user_model.objects.create_user(
            username="familia_teste_inativo", is_active=False,
        )
        PerfilUsuario.objects.get_or_create(user=cls.inativo, tipo_perfil="admin")
        cls.familia = Family.objects.create(
            registration_number="T83001", responsible_name="Responsável sintético",
            birth_date=date(1980, 1, 2), sex="Feminino", status="ativo",
            num_residents=1, has_adult=1, cpf=None,
        )

    def caminhos_tela(self):
        return (reverse("family_create"), reverse("family_edit", args=[self.familia.pk]))

    def estado(self):
        return (
            list(Family.objects.order_by("pk").values()),
            Person.objects.count(),
            AppLog.objects.count(),
        )

    def test_servico_social_admin_e_superusuario_acessam_telas(self):
        usuarios = (self.usuarios["servicosocial"], self.usuarios["admin"], self.superusuario)
        for usuario in usuarios:
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                for url in self.caminhos_tela():
                    self.assertEqual(self.client.get(url).status_code, 200)
                # Envio sem efeito comprova que o POST autorizado chegou à view.
                prefixo = AlunoInlineFormSet.get_default_prefix()
                resposta = self.client.post(
                    self.caminhos_tela()[0], {f"{prefixo}-TOTAL_FORMS": "0"}
                )
                self.assertContains(resposta, "Nenhum cadastro foi salvo", status_code=400)

    def test_coordenacao_e_colaborador_nao_abrem_nem_enviam_formularios(self):
        antes = self.estado()
        for perfil in ("coordenacao", "colaborador"):
            with self.subTest(perfil=perfil):
                self.client.force_login(self.usuarios[perfil])
                for url in self.caminhos_tela():
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertEqual(self.estado(), antes)

    def test_servico_recusa_operador_inativo_ou_sem_perfil(self):
        for operador in (self.inativo, self.usuarios["coordenacao"]):
            with self.subTest(usuario=operador.username):
                form = Mock()
                with self.assertRaises(PermissionDenied):
                    criar_familia_com_responsavel(form, operador)
                form.is_valid.assert_not_called()

    def test_admin_bloqueia_add_e_change_mas_preserva_consulta(self):
        self.client.force_login(self.superusuario)
        modelo = Family._meta
        base = f"admin:{modelo.app_label}_{modelo.model_name}_"
        add = reverse(base + "add")
        detalhe = reverse(base + "change", args=[self.familia.pk])
        antes = self.estado()
        self.assertEqual(self.client.get(reverse(base + "changelist")).status_code, 200)
        self.assertEqual(self.client.get(detalhe).status_code, 200)
        self.assertEqual(self.client.get(add).status_code, 403)
        self.assertEqual(self.client.post(add, {"_save": "1"}).status_code, 403)
        self.assertEqual(self.client.post(detalhe, {"_save": "1"}).status_code, 403)
        self.assertEqual(self.estado(), antes)

    def test_api_preserva_get_recusa_escritas_cadastrais_e_mantem_rota_delete(self):
        cliente = APIClient()
        cliente.force_authenticate(user=self.superusuario)
        lista = reverse("family-list")
        detalhe = reverse("family-detail", args=[self.familia.pk])
        antes = self.estado()
        self.assertEqual(cliente.get(lista).status_code, 200)
        self.assertEqual(cliente.get(detalhe).status_code, 200)
        self.assertEqual(cliente.post(lista, {}, format="json").status_code, 405)
        self.assertEqual(cliente.put(detalhe, {}, format="json").status_code, 405)
        self.assertEqual(cliente.patch(detalhe, {}, format="json").status_code, 405)
        # Confere o roteamento sem excluir registros.
        self.assertEqual(resolve(detalhe).func.actions.get("delete"), "destroy")
        self.assertEqual(self.estado(), antes)
