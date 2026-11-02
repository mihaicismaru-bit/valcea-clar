import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import extract_pdf


class PDFExtractionTest(unittest.TestCase):
    def reader(self, pages):
        return SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda t=t: t) for t in pages])

    def test_text_pdf_works_without_ocr(self):
        reader = self.reader(['Programul instituției este descris în documentul oficial al primăriei.'])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **k: reader)}), mock.patch.object(extract_pdf.subprocess, 'run') as run:
            result = extract_pdf.extract(Path('document.pdf'))
        self.assertEqual(result['pages'][0]['method'], 'pdf-text')
        run.assert_not_called()

    def test_scanned_pdf_uses_romanian_ocr_and_preserves_page_number(self):
        reader = self.reader([''])
        result = SimpleNamespace(stdout='Rectificarea bugetului este propusă pentru administrația locală.'.encode('utf-8'))
        def locate(name):
            return {'pdftoppm': '/bin/pdftoppm', 'tesseract': '/bin/tesseract'}.get(name)
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **k: reader)}), mock.patch.object(extract_pdf.shutil, 'which', side_effect=locate), mock.patch.object(extract_pdf.subprocess, 'run', side_effect=[None, result]) as run:
            doc = extract_pdf.extract(Path('scanned.pdf'))
        self.assertEqual(doc['pages'][0]['page'], 1)
        self.assertEqual(doc['pages'][0]['method'], 'ocr')
        self.assertTrue(doc['pages'][0]['layout_warning'])
        self.assertIn('rectificarea', doc['pages'][0]['text'].lower())
        self.assertEqual(run.call_args.args[0][-2:], ['-l', 'ron'])

    def test_scanned_pdf_without_renderer_fails_instead_of_empty_text(self):
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **k: self.reader(['']))}), mock.patch.object(extract_pdf.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'pdftoppm'):
                extract_pdf.extract(Path('scanned.pdf'))


if __name__ == '__main__':
    unittest.main()
