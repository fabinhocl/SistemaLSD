"""Regularizacao conservadora de Person, versao 2; padrao somente planejamento."""
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone
from AppLSD.models import Family, Aluno, Adult, Person

MODELOS = {m.__name__: m for m in (Family, Aluno, Adult)}
VERSAO = 2


def json_canonico(valor):
    return json.dumps(valor, cls=DjangoJSONEncoder, sort_keys=True,
                      ensure_ascii=False, separators=(',', ':'))


def digest(valor):
    return hashlib.sha256(json_canonico(valor).encode('utf-8')).hexdigest()


def estado(obj):
    return {f.attname: getattr(obj, f.attname) for f in obj._meta.concrete_fields}


def modelos_monitorados():
    por_tabela = {}
    existentes = set(connection.introspection.table_names())
    for m in apps.get_models(include_auto_created=True):
        if m._meta.managed and not m._meta.proxy and m._meta.db_table in existentes:
            por_tabela.setdefault(m._meta.db_table, m)
    return [por_tabela[t] for t in sorted(por_tabela)]


def snapshot():
    resultado = {}
    for m in modelos_monitorados():
        campos = [f.attname for f in m._meta.concrete_fields]
        pk = m._meta.pk.attname
        resultado[m._meta.db_table] = {
            str(r[pk]): digest(r)
            for r in m._base_manager.order_by(pk).values(*campos).iterator()
        }
    return resultado


def assinatura_codigo():
    raiz = Path(settings.BASE_DIR).resolve()
    arquivos = {Path(__file__).resolve()}
    for config in apps.get_app_configs():
        pasta = Path(config.path).resolve()
        try:
            pasta.relative_to(raiz)
        except ValueError:
            continue
        if any(p in ('venv', '.venv', 'site-packages') for p in pasta.parts):
            continue
        arquivos.update(p.resolve() for p in pasta.rglob('*.py')
                        if '__pycache__' not in p.parts)
    return digest([(str(p.relative_to(raiz)) if p.is_relative_to(raiz) else p.name,
                    hashlib.sha256(p.read_bytes()).hexdigest())
                   for p in sorted(arquivos, key=str)])


def montar_person(obj):
    familia = isinstance(obj, Family)
    return Person(
        family_id=obj.pk if familia else obj.family_id,
        full_name=obj.responsible_name if familia else obj.name,
        birth_date=obj.birth_date,
        gender={'Feminino': 'F', 'Masculino': 'M'}.get(obj.sex, ''),
        cpf=re.sub(r'[^0-9]', '', str(obj.cpf or '')) or None,
        rg=getattr(obj, 'rg', None),
        phone=getattr(obj, 'telephone', None)
            if isinstance(obj, (Family, Adult)) else None,
        address=getattr(obj, 'address', None) if familia else None,
        neighborhood=getattr(obj, 'neighborhood', None) if familia else None,
        cep=getattr(obj, 'cep', None) if familia else None,
        reference_point=getattr(obj, 'reference_point', None) if familia else None,
    )


def erros_validacao(obj):
    try:
        obj.full_clean()
        return {}
    except ValidationError as exc:
        if not hasattr(exc, 'error_dict'):
            return {'__all__': ['validacao']}
        return {campo: [str(e.code or 'validacao') for e in erros]
                for campo, erros in exc.error_dict.items()}


def linhas_planejador():
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / 'auditoria.csv'
        call_command('planejar_vinculos_person', csv_path=str(arquivo),
                     stdout=io.StringIO(), stderr=io.StringIO())
        with arquivo.open(encoding='utf-8-sig', newline='') as entrada:
            linhas = list(csv.DictReader(entrada, delimiter=';'))
    return sorted(linhas, key=lambda r: (r['origem'], int(r['id'])))


def novo_plano():
    antes = snapshot()
    assinatura = assinatura_codigo()
    selecionados, bloqueados = [], []
    linhas = linhas_planejador()
    for linha in linhas:
        tipo, pk = linha['origem'], int(linha['id'])
        item = {'origem': tipo, 'id': pk}
        if linha['classificacao'] != 'CANDIDATO_CRIACAO':
            bloqueados.append({**item, 'etapa': 'identidade',
                               'classificacao': linha['classificacao']})
            continue
        m = MODELOS[tipo]
        obj = m.objects.get(pk=pk)
        campo = 'responsible' if m is Family else 'person'
        if getattr(obj, campo + '_id') is not None:
            raise CommandError('Vinculo mudou durante a leitura.')
        # Validacao de origem separada: clean pode modificar a instancia.
        erros_p = erros_validacao(montar_person(obj))
        erros_o = erros_validacao(m.objects.get(pk=pk))
        if erros_p or erros_o:
            bloqueados.append({**item, 'etapa': 'validacao',
                               'Person': erros_p, 'Origem': erros_o})
        else:
            selecionados.append(item)
    if snapshot() != antes or assinatura_codigo() != assinatura:
        raise CommandError('Base ou codigo mudou durante a leitura. Repita sem outros acessos.')
    plano = {
        'versao': VERSAO,
        'gerado_em': timezone.now().isoformat(),
        'assinatura_base': digest(antes),
        'assinatura_codigo': assinatura,
        'tabelas_monitoradas': sorted(antes),
        'selecionados': selecionados,
        'bloqueados': bloqueados,
        'resumo': {
            'origens': len(linhas), 'selecionados': len(selecionados),
            'bloqueados_identidade': sum(x['etapa'] == 'identidade' for x in bloqueados),
            'bloqueados_validacao': sum(x['etapa'] == 'validacao' for x in bloqueados),
        },
    }
    plano['integridade'] = digest(plano)
    return plano


def validar_plano(plano):
    conteudo = dict(plano)
    informado = conteudo.pop('integridade', None)
    if plano.get('versao') != VERSAO or informado != digest(conteudo):
        raise CommandError('Plano invalido, alterado ou de outra versao.')
    if plano.get('assinatura_codigo') != assinatura_codigo():
        raise CommandError('Codigo mudou: gere outro plano e confira.')


def bloquear_tabelas():
    if connection.vendor != 'postgresql':
        raise CommandError('Aplicacao v2 exige PostgreSQL. Planejamento pode ser consultado separadamente.')
    tabelas = ', '.join(connection.ops.quote_name(m._meta.db_table)
                        for m in modelos_monitorados())
    with connection.cursor() as cursor:
        cursor.execute('SET LOCAL lock_timeout = \'10s\'')
        cursor.execute('LOCK TABLE ' + tabelas + ' IN SHARE ROW EXCLUSIVE MODE')


def aplicar_plano(plano):
    """Tudo ou nada no banco padrao. Nao realiza operacoes familiares/atendimento."""
    validar_plano(plano)
    vinculos = []
    with transaction.atomic():
        bloquear_tabelas()
        antes = snapshot()
        if digest(antes) != plano['assinatura_base']:
            raise CommandError('Base diferente do plano: nenhuma aplicacao permitida.')
        atual = novo_plano()
        if (atual['selecionados'] != plano['selecionados'] or
                atual['bloqueados'] != plano['bloqueados']):
            raise CommandError('Classificacao mudou: gere outro plano.')
        esperado = {t: dict(linhas) for t, linhas in antes.items()}
        tabela_person = Person._meta.db_table
        for item in plano['selecionados']:
            m = MODELOS[item['origem']]
            obj = m.objects.get(pk=item['id'])
            campo = 'responsible' if m is Family else 'person'
            if getattr(obj, campo + '_id') is not None:
                raise CommandError('Vinculo preenchido: lote cancelado.')
            origem_esperada = estado(obj)
            pessoa = montar_person(obj)
            pessoa.full_clean()
            dados_person = estado(pessoa)
            pessoa.save()
            dados_person[Person._meta.pk.attname] = pessoa.pk
            if json_canonico(estado(Person.objects.get(pk=pessoa.pk))) != json_canonico(dados_person):
                raise CommandError('Person sofreu alteracao inesperada; lote cancelado.')
            # full_clean e save existentes continuam sendo executados.
            setattr(obj, campo, pessoa)
            obj.full_clean()
            obj.save(update_fields=[campo])
            origem_esperada[campo + '_id'] = pessoa.pk
            esperado[m._meta.db_table][str(obj.pk)] = digest(origem_esperada)
            esperado[tabela_person][str(pessoa.pk)] = digest(dados_person)
            vinculos.append({**item, 'person_id': pessoa.pk})
        depois = snapshot()
        if depois != esperado:
            tabelas = sorted(t for t in set(depois) | set(esperado)
                             if depois.get(t) != esperado.get(t))
            raise CommandError('Alteracoes fora do escopo em: ' + ', '.join(tabelas))
        if assinatura_codigo() != plano['assinatura_codigo']:
            raise CommandError('Codigo mudou durante a aplicacao; lote cancelado.')
    return vinculos


def gravar_exclusivo(caminho, dados):
    fd = os.open(str(caminho), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.flush()
        os.fsync(arquivo.fileno())


class Command(BaseCommand):
    help = 'Regularizacao Person v2. Sem --aplicar apenas gera plano novo.'
    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument('--plano', required=True)
        parser.add_argument('--aplicar', action='store_true')
        parser.add_argument('--confirmar-base-parada', action='store_true')
        parser.add_argument('--confirmar-plano')
        parser.add_argument('--banco-esperado')

    def handle(self, *args, **options):
        caminho = Path(options['plano'])
        if not caminho.parent.is_dir():
            raise CommandError('Diretorio de destino inexistente.')
        if not options['aplicar']:
            if caminho.exists():
                raise CommandError('Arquivo ja existe; use outro nome.')
            plano = novo_plano()
            gravar_exclusivo(caminho, plano)
            for chave, valor in plano['resumo'].items():
                self.stdout.write(f'{chave}: {valor}')
            campos = Counter()
            for item in plano['bloqueados']:
                for etapa in ('Person', 'Origem'):
                    for campo in item.get(etapa, {}):
                        campos[f'{etapa}.{campo}'] += 1
            for chave, valor in sorted(campos.items()):
                self.stdout.write(f'{chave}: {valor}')
            self.stdout.write('Integridade: ' + plano['integridade'])
            self.stdout.write(self.style.SUCCESS('PLANO V2 GERADO. Nenhuma gravacao no banco.'))
            return
        if not options['confirmar_base_parada']:
            raise CommandError('Exige backup e base sem outros acessos; falta --confirmar-base-parada.')
        if str(connection.settings_dict['NAME']) != options['banco_esperado']:
            raise CommandError('O nome do banco nao coincide com --banco-esperado.')
        if not caminho.is_file():
            raise CommandError('Plano nao encontrado.')
        plano = json.loads(caminho.read_text(encoding='utf-8'))
        validar_plano(plano)
        if options['confirmar_plano'] != plano['integridade']:
            raise CommandError('Falta confirmar o hash exato do plano com --confirmar-plano.')
        recibo = caminho.with_name(caminho.name + '.resultado.json')
        if recibo.exists():
            raise CommandError('Ja existe tentativa deste plano. Confira o resultado; nao repita.')
        gravar_exclusivo(recibo, {'situacao': 'iniciado', 'plano': plano['integridade']})
        try:
            vinculos = aplicar_plano(plano)
        except Exception as exc:
            self.stderr.write('APLICACAO NAO CONFIRMADA. Nao repita automaticamente. '
                              'Confira recibo e banco. Tipo: ' + type(exc).__name__)
            if isinstance(exc, CommandError):
                raise
            raise CommandError('Falha na aplicacao; diagnostico necessario.') from exc
        resultado = {'situacao': 'aplicado', 'plano': plano['integridade'],
                     'concluido_em': timezone.now().isoformat(), 'vinculos': vinculos}
        try:
            with recibo.open('w', encoding='utf-8') as arquivo:
                json.dump(resultado, arquivo, ensure_ascii=False, indent=2)
                arquivo.flush()
                os.fsync(arquivo.fileno())
        except OSError:
            self.stderr.write('BANCO JA COMMITADO; falha ao finalizar recibo. NAO REPITA.')
            self.stdout.write(json_canonico(resultado))
            return
        self.stdout.write(self.style.SUCCESS(f'Aplicados: {len(vinculos)}. Recibo finalizado.'))
