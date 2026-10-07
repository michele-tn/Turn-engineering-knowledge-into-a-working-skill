"""Preserve an authorized PDF and extract page-indexed text; Python 3.10+, pypdf."""
import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader, __version__


def sha256(path):
    with path.open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    source = args.pdf.resolve(strict=True)
    reader = PdfReader(source)
    if reader.is_encrypted:
        parser.error('Use an authorized, accessible PDF export. Encrypted input is not processed.')
    slug = re.sub(r'[^a-z0-9]+', '-', source.stem.lower()).strip('-') or 'book'
    target = args.output_dir.resolve() / slug
    if target.exists():
        parser.error('Output book folder already exists; choose another output directory.')
    parts = ['# Extracted source text', '', 'Text extraction only. Review diagrams, tables, code and reading order against the PDF.', '']
    empty = []
    errors = []
    replacements = 0
    for number, page in enumerate(reader.pages, 1):
        try:
            content = page.extract_text(extraction_mode='layout') or ''
        except Exception as exc:
            content = ''
            errors.append({'pdf_page': number, 'error_type': type(exc).__name__})
        if not content.strip():
            empty.append(number)
        replacements += content.count('\ufffd')
        fence = '~' * max(3, 1 + max((len(run) for run in re.findall(r'~+', content)), default=0))
        parts.extend([f'## PDF page {number:04d}', '', f'[Original page](original.pdf#page={number})', '', fence + 'text', content.rstrip(), fence, ''])
    target.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, target / 'original.pdf')
    if sha256(source) != sha256(target / 'original.pdf'):
        raise RuntimeError('Original copy integrity check failed.')
    (target / 'book.md').write_text('\n'.join(parts), encoding='utf-8')
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'extractor': 'pypdf', 'extractor_version': __version__, 'pdf_pages': len(reader.pages), 'empty_text_pages': empty, 'extraction_errors': errors, 'replacement_characters': replacements, 'files': {name: sha256(target / name) for name in ['original.pdf', 'book.md']}, 'limitations': 'No OCR or diagram recovery. Empty text and zero replacement characters do not prove accuracy. Record bibliographic identity, rights and source URL separately.'}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (target / 'INDEX.md').write_text('# Source index\n\n[Extracted text](book.md) · [Original PDF](original.pdf) · [Manifest](manifest.json)\n\nAdd verified title, edition, author, source URL, access rights and relevant PDF page ranges before using this source.\n', encoding='utf-8')
    print(f'Created {slug}: {len(reader.pages)} PDF pages; {len(empty)} pages without extracted text; {len(errors)} extraction errors. Review required.')


if __name__ == '__main__':
    main()
