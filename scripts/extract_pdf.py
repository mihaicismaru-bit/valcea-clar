"""Read native-text and scanned municipal PDFs, returning text by page.

OCR uses Romanian Tesseract when present, or Windows' installed Romanian OCR.
No content is published or sent to a remote service by this command.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def extract(pdf: Path) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError('pypdf is required for PDF reading') from exc
    reader = PdfReader(str(pdf), strict=False)
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError('PDF is password protected')
    if len(reader.pages) > 200:
        raise ValueError('PDF exceeds the 200-page limit')
    pages = []
    with tempfile.TemporaryDirectory(prefix='valcea-pdf-') as tmp:
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or '').strip()
            method = 'pdf-text'
            if len(''.join(text.split())) < 40:
                method = 'ocr'
                renderer = shutil.which('pdftoppm')
                if not renderer:
                    raise RuntimeError(f'page {number}: scanned PDF requires pdftoppm')
                out = Path(tmp) / f'page-{number}'
                subprocess.run([renderer, '-f', str(number), '-l', str(number), '-r', '160',
                                '-png', '-singlefile', str(pdf), str(out)],
                               check=True, capture_output=True, timeout=60)
                image = str(out) + '.png'
                tesseract = shutil.which('tesseract')
                if tesseract:
                    command = [tesseract, image, 'stdout', '-l', 'ron']
                elif sys.platform == 'win32':
                    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', str(Path(__file__).with_name('ocr_page_windows.ps1')),
                               '-ImagePath', image]
                else:
                    raise RuntimeError(f'page {number}: Romanian OCR is not installed')
                result = subprocess.run(command, check=True, capture_output=True, timeout=90)
                text = result.stdout.decode('utf-8-sig', errors='strict').strip()
                if len(''.join(text.split())) < 40:
                    raise ValueError(f'page {number}: insufficient OCR text; review required')
            pages.append({'page': number, 'method': method, 'text': text,
                          'layout_warning': method == 'ocr'})
    if not pages:
        raise ValueError('empty PDF')
    return {'pages': pages}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.pdf.resolve():
        parser.error('output cannot overwrite the source PDF')
    result = extract(args.pdf.resolve())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Read {len(result['pages'])} pages; OCR: {sum(p['method']=='ocr' for p in result['pages'])}.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
