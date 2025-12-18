# events/forms.py

from datetime import date
from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from .models import Event, EventParticipant
from AppLSD.models import Person, Adult, Family
from AppLSD.validators import validate_cpf

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'event_type',
            'title',
            'setor_responsible',
            'description',
            'partner_organization',
            'date',
            'start_time',
            'end_time',
            'location',
            'notes',
            'area_atuacao',
        ]
        labels = {
            'event_type': 'Tipo de Ação / Atividade',
            'title': 'Identificação da Ação / Atividade',
            'description': 'Descrição da Ação / Atividade',
            'partner_organization': 'Parceiro(a) na Ação / Atividade',
            'date': 'Data da Ação / Atividade',
            'start_time': 'Horário de Início',
            'end_time': 'Horário de Término',
            'location': 'Local da Ação / Atividade',
            'notes': 'Observações',
            'setor_responsible': 'Setor Responsável',
            'area_atuacao': 'Área de Atuação',
        }

        widgets = {
            'date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d',
            ),
            'start_time': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-control'}
            ),
            'end_time': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-control'}
            ),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # garante que o campo aceite o formato do widget
        self.fields['date'].input_formats = ['%Y-%m-%d']

class PersonQuickForm(forms.ModelForm):
    """Cadastro rápido de pessoa na tela de evento."""
    cpf = forms.CharField(
        label='CPF',
        required=False,
        validators=[validate_cpf],
    )
    class Meta:
        model = Person
        fields = [
                'full_name',
                'rg',
                'cpf',
                'birth_date',
                'gender',
                'phone',
                'address',
                'neighborhood',
                'cep',
                'profission',
            ]
        labels = {
            'full_name': 'Nome Completo',
            'rg': 'RG',
            'cpf': 'CPF',
            'birth_date': 'Data de Nascimento',
            'gender': 'Sexo',
            'phone': 'Telefone',
            'address': 'Endereço',
            'neighborhood': 'Bairro',
            'cep': 'CEP',
            'profission': 'Profissão',
        }

    widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'rg': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control'}),
        }
# 1) Validação de CPF (simples, sem dígitos verificadores completos)
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf', '').replace('.', '').replace('-', '')
        if cpf and (not cpf.isdigit() or len(cpf) != 11):
            raise forms.ValidationError('CPF deve conter 11 dígitos numéricos.')
        return cpf


class EventParticipantForm(forms.ModelForm):
    person = forms.ModelChoiceField(
        queryset=Person.objects.all().order_by('full_name'),
        label='Pessoa',
        widget=forms.Select(attrs={'class': 'form-select d-none'}),
        required=False,
    )
    class Meta:
        model = EventParticipant
        fields = ['person', 'role', 'attendance_status', 'group_label']
        labels = {
            'role': '',
            'attendance_status': '',
            'group_label': '',
            
        }

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)  # vamos passar o evento pela view
        super().__init__(*args, **kwargs)

        qs = Person.objects.all()

        if event:
            today = date.today()
            if event.event_type == 'IDOSOS':
                # 60+ anos
                limite = today.replace(year=today.year - 60)
                qs = qs.filter(birth_date__lte=limite)
            elif event.event_type == 'GESTANTES':
                # exemplo: filtrar só mulheres em idade fértil (ajuste depois)
                qs = qs.filter(gender='F')
            # outros tipos podem ter outras regras aqui

        self.fields['person'].queryset = qs.order_by('full_name')

   

def make_event_participant_formset(event=None, *args, **kwargs):
    FormSet = inlineformset_factory(
        Event,
        EventParticipant,
        form=EventParticipantForm,
        extra=1,
        can_delete=True,
    )

    class EventParticipantFormSet(FormSet):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for form in self.forms:
                form.__init__(event=event, *form.args, **form.kwargs)

    return EventParticipantFormSet(*args, **kwargs)

EventParticipantFormSet = inlineformset_factory(
    Event,
    EventParticipant,
    form=EventParticipantForm,
    extra=1,
    can_delete=True,
)
