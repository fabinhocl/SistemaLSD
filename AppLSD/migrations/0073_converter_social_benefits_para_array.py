from django.db import migrations

def converter_para_array(apps, schema_editor):
    Family = apps.get_model('AppLSD', 'Family')

    for family in Family.objects.all():
        valor = family.social_benefits  # no servidor ainda pode ser string

        if not valor:
            family.social_benefits = []
        else:
            # se já for lista (dev), não mexe
            if isinstance(valor, list):
                continue

            # transforma string em lista com um item
            family.social_benefits = [valor.strip()]

        family.save(update_fields=['social_benefits'])


class Migration(migrations.Migration):

    dependencies = [
        ('AppLSD', '0072_aluno_rede_ensino'),  # mantém exatamente como está
    ]

    operations = [
        migrations.RunPython(converter_para_array, migrations.RunPython.noop),
    ]
