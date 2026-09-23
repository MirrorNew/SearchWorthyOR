"""Immutable versions, checked quotations, and observed-link read admission."""
from dataclasses import dataclass, asdict
import re
import unicodedata
from urllib.parse import urljoin, urlsplit
from searchworthy.contracts import identity, normalized


def _layout_text(text, *, ignore_case=False):
    """Normalize typography, not words, signs, numbers or case-sensitive IDs."""
    table = str.maketrans({'“': '"', '”': '"', '„': '"', '‘': "'", '’': "'", '‐': '-', '‑': '-'})
    parts, positions = [], []
    for match in re.finditer(r'[^\u0300-\u036f][\u0300-\u036f]*|[\u0300-\u036f]+', text):
        token = unicodedata.normalize('NFC', match.group()).translate(table)
        token = ''.join(chr(ord(c) - 0xfee0) if 0xff01 <= ord(c) <= 0xff5e else c for c in token)
        if ignore_case:
            token = token.casefold()
        parts.append(token)
        positions.extend([match.span()] * len(token))
    return ''.join(parts), positions


def _text_span(text, query, *, ignore_case=False):
    """Match benign layout differences and return coordinates in original text."""
    if not isinstance(query, str) or not query.strip():
        return None
    text, positions = _layout_text(text, ignore_case=ignore_case)
    query, _ = _layout_text(query, ignore_case=ignore_case)
    match = re.search(r'\s+'.join(re.escape(token) for token in query.split()), text)
    if not match:
        return None
    start, end = match.span()
    return positions[start][0], positions[end - 1][1]


@dataclass(frozen=True)
class Document:
    id: str
    url: str
    text: str
    title: str
    source_kind: str
    version: str
    links: tuple = ()


class EvidenceStore:
    def __init__(self, public_text):
        self.documents = {}
        self.search_results = {}
        self.fragments = {}
        self.views = []
        self.preferred_ranges = {}
        self.requirement_visible = {}
        self.temporal_evidence = {}
        self.add('public:task', public_text, 'Public task', 'LOCAL', alias='task')

    def add(self, url, text, title='', source_kind='EXTERNAL', links=(), alias=None):
        if not isinstance(text, str) or not text.strip():
            raise ValueError('empty evidence document')
        version = identity('version', text)
        doc_id = alias or identity('doc', [url, version])
        value = Document(doc_id, url, text, title, source_kind, version, tuple(links))
        if doc_id in self.documents and self.documents[doc_id] != value:
            raise ValueError('cannot overwrite immutable document version')
        self.documents[doc_id] = value
        return doc_id

    def fragment(self, document_id, start, end):
        doc = self.documents[document_id]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(doc.text):
            raise ValueError('fragment offsets must index the original stored string')
        quote = doc.text[start:end]
        fid = identity('fragment', [doc.id, doc.version, start, end])
        value = {'id': fid, 'document': doc.id, 'document_version': doc.version,
                 'start': start, 'end': end, 'quote': quote, 'text_hash': identity('text', quote)}
        self.fragments[fid] = value
        return value

    def resolve_fragments(self, value):
        if isinstance(value, list):
            return [self.resolve_fragments(x) for x in value]
        if not isinstance(value, dict):
            return value
        if 'fragment_id' in value:
            fid = value['fragment_id']
            if fid not in self.fragments:
                raise ValueError('fragment was not exposed: ' + str(fid))
            f = self.fragments[fid]
            doc = self.documents[f['document']]
            if doc.version != f['document_version'] or identity('text', doc.text[f['start']:f['end']]) != f['text_hash']:
                raise ValueError('stale/corrupt fragment')
            if 'quote' in value and (not isinstance(value['quote'], str)
                    or ' '.join(_layout_text(value['quote'])[0].split()) != ' '.join(_layout_text(f['quote'])[0].split())):
                raise ValueError('fragment quote cannot be rewritten')
            return {'document': f['document'], 'quote': f['quote']}
        return {k: self.resolve_fragments(v) for k, v in value.items()}

    def localize(self, requirement_ids, document_id, query='', start=None, end=None):
        doc = self.documents[document_id]
        if start is None:
            match = _text_span(doc.text, query, ignore_case=True)
            if match is None:
                raise ValueError('localization text not found in stored document')
            start, end = match
        # Retain context for negation, headings and exceptions. Expansion changes
        # a view, never the immutable source or source-character coordinates.
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(doc.text):
            raise ValueError('invalid localization range')
        span = [max(0, start - 1200), min(len(doc.text), end + 2400)]
        for rid in requirement_ids:
            ranges = self.preferred_ranges.setdefault(rid, {}).setdefault(document_id, [])
            if span not in ranges:
                ranges.append(span)
        return self.fragment(document_id, *span)

    def focused_view(self, requirement_ids, queries=(), citations=(), call_id=None):
        focused_citations = list(citations)
        for rid in requirement_ids:
            for did, spans in self.preferred_ranges.get(rid, {}).items():
                focused_citations.extend({'document': did, 'quote': self.documents[did].text[a:b]} for a, b in spans)
        documents = self.context(queries, focused_citations)
        fragment_ids = []
        for doc in documents:
            doc['fragments'] = [self.fragment(doc['id'], a, b) for a, b in doc.get('selected_ranges', []) if a < b]
            fragment_ids.extend(f['id'] for f in doc['fragments'])
        material = sorted({(self.fragments[f]['document_version'], self.fragments[f]['text_hash']) for f in fragment_ids})
        view = {'view_id': identity('view', [sorted(requirement_ids), material]),
                'requirement_ids': list(requirement_ids), 'fragment_ids': fragment_ids,
                'call_id': call_id, 'truncated': any(not d['view_complete'] for d in documents),
                'material_signature': identity('visible-material', material)}
        self.views.append(view)
        for rid in requirement_ids:
            self.requirement_visible[rid] = view['material_signature']
        return documents, view

    def range_signature(self, requirement_id):
        material = []
        for did, ranges in self.preferred_ranges.get(requirement_id, {}).items():
            d = self.documents[did]
            material.extend((d.url, d.version, d.text[a:b]) for a, b in ranges)
        return identity('requirement-material', sorted(set(material)))

    def add_temporal_evidence(self, document_id, publication_date=None, effective_interval=None,
                              task_date=None, citations=()):
        # Unknown temporal facts remain None; fetch time and text hashes provide
        # no evidence of effective dates.
        if any(x is not None for x in (publication_date, effective_interval, task_date)):
            self.check(list(citations))
        self.temporal_evidence[document_id] = {'publication_date': publication_date,
            'effective_interval': effective_interval, 'task_date': task_date, 'citations': list(citations)}

    def check(self, citations, *, local_only=False):
        if not isinstance(citations, list) or not citations:
            raise ValueError('missing source citations')
        for citation in citations:
            doc = self.documents.get(citation.get('document'))
            if doc is None:
                raise ValueError('citation document not observed: ' + str(citation.get('document')))
            raw_quote = citation.get('quote', '')
            if not isinstance(raw_quote, str):
                raise ValueError('citation quote must be text')
            span = _text_span(doc.text, raw_quote)
            if span is None:
                raise ValueError('quote absent from observed document ' + doc.id + ': ' + repr(citation.get('quote', '')[:280]))
            if local_only and doc.source_kind != 'LOCAL':
                raise ValueError('local correction requires public task source')
            original = doc.text[span[0]:span[1]]
            if original != raw_quote:
                citation['submitted_quote'] = raw_quote
                citation['quote'] = original
                citation['match_method'] = 'layout_normalized'
                citation['source_span'] = list(span)

    def observed_url(self, url):
        return url in self.search_results or any(url == d.url or url in d.links or url in d.text for d in self.documents.values())

    def export(self):
        return [asdict(d) for d in self.documents.values()]

    def context(self, queries=(), citations=(), max_chars=80000, per_document=16000):
        """Select observed passages, retaining full originals in the evidence store.

        Quote-centered review windows override lexical search windows. Truncation
        is explicit and never turns the selection into a completeness claim.
        """
        terms = set()
        for query in queries:
            terms.update(re.findall(r'[A-Za-z][A-Za-z0-9_-]{2,}|[\u3400-\u9fff]{2,6}', query.lower()))
        quote_map = {}
        for c in citations:
            quote_map.setdefault(c['document'], []).append(c['quote'])
        result, remaining = [], max_chars
        # Public input and specifically cited sources are always placed first.
        ordered = sorted(self.documents.values(), key=lambda d: (d.id != 'task', d.id not in quote_map, d.id))
        for doc in ordered:
            cap = min(per_document, remaining)
            if doc.id == 'task':
                cap = max(cap, len(doc.text))
            if cap <= 0:
                result.append({**asdict(doc), 'text': '', 'view_complete': False, 'full_text_chars': len(doc.text),
                               'view_note': 'document observed and stored; passage budget exhausted'})
                continue
            if len(doc.text) <= cap:
                text, ranges = doc.text, [[0, len(doc.text)]]
            else:
                centers = [(0, 1500)]
                for quote in quote_map.get(doc.id, []):
                    match = _text_span(doc.text, quote)
                    if match:
                        pos, end = match
                        centers.append((max(0, pos - 1800), min(len(doc.text), end + 2600)))
                blocks = [(start, doc.text[start:start + 3500]) for start in range(0, len(doc.text), 3000)]
                blocks.sort(key=lambda item: -sum(item[1].lower().count(term) for term in terms))
                centers.extend((start, min(len(doc.text), start + 3500)) for start, _ in blocks[:5])
                ranges = []
                used = 0
                for start, end in centers:
                    if any(start >= a and end <= b for a, b in ranges):
                        continue
                    if used >= cap:
                        break
                    end = min(end, start + cap - used)
                    ranges.append([start, end])
                    used += end - start
                ranges.sort()
                text = '\n[... observed passage boundary ...]\n'.join(doc.text[a:b] for a, b in ranges)
            result.append({**asdict(doc), 'text': text, 'view_complete': len(doc.text) <= cap,
                           'full_text_chars': len(doc.text), 'selected_ranges': ranges})
            remaining -= len(text)
        return result
