from django import forms
from .models import Documento, TipoDocumento, MetadadoValor, Setor, Categoria, PermissaoSetor, CampoMetadado


class PermissaoSetorForm(forms.ModelForm):
    class Meta:
        model = PermissaoSetor
        fields = [
            'user',
            'setor',
            'pode_visualizar',
            'pode_editar',
            'pode_excluir',
        ]

class SetorForm(forms.ModelForm):
    class Meta:
        model = Setor
        fields = [
            'nome',
            'descricao',
            'ativo',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Patrimônio',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva a responsabilidade do setor',
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = [
            'setor',
            'nome',
            'descricao',
            'pai',
            'ativo',
        ]
        widgets = {
            'setor': forms.Select(attrs={'class': 'form-select'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
            'pai': forms.Select(attrs={'class': 'form-select'}),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['setor'].queryset = Setor.objects.filter(
            ativo=True
        ).order_by('nome')

        self.fields['pai'].queryset = Categoria.objects.filter(
            ativo=True
        ).order_by('setor__nome', 'nivel', 'nome')


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = [
            'setor',
            'categoria',
            'tipo_documento',
            'titulo',
            'codigo_registro',
            'descricao',
            'status',
            'nivel_sigilo',
            'data_documento',
            'data_validade',
            'localizacao_fisica',
            'tags',
        ]
        widgets = {
            'setor': forms.Select(attrs={
                'class': 'form-select',
            }),
            'categoria': forms.Select(attrs={
                'class': 'form-select',
            }),
            'tipo_documento': forms.Select(attrs={
                'class': 'form-select',
            }),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'codigo_registro': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'nivel_sigilo': forms.Select(attrs={
                'class': 'form-select',
            }),
            'data_documento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'data_validade': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'localizacao_fisica': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'tags': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 3,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['setor'].queryset = Setor.objects.filter(
            ativo=True
        ).order_by('nome')

        setor_id = None

        # Ao submeter o formulário, usa o setor enviado.
        if self.data.get('setor'):
            setor_id = self.data.get('setor')

        # Ao editar um documento, usa o setor já salvo.
        elif self.instance and self.instance.pk:
            setor_id = self.instance.setor_id

        if setor_id:
            self.fields['categoria'].queryset = Categoria.objects.filter(
                setor_id=setor_id,
                ativo=True,
            ).order_by(
                'nivel',
                'nome',
            )
        else:
            self.fields['categoria'].queryset = Categoria.objects.none()

        categoria_id = None

        if self.data.get('categoria'):
            categoria_id = self.data.get('categoria')

        elif self.instance and self.instance.pk:
            categoria_id = self.instance.categoria_id

        if categoria_id:
            self.fields['tipo_documento'].queryset = (
                TipoDocumento.objects.filter(
                    categoria_id=categoria_id,
                    ativo=True,
                ).order_by('nome')
            )
        else:
            self.fields['tipo_documento'].queryset = (
                TipoDocumento.objects.none()
            )

    def clean(self):
        cleaned_data = super().clean()

        setor = cleaned_data.get('setor')
        categoria = cleaned_data.get('categoria')
        tipo_documento = cleaned_data.get('tipo_documento')

        if setor and categoria:
            if categoria.setor_id != setor.id:
                self.add_error(
                    'categoria',
                    'A categoria selecionada não pertence ao setor informado.'
                )

        if categoria and tipo_documento:
            if tipo_documento.categoria_id != categoria.id:
                self.add_error(
                    'tipo_documento',
                    'O tipo de documento não pertence à categoria informada.'
                )

        return cleaned_data  

class DocumentoFilterForm(forms.Form):
    """Formulrio de filtros para lista de documentos"""
    setor = forms.ModelChoiceField(
        queryset=Setor.objects.filter(ativo=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.filter(ativo=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Documento.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    nivel_sigilo = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Documento.NIVEL_SIGILO_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por ttulo, cigo ou descrio...'
        })
    )


class TipoDocumentoForm(forms.ModelForm):
    class Meta:
        model = TipoDocumento
        fields = [
            'categoria',
            'nome',
            'descricao',
            'ativo',
        ]
        widgets = {
            'categoria': forms.Select(attrs={
                'class': 'form-select',
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Nota fiscal',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['categoria'].queryset = Categoria.objects.filter(
            ativo=True
        ).select_related(
            'setor'
        ).order_by(
            'setor__nome',
            'nome',
        )


class MetadadoValorForm(forms.ModelForm):
    """Formulrio dinmico para valores de metadado"""
    class Meta:
        model = MetadadoValor
        fields = ['valor_texto', 'valor_numero', 'valor_data', 'valor_booleano']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Esconder campos no baseados no tipo do campo
        if self.instance.campo:
            tipo = self.instance.campo.tipo
            for field_name in ['valor_texto', 'valor_numero', 'valor_data', 'valor_booleano']:
                self.fields[field_name].required = False
                self.fields[field_name].widget = forms.HiddenInput()

            # Mostrar apenas o campo relevante
            if tipo in ['texto', 'texto_longo', 'lista']:
                self.fields['valor_texto'].widget = forms.TextInput(attrs={'class': 'form-control'})
                self.fields['valor_texto'].required = self.instance.campo.obrigatorio
            elif tipo == 'numero':
                self.fields['valor_numero'].widget = forms.NumberInput(attrs={'class': 'form-control'})
                self.fields['valor_numero'].required = self.instance.campo.obrigatorio
            elif tipo == 'data':
                self.fields['valor_data'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
                self.fields['valor_data'].required = self.instance.campo.obrigatorio
            elif tipo == 'booleano':
                self.fields['valor_booleano'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
                self.fields['valor_booleano'].required = False


class CampoMetadadoForm(forms.ModelForm):
    class Meta:
        model = CampoMetadado
        fields = [
            'tipo_documento',
            'nome',
            'tipo',
            'obrigatorio',
            'opcoes_lista',
            'ordem',
            'ativo',
        ]
        widgets = {
            'tipo_documento': forms.Select(attrs={
                'class': 'form-select',
            }),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Número da nota',
            }),
            'tipo': forms.Select(attrs={
                'class': 'form-select',
            }),
            'obrigatorio': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'opcoes_lista': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': (
                    'Ex.: Ordinária,Extraordinária'
                ),
            }),
            'ordem': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'ativo': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['tipo_documento'].queryset = (
            TipoDocumento.objects.filter(
                ativo=True
            ).select_related(
                'categoria',
                'categoria__setor',
            ).order_by(
                'categoria__setor__nome',
                'categoria__nome',
                'nome',
            )
        )

