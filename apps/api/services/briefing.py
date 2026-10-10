"""Bounded Word document text extraction; no files, macros or links are executed."""
import base64
import binascii
import io
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib

from fastapi import HTTPException

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DOCUMENT_BASE64 = 4 * ((MAX_DOCUMENT_BYTES + 2) // 3)
BRIEFING_TEXT_LIMIT = 20_000
GUIDELINE_TEXT_LIMIT = 12_000


def validate_briefing_text(text: str, *, guidelines: bool = False) -> str:
    if re.search(r'[\x00-\x08\x0b\x0e-\x1f\x7f-\x9f]', text):
        raise HTTPException(400, 'This document contains unreadable characters. Save it as UTF-8 or paste readable text.')
    limit = GUIDELINE_TEXT_LIMIT if guidelines else BRIEFING_TEXT_LIMIT
    if len(text) > limit:
        label = 'Guidelines' if guidelines else 'Briefings'
        raise HTTPException(400, f'{label} can contain up to {limit:,} characters. Shorten the text and try again.')
    return text


WORD_NAMESPACE = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


class _WordXML(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError('Document types are not allowed')


def docx_text(encoded: str) -> str:
    try:
        if len(encoded) > MAX_DOCUMENT_BASE64:
            raise ValueError('too large')
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError('too large')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > MAX_DOCUMENT_BYTES:
                raise ValueError('expanded document too large')
            with archive.open(info) as source:
                xml = source.read(MAX_DOCUMENT_BYTES + 1)
        if len(xml) > MAX_DOCUMENT_BYTES:
            raise ValueError('unsupported XML')
        root = ET.fromstring(xml, parser=ET.XMLParser(target=_WordXML()))
        # OOXML Strict uses a different namespace but the same paragraph/run structure.
        namespace = root.tag.removesuffix('document').strip('{}')
        if namespace not in (WORD_NAMESPACE, 'http://purl.oclc.org/ooxml/wordprocessingml/main'):
            raise ValueError('not a Word document')
        tag = lambda name: f'{{{namespace}}}{name}'
        lines = []
        for paragraph in root.iter(tag('p')):
            parts = []
            for node in paragraph.iter():
                if node.tag == tag('t'):
                    parts.append(node.text or '')
                elif node.tag == tag('tab'):
                    parts.append('\t')
                elif node.tag in (tag('br'), tag('cr')):
                    parts.append('\n')
            if text := ''.join(parts).strip():
                lines.append(text)
        text = '\n'.join(lines).strip()
    except (ValueError, binascii.Error, zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError, ET.ParseError, zlib.error):
        raise HTTPException(400, 'Could not read this Word document. Save it as a .docx under 10 MB, then try again.') from None
    if not text:
        raise HTTPException(400, 'This Word document has no readable text. Add your briefing as text or upload a PDF.')
    return text
