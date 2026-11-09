from django.test import TestCase
from django.contrib.auth.models import User
from .models import Setor, Categoria, TipoDocumento, Documento


class SetorModelTest(TestCase):
    def test_criar_setor(self):
        setor = Setor.objects.create(nome='Patrimnio', descricao='Setor de patrimnio')
        self.assertEqual(str(setor), 'Patrimnio')
        self.assertTrue(setor.ativo)


class CategoriaModelTest(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome='Financeiro')

    def test_criar_categoria(self):
        categoria = Categoria.objects.create(
            setor=self.setor,
            nome='Documentos Contbeis'
        )
        self.assertEqual(categoria.nivel, 1)
        self.assertIn('Financeiro', str(categoria))

    def test_categoria_com_pai(self):
        pai = Categoria.objects.create(setor=self.setor, nome='Nvel 1')
        filho = Categoria.objects.create(
            setor=self.setor,
            nome='Nvel 2',
            pai=pai
        )
        self.assertEqual(filho.nivel, 2)


class DocumentoModelTest(TestCase):
    def setUp(self):
        self.setor = Setor.objects.create(nome='Secretaria')
        self.categoria = Categoria.objects.create(setor=self.setor, nome='Atas')
        self.tipo = TipoDocumento.objects.create(categoria=self.categoria, nome='Ata de Reunio')
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_criar_documento(self):
        doc = Documento.objects.create(
            setor=self.setor,
            categoria=self.categoria,
            tipo_documento=self.tipo,
            titulo='Teste Documento',
            codigo_registro='TEST-001',
            criado_por=self.user
        )
        self.assertEqual(doc.status, 'rascunho')
        self.assertEqual(doc.nivel_sigilo, 'publico')
        self.assertEqual(str(doc), 'TEST-001 - Teste Documento')
