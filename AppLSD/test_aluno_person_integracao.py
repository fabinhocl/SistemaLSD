"""Suite sintetica das telas de assistidos. Exige PostgreSQL e manage.py test."""
from datetime import date, time
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models.signals import post_save
from django.http import HttpResponse
from django.test import TestCase, Client, override_settings
from django.urls import path
from django.urls.resolvers import RegexPattern, URLResolver
from AppLSD import views_templates as telas
from AppLSD.models import Family, Aluno, Person, Adult, PerfilUsuario, AppLog, Turma, Activity, HistoricoDesligamento, FrequenciaTurma, FrequenciaAluno
from AppLSD.aluno_person_services import criar_aluno_com_person, salvar_edicao_aluno, criar_token_edicao_aluno
from AppLSD.management.commands import aplicar_lote_person_v2 as lote
from AppLSD.test_person_lote_v2 import cpf_teste

_URLCONF_REAL = settings.ROOT_URLCONF


def destino(request, pk=None):
    return HttpResponse("Destino sintetico")


urlpatterns = [
    path("alunos/new/", telas.aluno_create, name="aluno_create"),
    path("alunos/edit/<int:pk>/", telas.aluno_edit, name="aluno_edit"),
    path("alunos/<int:pk>/", destino, name="aluno_detail"),
    path("families/<int:pk>/", destino, name="family_detail"),
]
urlpatterns += [URLResolver(RegexPattern(r"^"), _URLCONF_REAL)]


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=["testserver"], MIDDLEWARE=[
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware"])
class AlunoPersonIntegracaoTests(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.seq = 0
        self.familia = self.nova_familia()
        self.usuario = self.operador("social_aluno", "servicosocial")

    def cpf(self):
        self.seq += 1
        return cpf_teste(654300000 + self.seq)

    def nova_familia(self):
        f = Family(registration_number="P" + str(self.seq + 1), responsible_name="Responsavel sintetica",
            social_name="Responsavel sintetica", cpf=self.cpf(), birth_date=date(1980, 1, 2), sex="Feminino",
            mae_solo="Não", marital_status="solteira", education="Ens. Med. Comp.", race="Pardo",
            religion="Não possui religião", cep="57000-000", address="Endereco sintetico", neighborhood="Bairro sintetico",
            num_residents=3, has_adult=2, has_child=1, status="ativo", location="")
        f.full_clean()
        f.save()
        return f

    def operador(self, nome, perfil=None, **kwargs):
        u = get_user_model().objects.create_user(username=nome, password="SenhaSintetica!", **kwargs)
        if perfil:
            PerfilUsuario.objects.get_or_create(user=u, tipo_perfil=perfil)
        return u

    def dados(self, **kwargs):
        dados = dict(name="Assistido sintetico Person", cpf=self.cpf(), birth_date=date(2016, 3, 15),
            sex="Masculino", status_lsd="Frequentando", health_problem="não", uso_medicacao="não",
            frequencia_tipo="diaria", dias_semana=[], possui_sisc="sim")
        dados.update(kwargs)
        return dados

    def criar(self, dados=None, usuario=None):
        return criar_aluno_com_person(usuario=usuario or self.usuario, familia_id=self.familia.pk,
            dados=dados if dados is not None else self.dados())["aluno"]

    def editar(self, aluno, alteracoes, usuario=None, token=None):
        u = usuario or self.usuario
        if token is None:
            _, token = criar_token_edicao_aluno(usuario=u, aluno_id=aluno.pk)
        return salvar_edicao_aluno(usuario=u, aluno_id=aluno.pk, alteracoes=alteracoes, token=token)

    def bloqueio_criacao(self, dados):
        antes = lote.snapshot()
        with self.assertRaises(ValidationError):
            self.criar(dados)
        self.assertEqual(lote.snapshot(), antes)

    def url(self, aluno=None):
        return f"/alunos/edit/{aluno.pk}/" if aluno else f"/alunos/new/?family_id={self.familia.pk}"

    def post(self, aluno=None, **kwargs):
        if aluno:
            dados = {c: getattr(aluno,c) for c in self.dados(cpf=aluno.cpf)}
            _, token = criar_token_edicao_aluno(usuario=self.usuario, aluno_id=aluno.pk)
            dados["token_aluno_person"] = token
        else:
            dados = self.dados()
        dados.update(family=self.familia.pk)
        dados.update(kwargs)
        for chave in list(dados):
            if dados[chave] is None:
                dados[chave] = ""
        return dados

    def test_cria_duas_pontas_e_dois_logs(self):
        a = self.criar()
        self.assertIsNotNone(a.person_id)
        self.assertEqual(a.person.full_name, a.name)
        self.assertEqual(a.person.family_id, a.family_id)
        self.assertEqual(a.criado_por_id, self.usuario.pk)
        self.assertEqual(set(AppLog.objects.values_list("acao",flat=True)), {"person_criada","aluno_criado"})
        self.assertEqual(AppLog.objects.count(),2)
        self.assertIsNone(a.turma_id)
        self.assertEqual(HistoricoDesligamento.objects.count(),0)

    def test_sem_cpf_cria_e_edita(self):
        a = self.criar(self.dados(cpf=None))
        self.editar(a,{"name":"Assistido corrigido sintetico"})
        a.refresh_from_db()
        self.assertEqual(a.name,a.person.full_name)
        self.assertIsNone(a.cpf)
        self.assertIsNone(a.person.cpf)

    def test_nascimento_opcional(self):
        a=self.criar(self.dados(birth_date=None))
        self.assertIsNone(a.person.birth_date)

    def test_coord_nao_cria(self):
        u=self.operador("coord_cria","coordenacao")
        antes=lote.snapshot()
        with self.assertRaises(PermissionDenied):self.criar(usuario=u)
        self.assertEqual(lote.snapshot(),antes)

    def test_coord_edita_com_colaborador_tambem(self):
        a=self.criar()
        u=self.operador("coord_edita","coordenacao")
        PerfilUsuario.objects.get_or_create(user=u,tipo_perfil="colaborador")
        self.editar(a,{"name":"Nome corrigido coordenacao"},usuario=u)
        a.refresh_from_db()
        self.assertEqual(a.name,a.person.full_name)
        self.assertEqual(a.editado_por_id,u.pk)

    def test_admin_cria_e_edita(self):
        u=self.operador("admin_aluno","admin")
        a=self.criar(usuario=u)
        self.editar(a,{"name":"Nome admin sintetico"},usuario=u)
        a.refresh_from_db()
        self.assertEqual(a.name,a.person.full_name)

    def test_superusuario_ativo(self):
        u=self.operador("super_aluno",is_superuser=True,is_staff=True)
        self.assertIsNotNone(self.criar(usuario=u).person_id)

    def test_usuario_inativo_bloqueado(self):
        self.usuario.is_active=False
        self.usuario.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):self.criar()

    def test_perfil_revogado_nao_e_aceito_pelo_objeto_antigo(self):
        a=self.criar()
        _,token=criar_token_edicao_aluno(usuario=self.usuario,aluno_id=a.pk)
        PerfilUsuario.objects.filter(user=self.usuario,tipo_perfil="servicosocial").delete()
        with self.assertRaises(PermissionDenied):self.editar(a,{"name":"Nao salvar"},token=token)

    def test_educadora_nao_edita_cadastro(self):
        a=self.criar()
        with self.assertRaises(PermissionDenied):self.editar(a,{"name":"Nao salvar"},usuario=self.operador("educ_aluno","educadora"))

    def test_cpf_duplicado_responsavel_bloqueia(self):
        self.bloqueio_criacao(self.dados(cpf=self.familia.cpf))

    def test_person_existente_nao_e_reutilizada(self):
        cpf=self.cpf()
        Person.objects.create(family=self.familia,full_name="Outra identidade",gender="M",cpf=cpf)
        self.bloqueio_criacao(self.dados(cpf=cpf))

    def test_cpf_duplicado_adulto_bloqueia(self):
        cpf=self.cpf()
        Adult.objects.create(family=self.familia,name="Adulto outro sintetico",social_name="Outro",cpf=cpf,sex="Masculino",education="med_comp",status="trabalha")
        self.bloqueio_criacao(self.dados(cpf=cpf))

    def test_nome_e_nascimento_iguais_bloqueiam_sem_cpf(self):
        self.criar(self.dados(cpf=None))
        self.bloqueio_criacao(self.dados(cpf=None))

    def test_nomes_distintos_sem_cpf_permitidos(self):
        self.criar(self.dados(cpf=None))
        self.criar(self.dados(cpf=None,name="Outro assistido sintetico"))
        self.assertEqual(Person.objects.count(),2)

    def test_reenvio_imediato_identico_nao_duplica(self):
        dados=self.dados()
        self.criar(dados)
        self.bloqueio_criacao(dados)

    def test_familia_inativa_nao_recebe_frequentando(self):
        self.familia.status="inativo"
        self.familia.save(update_fields=["status"])
        self.bloqueio_criacao(self.dados())

    def test_familia_excluida_bloqueada(self):
        self.familia.excluido=True
        self.familia.save(update_fields=["excluido"])
        self.bloqueio_criacao(self.dados())

    def test_criacao_nao_desliga(self):
        self.bloqueio_criacao(self.dados(status_lsd="desligado"))

    def test_cpf_invalido_bloqueado(self):
        self.bloqueio_criacao(self.dados(cpf="11111111111"))

    def test_sexo_ausente_bloqueado(self):
        self.bloqueio_criacao(self.dados(sex=""))

    def test_sisc_sem_justificativa_bloqueado(self):
        self.bloqueio_criacao(self.dados(possui_sisc="nao"))

    def test_dias_especificos_sem_dia_bloqueados(self):
        self.bloqueio_criacao(self.dados(frequencia_tipo="especificos",dias_semana=[]))

    def test_saude_sem_detalhe_bloqueada(self):
        self.bloqueio_criacao(self.dados(health_problem="sim",special_need=""))

    def test_medicacao_sem_detalhe_bloqueada(self):
        self.bloqueio_criacao(self.dados(uso_medicacao="sim",qual_medicacao=""))

    def test_edicao_sincroniza_nome_data_sexo(self):
        a=self.criar()
        self.editar(a,{"name":"Nome novo sintetico","birth_date":date(2015,6,1),"sex":"Feminino"})
        a.refresh_from_db()
        self.assertEqual((a.name,a.birth_date,"F"),(a.person.full_name,a.person.birth_date,a.person.gender))
        self.assertEqual(AppLog.objects.count(),4)

    def test_campo_escolar_nao_e_copiado_para_person(self):
        a=self.criar()
        antes=lote.estado(a.person)
        self.editar(a,{"school":"Escola sintetica"})
        a.person.refresh_from_db()
        self.assertEqual(lote.estado(a.person),antes)

    def test_sem_alteracao_nao_grava_logs(self):
        a=self.criar()
        antes=lote.snapshot()
        self.assertFalse(self.editar(a,{})["alterado"])
        self.assertEqual(lote.snapshot(),antes)

    def test_cpf_vazio_formulario_nao_gera_alteracao_sozinha(self):
        a=self.criar(self.dados(cpf=None))
        antes=lote.snapshot()
        self.assertFalse(self.editar(a,{"cpf":""})["alterado"])
        self.assertEqual(lote.snapshot(),antes)

    def test_troca_inclusao_remocao_cpf_bloqueadas(self):
        a=self.criar()
        for valor in (self.cpf(),None):
            antes=lote.snapshot()
            with self.assertRaises(ValidationError):self.editar(a,{"cpf":valor})
            self.assertEqual(lote.snapshot(),antes)
        b=self.criar(self.dados(cpf=None,name="Segundo assistido sintetico"))
        with self.assertRaises(ValidationError):self.editar(b,{"cpf":self.cpf()})

    def test_campos_protegidos_nao_aceitos(self):
        a=self.criar()
        for campo in ("family_id","person_id","turma_id","criado_por_id","motivo_desligamento_codigo"):
            with self.assertRaises(ValidationError):self.editar(a,{campo:999})

    def test_token_adulterado_bloqueia(self):
        a=self.criar()
        with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao salvar"},token="invalido")

    def test_token_outro_usuario_bloqueia(self):
        a=self.criar()
        _,token=criar_token_edicao_aluno(usuario=self.usuario,aluno_id=a.pk)
        u=self.operador("outro_aluno","coordenacao")
        with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao salvar"},usuario=u,token=token)

    def test_formulario_antigo_nao_sobrescreve(self):
        a=self.criar()
        _,token=criar_token_edicao_aluno(usuario=self.usuario,aluno_id=a.pk)
        Aluno.objects.filter(pk=a.pk).update(school="Mudanca concorrente")
        antes=lote.snapshot()
        with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao salvar"},token=token)
        self.assertEqual(lote.snapshot(),antes)

    def test_person_alterada_invalida_formulario(self):
        a=self.criar()
        _,token=criar_token_edicao_aluno(usuario=self.usuario,aluno_id=a.pk)
        Person.objects.filter(pk=a.person_id).update(phone="Mudanca concorrente")
        with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao salvar"},token=token)

    def test_legado_sem_person_nao_e_regularizado(self):
        a=Aluno(family=self.familia,**self.dados())
        a.save()
        antes=lote.snapshot()
        with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao salvar"})
        self.assertEqual(lote.snapshot(),antes)

    def test_legado_desligado_sem_codigo_permanece_intocado(self):
        a=self.criar()
        Aluno.objects.filter(pk=a.pk).update(status_lsd="desligado",motivo_desligamento_codigo="")
        a.refresh_from_db()
        antes=lote.snapshot()
        with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao salvar"})
        self.assertEqual(lote.snapshot(),antes)

    def test_person_compartilhada_bloqueia(self):
        a=self.criar()
        Family.objects.filter(pk=self.familia.pk).update(responsible_id=a.person_id)
        with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao salvar"})

    def test_edicao_comum_nao_desliga(self):
        a=self.criar()
        antes=lote.snapshot()
        with self.assertRaises(ValidationError):self.editar(a,{"status_lsd":"desligado"})
        self.assertEqual(lote.snapshot(),antes)

    def test_reativacao_nao_apaga_historico_nem_inventa_turma(self):
        a=self.criar()
        Aluno.objects.filter(pk=a.pk).update(status_lsd="desligado",motivo_desligamento_codigo="outro_responsavel",motivo_desligamento="Historico sintetico")
        a.refresh_from_db()
        self.editar(a,{"status_lsd":"Frequentando"})
        a.refresh_from_db()
        self.assertIsNone(a.turma_id)
        self.assertEqual(a.motivo_desligamento,"Historico sintetico")

    def test_edicao_preserva_turma_atividade_e_dados_sensiveis(self):
        a=self.criar(self.dados(health_problem="sim",special_need="Dado sintetico saude",uso_medicacao="sim",qual_medicacao="Dado sintetico medicacao",frequencia_tipo="especificos",dias_semana=["segunda"]))
        turma=Turma.objects.create(faixa_etaria="06-07 anos",grupo="Grupo Crianca Feliz",turno="Matutino",ano_letivo=2026)
        Aluno.objects.filter(pk=a.pk).update(turma=turma)
        at=Activity.objects.create(atividade="Atividade sintetica",tipo="educativa",horario_inicio=time(14),horario_fim=time(15))
        at.alunos.add(a)
        self.editar(a,{"name":"Nome alterado sintetico"})
        a.refresh_from_db()
        self.assertEqual(a.turma_id,turma.pk)
        self.assertTrue(at.alunos.filter(pk=a.pk).exists())
        self.assertEqual(a.special_need,"Dado sintetico saude")
        self.assertEqual(a.qual_medicacao,"Dado sintetico medicacao")
        self.assertEqual(a.dias_semana,["segunda"])

    def test_falha_no_save_da_origem_reverte_person_criada(self):
        antes=lote.snapshot()
        with patch.object(Aluno,"save",side_effect=RuntimeError("Falha sintetica")):
            with self.assertRaises(RuntimeError):self.criar()
        self.assertEqual(lote.snapshot(),antes)

    def test_falha_no_segundo_log_da_criacao_reverte_tudo(self):
        from AppLSD.aluno_person_services import registrar_log
        chamadas=[]
        def falhar(*args,**kwargs):
            chamadas.append(1)
            if len(chamadas)==2:raise RuntimeError("Falha sintetica log")
            return registrar_log(*args,**kwargs)
        antes=lote.snapshot()
        with patch("AppLSD.aluno_person_services.registrar_log",side_effect=falhar):
            with self.assertRaises(RuntimeError):self.criar()
        self.assertEqual(lote.snapshot(),antes)

    def test_falha_no_log_da_edicao_reverte_ambas_pontas(self):
        a=self.criar()
        antes=lote.snapshot()
        with patch("AppLSD.aluno_person_services.registrar_log",side_effect=RuntimeError("Falha sintetica")):
            with self.assertRaises(RuntimeError):self.editar(a,{"name":"Nao persistir"})
        self.assertEqual(lote.snapshot(),antes)

    def test_signal_muda_person_e_operacao_e_revertida(self):
        def mudar(sender,instance,created,**kwargs):
            if created:Person.objects.filter(pk=instance.pk).update(full_name="Alteracao indevida")
        antes=lote.snapshot()
        post_save.connect(mudar,sender=Person,weak=False)
        try:
            with self.assertRaises(ValidationError):self.criar()
        finally:post_save.disconnect(mudar,sender=Person)
        self.assertEqual(lote.snapshot(),antes)

    def test_get_criacao_nao_grava(self):
        self.client.force_login(self.usuario)
        antes=lote.snapshot()
        r=self.client.get(self.url())
        self.assertEqual(r.status_code,200)
        self.assertEqual(lote.snapshot(),antes)
        self.assertNotContains(r,'name="token_aluno_person"')

    def test_get_edicao_tem_token_e_campos_saude_vinculados(self):
        a=self.criar(self.dados(health_problem="sim",special_need="DadoSaudeSintetico",uso_medicacao="sim",qual_medicacao="DadoMedicacaoSintetico"))
        self.client.force_login(self.usuario)
        r=self.client.get(self.url(a))
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'name="token_aluno_person"')
        self.assertContains(r,'DadoSaudeSintetico')
        self.assertContains(r,'DadoMedicacaoSintetico')

    def test_post_criacao_pelo_wrapper(self):
        self.client.force_login(self.usuario)
        r=self.client.post(self.url(),self.post(cpf=""))
        self.assertEqual(r.status_code,302)
        self.assertEqual(Aluno.objects.count(),1)
        self.assertIsNotNone(Aluno.objects.get().person_id)

    def test_post_edicao_pelo_wrapper(self):
        a=self.criar()
        self.client.force_login(self.usuario)
        r=self.client.post(self.url(a),self.post(a,name="Nome navegador sintetico"))
        self.assertEqual(r.status_code,302)
        a.refresh_from_db()
        self.assertEqual(a.name,a.person.full_name)

    def test_view_coord_criacao_403_edicao_200(self):
        a=self.criar()
        u=self.operador("coord_http","coordenacao")
        self.client.force_login(u)
        self.assertEqual(self.client.get(self.url()).status_code,403)
        self.assertEqual(self.client.get(self.url(a)).status_code,200)

    def test_view_familia_adulterada_bloqueia(self):
        outra=self.nova_familia()
        self.client.force_login(self.usuario)
        r=self.client.post(self.url(),self.post(family=outra.pk))
        self.assertEqual(r.status_code,400)
        self.assertEqual(Person.objects.count(),0)

    def test_view_sem_token_nao_edita(self):
        a=self.criar()
        self.client.force_login(self.usuario)
        dados=self.post(a,name="Nao persistir")
        dados.pop("token_aluno_person")
        antes=lote.snapshot()
        r=self.client.post(self.url(a),dados)
        self.assertEqual(r.status_code,400)
        self.assertEqual(lote.snapshot(),antes)

    def test_post_invalido_preserva_token_original(self):
        a=self.criar()
        self.client.force_login(self.usuario)
        dados=self.post(a,name="")
        r=self.client.post(self.url(a),dados)
        self.assertEqual(r.status_code,400)
        self.assertContains(r,dados["token_aluno_person"],status_code=400)

    def test_confirmacao_de_desligamento_delega_ao_endpoint_existente(self):
        a=self.criar()
        u=self.operador("coord_modal","coordenacao")
        self.client.force_login(u)
        _,token=criar_token_edicao_aluno(usuario=u,aluno_id=a.pk)
        antes=lote.snapshot()
        with patch("AppLSD.views_templates.desativar_aluno",return_value=HttpResponse(status=302)) as mock:
            r=self.client.post(self.url(a),{"acao":"confirmar_desligamento","token_aluno_person":token,"motivo":"outro_responsavel","senha":"SenhaSintetica!"})
        self.assertEqual(r.status_code,302)
        mock.assert_called_once()
        self.assertEqual(lote.snapshot(),antes)

    def test_confirmacao_sem_token_nao_delega(self):
        a=self.criar()
        u=self.operador("coord_modal_sem_token","coordenacao")
        self.client.force_login(u)
        with patch("AppLSD.views_templates.desativar_aluno") as mock:
            r=self.client.post(self.url(a),{"acao":"confirmar_desligamento"})
        self.assertEqual(r.status_code,400)
        mock.assert_not_called()

    def test_csrf_rejeita_sem_token(self):
        c=Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        r=c.post(self.url(),self.post())
        self.assertEqual(r.status_code,403)
        self.assertEqual(Person.objects.count(),0)

    def test_csrf_aceita_e_cria_sem_cpf(self):
        c=Client(enforce_csrf_checks=True)
        c.force_login(self.usuario)
        r=c.get(self.url())
        self.assertEqual(r.status_code,200)
        r=c.post(self.url(),self.post(cpf=""),HTTP_X_CSRFTOKEN=c.cookies[settings.CSRF_COOKIE_NAME].value)
        self.assertEqual(r.status_code,302)
        self.assertIsNone(Aluno.objects.get().person.cpf)

    def test_desligamento_real_pelo_modal_preserva_person_e_cria_historico(self):
        a=self.criar()
        turma=Turma.objects.create(faixa_etaria="06-07 anos",grupo="Grupo Crianca Feliz",turno="Matutino",ano_letivo=2026)
        Aluno.objects.filter(pk=a.pk).update(turma=turma)
        at=Activity.objects.create(atividade="Atividade desligamento sintetica",tipo="educativa",horario_inicio=time(14),horario_fim=time(15))
        at.alunos.add(a)
        u=self.operador("coord_desliga_real","coordenacao")
        self.client.force_login(u)
        _,token=criar_token_edicao_aluno(usuario=u,aluno_id=a.pk)
        person_antes=lote.estado(a.person)
        r=self.client.post(self.url(a),{"acao":"confirmar_desligamento","token_aluno_person":token,"senha":"SenhaSintetica!","motivo":"outro_responsavel","observacao":"Evidencia sintetica"})
        self.assertEqual(r.status_code,302)
        a.refresh_from_db()
        self.assertEqual(a.status_lsd,"desligado")
        self.assertIsNone(a.turma_id)
        self.assertFalse(at.alunos.filter(pk=a.pk).exists())
        self.assertEqual(HistoricoDesligamento.objects.filter(aluno=a).count(),1)
        self.assertEqual(lote.estado(a.person),person_antes)

    def test_social_desliga_pelo_modal_preserva_person_e_cria_historico(self):
        from AppLSD.models import HistoricoDesligamento, Person

        a = self.criar()
        self.client.force_login(self.usuario)

        person_id_antes = a.person_id
        self.assertIsNotNone(person_id_antes)

        pessoa_antes = lote.estado(
            Person.objects.get(pk=person_id_antes)
        )

        historicos_antes = (
            HistoricoDesligamento.objects
            .filter(aluno=a)
            .count()
        )

        _, token = criar_token_edicao_aluno(
            usuario=self.usuario,
            aluno_id=a.pk,
        )

        r = self.client.post(
            self.url(a),
            {
                "acao": "confirmar_desligamento",
                "token_aluno_person": token,
                "senha": "SenhaSintetica!",
                "motivo": "horario_integral",
                "observacao": "Desligamento sintético pelo Serviço Social.",
            },
        )

        self.assertRedirects(
            r,
            f"/alunos/{a.pk}/",
            fetch_redirect_response=False,
        )

        a.refresh_from_db()

        self.assertEqual(a.status_lsd, "desligado")
        self.assertEqual(
            a.motivo_desligamento_codigo,
            "horario_integral",
        )
        self.assertEqual(
            a.observacao_desligamento,
            "Desligamento sintético pelo Serviço Social.",
        )
        self.assertEqual(a.desligado_por_id, self.usuario.pk)
        self.assertIsNotNone(a.data_desligamento)
        self.assertIsNone(a.turma_id)

        self.assertEqual(a.person_id, person_id_antes)
        self.assertEqual(
            lote.estado(Person.objects.get(pk=person_id_antes)),
            pessoa_antes,
        )

        historicos = (
            HistoricoDesligamento.objects
            .filter(aluno=a)
        )

        self.assertEqual(
            historicos.count(),
            historicos_antes + 1,
        )

        evento = historicos.order_by("-pk").first()

        self.assertEqual(
            evento.tipo_evento,
            HistoricoDesligamento.TipoEvento.ALUNO_DESLIGADO,
        )
        self.assertEqual(evento.motivo_codigo, "horario_integral")
        self.assertEqual(evento.motivo_descricao, "Horário Integral")
        self.assertEqual(evento.criado_por_id, self.usuario.pk)
        self.assertEqual(
            evento.observacao,
            "Desligamento sintético pelo Serviço Social.",
        )


    def test_social_desliga_com_motivo_maiores_17_anos(self):
        from AppLSD.models import HistoricoDesligamento

        a = self.criar()
        self.client.force_login(self.usuario)

        historicos_antes = (
            HistoricoDesligamento.objects
            .filter(aluno=a)
            .count()
        )

        _, token = criar_token_edicao_aluno(
            usuario=self.usuario,
            aluno_id=a.pk,
        )

        r = self.client.post(
            self.url(a),
            {
                "acao": "confirmar_desligamento",
                "token_aluno_person": token,
                "senha": "SenhaSintetica!",
                "motivo": "maiores_17_anos",
            },
        )

        self.assertRedirects(
            r,
            f"/alunos/{a.pk}/",
            fetch_redirect_response=False,
        )

        a.refresh_from_db()

        self.assertEqual(a.status_lsd, "desligado")
        self.assertEqual(
            a.motivo_desligamento_codigo,
            "maiores_17_anos",
        )
        self.assertEqual(a.desligado_por_id, self.usuario.pk)

        historicos = (
            HistoricoDesligamento.objects
            .filter(aluno=a)
        )

        self.assertEqual(
            historicos.count(),
            historicos_antes + 1,
        )

        evento = historicos.order_by("-pk").first()

        self.assertEqual(evento.motivo_codigo, "maiores_17_anos")
        self.assertEqual(
            evento.motivo_descricao,
            "Maiores de 17 anos",
        )
        self.assertEqual(evento.criado_por_id, self.usuario.pk)

    def test_modal_senha_errada_retorna_400_sem_gravar(self):
        a=self.criar()
        u=self.operador("coord_senha_invalida","coordenacao")
        self.client.force_login(u)
        _,token=criar_token_edicao_aluno(usuario=u,aluno_id=a.pk)
        antes=lote.snapshot()
        r=self.client.post(self.url(a),{"acao":"confirmar_desligamento","token_aluno_person":token,"senha":"SenhaErrada","motivo":"outro_responsavel"})
        self.assertEqual(r.status_code,400)
        self.assertEqual(lote.snapshot(),antes)
        self.assertContains(r,token,status_code=400)

    def test_modal_formulario_antigo_nao_executa_desligamento(self):
        a=self.criar()
        u=self.operador("coord_token_antigo","coordenacao")
        self.client.force_login(u)
        _,token=criar_token_edicao_aluno(usuario=u,aluno_id=a.pk)
        Aluno.objects.filter(pk=a.pk).update(school="Escola alterada depois do GET")
        antes=lote.snapshot()
        with patch("AppLSD.views_templates.desativar_aluno") as mock:
            r=self.client.post(self.url(a),{"acao":"confirmar_desligamento","token_aluno_person":token,"senha":"SenhaSintetica!","motivo":"outro_responsavel"})
        self.assertEqual(r.status_code,400)
        mock.assert_not_called()
        self.assertEqual(lote.snapshot(),antes)

    def test_signal_altera_vinculo_operacional_e_edicao_reverte(self):
        a=self.criar()
        at=Activity.objects.create(atividade="Atividade protegida sintetica",tipo="educativa",horario_inicio=time(14),horario_fim=time(15))
        at.alunos.add(a)
        def remover(sender,instance,created,**kwargs):
            if not created:at.alunos.remove(instance)
        antes=lote.snapshot()
        post_save.connect(remover,sender=Aluno,weak=False)
        try:
            with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao persistir"})
        finally:post_save.disconnect(remover,sender=Aluno)
        self.assertEqual(lote.snapshot(),antes)

    def test_edicao_nao_reescreve_frequencia_existente(self):
        a=self.criar()
        turma=Turma.objects.create(faixa_etaria="06-07 anos",grupo="Grupo Crianca Feliz",turno="Matutino",ano_letivo=2026)
        chamada=FrequenciaTurma.objects.create(turma=turma,data=date(2026,11,10))
        freq=FrequenciaAluno.objects.create(chamada=chamada,aluno=a,presente=True,status="P",motivo_falta="")
        antes=lote.estado(freq)
        self.editar(a,{"name":"Nome corrigido sem mudar chamada"})
        freq.refresh_from_db()
        self.assertEqual(lote.estado(freq),antes)

    def test_signal_altera_frequencia_e_edicao_reverte(self):
        a=self.criar()
        turma=Turma.objects.create(faixa_etaria="06-07 anos",grupo="Grupo Crianca Feliz",turno="Matutino",ano_letivo=2026)
        chamada=FrequenciaTurma.objects.create(turma=turma,data=date(2026,11,10))
        freq=FrequenciaAluno.objects.create(chamada=chamada,aluno=a,presente=True,status="P",motivo_falta="")
        def mudar(sender,instance,created,**kwargs):
            if not created:FrequenciaAluno.objects.filter(pk=freq.pk).update(presente=False,status="F",motivo_falta="SJ")
        antes=lote.snapshot()
        post_save.connect(mudar,sender=Aluno,weak=False)
        try:
            with self.assertRaises(ValidationError):self.editar(a,{"name":"Nao persistir"})
        finally:post_save.disconnect(mudar,sender=Aluno)
        self.assertEqual(lote.snapshot(),antes)
