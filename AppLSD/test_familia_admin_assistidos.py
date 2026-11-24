from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .forms import AlunoInlineFormSet
from .models import Aluno, AppLog, Family, Person


class FamiliaAdminAssistidosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.superusuario = User.objects.create_superuser(
            username="super_teste_familia_admin",
            password=None,
        )
        cls.consultor = User.objects.create_user(
            username="consulta_teste_aluno",
            is_staff=True,
        )
        cls.consultor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label=Aluno._meta.app_label,
                content_type__model=Aluno._meta.model_name,
                codename="view_aluno",
            )
        )
        familia = Family.objects.create(
            registration_number="T80001",
            responsible_name="Responsável sintético",
            birth_date=date(1980, 1, 2),
            sex="Feminino",
            status="ativo",
            num_residents=2,
            has_adult=1,
            has_child=1,
        )
        cls.aluno = Aluno.objects.create(
            family=familia,
            name="Assistido sintético",
            birth_date=date(2018, 4, 5),
            sex="Masculino",
            status_lsd="Frequentando",
            possui_sisc="nao",
            justificativa_sisc="outros",
            justificativa_sisc_outros="Fixture de teste",
        )

    def url_admin(self, acao, *args):
        meta = Aluno._meta
        return reverse(
            f"admin:{meta.app_label}_{meta.model_name}_{acao}",
            args=args,
        )

    def test_formulario_legado_retorna_400_sem_gravar(self):
        self.client.force_login(self.superusuario)
        modelos = (Family, Aluno, Person, AppLog)
        antes = {modelo: modelo.objects.count() for modelo in modelos}
        prefixo = AlunoInlineFormSet.get_default_prefix()

        resposta = self.client.post(
            reverse("family_create"),
            {
                "registration_number": "T80002",
                "responsible_name": "Outra família sintética",
                f"{prefixo}-TOTAL_FORMS": "1",
                f"{prefixo}-INITIAL_FORMS": "0",
                f"{prefixo}-0-name": "Assistido do formulário antigo",
            },
        )

        self.assertContains(
            resposta, "Nenhum cadastro foi salvo", status_code=400
        )
        for modelo in modelos:
            with self.subTest(modelo=modelo.__name__):
                self.assertEqual(modelo.objects.count(), antes[modelo])

    def test_usuario_com_permissao_consegue_consultar(self):
        self.client.force_login(self.consultor)
        self.assertContains(
            self.client.get(self.url_admin("changelist")),
            self.aluno.name,
        )
        self.assertContains(
            self.client.get(self.url_admin("change", self.aluno.pk)),
            self.aluno.name,
        )

    def test_admin_recusa_gravacao_direta_e_exclusao_em_lote(self):
        meta = Aluno._meta
        antes = list(Aluno.objects.order_by("pk").values())
        for usuario in (self.consultor, self.superusuario):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                for acao, args, dados in (
                    ("add", (), {"name": "Inclusão indevida", "_save": "1"}),
                    (
                        "change",
                        (self.aluno.pk,),
                        {"name": "Alteração indevida", "_save": "1"},
                    ),
                    ("delete", (self.aluno.pk,), {"post": "yes"}),
                ):
                    with self.subTest(acao=acao):
                        self.assertEqual(
                            self.client.post(
                                self.url_admin(acao, *args), dados
                            ).status_code,
                            403,
                        )

                lista = self.url_admin("changelist")
                resposta = self.client.get(lista)
                model_admin = resposta.context["cl"].model_admin
                self.assertNotIn(
                    "delete_selected",
                    model_admin.get_actions(resposta.wsgi_request),
                )
                resposta = self.client.post(
                    lista,
                    {
                        "action": "delete_selected",
                        "_selected_action": str(self.aluno.pk),
                        "post": "yes",
                        "index": "0",
                    },
                )
                # Uma ação indisponível pode ser ignorada ou redirecionada.
                self.assertIn(resposta.status_code, (200, 302, 403))
                self.assertEqual(
                    list(Aluno.objects.order_by("pk").values()), antes
                )