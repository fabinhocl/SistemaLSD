from django.core.management.base import BaseCommand
from AppLSD.models import Family
import re

class Command(BaseCommand):
    help = "Normaliza todos os CPFs das famílias para o formato xxx.xxx.xxx-xx"

    def handle(self, *args, **kwargs):
        families = Family.objects.all()
        total = families.count()
        updated = 0

        for family in families:
            if family.cpf:
                # tira tudo que não for número
                digits = re.sub(r'\D', '', str(family.cpf))

                if len(digits) == 11:
                    formatted = f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
                    if family.cpf != formatted:
                        family.cpf = formatted
                        family.save(update_fields=["cpf"])
                        updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Normalização concluída. {updated} de {total} registros atualizados."
        ))
