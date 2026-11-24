"""Testes sinteticos. Executar somente com manage.py test em PostgreSQL."""
from datetime import date
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.http import HttpResponse
from django.test import TestCase, Client, override_settings
from django.urls import path
from django.urls.resolvers import RegexPattern, URLResolver
from AppLSD.models import Family, Adult, Aluno, Person, PerfilUsuario, AppLog
from AppLSD.adulto_person_criacao_services import criar_adulto_com_person
from AppLSD.adulto_person_services import criar_token_edicao_adulto, salvar_edicao_adulto
from AppLSD.management.commands import aplicar_lote_person_v2 as lote
from AppLSD.test_person_lote_v2 import cpf_teste
from AppLSD import views_templates


def detalhe(request, pk=None):
    return HttpResponse("Destino sintetico")


# URLCONF_REAL_CRIACAO_TESTE_V1
_URLCONF_PROJETO_CRIACAO_TESTE = settings.ROOT_URLCONF
if _URLCONF_PROJETO_CRIACAO_TESTE == __name__:
    raise RuntimeError('Execute os testes com as configuracoes normais do projeto.')

urlpatterns = [
    path("adult/new/", views_templates.adult_create, name="adult_create"),
    path("families/<int:pk>/", detalhe, name="family_detail"),
    path("families/", detalhe, name="family_list"),
]

# Resolucao tardia: importa as rotas reais somente quando forem consultadas.
# Mantem as tres rotas sinteticas para o despacho das requisicoes testadas.
urlpatterns += [URLResolver(RegexPattern(r'^'), _URLCONF_PROJETO_CRIACAO_TESTE)]


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=["testserver"],
    MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware",
                "django.middleware.csrf.CsrfViewMiddleware",
                "django.contrib.auth.middleware.AuthenticationMiddleware",
                "django.contrib.messages.middleware.MessageMiddleware"])
class CriacaoAdultoPersonTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.seq = 0
        self.familia = self.nova_familia()
        self.usuario = self.operador("social_criacao", "servicosocial")

    def cpf(self):
        self.seq += 1
        return cpf_teste(432100000 + self.seq)

    def nova_familia(self):
        f = Family(
            registration_number="S" + str(self.seq + 1), responsible_name="Responsavel sintetica",
            social_name="Responsavel sintetica", cpf=self.cpf(), birth_date=date(1980, 1, 2),
            sex="Feminino", mae_solo="Não", marital_status="solteira",
            education="Ens. Med. Comp.", race="Pardo", religion="Não possui religião",
            cep="57000-000", address="Endereco sintetico", neighborhood="Bairro sintetico",
            num_residents=3, has_adult=2, has_child=1, status="ativo", location="")
        f.full_clean()
        f.save()
        return f

    def operador(self, username, perfil=None, **kwargs):
        u = get_user_model().objects.create_user(username=username, password="SenhaSintetica!", **kwargs)
        if perfil:
            PerfilUsuario.objects.get_or_create(user=u, tipo_perfil=perfil)
        return u

    def dados(self, **kwargs):
        dados = dict(name="Adulto sintetico criacao", social_name="Nome sintetico",
                     cpf=self.cpf(), birth_date=date(1985, 2, 3), sex="Masculino",
                     education="med_comp", status="trabalha", telephone="82999990000")
        dados.update(kwargs)
        return dados

    def criar(self, dados=None, usuario=None):
        return criar_adulto_com_person(usuario=usuario or self.usuario,
            familia_id=self.familia.pk, dados=dados if dados is not None else self.dados())

    def verificar_bloqueio(self, dados):
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.criar(dados)
        self.assertEqual(lote.snapshot(), antes)

    def test_cria_duas_pontas_e_dois_logs(self):
        antes_familia = lote.estado(self.familia)
        r = self.criar()
        a = r["adulto"]
        p = Person.objects.get(pk=r["person_id"])
        self.assertEqual(a.person_id, p.pk)
        self.assertEqual((p.full_name, p.birth_date, p.gender), (a.name, a.birth_date, "M"))
        self.assertEqual(a.criado_por_id, self.usuario.pk)
        self.assertEqual(AppLog.objects.count(), 2)
        self.assertEqual(set(AppLog.objects.values_list("acao", flat=True)), {"adulto_criado", "person_criada"})
        self.assertEqual(set(AppLog.objects.values_list("criado_por_id", flat=True)), {self.usuario.pk})
        self.familia.refresh_from_db()
        self.assertEqual(lote.estado(self.familia), antes_familia)
        self.assertEqual(Aluno.objects.count(), 0)

    def test_cria_sem_cpf(self):
        a = self.criar(self.dados(cpf=None))["adulto"]
        self.assertIsNone(a.cpf)
        self.assertIsNone(a.person.cpf)

    def test_cpf_vazio_normalizado_para_null(self):
        a = self.criar(self.dados(cpf="   "))["adulto"]
        self.assertIsNone(a.cpf)
        self.assertIsNone(a.person.cpf)

    def test_nascimento_desconhecido_continua_opcional(self):
        a = self.criar(self.dados(birth_date=None))["adulto"]
        self.assertIsNone(a.birth_date)
        self.assertIsNone(a.person.birth_date)

    def test_telefone_fica_apenas_no_adulto(self):
        a = self.criar()["adulto"]
        self.assertEqual(a.telephone, "82999990000")
        self.assertIsNone(a.person.phone)

    def test_sem_cpf_permite_edicao_posterior(self):
        a = self.criar(self.dados(cpf=None))["adulto"]
        _, token = criar_token_edicao_adulto(usuario=self.usuario, adulto_id=a.pk)
        r = salvar_edicao_adulto(usuario=self.usuario, adulto_id=a.pk,
            alteracoes={"name": "Adulto sintetico corrigido"}, token=token)
        a.refresh_from_db()
        self.assertTrue(r["alterado"])
        self.assertEqual(a.person.full_name, a.name)
        self.assertIsNone(a.cpf)

    def test_sem_cpf_sem_alteracao_nao_gera_log(self):
        a = self.criar(self.dados(cpf=None))["adulto"]
        _, token = criar_token_edicao_adulto(usuario=self.usuario, adulto_id=a.pk)
        antes = lote.snapshot()
        r = salvar_edicao_adulto(usuario=self.usuario, adulto_id=a.pk, alteracoes={}, token=token)
        self.assertFalse(r["alterado"])
        self.assertEqual(lote.snapshot(), antes)

    def test_incluir_cpf_na_edicao_comum_continua_bloqueado(self):
        a = self.criar(self.dados(cpf=None))["adulto"]
        _, token = criar_token_edicao_adulto(usuario=self.usuario, adulto_id=a.pk)
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            salvar_edicao_adulto(usuario=self.usuario, adulto_id=a.pk,
                alteracoes={"cpf": self.cpf()}, token=token)
        self.assertEqual(lote.snapshot(), antes)

    def test_remover_cpf_na_edicao_comum_continua_bloqueado(self):
        a = self.criar()["adulto"]
        _, token = criar_token_edicao_adulto(usuario=self.usuario, adulto_id=a.pk)
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            salvar_edicao_adulto(usuario=self.usuario, adulto_id=a.pk,
                alteracoes={"cpf": None}, token=token)
        self.assertEqual(lote.snapshot(), antes)

    def test_sem_cpf_nao_pode_mudar_para_identificacao_ambigua(self):
        a = self.criar(self.dados(cpf=None))["adulto"]
        self.criar(self.dados(name="Outro adulto sintetico", cpf=None))
        _, token = criar_token_edicao_adulto(usuario=self.usuario, adulto_id=a.pk)
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            salvar_edicao_adulto(usuario=self.usuario, adulto_id=a.pk,
                alteracoes={"name": "Outro adulto sintetico"}, token=token)
        self.assertEqual(lote.snapshot(), antes)

    def test_reenvio_identico_nao_duplica(self):
        dados = self.dados()
        self.criar(dados)
        self.verificar_bloqueio(dados)

    def test_varios_sem_cpf_com_identificacao_distinta(self):
        self.criar(self.dados(cpf=None))
        self.criar(self.dados(cpf=None, name="Outro nome sintetico"))
        self.assertEqual(Adult.objects.count(), 2)
        self.assertEqual(Person.objects.count(), 2)

    def test_mesmo_nome_e_data_sem_cpf_bloqueia(self):
        self.criar(self.dados(cpf=None))
        self.verificar_bloqueio(self.dados(cpf=None))

    def test_nome_normalizado_duplicado_bloqueia(self):
        self.criar(self.dados(name="Adulto Árvore", cpf=None))
        self.verificar_bloqueio(self.dados(name="  ADULTO ARVORE  ", cpf=None))

    def test_nome_igual_e_nascimento_desconhecido_bloqueia(self):
        self.criar(self.dados(cpf=None))
        self.verificar_bloqueio(self.dados(cpf=None, birth_date=None))

    def test_nome_igual_datas_distintas_nao_e_fundido(self):
        self.criar(self.dados(cpf=None))
        self.criar(self.dados(cpf=None, birth_date=date(1986, 4, 5)))
        self.assertEqual(Person.objects.count(), 2)

    def test_cpf_ja_presente_em_responsavel_bloqueia(self):
        self.verificar_bloqueio(self.dados(cpf=self.familia.cpf))

    def test_person_existente_nao_e_reutilizada(self):
        cpf = self.cpf()
        Person.objects.create(family=self.familia, full_name="Identidade sintetica",
            gender="M", birth_date=date(1970, 1, 2), cpf=cpf)
        self.verificar_bloqueio(self.dados(cpf=cpf))

    def test_legado_fora_do_recorte_tambem_e_consultado(self):
        f = self.nova_familia()
        f.status = None
        f.save(update_fields=["status"])
        self.verificar_bloqueio(self.dados(cpf=f.cpf))

    def test_origem_excluida_tambem_e_consultada(self):
        a = self.criar()["adulto"]
        a.excluido = True
        a.save(update_fields=["excluido"])
        self.verificar_bloqueio(self.dados(cpf=a.cpf, name="Nome diferente sintetico"))

    def test_sexo_ausente_nao_cria_person(self):
        self.verificar_bloqueio(self.dados(sex=""))

    def test_cpf_invalido_nao_cria(self):
        self.verificar_bloqueio(self.dados(cpf="11111111111"))

    def test_nome_vazio_nao_cria(self):
        self.verificar_bloqueio(self.dados(name=" "))

    def test_campos_protegidos_bloqueados(self):
        self.verificar_bloqueio(self.dados(family_id=self.familia.pk))

    def test_familia_excluida_bloqueada(self):
        self.familia.excluido = True
        self.familia.save(update_fields=["excluido"])
        self.verificar_bloqueio(self.dados())

    def test_admin_por_perfil_cria(self):
        self.criar(usuario=self.operador("admin_criacao", "admin"))
        self.assertEqual(Person.objects.count(), 1)

    def test_superusuario_ativo_cria(self):
        self.criar(usuario=self.operador("super_criacao", is_superuser=True, is_staff=True))
        self.assertEqual(Person.objects.count(), 1)

    def test_coordenacao_nao_cria(self):
        with self.assertRaises(PermissionDenied):
            self.criar(usuario=self.operador("coord_criacao", "coordenacao"))
        self.assertEqual(Person.objects.count(), 0)

    def test_permissao_django_isolada_nao_libera(self):
        from django.contrib.auth.models import Permission
        u = self.operador("colab_criacao")
        ct = ContentType.objects.get_for_model(Adult)
        u.user_permissions.add(Permission.objects.get(content_type=ct, codename="add_adult"))
        with self.assertRaises(PermissionDenied):
            self.criar(usuario=u)
        self.assertEqual(Person.objects.count(), 0)

    def test_usuario_inativo_nao_cria(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.criar()
        self.assertEqual(Person.objects.count(), 0)

    def test_falha_no_save_adulto_reverte_person(self):
        antes = lote.snapshot()
        with patch.object(Adult, "save", side_effect=RuntimeError("Falha sintetica")):
            with self.assertRaises(RuntimeError):
                self.criar()
        self.assertEqual(lote.snapshot(), antes)

    def test_falha_no_segundo_log_reverte_tudo(self):
        from AppLSD.adulto_person_criacao_services import registrar_log
        chamadas = []
        def falhar(*args, **kwargs):
            chamadas.append(1)
            if len(chamadas) == 2:
                raise RuntimeError("Falha sintetica no log")
            return registrar_log(*args, **kwargs)
        antes = lote.snapshot()
        with patch("AppLSD.adulto_person_criacao_services.registrar_log", side_effect=falhar):
            with self.assertRaises(RuntimeError):
                self.criar()
        self.assertEqual(lote.snapshot(), antes)

    def test_signal_altera_identidade_cancela(self):
        from django.db.models.signals import post_save
        def alterar(sender, instance, created, **kwargs):
            if created:
                Person.objects.filter(pk=instance.pk).update(full_name="Alteracao indevida")
        antes = lote.snapshot()
        post_save.connect(alterar, sender=Person, weak=False)
        try:
            with self.assertRaises(ValidationError):
                self.criar()
        finally:
            post_save.disconnect(alterar, sender=Person)
        self.assertEqual(lote.snapshot(), antes)

    def test_get_pelo_wrapper_nao_grava_nem_exibe_token_edicao(self):
        self.client.force_login(self.usuario)
        antes = lote.snapshot()
        r = self.client.get(f"/adult/new/?family_id={self.familia.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Adult e Person")
        self.assertNotContains(r, 'name="token_identificacao"')
        self.assertEqual(lote.snapshot(), antes)

    def test_post_pelo_wrapper_cria_e_redireciona(self):
        self.client.force_login(self.usuario)
        dados = self.dados()
        dados["birth_date"] = "1985-02-03"
        dados["family"] = self.familia.pk
        r = self.client.post(f"/adult/new/?family_id={self.familia.pk}", dados)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, f"/families/{self.familia.pk}/")
        self.assertEqual(Adult.objects.count(), 1)
        self.assertEqual(Person.objects.count(), 1)

    def test_post_familia_adulterada_bloqueia(self):
        outra = self.nova_familia()
        self.client.force_login(self.usuario)
        dados = self.dados()
        dados.update(family=outra.pk, birth_date="1985-02-03")
        r = self.client.post(f"/adult/new/?family_id={self.familia.pk}", dados)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Person.objects.count(), 0)

    def test_view_coordenacao_recebe_403(self):
        self.client.force_login(self.operador("coord_view_criacao", "coordenacao"))
        r = self.client.get(f"/adult/new/?family_id={self.familia.pk}")
        self.assertEqual(r.status_code, 403)

    def test_view_anonimo_redirecionado(self):
        r = self.client.get(f"/adult/new/?family_id={self.familia.pk}")
        self.assertEqual(r.status_code, 302)

    def test_post_invalido_nao_cria(self):
        self.client.force_login(self.usuario)
        r = self.client.post(f"/adult/new/?family_id={self.familia.pk}", {"family": self.familia.pk})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Person.objects.count(), 0)

    def test_csrf_real_rejeita_post_sem_token(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        r = c.post(f"/adult/new/?family_id={self.familia.pk}", {"family": self.familia.pk})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Person.objects.count(), 0)

    def test_csrf_real_aceita_token_e_cria_sem_cpf(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        url = f"/adult/new/?family_id={self.familia.pk}"
        r = c.get(url)
        self.assertEqual(r.status_code, 200)
        token = c.cookies[settings.CSRF_COOKIE_NAME].value
        dados = self.dados(cpf="")
        dados.update(family=self.familia.pk, birth_date="1985-02-03")
        r = c.post(url, dados, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Person.objects.count(), 1)
        self.assertIsNone(Adult.objects.get().cpf)
