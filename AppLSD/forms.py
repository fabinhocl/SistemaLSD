from django import forms
from .models import Family, Aluno, Turma, Activity, User, OcorrenciaAluno, Adult
from dal import autocomplete
from django.core.validators import RegexValidator
from django.forms.models import inlineformset_factory
from django.forms import DateInput
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column
from .validators import cpf_validator
from datetime import date
import re




def format_cpf(cpf):
    # Remove tudo que não é número
    cpf_numeros = re.sub(r'\D', '', cpf)
    if len(cpf_numeros) != 11:
        return cpf  # Retorna como está se tiver tamanho inesperado
    return '{}.{}.{}-{}'.format(
        cpf_numeros[:3], cpf_numeros[3:6], cpf_numeros[6:9], cpf_numeros[9:]
    )
class FamilyForm(forms.ModelForm):
    nis = forms.CharField(
        max_length=11,
        required=False,
        validators=[RegexValidator(r'^\d{11}$', message='NIS deve ter 11 dígitos numéricos')]
    )
    rg = forms.CharField(
        max_length=20,
        required=False,
        validators=[RegexValidator(r'^\d+$', message='RG deve conter apenas dígitos')]
    )
    cpf = forms.CharField(
        label='CPF',
        required=True,
        max_length=14,
        widget=forms.TextInput(attrs={'id': 'cpf', 'placeholder': 'xxx.xxx.xxx-xx'}),
        #validators=[validate_cpf]
    )
        
    telephone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={'id': 'telephone', 'placeholder': '(99) 99999-9999'}),
        
        )
        
    
    telephone_2 = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone 2",
        widget=forms.TextInput(attrs={'id': 'telephone_2', 'placeholder': '(99) 99999-9999'}),
    )

    is_benefits = forms.ChoiceField(
        choices=[('Sim', 'Sim'), ('Não', 'Não')],
        widget=forms.RadioSelect,
        label="Beneficiário de Programas Sociais?"
    )
    social_benefits = forms.ChoiceField(
        choices=Family.PROGRAMAS_SOCIAIS_CHOICES,
        widget=forms.Select,
        required=False,
        label="Qual Programa?"
    )
    
    has_proven_income = forms.ChoiceField(
        choices=[('Sim', 'Sim'), ('Não', 'Não')],
        widget=forms.RadioSelect,
        label="Possui renda comprovada?"
    )
    income_types = forms.MultipleChoiceField(
        choices=Family.INCOME_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Tipo de renda comprovada"
    )
    others_contribute = forms.ChoiceField(
    choices=[('Sim', 'Sim'), ('Não', 'Não')],
    widget=forms.RadioSelect,
    label="Outras pessoas contribuem?"
    )
    who_contributes = forms.CharField(
        required=False,
        label="Quem contribui?"
    )
    is_working = forms.ChoiceField(
        choices=[('Sim', 'Sim'), ('Não', 'Não')],
        widget=forms.RadioSelect,
        label="Trabalhando no momento?"
    )
    function = forms.CharField(
        required=False,
        label="Qual função?"
    )
    idade = forms.CharField(label='Idade', required=False, widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    class Meta:
        model = Family
        
        fields = [
            'registration_number',
            'responsible_name',
            'social_name',
            'nis',
            'rg',
            'cpf',
            'birth_date',
            'idade',
            'sex',
            'mae_solo',
            'gestante',
            'cep',
            'address',
            'number',
            'neighborhood',
            'reference_point',
            'telephone',
            'nome_contato',
            'telephone_2',
            'nome_contato_2',
            'marital_status',
            'education',
            'race',
            'religion',
            'is_benefits',
            'social_benefits',
            'bolsa_familia_value',
            'occupation',
            'is_working',
            'location',
            'has_proven_income',
            'income_types',
            'salary_range',
            'others_contribute',
            'who_contributes',
            'domicile_type',
            'aluguel_value',
            'num_residents',
            'has_pcd',
            'has_adult',
            'has_elderly',
            'has_adolescent',
            'has_child',
            'has_pregnant',
            'file_info',
            'status',
            'motivo_desligamento',
        ]
        labels = {
            'registration_number': 'Inscrição',
            'responsible_name': 'Responsável',
            'social_name': 'Nome Social',
            'nis': 'NIS',
            'rg': 'RG',
            'cpf': 'CPF',
            'birth_date': 'Data de Nascimento',
            'idade': 'Idade',
            'sex': 'Sexo',
            'mae_solo': 'Mãe Solo',
            'gestante': 'Gestante',
            'cep': 'CEP',
            'address': 'Endereço',
            'number': 'Nº',
            'neighborhood': 'Bairro',
            'reference_point': 'Ponto de Referência',
            'telephone': 'Telefone',
            'nome_contato': 'Nome do Contato',
            'telephone_2': 'Telefone 2',
            'nome_contato_2': 'Nome do Contato',
            'marital_status': 'Estado Civil',
            'education': 'Escolaridade',
            'race': 'Raça',
            'religion': 'Religião',
            'is_benefits': 'É Beneficiário(a) de Progrma Sociais',
            'social_benefits': 'Qual Programas Sociais',
            'occupation': 'Ocupação/Profissão',
            'is_working': 'Está Trabalhando?',
            'location': 'Qual local?',
            'has_proven_income': 'Possui Renda Comprovada',
            'income_types': 'Tipo de Renda Comprovada',
            'salary_range': 'Faixa Salarial',
            'others_contribute': 'Outras Pessoas Contribuem com a Renda da Família',
            'who_contributes': 'Quem Contribui',
            'domicile_type': 'Informações sobre o Domicílio',
            'num_residents': 'Quantidade de Pessoas no Domicílio',
            'has_pcd': 'PCD',
            'has_adult': 'Adulto',
            'has_elderly': 'Idoso',
            'has_adolescent': 'Adolescente',
            'has_child': 'Criança',
            'has_pregnant': 'Gestante',
            'file_info': 'Arquivo',
            'status': 'Situação',
            'motivo_desligamento': 'Motivo do Desligamento (se aplicável)',
        }
        widgets = {
            'birth_date': DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'bolsa_familia_value': forms.NumberInput(attrs={'class': 'form-control',
                'step': '0.01',
                'min': '0',}),
            'aluguel_value': forms.NumberInput(attrs={'class': 'form-control',
                'step': '0.01',
                'min': '0',}),
            #'marital_status': forms.RadioSelect,
            #'education': forms.RadioSelect,
            #'race': forms.RadioSelect,
            #'religion': forms.RadioSelect,
            # Adicione widgets para outros campos conforme necessidade
        }

   
    def clean_cpf(self):
        value = self.cleaned_data["cpf"]
        digits = ''.join(filter(str.isdigit, value or ''))
        # já foi validado pelo validator; aqui você só normaliza
        return cpf_validator.mask(digits)  # se quiser salvar sempre formatado
    
    def clean_nis(self):
        nis = self.cleaned_data.get('nis')
        if nis and not nis.isdigit():
            raise forms.ValidationError("NIS deve conter apenas números.")
        return nis

    def clean_rg(self):
        rg = self.cleaned_data.get('rg')
        if rg and not rg.isdigit():
            raise forms.ValidationError("RG deve conter apenas números.")
        return rg

    def clean_telephone(self):
        tel = self.cleaned_data.get("telephone")
        # já validado via RegexValidator
        return tel

    def clean(self):
        cleaned_data = super().clean()
        # Aqui pode validar relações entre campos se necessário
        return cleaned_data


    

    def calcular_idade(birth_date):
        from datetime import date
        hoje = date.today()
        idade = hoje.year - birth_date.year - ((hoje.month, hoje.day) < (birth_date.month, birth_date.day))
        return idade

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('num_residents')
        soma = (
            cleaned_data.get('has_adult', 0) +
            cleaned_data.get('has_elderly', 0) +
            cleaned_data.get('has_pcd', 0) +
            cleaned_data.get('has_adolescent', 0) +
            cleaned_data.get('has_child', 0) +
            cleaned_data.get('has_pregnant', 0)
        )
        if total is not None and soma != total:
            raise forms.ValidationError('A soma dos tipos deve ser igual ao total de pessoas no domicílio.')
        return cleaned_data

    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['birth_date'].input_formats = ['%Y-%m-%d']
            self.helper = FormHelper()
            self.helper.layout = Layout(
                # Outras linhas...
                Row(
                    Column('is_benefits', css_class='col-md-4'),
                    Column('social_benefits', css_class='col-md-4'),
                ),
                Row(
                    Column('occupation', css_class='col-md-4'),
                    Column('is_working', css_class='col-md-4'),
                    Column('location', css_class='col-md-4'),
                ),
                Row(
                    Column('has_proven_income', css_class='col-md-4'),
                    Column('income_types', css_class='col-md-4'),
                    Column('salary_range', css_class='col-md-4'),
                ),
                Row(
                    Column('others_contribute', css_class='col-md-4'),
                    Column('who_contributes', css_class='col-md-4'),
                ),
                Row(
                    Column('num_residents', css_class='col-md-4'),
                    # Campos dos tipos em uma linha
                    Column('has_adult', css_class='col-md-2'),
                    Column('has_elderly', css_class='col-md-2'),
                    Column('has_pcd', css_class='col-md-2'),
                    Column('has_adolescent', css_class='col-md-2'),
                    Column('has_child', css_class='col-md-2'),
                    Column('has_pregnant', css_class='col-md-2'),
                )   
                # Continue com os demais campos...
            )


class AdultForm(forms.ModelForm):
    telephone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        widget=forms.TextInput(attrs={'id': 'telephone', 'placeholder': '(99) 99999-9999'}),
        
        )
    cpf = forms.CharField(
        label='CPF',
        required=True,
        max_length=14,
        widget=forms.TextInput(attrs={'id': 'cpf', 'placeholder': 'xxx.xxx.xxx-xx'}),
    )
    idade = forms.CharField(label='Idade', required=False, widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    class Meta:
        model = Adult
        fields = ['family', 'name', 'cpf', 'social_name', 'sex', 'parentesco', 'birth_date', 'idade', 'education', 'ocupacao', 'renda', 'status', 'telephone']
        labels = {
            'family': 'Família',
            'name': 'Nome',
            'cpf': 'CPF',
            'social_name': 'Nome Social',
            'sex': 'Sexo',
            'parentesco': 'Parentesco (Adulto com o Responsável)',
            'birth_date': 'Data de Nascimento',
            'idade': 'Idade',
            'education': 'Escolaridade',
            'ocupacao': 'Ocupação/Profissão',
            'renda': 'Renda',
            'status': 'Situação',
            'telephone': 'Telefone',
        }
        widgets = {
            'family': forms.HiddenInput(),
            'birth_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),   
        }

    def clean_cpf(self):
        value = self.cleaned_data.get("cpf")
        digits = ''.join(filter(str.isdigit, value or ''))
        if not digits:
            return ''          # aceita vazio, se for sua regra
        if not cpf_validator.validate(digits):
            raise forms.ValidationError("CPF inválido.")
        return cpf_validator.mask(digits)
    
    def clean_telephone(self):
        tel = self.cleaned_data.get("telephone")
        # já validado via RegexValidator
        return tel

class AlunoForm(forms.ModelForm):
    health_problem = forms.ChoiceField(
        choices=[('sim', 'Sim'), ('não', 'Não')],
        widget=forms.RadioSelect,
        label="Tem problema de Saúde?"
    )
    special_need = forms.CharField(required=False, label="Qual função?")
    uso_medicacao = forms.ChoiceField(
        choices=[('sim', 'Sim'), ('não', 'Não')],
        widget=forms.RadioSelect,
        label="Faz uso de Medicação?"
    )
    qual_medicacao = forms.CharField(required=False, label="Qual medicação?")
    idade = forms.CharField(
        label='Idade',
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly'})
    )

    DIAS_SEMANA = (
        ('segunda', 'Segunda-feira'),
        ('terca', 'Terça-feira'),
        ('quarta', 'Quarta-feira'),
        ('quinta', 'Quinta-feira'),
        ('sexta', 'Sexta-feira'),
    )

    dias_semana = forms.MultipleChoiceField(
        choices=DIAS_SEMANA,
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    cpf = forms.CharField(
        label='CPF',
        required=False,
        max_length=14,
        widget=forms.TextInput(attrs={'id': 'cpf', 'placeholder': 'xxx.xxx.xxx-xx'}),
    )
    nis = forms.CharField(
        max_length=11,
        required=False,
        validators=[RegexValidator(r'^\d{11}$', message='NIS deve ter 11 dígitos numéricos')]
    )
    class Meta:
        model = Aluno
        fields = '__all__'
        exclude = ('activities',)
        labels = {
            'family': 'Família',
            'name': 'Nome do Aluno',
            'cpf': 'CPF',
            'nis': 'NIS',
            'sex': 'Sexo',
            'parentesco': 'Parentesco (Criança com o Responsável)',
            'birth_date': 'Data de Nascimento',
            'idade': 'Idade',
            'school': 'Escola',
            'serie': 'Série',
            'ensino': 'Ensino',
            'turno': 'Turno',
            'health_problem': 'Tem Problema de Saúde?',
            'special_need': 'Qual problema de Saúde?',
            'uso_medicacao': 'Faz uso de Medicação',
            'qual_medicacao': 'Qual Medicação?',
            'frequencia_tipo': 'Tipo de Frequência',
            'dias_semana': 'Dias da Semana',
            'status_lsd': 'Situação Atual no Lar',
            'faixa_etaria': 'Faixa Etária',
        }
        widgets = {
            'family': forms.Select(attrs={'class': 'form-select'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'ensino': forms.Select(attrs={'class': 'form-select', 'id': 'ensino'}),
            'serie': forms.Select(attrs={'class': 'form-select', 'id': 'serie'}),
            'health_problem': forms.RadioSelect(),
            'uso_medicacao': forms.RadioSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.template_pack = 'bootstrap5'
        self.helper.layout = Layout(
            Row(
                Column('birth_date', css_class='col-md-6 mb-0'),
                Column('idade', css_class='col-md-6 mb-0'),
            ),
            'family',
            'parentesco',
            'name',
            'sex',
            'school',
            'ensino',
            'serie',
            'turno',
            'health_problem',
            'special_need',
            'uso_medicacao',
            'qual_medicacao',
            'status_lsd',
            'faixa_etaria',
        )

        # se quiser garantir valor default para radios ao criar:
        if not self.instance.pk:
            self.fields['health_problem'].initial = 'não'
            self.fields['uso_medicacao'].initial = 'não'

    def calcular_idade(self, birth_date):
        if not birth_date:
            return None
        hoje = date.today()
        return hoje.year - birth_date.year - (
            (hoje.month, hoje.day) < (birth_date.month, birth_date.day)
        )
    
    def calcular_faixa_etaria(self, idade):
        if idade is None:
            return None
        if 6 <= idade <= 7:
            return '06 a 07 anos'
        if 8 <= idade <= 9:
            return '08 a 09 anos'
        if 10 <= idade <= 12:
            return '10 a 12 anos'
        if 13 <= idade <= 17:
            return '13 a 17 anos'
        return None

    def clean(self):
        cleaned_data = super().clean()

        health_problem = cleaned_data.get('health_problem')
        special_need = cleaned_data.get('special_need')
        if health_problem == 'sim' and not special_need:
            self.add_error('special_need', 'Este campo é obrigatório quando há problema de saúde.')

        frequencia_tipo = cleaned_data.get('frequencia_tipo')
        dias_semana = cleaned_data.get('dias_semana', [])
        if frequencia_tipo == 'especificos' and not dias_semana:
            self.add_error('dias_semana', 'Selecione pelo menos um dia da semana.')

        birth_date = cleaned_data.get("birth_date")
        if birth_date:
            idade = self.calcular_idade(birth_date)
            cleaned_data["faixa_etaria"] = self.calcular_faixa_etaria(idade)

        return cleaned_data

    def clean_cpf(self):
        value = self.cleaned_data.get("cpf")
        digits = ''.join(filter(str.isdigit, value or ''))
        if not digits:
            return ''
        if not cpf_validator.validate(digits):
            raise forms.ValidationError("CPF inválido.")
        return cpf_validator.mask(digits)
    
    def clean_nis(self):
        nis = self.cleaned_data.get('nis')
        if nis and not nis.isdigit():
            raise forms.ValidationError("NIS deve conter apenas números.")
        return nis

    def save(self, commit=True):
        instance = super().save(commit=False)
        dias_semana = self.cleaned_data.get('dias_semana', [])
        instance.dias_semana = dias_semana
        if commit:
            instance.save()
        return instance
    


AlunoInlineFormSet = forms.inlineformset_factory(
    Family, Aluno, form=AlunoForm,
    fields=[
        'name',
        'parentesco',
        'birth_date',
        'school',
        'serie',
        'turno',
        'health_problem',
        'status_lsd',
        # adicione outros campos conforme o seu model
    ],
    extra=0, can_delete=True
)

AdultFormSet = inlineformset_factory(
    Family, Adult,
    fields=['name', 'parentesco', 'birth_date', 'education', 'ocupacao', 'renda', 'status', 'telephone'],
    extra=0, can_delete=True
)
        
class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['educadora', 'faixa_etaria', 'sala', 'turno']
        labels = {'educadora': 'Nome da Educadora', 'faixa_etaria': 'Faixa Etária', 'sala': 'Sala', 'turno': 'Turno'}


class ActivityForm(forms.ModelForm):
    TIPO_CHOICES = (
        ('arte_cultura', 'Arte e Cultura'),
        ('educativa', 'Socioeducativa'),
        ('esporte', 'Esporte e Lazer'),
        ('tecnologia', 'Tecnologia'),
    )
    tipo = forms.ChoiceField(choices=TIPO_CHOICES, label='Tipo')
    DIAS_SEMANAS_CHOICES = (
        ('segunda', 'Segunda-feira'),
        ('terca', 'Terça-feira'),
        ('quarta', 'Quarta-feira'),
        ('quinta', 'Quinta-feira'),
        ('sexta', 'Sexta-feira'),
    )
    dia_semana = forms.MultipleChoiceField(choices=DIAS_SEMANAS_CHOICES, widget=forms.CheckboxSelectMultiple, label='Dias da Semana')
    class Meta:
        model = Activity
        fields = ['facilitador','atividade', 'tipo', 'dia_semana', 'turno']
        labels = {'facilitador': 'Nome Facilitador(a)','atividade': 'Nome da Atividade', 'tipo': 'Tipo', 'dia_semana': 'Dias da Semana', 'turno': 'Turno'}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['facilitador'].queryset = User.objects.filter(perfis__tipo_perfil='facilitador')

class AddAlunosToTurmaForm(forms.Form):
    alunos = forms.ModelMultipleChoiceField(
        queryset=Aluno.objects.filter(turma__isnull=True),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Selecione os alunos para adicionar à turma"
    )

class AlunoFiltroForm(forms.Form):
    nome = forms.CharField(label='Nome', required=False)
    familia = forms.ModelChoiceField(
        queryset=Family.objects.all(),
        required=False,
        label='Família'
    )
    escola = forms.CharField(label='Escola', required=False)

class MoverAlunoForm(forms.Form):
    turma_destino = forms.ModelChoiceField(queryset=Turma.objects.all(), label="Nova Turma")
    motivo = forms.CharField(max_length=255, required=False, label="Motivo da movimentação")

class OcorrenciaAlunoForm(forms.ModelForm):
    class Meta:
        model = OcorrenciaAluno
        fields = ['tipo', 'descricao', 'responsavel', 'observacoes']

class UsuarioForm(forms.ModelForm):
    STATUS_CHOICES = (
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
    )
    senha = forms.CharField(label='Senha', widget=forms.PasswordInput)
    status = forms.ChoiceField(choices=STATUS_CHOICES, label='Status', initial='ativo')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email']  # escolha os campos desejados
        help_texts = {
            'username': '',  # Remove o help_text padrão
        }
        labels = {
            'username': 'Usuário',
            'first_name': 'Nome',
            'email': 'Email',
            'senha': 'Senha',
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['senha'])
        status = self.cleaned_data.get('status')
        if commit:
            user.save()
        return user



