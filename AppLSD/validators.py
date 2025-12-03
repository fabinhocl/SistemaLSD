# AppLSD/validators.py
from django.core.exceptions import ValidationError
from validate_docbr import CPF

cpf_validator = CPF()

def validate_cpf(value: str):
    # Remove pontos e traço, caso o usuário digite formatado
    doc = ''.join(filter(str.isdigit, value or ''))
    if not cpf_validator.validate(doc):
        raise ValidationError("CPF inválido.")
