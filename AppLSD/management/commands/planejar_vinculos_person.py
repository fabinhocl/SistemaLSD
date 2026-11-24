"""Planejamento conservador de vinculos Person. Nao grava no banco."""
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from AppLSD.models import Family, Aluno, Adult, Person


EXCECOES = {
    ("Aluno", 59): "CPF do responsavel no aluno; aguarda correcao",
    ("Aluno", 45): "CPF do responsavel no aluno; aguarda correcao",
    ("Family", 96): "Mesma pessoa que Adult#98; decidir vinculo conjunto",
    ("Adult", 98): "Mesma pessoa que Family#96; nao excluir",
    ("Aluno", 213): "Duplicidade com Aluno#414; historico preservado",
    ("Aluno", 414): "Duplicidade com Aluno#213; historico preservado",
    ("Aluno", 295): "Duplicidade com Aluno#419; frequencias conflitantes",
    ("Aluno", 419): "Duplicidade com Aluno#295; frequencias conflitantes",
}


def nome(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())


def cpf(valor):
    return re.sub(r"[^0-9]", "", str(valor or ""))


def cpf_valido(valor):
    if len(valor) != 11 or len(set(valor)) == 1:
        return False
    return all(
        (sum(int(valor[i]) * (n + 1 - i) for i in range(n)) * 10 % 11) % 10 == int(valor[n])
        for n in (9, 10)
    )


class Command(BaseCommand):
    help = "Simula vinculos com Person; apenas consultas ao banco e CSV sem nomes/CPFs."
    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, dest="csv_path")

    def handle(self, *args, **options):
        caminho = Path(options["csv_path"])
        if caminho.exists():
            raise CommandError("O CSV ja existe. Use outro nome para preservar a auditoria anterior.")
        if not caminho.parent.is_dir():
            raise CommandError("O diretorio de destino do CSV nao existe.")

        pessoas = list(Person.objects.all())
        por_cpf_person = defaultdict(list)
        por_nome_data_person = defaultdict(list)
        for p in pessoas:
            if cpf(p.cpf):
                por_cpf_person[cpf(p.cpf)].append(p)
            if p.birth_date and nome(p.full_name):
                por_nome_data_person[(nome(p.full_name), p.birth_date)].append(p)

        registros = []
        for model, campo_nome, campo_vinculo in (
            (Family, "responsible_name", "responsible_id"),
            (Aluno, "name", "person_id"),
            (Adult, "name", "person_id"),
        ):
            for obj in model.objects.all().iterator():
                registros.append({
                    "origem": model.__name__, "id": obj.pk,
                    "familia": obj.pk if model is Family else obj.family_id,
                    "person": getattr(obj, campo_vinculo),
                    "nome": nome(getattr(obj, campo_nome)),
                    "data": obj.birth_date, "cpf": cpf(obj.cpf),
                    "sexo": {"Feminino": "F", "Masculino": "M"}.get(obj.sex),
                })

        por_cpf_origem = defaultdict(list)
        por_nome_data_origem = defaultdict(list)
        for r in registros:
            if r["cpf"]:
                por_cpf_origem[r["cpf"]].append(r)
            if r["nome"] and r["data"]:
                por_nome_data_origem[(r["nome"], r["data"])].append(r)

        saida = []
        for r in registros:
            motivos = []
            destino = ""
            chave = (r["origem"], r["id"])
            if chave in EXCECOES:
                motivos.append(EXCECOES[chave])
            if r["person"] is not None:
                motivos.append("Vinculo existente: preservar e revisar em auditoria especifica")
            if not r["nome"]:
                motivos.append("Nome ausente")
            if r["sexo"] is None:
                motivos.append("Sexo ausente ou sem mapeamento para Person.gender")
            if not r["cpf"]:
                motivos.append("CPF ausente: correspondencia exige revisao")
            elif not cpf_valido(r["cpf"]):
                motivos.append("CPF invalido")
            if r["cpf"] and len(por_cpf_origem[r["cpf"]]) > 1:
                motivos.append("CPF repetido entre registros de origem")
            nd = (r["nome"], r["data"])
            if r["data"] and len(por_nome_data_origem[nd]) > 1:
                motivos.append("Nome/nascimento repetidos entre origens")

            candidatos = por_cpf_person.get(r["cpf"], []) if r["cpf"] else []
            mesmo_nome_data = por_nome_data_person.get(nd, []) if r["data"] else []
            if len(candidatos) > 1:
                motivos.append("Mais de um Person com o CPF")
            elif len(candidatos) == 1:
                p = candidatos[0]
                destino = p.pk
                if (nome(p.full_name), p.birth_date, p.gender) != (r["nome"], r["data"], r["sexo"]):
                    motivos.append("Identificacao diverge do Person com mesmo CPF")
                if p.family_id not in (None, r["familia"]):
                    motivos.append("Familia diverge do Person")
                if p.family_id is None:
                    motivos.append("Person existente sem familia: revisar antes de associar")
                if any(q.pk != p.pk for q in mesmo_nome_data):
                    motivos.append("Outro Person com mesmo nome/nascimento")
            elif mesmo_nome_data:
                motivos.append("Person com mesmo nome/nascimento e CPF nao correspondente")

            acao = "PENDENTE" if motivos else (
                "CANDIDATO_VINCULO" if destino else "CANDIDATO_CRIACAO"
            )
            saida.append({
                "origem": r["origem"], "id": r["id"],
                "familia_id": r["familia"], "person_atual_id": r["person"] or "",
                "person_candidato_id": destino, "classificacao": acao,
                "nascimento_ausente": "sim" if r["data"] is None else "nao",
                "motivos": "; ".join(motivos),
            })

        with caminho.open("x", encoding="utf-8-sig", newline="") as arquivo:
            campos = ("origem", "id", "familia_id", "person_atual_id", "person_candidato_id", "classificacao", "nascimento_ausente", "motivos")
            writer = csv.DictWriter(arquivo, fieldnames=campos, delimiter=";")
            writer.writeheader()
            writer.writerows(saida)

        self.stdout.write(f"Registros de origem analisados: {len(registros)}")
        self.stdout.write(f"Person existentes: {len(pessoas)}")
        contagens = Counter(r["classificacao"] for r in saida)
        for classe in ("CANDIDATO_CRIACAO", "CANDIDATO_VINCULO", "PENDENTE"):
            self.stdout.write(f"{classe}: {contagens[classe]}")
        self.stdout.write(f"Origens sem nascimento: {sum(r['nascimento_ausente'] == 'sim' for r in saida)}")
        self.stdout.write(self.style.SUCCESS("SIMULACAO: nenhuma gravacao no banco. CSV criado."))
