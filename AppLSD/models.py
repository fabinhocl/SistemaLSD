from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date
from AppLSD.validators import validate_cpf

#from localflavor.br.forms import BRCPFField
import re
import ast
import json


class Family(models.Model):
    """
    Representa uma família no sistema, com dados cadastrais e sociais.
    """
    # Dados básicos
    registration_number = models.CharField(
    max_length=10,  # YYYYNN (ex: 202601)
    unique=True,
    blank=True,  # Permite vazio durante criação
    #editable=False  # Impede edição manual 
    )
    responsible_name = models.CharField(max_length=255, default='')
    social_name = models.CharField(max_length=255, default='')
    nis = models.CharField(max_length=20, default='', blank=True, null=True)
    rg = models.CharField(max_length=20, default='', blank=True, null=True)
    cpf = models.CharField(max_length=14, default='', validators=[validate_cpf], unique=True, blank=True, null=True)
    birth_date = models.DateField(default='', blank=True, null=True)
    ESCOLHA_SEXO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Masculino', 'Masculino'),
    ('Feminino', 'Feminino')
    ]
    sex = models.CharField(max_length=10, choices=ESCOLHA_SEXO, verbose_name="Sexo", default= "Escolha o sexo", blank=True, null=True)
    SIM_NAO_CHOICES = [
    ('sim', 'Sim'),
    ('não', 'Não')
]
    # Programas sociais (checkbox múltiplo)
    mae_solo = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='não')
    cep = models.CharField("CEP", max_length=9, blank=False, null=True)
    address = models.CharField(max_length=300, blank=False, null=True)
    number = models.CharField(max_length=10, default="S/N", blank=True, null=True)
    neighborhood = models.CharField(max_length=100, default="Não informado")
    reference_point = models.CharField(max_length=200, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    telephone_2 = models.CharField(max_length=20, blank=True, null=True)
    # Estado civil
    ESTADO_CIVIL_CHOICES = [('solteira', 'Solteira'), ('casada', 'Casada'), ('separada', 'Separada'), ('viuva', 'Viúva'), ('divorciada', 'Divorciada'), ('uniao_estavel', 'União Estável'), ('convive', 'Convive com Alguém'), ('outro', 'Outro')]
    marital_status = models.CharField(max_length=30, choices=ESTADO_CIVIL_CHOICES, verbose_name="Estado Civil", default= "Escolha o estado civil", blank=True, null=True)
    # Escolaridade
    ESCOLARIDADE_CHOICES = [
        ('analfabeto', 'Analfabeto'),
        ('fund_comp', 'Ens. Fund. Comp.'),
        ('fund_incomp', 'Ens. Fund. Incomp.'),
        ('med_comp', 'Ens. Med. Comp.'),
        ('med_incomp', 'Ens. Med. Incomp.'),
        ('sup_comp', 'Ens. Sup. Comp.'),
        ('sup_incomp', 'Ens. Sup. Incomp.'),
    ]
    education = models.CharField(max_length=50, choices=ESCOLARIDADE_CHOICES, verbose_name="Escolaridade", default="Escolha a escolaridade", blank=True, null=True)
    # Raça/Cor
    RACA_CHOICES = [
        ('branco', 'Branco'),
        ('preto', 'Preto'),
        ('pardo', 'Pardo'),
        ('amarelo', 'Amarelo'),
        ('indigena', 'Indígena'),
    ]
    race = models.CharField(max_length=30, choices=RACA_CHOICES, verbose_name="Raça", default="Escolha a raça", blank=True, null=True)
    # Religião
    RELIGIAO_CHOICES = [
        ('catolico', 'Católico'),
        ('evangelico', 'Evangélico'),
        ('espirita', 'Espírita'),
        ('matriz_africana', 'Matriz Africana'),
        ('nao_possui', 'Não possui religião'),
    ]
    religion = models.CharField(max_length=30, choices=RELIGIAO_CHOICES, verbose_name="Religião", default="Escolha a religião", blank=True, null=True)
    # Escolhas SIM ou NÂO
    SIM_NAO_CHOICES = [
    ('sim', 'Sim'),
    ('não', 'Não')
]
    # Programas sociais (checkbox múltiplo)
    is_benefits = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='não')
    # Qual Programas sociais (checkbox múltiplo)
    PROGRAMAS_SOCIAIS_CHOICES = [
        ('bolsa_brasil', 'Programa Bolsa Brasil - PBF'),
        ('bpc', 'Benefício de Prestação Continuada - BPC'),
        ('cria_alagoana', 'Criança Alagoana - CRIA'),
    ]
    social_benefits = models.CharField(max_length=255, choices=PROGRAMAS_SOCIAIS_CHOICES, verbose_name="Programas Sociais", blank=True, null=True)
    
    # Ocupação/profissão
    occupation = models.CharField(max_length=100, blank=True, null=True)
    
    # Trabalhando no momento
    is_working = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='não')
    function = models.CharField(max_length=100, default=False, blank=True, null=False)

    # Renda comprovada
    has_proven_income = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='não')
    # Tipos de renda (checkbox múltiplo)
    INCOME_TYPE_CHOICES = [
        ('carteira_assinada', 'Carteira Assinada'),
        ('contrato', 'Contrato'),
        ('pensao', 'Pensão'),
        ('auxilio_doenca', 'Auxílio Doença'),
        ('aposentado', 'Aposentado'),
    ]
    income_types = models.JSONField(default=list, blank=True, null=False)
    # Faixa salarial
    SALARIO_CHOICES = [
        ('', '---------'),  # Django usa por padrão esse rótulo se vazio
        ('1_sm', '1 Salário Mínimo'),
        ('2_sm', '2 Salários Mínimos'),
    ]
    salary_range = models.CharField(max_length=10, choices=SALARIO_CHOICES, blank=True, null=True)
    #min_salary_1 = models.BooleanField(default=False)
    #min_salary_2 = models.BooleanField(default=False)

    # Outras pessoas contribuem
    others_contribute = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='não')
    who_contributes = models.CharField(max_length=100, blank=True, null=True)

     # Informações sobre o domicílio
    DOMICILE_CHOICES = [
        ('proprio', 'Próprio'), ('alugado', 'Alugado'), ('cedido', 'Cedido')
    ]
    domicile_type = models.CharField(max_length=10, choices=DOMICILE_CHOICES, blank=True, null=True)
    
    # Extras
    num_residents = models.IntegerField(default=0)
    has_pcd = models.IntegerField(default=0)
    has_adult = models.IntegerField(default=0)
    has_elderly = models.IntegerField(default=0)
    has_adolescent = models.IntegerField(default=0)
    has_child = models.IntegerField(default=0)
    has_pregnant = models.IntegerField(default=0)
    file_info = models.FileField(upload_to='families_docs/', blank=True, null=True)
    STATUS_CHOICES = [
        ('ativo', 'Ativo'), ('inativo', 'Inativo'), ('desligado', 'Desligado'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, blank=True, null=True)
    motivo_desligamento = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    
    #aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='families')
    @property
    def idade(self):
        if not self.birth_date:
            return ""
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    def save(self, *args, **kwargs):
        """
        Formata o CPF antes de salvar.
        """
        if self.cpf:
            digits = re.sub(r'\D', '', str(self.cpf))
            if len(digits) == 11:
                self.cpf = f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.responsible_name} - {self.cpf}"
    
    #Procedimento para gerar número de registro automático
    """
    def save(self, *args, **kwargs):
        if self._state.adding and not self.registration_number:  # Novo registro sem número
            current_year = timezone.now().year
            with transaction.atomic():
                # Conta registros do ano atual + 1
                next_seq = Family.objects.filter(
                    registration_number__startswith=f"{current_year}"
                ).count() + 1
                self.registration_number = f"{current_year}{next_seq:02d}"
                
                # Verifica unicidade (defesa contra concorrência)
                if Family.objects.filter(registration_number=self.registration_number).exists():
                    raise ValidationError(f"Número {self.registration_number} já existe")
        
        super().save(*args, **kwargs)
    """

    """
    Representa o adulto cadastrado em família.
    """
class Adult(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='adults')
    cpf = models.CharField(max_length=14, default='', validators=[validate_cpf], blank=True, null=True, unique=True)
    name = models.CharField(max_length=100)
    social_name = models.CharField(max_length=255, default='')
    ESCOLHA_SEXO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Masculino', 'Masculino'),
    ('Feminino', 'Feminino')
    ]
    sex = models.CharField(max_length=10, choices=ESCOLHA_SEXO, verbose_name="Sexo", default= "Escolha o sexo", blank=True, null=True)
    parentesco = models.CharField(max_length=50, default='', blank=True)
    birth_date = models.DateField(blank=True, null=True)
    ESCOLARIDADE_CHOICES = [
        ('analfabeto', 'Analfabeto'),
        ('fund_comp', 'Ens. Fund. Comp.'),
        ('fund_incomp', 'Ens. Fund. Incomp.'),
        ('med_comp', 'Ens. Med. Comp.'),
        ('med_incomp', 'Ens. Med. Incomp.'),
        ('sup_comp', 'Ens. Sup. Comp.'),
        ('sup_incomp', 'Ens. Sup. Incomp.'),
    ]
    education = models.CharField(max_length=50, choices=ESCOLARIDADE_CHOICES, verbose_name="Escolaridade", default="Escolha a escolaridade", blank=True, null=True)
    ocupacao = models.CharField(max_length=100, blank=True, null=True)
    renda = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)

    @property
    def idade(self):
        if not self.birth_date:
            return ""
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    """
    Representa um aluno, pertencente a uma família, turma e atividades.
    """
class Aluno(models.Model):
    family = models.ForeignKey('Family', on_delete=models.CASCADE, related_name='alunos')
    name = models.CharField(max_length=200, default='')
    cpf = models.CharField(max_length=14, default='', validators=[validate_cpf], unique=True, blank=True, null=True)
    parentesco = models.CharField(max_length=50, default='', blank=True)
    birth_date = models.DateField(blank=True, null=True)
    ESCOLHA_SEXO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Masculino', 'Masculino'),
    ('Feminino', 'Feminino')
    ]
    sex = models.CharField(max_length=10, choices=ESCOLHA_SEXO, verbose_name="Sexo", default= "Escolha o sexo", blank=True, null=True)
    school = models.CharField(max_length=200, default='', blank=True)
    ENSINO_CHOICES = [
    ('', 'Selecione o ensino'),  # Django usa por padrão esse rótulo se vazio
    ('fundamental1', 'Ensino Fundamental 1'),
    ('fundamental2', 'Ensino Fundamental 2'),
    ('medio', 'Ensino Médio'),
    ]
    ensino = models.CharField(max_length=100, choices=ENSINO_CHOICES, default='', blank=True)
    serie = models.CharField(max_length=10, verbose_name="Série", default='', blank=True)
    ESCOLHA_TURNO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Matutino', 'Matutino'),
    ('Vespertino', 'Vespertino')
    ]
    turno = models.CharField(max_length=20, choices=ESCOLHA_TURNO, default='', blank=True)
    PROBLEMA_SAUDE_CHOICES = [
    ('sim', 'Sim'),
    ('não', 'Não')
    ]
    health_problem = models.CharField(max_length=3, choices=PROBLEMA_SAUDE_CHOICES, default='', blank=True)
    special_need = models.CharField(max_length=200, default='', blank=True)
    MEDICATION_CHOICES = [
    ('sim', 'Sim'),
    ('não', 'Não')
    ]
    uso_medicacao = models.CharField(max_length=10, choices=MEDICATION_CHOICES, default='', blank=True)
    qual_medicacao = models.CharField(max_length=200, default='', blank=True)

    FREQUENCIA_OPCOES = (
        ('diaria', 'Diariamente'),
        ('especificos', 'Dias específicos'),
    )
    
    frequencia_tipo = models.CharField(
        max_length=20,
        choices=FREQUENCIA_OPCOES,
        default='diaria',
        verbose_name='Tipo de frequência'
    )
    
    dias_semana = models.JSONField(
        default=list,  # [] vazio por padrão
        blank=True,
        verbose_name='Dias da semana'
    )
    
    STATUS_CHOICES = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('ativo', 'Ativo'),
    ('inativo', 'Inativo'),
    ('Suspenso', 'Suspenso'),
    ('desligado', 'Desligado')
    ]
    status_lsd = models.CharField(max_length=15, choices=STATUS_CHOICES, default='', blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.SET_NULL, null=True, blank=True, related_name='alunos')
    #turma = models.ManyToManyRelationship(Turma, on_delete=models.SET_NULL, null=True, blank=True, related_name='alunos')
    activities = models.ManyToManyField('Activity', blank=True)

    def __str__(self):
            return self.name
    
    @property
    def idade(self):
        if not self.birth_date:
            return ""
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
    
    
    """
    Representa uma turma de assistidos.
    """
class Turma(models.Model):
    educadora = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='turmas')
    FAIXAS_ETARIAS = [('06-07 anos', '06 a 07 anos'),('08-09 anos', '08 a 09 anos'),('10-12 anos', '10 a 12 anos'),('13-17 anos', '13 a 17 anos')]
    faixa_etaria = models.CharField(max_length=15, choices=FAIXAS_ETARIAS, verbose_name="Faixa Etária", default="Selecione a faixa  etária")
    sala = models.CharField(max_length=100)
    ESCOLHA_TURNO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Matutino', 'Matutino'),
    ('Vespertino', 'Vespertino')
    ]
    turno = models.CharField(max_length=20, choices=ESCOLHA_TURNO, default='', blank=True)
    ano_letivo = models.IntegerField(default=timezone.now().year)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    


    def __str__(self):
        return f"{self.sala} - Educadora: {self.educadora.get_full_name() if self.educadora else 'Sem Educadora'}"

"""
    Representa uma atividade (cultural, esportiva, etc) com alunos associados.
    """

class Activity(models.Model):
    atividade = models.CharField(max_length=200, default='', blank=True)
    facilitador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='atividades')
    TIPO_CHOICES = (
        ('arte_cultura', 'Arte e Cultura'),
        ('educativa', 'Socioeducativa'),
        ('esporte', 'Esporte e Lazer'),
        ('tecnologia', 'Tecnologia'),
    )
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default='', blank=True)
    dia_semana =models.CharField(max_length=50, default='', blank=True)
    ESCOLHA_TURNO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Matutino', 'Matutino'),
    ('Vespertino', 'Vespertino')
    ]
    turno = models.CharField(max_length=50, choices=ESCOLHA_TURNO, default='', blank=True)
    alunos = models.ManyToManyField('Aluno', related_name='atividades')
    def __str__(self):
        return self.atividade

    def get_dia_semana_display(self):
            if not self.dia_semana:
                return "-"
            try:
                dias = ast.literal_eval(self.dia_semana)
                if isinstance(dias, list):
                    return ', '.join([str(dia).capitalize() for dia in dias])
            # Se salva como string separada por vírgula
                return self.dia_semana
            except Exception:
                return self.dia_semana


# models.py (adapte conforme seu modelo)
class PerfilUsuario(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='perfis')
    #nivel_permissao = models.CharField(max_length=50)
    tipo_perfil = models.CharField(max_length=20, default='colaborador', 
        choices=[
            ('admin', 'Admin'),
            ('coordenacao', 'Coordenação'),
            ('servicosocial', 'Serviço Social'),
            ('educadora', 'Educadora'),
            ('facilitador', 'Facilitador(a)'),
            ('administrativo', 'Administrativo'),
            ('diretoria', 'Diretoria'),
            ('colaborador', 'Colaborador'),
            ('financeiro', 'Financeiro'),
            ('nutricao', 'Nutrição'),
        ]
    )
    def __str__(self):
        return f"{self.user.username} - {self.get_tipo_perfil_display()}"
    
    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'

# Criar Perfil automaticamente ao criar User
@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    if created and not PerfilUsuario.objects.filter(user=instance, tipo_perfil='colaborador').exists():
        PerfilUsuario.objects.create(user=instance, tipo_perfil='colaborador')

@receiver(post_save, sender=User)
def salvar_perfil_usuario(sender, instance, **kwargs):
    if hasattr(instance, 'perfilusuario'):
        instance.perfis.all()
    
def cadastrar_educadora(request):
    if request.method == "POST":
        # ... criar user/usuario ...
        # Antes de adicionar perfil:
        PerfilUsuario.objects.filter(user=usuario, tipo_perfil='colaborador').delete()
        PerfilUsuario.objects.create(user=usuario, tipo_perfil='educadora')



class FrequenciaTurma(models.Model):
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, null=True, blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, null=True, blank=True)
    
    data = models.DateField(blank=True, null=True)
    presente = models.BooleanField(default=True)  # True: presente, False: falta
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='frequencias_turma_criadas')

    def __str__(self):
        return f"{self.aluno} - {self.turma} - {self.data} - {'Presente' if self.presente else 'Falta'}"

class FrequenciaAtividade(models.Model):
    """
    Frequência individual de aluno para uma chamada de atividade.
    """
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, null=True, blank=True)
    atividade = models.ForeignKey('Activity', on_delete=models.CASCADE, null=True, blank=True)
    data = models.DateField(blank=True, null=True)
    presente = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='frequencias_atividade_criadas')

    def __str__(self):
        return f"{self.aluno} - {self.atividade} - {self.data} - {'Presente' if self.presente else 'Falta'}"


class FrequenciaAluno(models.Model):
    
    #Frequência individual de aluno para uma chamada.
    
    chamada = models.ForeignKey(FrequenciaTurma, on_delete=models.CASCADE, related_name='presencas')
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE)
    presente = models.BooleanField(default=True)
    motivo_falta = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.aluno.name} ({'P' if self.presente else 'F'})"

class MovimentacaoTurmaAluno(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="historico_turmas")
    turma_origem = models.ForeignKey(Turma, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    turma_destino = models.ForeignKey(Turma, on_delete=models.CASCADE)
    data_movimentacao = models.DateField(auto_now_add=True)
    motivo = models.CharField(max_length=200, blank=True)

class OcorrenciaAluno(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE, related_name="ocorrencias")
    data = models.DateField(auto_now_add=True)
    ESCOLHA_OCORRENCIA = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Advertência', 'Advertência'),
    ('Atestado Médico', 'Atestado Médico'),
    ('Afastamento Atividades', 'Afastamentodas Atividades'),
    ('Desligamento', 'Desligamento'),
    ('Elogio', 'Elogio'),
    ('Suspensão', 'Suspensão'),
    ('Outro', 'Outro')
    ]
    tipo = models.CharField(max_length=100, choices=ESCOLHA_OCORRENCIA, default='', blank=True)
    descricao = models.TextField()
    responsavel = models.CharField(max_length=100, blank=True)  # Quem registrou
    ESCOLHA_OBSERVACAO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Doença', 'Doença'),
    ('Indisciplina', 'Indisciplina'),
    ('Descumprimento das regras da instituição', 'Descumprimento das regras da instituição'),
    ('Falta', 'Falta'),
    ('Outro', 'Outro')
    ]
    observacoes = models.CharField(max_length=100, choices=ESCOLHA_OBSERVACAO, default='', blank=True)

    def __str__(self):
        return f"{self.aluno.name} - {self.tipo} - {self.data}"



def validar_cpf(value):
    """
    Valida CPF no formato XXX.XXX.XXX-XX ou apenas números.
    """
    cpf = re.sub(r'[^0-9]', '', str(value))  # remove pontos e traços

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError("CPF inválido.")

    # Validação dos dígitos verificadores
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito1 = ((soma * 10) % 11) % 10
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito2 = ((soma * 10) % 11) % 10

    if not (int(cpf[9]) == digito1 and int(cpf[10]) == digito2):
        raise ValidationError("CPF inválido.")

 