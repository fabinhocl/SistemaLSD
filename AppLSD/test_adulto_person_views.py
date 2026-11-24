"""Testes das views por RequestFactory; CSRF middleware nao e exercitado aqui."""
import re
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from AppLSD import test_person_lote_v2 as fixtures
from AppLSD import adulto_person_views as nova_view
from AppLSD.adulto_person_services import criar_token_edicao_adulto
from AppLSD.models import PerfilUsuario, Person
from AppLSD.management.commands import aplicar_lote_person_v2 as lote


class AdultoPersonViewsTests(TestCase):
    proximo_cpf = fixtures.LotePersonV2Tests.proximo_cpf
    criar_familia = fixtures.LotePersonV2Tests.criar_familia

    def setUp(self):
        fixtures.LotePersonV2Tests.setUp(self)
        lote.aplicar_plano(lote.novo_plano())
        self.adulto.refresh_from_db()
        self.usuario = self.novo_usuario('social_sintetico', 'servicosocial')
        self.rf = RequestFactory()
        _, self.token = criar_token_edicao_adulto(usuario=self.usuario, adulto_id=self.adulto.pk)

    def novo_usuario(self, nome, perfil=None, superusuario=False):
        usuario = get_user_model().objects.create_user(
            username=nome, password=None, is_superuser=superusuario, is_staff=superusuario)
        if perfil:
            PerfilUsuario.objects.create(user=usuario, tipo_perfil=perfil)
        return usuario

    def request(self, metodo='GET', dados=None, usuario=None, url='/adulto/editar/'):
        req = self.rf.get(url) if metodo == 'GET' else self.rf.post(url, dados or {})
        req.user = usuario if usuario is not None else self.usuario
        req.session = {}
        req._messages = FallbackStorage(req)
        return req

    def dados(self, **alteracoes):
        a = self.adulto
        dados = {
            'family': str(a.family_id), 'name': a.name, 'cpf': a.cpf,
            'social_name': a.social_name, 'sex': a.sex,
            'parentesco': a.parentesco or '',
            'birth_date': a.birth_date.isoformat() if a.birth_date else '',
            'education': a.education or '', 'ocupacao': a.ocupacao or '',
            'renda': a.renda or '', 'status': a.status or '',
            'telephone': a.telephone or '', 'token_identificacao': self.token,
        }
        dados.update(alteracoes)
        return dados

    def test_get_exibe_token_sem_gravar(self):
        antes = lote.snapshot()
        resposta = nova_view.adult_edit(self.request(), pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 200)
        self.assertRegex(resposta.content.decode(), r'name="token_identificacao"\s+value="[^"]+"')
        self.assertEqual(lote.snapshot(), antes)

    def test_post_sincroniza_e_redireciona(self):
        resposta = nova_view.adult_edit(self.request('POST', self.dados(name='Nome sintetico corrigido')),
                                        pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 302)
        self.adulto.refresh_from_db()
        self.assertEqual(self.adulto.name, 'Nome sintetico corrigido')
        self.assertEqual(Person.objects.get(pk=self.adulto.person_id).full_name, self.adulto.name)

    def test_post_cpf_diferente_exibe_erro_sem_gravar(self):
        antes = lote.snapshot()
        resposta = nova_view.adult_edit(self.request('POST', self.dados(cpf=self.proximo_cpf())),
                                        pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(lote.snapshot(), antes)
        self.assertIn(self.token, resposta.content.decode())

    def test_post_mudanca_de_familia_e_recusado(self):
        outra = self.criar_familia()
        antes = lote.snapshot()
        resposta = nova_view.adult_edit(self.request('POST', self.dados(family=str(outra.pk))),
                                        pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(lote.snapshot(), antes)

    def test_post_sem_token_e_recusado(self):
        antes = lote.snapshot()
        resposta = nova_view.adult_edit(self.request('POST', self.dados(token_identificacao='')),
                                        pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(lote.snapshot(), antes)

    def test_post_desatualizado_nao_renova_token(self):
        self.adulto.telephone = '000000000'
        self.adulto.save(update_fields=['telephone'])
        antes = lote.snapshot()
        resposta = nova_view.adult_edit(self.request('POST', self.dados(name='Nao persistir')),
                                        pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(self.token, resposta.content.decode())
        self.assertEqual(lote.snapshot(), antes)

    def test_formulario_invalido_preserva_token(self):
        antes = lote.snapshot()
        resposta = nova_view.adult_edit(self.request('POST', self.dados(name='')),
                                        pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(self.token, resposta.content.decode())
        self.assertEqual(lote.snapshot(), antes)

    def test_anonimo_e_redirecionado_para_login(self):
        resposta = nova_view.adult_edit(self.request(usuario=AnonymousUser()), pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 302)

    def test_coordenacao_nao_edita(self):
        usuario = self.novo_usuario('coord_sintetico', 'coordenacao')
        with self.assertRaises(PermissionDenied):
            nova_view.adult_edit(self.request(usuario=usuario), pk=self.adulto.pk)

    def test_admin_por_perfil_edita(self):
        usuario = self.novo_usuario('admin_sintetico', 'admin')
        resposta = nova_view.adult_edit(self.request(usuario=usuario), pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 200)

    def test_superusuario_mantem_acesso_administrativo(self):
        usuario = self.novo_usuario('super_sintetico', superusuario=True)
        resposta = nova_view.adult_edit(self.request(usuario=usuario), pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 200)

    def test_permissao_django_isolada_nao_libera_colaborador(self):
        usuario = self.novo_usuario('colab_sintetico')
        usuario.user_permissions.add(Permission.objects.get(
            content_type__app_label='AppLSD', codename='change_adult'))
        with self.assertRaises(PermissionDenied):
            nova_view.adult_edit(self.request(usuario=usuario), pk=self.adulto.pk)

    def test_view_antiga_encaminha_edicao_ao_servico_novo(self):
        from AppLSD.views_templates import adult_edit
        resposta = adult_edit(self.request('POST', self.dados(name='Nome via entrada antiga')),
                              pk=self.adulto.pk)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Person.objects.get(pk=self.adulto.person_id).full_name, 'Nome via entrada antiga')

    def test_criacao_existente_respeita_perfis_sem_ganhar_token_de_edicao(self):
        from AppLSD.views_templates import adult_create
        url = '/adulto/criar/?family_id=' + str(self.familia.pk)
        negado = self.novo_usuario('sem_acesso_criacao')
        with self.assertRaises(PermissionDenied):
            adult_create(self.request(usuario=negado, url=url))
        resposta = adult_create(self.request(url=url))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('name="token_identificacao"', resposta.content.decode())
