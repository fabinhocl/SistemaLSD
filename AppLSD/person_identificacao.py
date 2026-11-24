"""Preparacao de identificacao para futura integracao das edicoes.

Apenas consultas e instancias em memoria. Nao salva origem ou Person.
Nao e servico completo de edicao, autorizacao, auditoria ou concorrencia.
"""
import re
from django.core.exceptions import ValidationError
from AppLSD.models import Family, Adult, Aluno, Person


def _cpf(valor):
    return re.sub(r'[^0-9]', '', str(valor or ''))


def preparar_identificacao_person(origem):
    """Recebe origem existente, possivelmente editada em memoria.

    Retorna Person nao salva e lista de campos de identificacao alterados.
    CPF divergente, troca de vinculo/familia e compartilhamento entre
    cadastros exigem fluxo proprio; nao sao resolvidos automaticamente.
    O chamador futuro devera autorizar, bloquear, revalidar, salvar e auditar
    ambas as pontas na mesma transacao. Nao chamar save neste modulo.
    """
    if type(origem) not in (Family, Adult, Aluno):
        raise ValidationError('Tipo de cadastro nao suportado.')
    if origem.pk is None or origem._state.adding:
        raise ValidationError('Este fluxo aceita somente cadastros existentes.')

    modelo = type(origem)
    campo_vinculo = 'responsible_id' if modelo is Family else 'person_id'
    persistida = modelo.objects.get(pk=origem.pk)
    person_id = getattr(persistida, campo_vinculo)
    if person_id is None:
        raise ValidationError('Cadastro sem Person: requer regularizacao especifica.')
    if getattr(origem, campo_vinculo) != person_id:
        raise ValidationError('Troca de identidade nao e uma edicao comum.')
    if modelo is not Family and origem.family_id != persistida.family_id:
        raise ValidationError('Mudanca de familia exige fluxo proprio.')

    pessoa = Person.objects.get(pk=person_id)
    familia_origem = origem.pk if modelo is Family else origem.family_id
    if pessoa.family_id != familia_origem:
        raise ValidationError('Referencia familiar divergente: revisar antes de editar.')

    referencias = (
        Family.objects.filter(responsible_id=person_id).count()
        + Adult.objects.filter(person_id=person_id).count()
        + Aluno.objects.filter(person_id=person_id).count()
    )
    if referencias != 1:
        raise ValidationError('Person compartilhada entre cadastros: exige edicao coordenada.')

    cpf_origem = _cpf(origem.cpf)
    # CPF vazio e aceito apenas para Adult quando ambas as pontas ja estao vazias.
    if (not cpf_origem and modelo is not Adult) or cpf_origem != _cpf(pessoa.cpf):
        raise ValidationError({'cpf': 'Inclusao, remocao ou correcao de CPF exige fluxo proprio.'})
    # Impede aproveitar uma divergencia anterior para trocar CPF silenciosamente.
    if cpf_origem != _cpf(persistida.cpf):
        raise ValidationError({'cpf': 'Alteracao de CPF nao permitida na edicao comum.'})

    for m in (Family, Adult, Aluno):
        candidatos = m.objects.filter(cpf__isnull=False).values_list('pk', 'cpf')
        for pk, valor in candidatos.iterator():
            if m is modelo and pk == origem.pk:
                continue
            if cpf_origem and _cpf(valor) == cpf_origem:
                raise ValidationError({'cpf': 'CPF presente em outra origem: revisar identidade.'})
    for pk, valor in Person.objects.exclude(pk=person_id).values_list('pk', 'cpf').iterator():
        if cpf_origem and _cpf(valor) == cpf_origem:
            raise ValidationError({'cpf': 'CPF presente em outro Person: revisar identidade.'})

    if modelo is Adult and not cpf_origem:
        from AppLSD.adulto_person_identidade import validar_identidade_adulto
        validar_identidade_adulto(
            origem, excluir_origem_id=origem.pk, excluir_person_id=person_id)

    genero = {'Feminino': 'F', 'Masculino': 'M'}.get(origem.sex)
    if genero is None:
        raise ValidationError({'sex': 'Sexo sem mapeamento para Person.gender.'})
    nome = origem.responsible_name if modelo is Family else origem.name
    if not str(nome or '').strip():
        campo_nome = 'responsible_name' if modelo is Family else 'name'
        raise ValidationError({campo_nome: 'Informe o nome.'})

    novos = {'full_name': nome, 'birth_date': origem.birth_date, 'gender': genero}
    alterados = [campo for campo, valor in novos.items() if getattr(pessoa, campo) != valor]
    for campo, valor in novos.items():
        setattr(pessoa, campo, valor)
    pessoa.full_clean()
    return pessoa, alterados
