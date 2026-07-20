from django.db import models, transaction
from django.db.models.signals import post_save
from django.conf import settings
from django.contrib.auth.models import User 
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.dispatch import receiver
from django.utils import timezone, dateformat
from datetime import date
from AppLSD.validators import validate_cpf
from AppLSD.utils import sincronizar_grupos_usuario




#from localflavor.br.forms import BRCPFField
import re
import ast
import json

#sistema de **auditoria/logs completo**
class AuditModel(models.Model):
    """
    Modelo abstrato para adicionar campos de auditoria em todos os modelos
    """
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_criado',
        verbose_name='Criado por'
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_editado',
        verbose_name='Editado por'
    )
    editado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Editado em'
    )
    excluido = models.BooleanField(default=False, verbose_name='Excluído')
    excluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_excluido',
        verbose_name='Excluído por'
    )
    excluido_em = models.DateTimeField(null=True, blank=True, verbose_name='Excluído em')
    
    class Meta:
        abstract = True  # Importante: modelo abstrato não cria tabela
    
    def soft_delete(self, user):
        self.excluido = True
        self.excluido_por = user
        self.excluido_em = timezone.now()
        self.save()

class AppLog(AuditModel):
    # Referência genérica para qualquer modelo (Aluno, Family, Adult, Activity, Movimentacao...)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    objeto = GenericForeignKey('content_type', 'object_id')

    acao = models.CharField(max_length=100)        # ex: 'aluno_criado', 'aluno_movido'
    descricao = models.TextField()

    class Meta:
        verbose_name = 'Log do Sistema'
        verbose_name_plural = 'Logs do Sistema'
        ordering = ['-criado_em']


class Person(models.Model):
    family = models.ForeignKey(
        'Family', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='members'
    )
    full_name = models.CharField(max_length=255)
    birth_date = models.DateField()
    GENDER_CHOICES = (
        ('F', 'Feminino'),
        ('M', 'Masculino'),
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    cpf = models.CharField(max_length=14, blank=True, null=True, unique=False)
    rg = models.CharField(max_length=20, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    neighborhood = models.CharField(max_length=120, blank=True, null=True)
    cep = models.CharField(max_length=10, blank=True, null=True)
    reference_point = models.CharField(max_length=255, blank=True, null=True)

    # campos sociais e de saúde podem seguir o modelo da ficha do idoso
    schooling = models.CharField(max_length=50, blank=True, null=True)
    occupation = models.CharField(max_length=120, blank=True, null=True)
    income_type = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    profission = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.full_name

    @property
    def age(self):
        from datetime import date
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    @property
    def age_group(self):
        if self.age < 12:
            return 'Crianca'
        elif self.age < 19:
            return 'Adolescente'
        elif self.age < 60:
            return 'Adulto'
        return 'Idoso'


class Family(AuditModel):
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
    responsible = models.ForeignKey('Person', on_delete=models.CASCADE, related_name='families_responsible', blank=True, null=True)
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
    sex = models.CharField(max_length=15, choices=ESCOLHA_SEXO, verbose_name="Sexo", default= "Escolha o sexo", blank=True, null=True)
    SIM_NAO_CHOICES = [
    ('Sim', 'Sim'),
    ('Não', 'Não')
]
    # Programas sociais (checkbox múltiplo)
    mae_solo = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='não')
    SIM_NAO_CHOICES = [
    ('', '---------'),    
    ('Sim', 'Sim'),
    ('Não', 'Não'),
    ('Nutriz', 'Nutriz')
    ]
    gestante = models.CharField(max_length=15, choices=SIM_NAO_CHOICES, blank=True, default="")
    cep = models.CharField("CEP", max_length=9, blank=False, null=True)
    address = models.CharField(max_length=300, blank=False, null=True)
    number = models.CharField(max_length=10, default="S/N", blank=True, null=True)
    neighborhood = models.CharField(max_length=100, default="Não informado")
    reference_point = models.CharField(max_length=200, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    nome_contato = models.CharField(max_length=100, blank=True, null=True)
    telephone_2 = models.CharField(max_length=20, blank=True, null=True)
    nome_contato_2 = models.CharField(max_length=100, blank=True, null=True)
    # Estado civil
    ESTADO_CIVIL_CHOICES = [('solteira', 'Solteira'), ('casada', 'Casada'), ('separada', 'Separada'), ('viuva', 'Viúva'), ('divorciada', 'Divorciada'), ('uniao_estavel', 'União Estável'), ('convive', 'Convive com Alguém'), ('outro', 'Outro')]
    marital_status = models.CharField(max_length=30, choices=ESTADO_CIVIL_CHOICES, verbose_name="Estado Civil", default= "Escolha o estado civil", blank=True, null=True)
    # Escolaridade
    ESCOLARIDADE_CHOICES = [
        ('Analfabeto', 'Analfabeto'),
        ('Ens. Fund. Comp.', 'Ens. Fund. Comp.'),
        ('Ens. Fund. Incomp.', 'Ens. Fund. Incomp.'),
        ('Ens. Med. Comp.', 'Ens. Med. Comp.'),
        ('Ens. Med. Incomp.', 'Ens. Med. Incomp.'),
        ('Ens. Sup. Comp.', 'Ens. Sup. Comp.'),
        ('Ens. Sup. Incomp.', 'Ens. Sup. Incomp.'),
    ]
    education = models.CharField(max_length=50, choices=ESCOLARIDADE_CHOICES, verbose_name="Escolaridade", default="Escolha a escolaridade", blank=True, null=True)
    # Raça/Cor
    RACA_CHOICES = [
        ('Branco', 'Branco'),
        ('Preto', 'Preto'),
        ('Pardo', 'Pardo'),
        ('Amarelo', 'Amarelo'),
        ('Indígena', 'Indígena'),
    ]
    race = models.CharField(max_length=30, choices=RACA_CHOICES, verbose_name="Raça", default="Escolha a raça", blank=True, null=True)
    # Religião
    RELIGIAO_CHOICES = [
        ('Católico', 'Católico'),
        ('Evangélico', 'Evangélico'),
        ('Espírita', 'Espírita'),
        ('Matriz Africana', 'Matriz Africana'),
        ('Não possui religião', 'Não possui religião'),
    ]
    religion = models.CharField(max_length=30, choices=RELIGIAO_CHOICES, verbose_name="Religião", default="Escolha a religião", blank=True, null=True)
    # Escolhas SIM ou NÂO
    SIM_NAO_CHOICES = [
    ('Sim', 'Sim'),
    ('Não', 'Não')
]
    # Programas sociais (checkbox múltiplo)
    is_benefits = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='Não')
    # Qual Programas sociais (checkbox múltiplo)
    PROGRAMAS_SOCIAIS_CHOICES = [
        ('Programa Bolsa Família - PBF', 'Programa Bolsa Família - PBF'),
        ('Benefício de Prestação Continuada - BPC', 'Benefício de Prestação Continuada - BPC'),
        ('Criança Alagoana - CRIA', 'Criança Alagoana - CRIA'),
    ]
    social_benefits = ArrayField(
        models.CharField(max_length=50, choices=PROGRAMAS_SOCIAIS_CHOICES),
        blank=True,
        default=list,
        verbose_name="Programas Sociais"
    )
    bolsa_familia_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Valor do Bolsa Família"
    )
    # Ocupação/profissão
    occupation = models.CharField(max_length=100, blank=True, null=True)
    
    # Trabalhando no momento
    is_working = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='Não')
    location = models.CharField(max_length=100, default=False, blank=True, null=False)

    # Renda comprovada
    has_proven_income = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='Não')
    # Tipos de renda (checkbox múltiplo)
    INCOME_TYPE_CHOICES = [
        ('carteira_assinada', 'Carteira Assinada'),
        ('contrato', 'Contrato'),
        ('pensao', 'Pensão'),
        ('auxilio_doenca', 'Auxílio Doença'),
        ('aposentado', 'Aposentado'),
        ('bpc', 'BPC'),
        
    ]
    income_types = models.JSONField(default=list, blank=True, null=False)
    # Faixa salarial
    SALARIO_CHOICES = [
        ('', '---------'),  # Django usa por padrão esse rótulo se vazio
        ('1_sm', '1 Salário Mínimo'),
        ('2_sm', '2 Salários Mínimos'),
    ]
    salary_range = models.CharField(max_length=30, choices=SALARIO_CHOICES, blank=True, null=True)
    #min_salary_1 = models.BooleanField(default=False)
    #min_salary_2 = models.BooleanField(default=False)

    # Outras pessoas contribuem
    others_contribute = models.CharField(max_length=3, choices=SIM_NAO_CHOICES, blank=True, default='Não')
    who_contributes = models.CharField(max_length=100, blank=True, null=True)

     # Informações sobre o domicílio
    DOMICILE_CHOICES = [
        ('proprio', 'Próprio'), ('alugado', 'Alugado'), ('cedido', 'Cedido')
    ]
    domicile_type = models.CharField(max_length=30, choices=DOMICILE_CHOICES, blank=True, null=True)
    aluguel_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Valor do aluguel"
    )
    # Extras
    num_residents = models.PositiveIntegerField(
        verbose_name="Quantidade de Pessoas no Domicílio",
        validators=[MinValueValidator(1)]  # mínimo 1
    )
    has_pcd = models.PositiveIntegerField(
        verbose_name="PCD", default=0,
        validators=[MinValueValidator(0)]  # mínimo 0
    )
    has_adult = models.PositiveIntegerField(
        verbose_name="Adulto", default=0,
        validators=[MinValueValidator(0)]  # mínimo 0
    )
    has_elderly = models.PositiveIntegerField(
        verbose_name="Idoso", default=0,
        validators=[MinValueValidator(0)]  # mínimo 0
    )
    has_adolescent = models.PositiveIntegerField(
        verbose_name="Adolescente", default=0,
        validators=[MinValueValidator(0)]  # mínimo 0
    )
    has_child = models.PositiveIntegerField(
        verbose_name="Criança", default=0,
        validators=[MinValueValidator(0)]  # mínimo 0
    )
    has_pregnant = models.PositiveIntegerField(
        verbose_name="Gestante", default=0,
        validators=[MinValueValidator(0)]  # mínimo 0
    )
    #file_info = models.FileField(upload_to='families_docs/', blank=True, null=True)
    file_info = models.CharField(max_length=255, null=True, blank=True)
    STATUS_CHOICES = [
        ('ativo', 'Ativo'), ('inativo', 'Inativo'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, blank=True, null=True)
    """
    motivo_desligamento = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )"""
    
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


    def get_social_benefits_display_list(self):
        """Retorna lista com os textos legíveis dos programas sociais."""
        lookup = dict(self.PROGRAMAS_SOCIAIS_CHOICES)
        return [lookup.get(code, code) for code in (self.social_benefits or [])]
    
    def get_income_types_display_list(self):
        lookup = dict(self.INCOME_TYPE_CHOICES)
        return [lookup.get(code, code) for code in (self.income_types or [])]
    
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


class Adult(AuditModel):
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,   # importante
    )
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='adults')
    cpf = models.CharField(max_length=14, default=None, validators=[validate_cpf], blank=True, null=True, unique=True)
    name = models.CharField(max_length=100)
    social_name = models.CharField(max_length=255, default='')
    ESCOLHA_SEXO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazios
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
    SITUACAO_CHOICES = [
        ('trabalha', 'Trabalha'),
        ('nao_trabalha', 'Não Trabalha'),
        ('faz_bico', 'Faz Bico'),
        ('autonomo', 'Autônomo'),
    ]
    status = models.CharField(max_length=50, choices=SITUACAO_CHOICES, blank=True, null=True)
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
class Aluno(AuditModel):
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    family = models.ForeignKey('Family', on_delete=models.CASCADE, related_name='alunos')
    name = models.CharField(max_length=200, default='')
    cpf = models.CharField(max_length=14, default='', validators=[validate_cpf], blank=True, null=True, unique=False)
    nis = models.CharField(max_length=20, default='', blank=True, null=True)
    parentesco = models.CharField(max_length=50, default='', blank=True)
    birth_date = models.DateField(blank=True, null=True)
    ESCOLHA_SEXO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Masculino', 'Masculino'),
    ('Feminino', 'Feminino')
    ]
    sex = models.CharField(max_length=10, choices=ESCOLHA_SEXO, verbose_name="Sexo", default= "Escolha o sexo", blank=True, null=True)
    REDE_ENSINO_CHOICES = [
        ('municipal', 'Municipal'),
        ('estadual', 'Estadual'),
    ]
    rede_ensino = models.CharField(max_length=20, choices=REDE_ENSINO_CHOICES, default='', blank=True)
    school = models.CharField(max_length=200, default='', blank=True)
    ENSINO_CHOICES = [
    ('', 'Selecione o ensino'),  # Django usa por padrão esse rótulo se vazio
    ('infantil', 'Ensino Infantil'),
    ('fundamental1', 'Ensino Fundamental 1'),
    ('fundamental2', 'Ensino Fundamental 2'),
    ('medio', 'Ensino Médio'),
    ]
    ensino = models.CharField(max_length=100, choices=ENSINO_CHOICES, default='', blank=True)
    serie = models.CharField(max_length=30, verbose_name="Série", default='', blank=True)
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
    ('Frequentando', 'Frequentando'),
    ('desligado', 'Desligado')
    ]
    status_lsd = models.CharField(max_length=15, choices=STATUS_CHOICES, default='', blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.SET_NULL, null=True, blank=True, related_name='alunos')
    #turma = models.ManyToManyRelationship(Turma, on_delete=models.SET_NULL, null=True, blank=True, related_name='alunos')
    #activities = models.ManyToManyField('Activity', blank=True)

    motivo_desligamento = models.TextField(
        blank=True,
        null=True,
        verbose_name='Motivo do desligamento'
    )
    data_desligamento = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Data do desligamento'
    )
    desligado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='alunos_desligados',
        verbose_name='Desligado por'
    )

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

    def get_serie_display_custom(self):
        """Retorna o texto legível da série baseado no ensino"""
        series_map = {
            'infantil': {
                'alfabetizacao': 'Alfabetização',
            },
            'fundamental1': {
                '1': '1º ano',
                '2': '2º ano',
                '3': '3º ano',
                '4': '4º ano',
                '5': '5º ano',
            },
            'fundamental2': {
                '6': '6º ano',
                '7': '7º ano',
                '8': '8º ano',
                '9': '9º ano',
            },
            'medio': {
                '1': '1º ano',
                '2': '2º ano',
                '3': '3º ano',
            }
        }
        
        # Converte para string para comparação
        serie_str = str(self.serie) if self.serie else ''
        
        if self.ensino in series_map and serie_str in series_map[self.ensino]:
            return series_map[self.ensino][serie_str]
        return self.serie  # Retorna o valor original se não encontrar
    
    def get_ensino_display_custom(self):
        """Retorna o texto legível do ensino"""
        ensino_map = {
            'infantil': 'Ensino Infantil',
            'fundamental1': 'Ensino Fundamental 1',
            'fundamental2': 'Ensino Fundamental 2',
            'medio': 'Ensino Médio',
        }
        return ensino_map.get(self.ensino, self.ensino)
  
    @property
    def faixa_etaria(self):
        idade = self.idade  # já é calculada pela @property idade
        if idade in ("", None):
            return None

        idade = int(idade)

        if 6 <= idade <= 7:
            return '06 a 07 anos'
        if 8 <= idade <= 9:
            return '08 a 09 anos'
        if 10 <= idade <= 12:
            return '10 a 12 anos'
        if 13 <= idade <= 17:
            return '13 a 17 anos'
        return None


"""
    Representa uma turma de assistidos.
"""

class Turma(AuditModel):
    educadora = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='turmas')
    FAIXAS_ETARIAS = [('06-07 anos', '06 a 07 anos'),('08-09 anos', '08 a 09 anos'),('08-10 anos', '08 a 10 anos'),('10-12 anos', '10 a 12 anos'),('13-14 anos', '13 a 14 anos'),('13-17 anos', '13 a 17 anos'),('15-17 anos', '15 a 17 anos')]
    faixa_etaria = models.CharField(max_length=15, choices=FAIXAS_ETARIAS, verbose_name="Faixa Etária", default="Selecione a faixa  etária")
    #sala = models.CharField(max_length=100)
    ESCOLHA_GRUPO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Grupo Criança Feliz', 'Grupo Criança Feliz'),
    ('Grupo Primeira Infância', 'Grupo Primeira Infância'),
    ('Grupo Brincar e Aprender', 'Grupo Brincar e Aprender'),
    ('Grupo Pequenos Aventureiros', 'Grupo Pequenos Aventureiros'),
    ('Grupo Pequenos Talentos', 'Grupo Pequenos Talentos'),
    ('Grupo Crescer e Desenvolver', 'Grupo Crescer e Desenvolver'),
    ('Grupo Jovens Criativos', 'Grupo Jovens Criativos'),
    ('Grupo Jovens Sonhadores', 'Grupo Jovens Sonhadores'),
    ('Grupo Pensando no Futuro', 'Grupo Pensando no Futuro'),
    ('Grupo Futuro Brilhante', 'Grupo Futuro Brilhante'),
    ('Grupo Nova Geração', 'Grupo Nova Geração'),

    ]
    grupo = models.CharField(max_length=100,choices=ESCOLHA_GRUPO, blank=True, null=True)
    ESCOLHA_TURNO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Matutino', 'Matutino'),
    ('Vespertino', 'Vespertino')
    ]
    turno = models.CharField(max_length=20, choices=ESCOLHA_TURNO, default='', blank=True)
    ano_letivo = models.IntegerField(default=timezone.now().year)

    def __str__(self):
        return f"{self.grupo} - Educadora: {self.educadora.first_name} - {self.turno}"



class TurmaLog(AuditModel):
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='logs')
    acao = models.CharField(max_length=100)          # ex: 'frequencia_criada'
    descricao = models.TextField()                   # texto humano: "Frequência de hoje registrada pela educadora Ana"
    
    class Meta:
        verbose_name = 'Log de Turma'
        verbose_name_plural = 'Logs de Turmas'

"""
    Representa uma atividade (cultural, esportiva, etc) com alunos associados.
    """
class Activity(AuditModel):
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
    #turma = models.ForeignKey("Turma", on_delete=models.CASCADE, related_name="atividades")
    horario_inicio = models.TimeField()
    horario_fim = models.TimeField()

    DIAS_SEMANAS_CHOICES = (
        ('segunda', 'Segunda-feira'),
        ('terca', 'Terça-feira'),
        ('quarta', 'Quarta-feira'),
        ('quinta', 'Quinta-feira'),
        ('sexta', 'Sexta-feira'),
    )
    def __str__(self):
        return self.atividade

    def get_dia_semana_display(self):
        """
        Retorna os dias formatados, ex.: 'Segunda-feira, Quarta-feira'.
        """
        if not self.dia_semana:
            return "-"

        try:
            # tentar ler como lista salva em string: "['segunda', 'quarta']"
            dias = ast.literal_eval(self.dia_semana)
            if isinstance(dias, list):
                # montar dict código -> label a partir do choices
                label_map = dict(self.DIAS_SEMANAS_CHOICES)
                return ', '.join(label_map.get(d, d).capitalize() for d in dias)
            # se não for lista, cai no return final
        except Exception:
            pass

        # fallback: texto cru (no caso de dados antigos)
        return self.dia_semana
    
    

class ActivityLog(AuditModel):
    Activity = models.ForeignKey('Activity', on_delete=models.CASCADE, related_name='logs')
    acao = models.CharField(max_length=100)          # ex: 'frequencia_criada'
    descricao = models.TextField()                   # texto humano: "Frequência de hoje registrada pela educadora Ana"
    
    class Meta:
        verbose_name = 'Log de Atividade'
        verbose_name_plural = 'Logs de Atividades'


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
    if created: # and not PerfilUsuario.objects.filter(user=instance).exists():
        #PerfilUsuario.objects.create(user=instance, tipo_perfil='colaborador')
        return


@receiver(post_save, sender='AppLSD.PerfilUsuario')
def sincronizar_grupos_perfil(sender, instance, **kwargs):
    # sempre que um PerfilUsuario for salvo, re-sincroniza os grupos
    sincronizar_grupos_usuario(instance.user)


class FrequenciaTurma(AuditModel):
    class StatusAula(models.TextChoices):
        NORMAL = 'NORMAL', 'Houve aula'
        NAO_HOUVE = 'NAO_HOUVE', 'Não houve aula'

    class MotivoNaoAula(models.TextChoices):
        FERIADO = 'FERIADO', 'Feriado'
        EVENTO_EXTERNO = 'EVENTO_EXTERNO', 'Evento externo'
        FALTA_ENERGIA = 'FALTA_ENERGIA', 'Falta de energia'
        SEM_AGUA = 'SEM_AGUA', 'Sem água'
        OUTRO = 'OUTRO', 'Outro'

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, null=True, blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, null=True, blank=True)
    data = models.DateField(blank=True, null=True)

    presente = models.BooleanField(default=True)

    status_aula = models.CharField(
        max_length=20,
        choices=StatusAula.choices,
        default=StatusAula.NORMAL
    )
    motivo_nao_aula = models.CharField(
        max_length=30,
        choices=MotivoNaoAula.choices,
        blank=True
    )
    observacao_nao_aula = models.CharField(
        max_length=255,
        blank=True
    )

    def __str__(self):
        return f"{self.turma} - {self.data} - {self.get_status_aula_display()}"


class MotivoFaltaChoices(models.TextChoices):
        SJ = 'SJ', 'Sem Justificativa'
        AM = 'AM', 'Atestado Médico'
        DM = 'DM', 'Declaração Médica'
        OT = 'OT', 'Outro'

class FrequenciaAtividade(AuditModel):
    """
    Frequência individual de aluno para uma chamada de atividade.
    """
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, null=True, blank=True)
    atividade = models.ForeignKey('Activity', on_delete=models.CASCADE, null=True, blank=True)
    data = models.DateField(blank=True, null=True)
    presente = models.BooleanField(default=True)
    motivo_falta = models.CharField(
        max_length=100,
        choices=MotivoFaltaChoices.choices,
        blank=True
    )

    class Meta:
        unique_together = ('atividade', 'aluno', 'data')

    def __str__(self):
        return f"{self.aluno} - {self.atividade} - {self.data} - {'Presente' if self.presente else 'Falta'}"
    

class FrequenciaAluno(models.Model):
    class StatusPresenca(models.TextChoices):
        PRESENTE = 'P', 'Presente'
        FALTA = 'F', 'Falta'
        NAO_HOUVE_AULA = 'NHA', 'Não houve aula'

    
    chamada = models.ForeignKey(FrequenciaTurma, on_delete=models.CASCADE, related_name='presencas')
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE)

    presente = models.BooleanField(default=True)

    status = models.CharField(
        max_length=3,
        choices=StatusPresenca.choices,
        default=StatusPresenca.PRESENTE
    )
    motivo_falta = models.CharField(
        max_length=100,
        choices=MotivoFaltaChoices.choices,
        blank=True
    )

    def __str__(self):
        return f"{self.aluno.name} ({self.get_status_display()})"
    
class MovimentacaoTurmaAluno(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    turma_origem = models.ForeignKey(Turma, on_delete=models.SET_NULL, null=True, related_name='+')
    turma_destino = models.ForeignKey(Turma, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    motivo = models.CharField(max_length=255, blank=True)
    data = models.DateTimeField(auto_now_add=True)

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

# Modelo para armazenar documentos relacionados à família
class DocumentoFamilia(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='documentos')
    ano = models.IntegerField()
    tipo = models.CharField(max_length=50, default='geral')  # ex: comprovante_endereco, rg, etc.
    arquivo = models.FileField(upload_to='familias/%Y/%m/%d/')
    criado_em = models.DateTimeField(auto_now_add=True)

