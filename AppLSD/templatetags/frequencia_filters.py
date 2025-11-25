from django import template

register = template.Library()

@register.filter
def filter_by_aluno(presencas_dict, aluno_id):
    """
    Retorna a presença de um aluno específico
    """
    return presencas_dict.get(aluno_id, {'presente': True, 'justificativa': ''})

@register.filter
def presentes_count(presencas):
    return sum(1 for p in presencas if p.presente)

@register.filter
def faltas_count(presencas):
    return sum(1 for p in presencas if not p.presente)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)