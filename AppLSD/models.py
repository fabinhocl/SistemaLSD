from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date

#from localflavor.br.forms import BRCPFField
import re


class Family(models.Model):
    """
    Representa uma família no sistema, com dados cadastrais e sociais.
    """
    # Dados básicos
    registration_number = models.CharField(max_length=100, default='')
    responsible_name = models.CharField(max_length=255, default='')
    nis = models.CharField(max_length=20, blank=True, null=True)
    rg = models.CharField(max_length=20, blank=True, null=True)
    cpf = models.CharField(max_length=14, unique=True, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    ESCOLHA_SEXO = [
    ('', '---------'),  # Django usa por padrão esse rótulo se vazio
    ('Masculino', 'Masculino'),
    ('Feminino', 'Feminino')
    ]
    sex = models.CharField(max_length=10, choices=ESCOLHA_SEXO, verbose_name="Sexo", default= "Escolha o sexo", blank=True, null=True)
    cep = models.CharField("CEP", max_length=9, blank=False, null=True)
    address = models.CharField(max_length=300, blank=False, null=True)
    neighborhood = models.CharField(max_length=100, default="Não informado")
    reference_point = models.CharField(max_length=200, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
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
    religion = models.CharField(max_length=50, choices=RELIGIAO_CHOICES, verbose_name="Religião", default="Escolha a religião", blank=True, null=True)
    # Programas sociais (checkbox múltiplo)
    PROGRAMAS_SOCIAIS_CHOICES = [
        ('bolsa_brasil', 'Programa Bolsa Brasil - PBF'),
        ('bpc', 'Benefício de Prestação Continuada - BPC'),
        ('cria_alagoana', 'Criança Alagoana - CRIA'),
    ]
    social_benefits = models.CharField(max_length=255, choices=PROGRAMAS_SOCIAIS_CHOICES, verbose_name="Programas Sociais", blank=True, null=True)
    # Ocupação/profissão
    occupation = models.CharField(max_length=100, blank=True, null=True)
    
    # Trabalhando no momento
    is_working = models.BooleanField(default=False)
    working_function = [('Sim', 'Sim'), ('Não', 'Não')]

    function = models.CharField(max_length=100, default=False, blank=True, null=False)

    # Renda comprovada
    has_proven_income = models.BooleanField(default=False)
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
        ('1_sm', '1 Salário Mínimo'),
        ('2_sm', '2 Salários Mínimos'),
    ]
    salary_range = models.CharField(max_length=10, choices=SALARIO_CHOICES, blank=True, null=True)
    #min_salary_1 = models.BooleanField(default=False)
    #min_salary_2 = models.BooleanField(default=False)

    # Outras pessoas contribuem
    others_contribute = models.BooleanField(default=False)
    who_contributes = models.CharField(max_length=100, blank=True, null=True)

     # Informações sobre o domicílio
    DOMICILE_CHOICES = [
        ('proprio', 'Próprio'), ('alugado', 'Alugado'), ('cedido', 'Cedido')
    ]
    domicile_type = models.CharField(max_length=10, choices=DOMICILE_CHOICES, blank=True, null=True)
    
    # Extras
    num_residents = models.IntegerField(default=0)
    has_elderly = models.BooleanField(default=False)
    has_adolescent = models.BooleanField(default=False)
    has_child = models.BooleanField(default=False)
    has_pregnant = models.BooleanField(default=False)
    file_info = models.FileField(upload_to='families_docs/', blank=True, null=True)
    #aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='families')


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
    
    """
    Representa o adulto cadastrado em família.
    """
class Adult(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='adults')
    name = models.CharField(max_length=100)
    parentesco = models.CharField(max_length=50, default='', blank=True)
    birth_date = models.DateField(blank=True, null=True)
    school_level = models.CharField(max_length=50)
    ocupacao = models.CharField(max_length=100)
    renda = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, blank=True, null=True)

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
    parentesco = models.CharField(max_length=50, default='', blank=True)
    birth_date = models.DateField(blank=True, null=True)
    school = models.CharField(max_length=200, default='', blank=True)
    serie = models.CharField(max_length=10, default='', blank=True)
    turno = models.CharField(max_length=20, default='', blank=True)
    health_problem = models.CharField(max_length=200, default='', blank=True)
    status_lsd = models.CharField(max_length=50, default='', blank=True)
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
    professor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='turmas')
    FAIXAS_ETARIAS = [('06-07 anos', '06 a 07 anos'),('08-09 anos', '08 a 09 anos'),('10-12 anos', '10 a 12 anos'),('13-17 anos', '13 a 17 anos')]
    faixa_etaria = models.CharField(max_length=15, choices=FAIXAS_ETARIAS, verbose_name="Faixa Etária", default="Selecione a faixa  etária")
    sala = models.CharField(max_length=100)
    turno = models.CharField(max_length=50)
    ano_letivo = models.IntegerField(default=timezone.now().year)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    


    def __str__(self):
        return f"{self.sala} - Prof: {self.professor.get_full_name() if self.professor else 'Sem Professor'}"

"""
    Representa uma atividade (cultural, esportiva, etc) com alunos associados.
    """

class Activity(models.Model):
    descricao = models.CharField(max_length=200, default='', blank=True)
    professor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='atividades')
    tipo = models.CharField(max_length=50, default='', blank=True)  # cultural ou esportiva
    dia_semana =models.CharField(max_length=50, default='', blank=True)
    turno = models.CharField(max_length=20, default='', blank=True)
    alunos = models.ManyToManyField('Aluno', related_name='atividades')
    def __str__(self):
        return self.descricao





"""
class PerfilProfessor(models.Model):
    TIPOS = (
        ('atividade', 'Professor de Atividade'),
        ('turma', 'Professor de Turma'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=50, choices=TIPOS)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_tipo_display()})"
"""
# models.py (adapte conforme seu modelo)
class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=[
        ('admin', 'Admin'),
        ('coordenação', 'Coordenação'),
        ('supervisor', 'Supervisor'),
        ('professor', 'Professor'),
        ('administrativo', 'Administrativo'),
        ('colaborador', 'Colaborador'),
    ])

# Criar Perfil automaticamente ao criar User
@receiver(post_save, sender=User)
def criar_perfil_usuario(sender, instance, created, **kwargs):
    if created:
       PerfilUsuario.objects.create(user=instance)

@receiver(post_save, sender=User)
def salvar_perfil_usuario(sender, instance, **kwargs):
    if hasattr(instance, 'perfilusuario'):
        instance.perfilusuario.save()


class FrequenciaTurma(models.Model):
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, null=True, blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, null=True, blank=True)
    data = models.DateField(blank=True, null=True)
    presente = models.BooleanField(default=True)  # True: presente, False: falta

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
    tipo = models.CharField(max_length=50)   # Ex: "Comportamento", "Saúde", etc.
    descricao = models.TextField()
    responsavel = models.CharField(max_length=100, blank=True)  # Quem registrou
    observacoes = models.TextField(blank=True)

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

 