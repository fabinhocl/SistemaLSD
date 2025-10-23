from django import forms
from .models import Family, Aluno, Turma, Activity, User, OcorrenciaAluno, Adult
from dal import autocomplete
from django.core.validators import RegexValidator
from django.forms.models import inlineformset_factory
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column




def validate_cpf(value):
    import re
    cpf_digits = re.sub(r'\D', '', value or '')
    if len(cpf_digits) != 11:
        raise forms.ValidationError('CPF deve ter 11 dígitos.')

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
        max_length=14,
        required=False,
        validators=[validate_cpf]
    )
        
    telephone = forms.CharField(
        max_length=20,
        required=False,
        label="Telefone",
        validators=[RegexValidator(
            r'^\(?\d{2}\)?\s?\d{4,5}-?\d{4}$',
            message='Telefone no formato válido (ex: (99) 99999-9999)'
        )]
        
    )
    has_proven_income = forms.ChoiceField(
        choices=[(True, 'Sim'), (False, 'Não')],
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
    choices=[(True, 'Sim'), (False, 'Não')],
    widget=forms.RadioSelect,
    label="Outras pessoas contribuem?"
    )
    who_contributes = forms.CharField(
        required=False,
        label="Quem contribui?"
    )
    is_working = forms.ChoiceField(
        choices=[(True, 'Sim'), (False, 'Não')],
        widget=forms.RadioSelect,
        label="Trabalhando no momento?"
    )
    function = forms.CharField(
        required=False,
        label="Qual função?"
    )

    class Meta:
        model = Family
        
        fields = [
            'registration_number',
            'responsible_name',
            'nis',
            'rg',
            'cpf',
            'birth_date',
            'sex',
            'cep',
            'address',
            'neighborhood',
            'reference_point',
            'telephone',
            'marital_status',
            'education',
            'race',
            'religion',
            'social_benefits',
            'occupation',
            'is_working',
            'function',
            'has_proven_income',
            'income_types',
            'salary_range',
            'others_contribute',
            'who_contributes',
            'num_residents',
            'has_elderly',
            'has_adolescent',
            'has_child',
            'has_pregnant',
            'file_info',
        ]
        labels = {
            'registration_number': 'Número de Inscrição',
            'responsible_name': 'Responsável',
            'nis': 'NIS',
            'rg': 'RG',
            'cpf': 'CPF',
            'birth_date': 'Data de Nascimento',
            'sex': 'Sexo',
            'cep': 'CEP',
            'address': 'Endereço',
            'neighborhood': 'Bairro',
            'reference_point': 'Ponto de Referência',
            'telephone': 'Telefone',
            'marital_status': 'Estado Civil',
            'education': 'Escolaridade',
            'race': 'Raça',
            'religion': 'Religião',
            'social_benefits': 'Beneficiária de Programas Sociais',
            'occupation': 'Ocupação/Profissão',
            'is_working': 'Está Trabalhando?',
            
            'has_proven_income': 'Possui Renda Comprovada',
            'salary_range': 'Faixa Salarial',
            'others_contribute': 'Outras Pessoas Contribuem com a Renda da Família',
            'who_contributes': 'Quem Contribui',
            'domicile_type': 'Informações sobre o Domicílio',
            'num_residents': 'Quantidade de Pessoas no Domicílio',
            'has_elderly': 'Idoso',
            'has_adolescent': 'Adolescente',
            'has_child': 'Criança',
            'has_pregnant': 'Gestante',
            'file_info': 'Arquivo',
        }
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'estado_civil': forms.RadioSelect,
            'escolaridade': forms.RadioSelect,
            'raca': forms.RadioSelect,
            'religiao': forms.RadioSelect,
            # Adicione widgets para outros campos conforme necessidade
        }

    def clean_responsible_name(self):
        name = self.cleaned_data.get("responsible_name")
        if not name or not name.strip():
            raise forms.ValidationError("Preencha o nome do responsável.")
        return name

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            validate_cpf(cpf)
        return cpf

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


def calcular_faixa_etaria(idade):
    if 6 <= idade <= 7:
        return '06 a 07 anos'
    if 8 <= idade <= 9:
        return '08 a 09 anos'
    if 10 <= idade <= 12:
        return '10 a 12 anos'
    if 13 <= idade <= 17:
        return '13 a 17 anos'
    return None

def calcular_idade(birth_date):
    from datetime import date
    hoje = date.today()
    idade = hoje.year - birth_date.year - ((hoje.month, hoje.day) < (birth_date.month, birth_date.day))
    return idade

class AdultForm(forms.ModelForm):
    class Meta:
        model = Adult
        fields = ['family', 'name', 'parentesco', 'birth_date', 'school_level', 'ocupacao', 'renda', 'status', 'phone']
        labels = {
            'family': 'Família',
            'name': 'Nome',
            'parentesco': 'Parentesco',
            'birth_date': 'Data de Nascimento',
            'school_level': 'Nível de Escolaridade',
            'ocupacao': 'Ocupação/Profissão',
            'renda': 'Renda',
            'status': 'Situação',
            'phone': 'Telefone',
        }
        widgets = {
            'family': forms.Select(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }

class AlunoForm(forms.ModelForm):
    idade = forms.CharField(label='Idade', required=False, widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    class Meta:
        model = Aluno
        exclude = ('activities',)  # Exclua 'activities' e 'family' se definido via inlineformset
        
        labels = {
            'family': 'Família',
            'name': 'Nome do Aluno',
            'parentesco': 'Parentesco',
            'birth_date': 'Data de Nascimento',
            'idade': 'Idade',
            'school': 'Escola',
            'serie': 'Série',
            'turno': 'Turno',
            'health_problem': 'Problema de Saúde',
            'status_lsd': 'Situação Atual no Lar',
            # adicione outros labels se necessário
        }
        widgets = {
            'family': forms.Select(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            # Se não usa seleção automática de família nesse form, pode remover 'family' aqui
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
            'name',
            'parentesco',
            'school',
            'serie',
            'turno',
            'health_problem',
            'status_lsd',
            'faixa_etaria',
            # outros campos, se houver
        )

    def clean(self):
        cleaned_data = super().clean()
        birth_date = cleaned_data.get("birth_date")
        if birth_date:
            idade = calcular_idade(birth_date)  # crie/calque a função calcular_idade em Python
            cleaned_data["faixa_etaria"] = calcular_faixa_etaria(idade)
        return cleaned_data



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
    fields=['name', 'parentesco', 'birth_date', 'school_level', 'ocupacao', 'renda', 'status', 'phone'],
    extra=0, can_delete=True
)
        
class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ['professor', 'faixa_etaria', 'sala', 'turno']
        labels = {'professor': 'Nome da Professora', 'faixa_etaria': 'Faixa Etária', 'sala': 'Sala', 'turno': 'Turno'}


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ['professor','descricao', 'tipo', 'dia_semana', 'turno']
        labels = {'professor': 'Nome da Professor(a)','descricao': 'Nome da Atividade', 'tipo': 'Tipo', 'dia_semana': 'Dias da Semana', 'turno': 'Turno'}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['professor'].queryset = User.objects.filter(perfilprofessor__tipo='atividade')

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



