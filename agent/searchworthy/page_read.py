"""Baseline-style HTTP/HTML/PDF reading, without a model or search call."""
import io
import ipaddress
import json
import math
import re
import socket
import threading
import time
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import certifi
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from searchworthy.runtime import BudgetExhausted, write

CHANNEL = 'BASELINE_HTTP'
RETRYABLE = {408, 429, 500, 502, 503, 504}


def official_source(url):
    """Recognize official domain boundaries for candidate routing, not factual validity."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower().rstrip('.')
    except (TypeError, ValueError):
        return False
    return (parsed.scheme in {'http', 'https'} and bool(host)
            and parsed.username is None and parsed.password is None
            and (host.endswith('.gov') or re.search(r'\.gov\.[a-z]{2}$', host) is not None
                 or any(host == domain or host.endswith('.' + domain)
                        for domain in ('gc.ca', 'europa.eu', 'gouv.fr'))))


def public_url(url):
    p = urlsplit(url)
    if (p.scheme != 'https' and not (p.scheme == 'http' and official_source(url))
            or not p.hostname or p.username is not None or p.password is not None):
        raise ValueError('PAGE_URL_BLOCKED: expected public HTTPS or official HTTP without credentials')
    try:
        literal = ipaddress.ip_address(p.hostname)
    except ValueError:
        literal = None
    addresses = {ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(
        p.hostname, p.port or (80 if p.scheme == 'http' else 443), type=socket.SOCK_STREAM)}
    # Same workstation TUN fake-IP exception as Baseline; literal/private URLs stay blocked.
    fake = ipaddress.ip_network('198.18.0.0/15')
    if not addresses or not (all(a.is_global for a in addresses) or
            (literal is None and '.' in p.hostname and all(a.version == 4 and a in fake for a in addresses))):
        raise ValueError('PAGE_URL_BLOCKED: URL resolves to a non-public address')


def _pdf_rule_links(page, source_url, page_number):
    """Yield observed official ELI document URIs, not inferred links or factual endorsements."""
    if not official_source(source_url):
        return
    for reference in page.get('/Annots') or []:
        try:
            annotation = reference.get_object()
            if annotation.get('/Subtype') != '/Link':
                continue
            action = annotation.get('/A')
            if action is None:
                continue
            action = action.get_object()
            uri = action.get('/URI')
            if (action.get('/S') != '/URI' or not isinstance(uri, str)
                    or any(c.isspace() for c in uri) or not official_source(uri)):
                continue
            parsed = urlsplit(uri)
            # ELI identifies an observed legal act, independently of its particular number.
            if not re.fullmatch(r'/eli/(?:reg|dir|dec)(?:_(?:impl|del))?/\d{4}/\d+(?:/[A-Za-z0-9_.-]+)*/?', parsed.path):
                continue
            if parsed.port is not None and not 0 < parsed.port <= 65535:
                continue
            yield {'url': uri, 'title': f'Observed legal text (PDF page {page_number})',
                   'observed_uri': uri, 'source_url': source_url, 'source_page': page_number}
        except (AttributeError, KeyError, TypeError, ValueError):
            continue  # A malformed link does not alter the extracted body.


def extract(data, content_type, url, *, queries=(), remaining=None, details=None):
    """Retain Baseline extraction limits; a login shell is not usable evidence."""
    if 'pdf' in content_type.lower() or urlsplit(url).path.lower().endswith('.pdf'):
        def check_time():
            if remaining is not None and remaining() <= 0:
                raise BudgetExhausted('wall_seconds')
        check_time()
        doc = PdfReader(io.BytesIO(data))
        check_time()
        terms=set(re.findall(r'[a-z]{3,}', ' '.join(q for q in queries if isinstance(q,str)).lower()))
        codes={re.sub(r'[.\s]+','',m.group(1)) for q in queries if isinstance(q,str) for m in
               re.finditer(r'\b(?:CN|HS)\s*(?:codes?\s*)?(\d{4}(?:[.\s]*\d{2}){0,2})(?!\d|[.\s]*\d{2}\b)',q,re.I)}
        terms-={'the','and','for','with','from','that','this','under','which','what','does','are','has','have',
                'was','were','will','can','could','should','would','into','their','whether','requirements',
                'official','regulations'}
        pages, candidates, links, linked = [], [], [], set()
        for index,page in enumerate(doc.pages):
            check_time()
            original=page.extract_text() or ''
            check_time()
            pages.append(original)
            if len(links) < 4:
                for link in _pdf_rule_links(page, url, index + 1):
                    key = urlsplit(link['url'])._replace(fragment='').geturl()
                    if key not in linked:
                        linked.add(key)
                        links.append(link)
                    if len(links) == 4:
                        break
            # Ordinary pages stay whole. Large pages expose source spans, not summaries.
            for start in range(0,len(original),12000):
                end=min(len(original),start+12000)
                words=set(re.findall(r'[a-z]{3,}',original[start:end].lower()))
                matched=terms & words
                for code in codes:
                    pattern=r'(?<![\d.])'+r'[.\s]*'.join([code[:4],*[code[n:n+2] for n in range(4,len(code),2)]])+r'(?!\d|[.\s]*\d{2}\b)'
                    if re.search(pattern,original[start:end]):matched.add(code)
                candidates.append((index,start,end,matched))
        if sum(len(page.strip()) for page in pages)<100:
            raise ValueError('PAGE_EMPTY_CONTENT: PDF has less than 100 readable characters')
        check_time()
        counts={term:sum(term in item[3] for item in candidates) for term in terms|codes}
        weights={term:1+math.log((len(candidates)+1)/(count+1)) for term,count in counts.items()}
        ranked=sorted(candidates,key=lambda item:(-sum(weights[t] for t in item[3]),item[0],item[1]))
        # Reserve a short disclosure and include markers in the unchanged character cap.
        selected=[];left=300000-160
        for index,start,end,_ in ranked:
            check_time()
            marker=f'\n[PDF page {index+1}; extracted characters {start}:{end}]\n'
            take=min(end-start,max(0,left-len(marker)-16))
            if take:
                selected.append((index,start,start+take))
                left-=len(marker)+16+take
            if left<=80:
                break
        selected.sort()
        selected_pages={index for index,_,_ in selected}
        omitted=[]
        for index,original in enumerate(pages):
            cursor=0
            for _,start,end in (item for item in selected if item[0]==index):
                if cursor<start:omitted.append({'page':index+1,'start':cursor,'end':start})
                cursor=end
            if cursor<len(original):omitted.append({'page':index+1,'start':cursor,'end':len(original)})
        prefix=(f'[PDF extraction: {len(selected_pages)} of {len(pages)} pages selected; '
                +('some original text is omitted.' if omitted else 'all extracted page text is included.')+']\n')
        parts=[prefix];spans=[];offset=len(prefix)
        for index,start,end in selected:
            marker=f'\n[PDF page {index+1}; extracted characters {start}:{end}]\n'
            parts.extend([marker,pages[index][start:end]])
            offset+=len(marker)
            spans.append({'page':index+1,'page_start':start,'page_end':end,
                          'output_start':offset,'output_end':offset+end-start})
            offset+=end-start
        text=''.join(parts)
        check_time()
        if details is not None:
            details.update(total_pages=len(pages),selected_pages=sorted(i+1 for i in selected_pages),
                           selected_spans=spans,omitted_spans=omitted,truncated=bool(omitted),
                           method='query_term_page_ranking',query_terms=sorted(terms),
                           classification_codes=sorted(codes),character_limit=300000,links=links)
        if len(text)>300000:
            raise ValueError('PAGE_EXTRACTION_LIMIT: PDF selection exceeds character limit')
        title = getattr(doc.metadata, 'title', None) or ''
        return title, text, 'pypdf'
    if 'html' not in content_type.lower() and not content_type.lower().startswith('text/'):
        raise ValueError('PAGE_UNSUPPORTED_CONTENT: ' + content_type)
    charset = re.search(r'charset=([^;\s]+)', content_type, re.I)
    for encoding in ([charset[1].strip('\"\'')] if charset else []) + ['utf-8', 'windows-1252']:
        try:
            html = data.decode(encoding)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    else:
        html = data.decode('utf-8', errors='replace')
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    for node in soup.select('script,style,noscript,svg,canvas,form,nav,header,footer,aside'):
        node.decompose()
    source = soup.select_one('main') or soup.select_one('article') or soup.select_one('[role="main"]') or soup.body or soup
    text = re.sub(r'\s+', ' ', source.get_text(' ', strip=True)).strip()[:100000]
    lower = (title + ' ' + text[:1200]).lower()
    blocked = any(x in lower for x in ('access denied', 'sign in to continue', 'log in to continue',
                  'enable javascript', 'javascript is required', 'just a moment', 'captcha', 'page not found', 'error 404'))
    login_shell = 'by continuing, you agree' in lower and 'sign in' in lower
    if len(text) < 1800 and (blocked or login_shell):
        raise ValueError('PAGE_NOT_READABLE: login, access restriction or JavaScript shell')
    if (len(text) < 1000 and re.match(r'^table\s+of\s+contents\b', text, re.I)
            and any(re.fullmatch(r'table\s+of\s+contents', h.get_text(' ', strip=True), re.I)
                    for h in source.find_all(['h1', 'h2', 'h3']))
            and sum(len(p.get_text(' ', strip=True)) for p in source.select('p')) < 200):
        raise ValueError('PAGE_DIRECTORY_ONLY: HTML contains a table of contents, not full document text')
    if len(text) < 200:
        raise ValueError('PAGE_EMPTY_CONTENT: HTML has less than 200 readable characters')
    return title, text, 'beautifulsoup_html'


def full_document(data, url):
    """Select one explicitly linked HTML full document, never construct its address."""
    targets = {}
    for node in BeautifulSoup(data, 'html.parser').find_all('a', href=True):
        label = re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()
        href = node.get('href')
        if not isinstance(href, str) or not href.strip() or not re.search(r'\bfull\s+(?:document|text)\b', label, re.I):
            continue
        target = urlsplit(urljoin(url, href.strip()))
        path = target.path.lower()
        if re.search(r'\b(?:PDF|XML)\b', label, re.I) or path.endswith(('.pdf', '.xml')):
            continue
        if not (re.search(r'\bHTML\b', label, re.I) or path.endswith(('.html', '.htm'))
                or node.get('type', '').lower() == 'text/html'):
            continue
        resolved = target._replace(fragment='').geturl()
        targets.setdefault(resolved, {'url': resolved, 'observed_href': href, 'observed_label': label})
    if len(targets) == 1:
        resolved, record = next(iter(targets.items()))
        if urlsplit(resolved).scheme == 'https' and resolved != urlsplit(url)._replace(fragment='').geturl():
            return record
    return None


def official_rule_links(data, url):
    """Keep at most four observed official rule entries, without browsing them."""
    if not official_source(url) or urlsplit(url).scheme != 'https':
        return []
    links, seen = [], set()
    for node in BeautifulSoup(data, 'html.parser').find_all('a', href=True):
        label = re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()
        href = node.get('href')
        if not isinstance(href, str) or not href.strip() or href.strip().startswith('#'):
            continue
        if any(parent.name in {'nav', 'footer', 'aside', 'form'} for parent in node.parents):
            continue
        if re.search(r'\b(?:explainer|overview|summary|faq|news|privacy|cookies?|accessibility|copyright|contact)\b|\bterms (?:of (?:use|service)|and conditions)\b', label, re.I):
            continue
        named_order = re.fullmatch(r'(?:[A-Z]{2,12}\s+)?Order\s+(?:No\.?|Number|#)\s*\d[\w./-]*(?:\s*[:\u2013\u2014]\s*.+)?', label, re.I)
        named_regulation = (re.search(r'\bRegulations?\s+(?:\([A-Z]{2,8}\)\s*)?(?:No\.?\s*)?\d[\w./-]*', label, re.I)
                            or re.fullmatch(r'(?:[A-Za-z][\w-]*\s+){2,}Regulations?', label))
        full = re.search(r'\bfull\s+(?:document|text)\b', label, re.I)
        if not (named_order or named_regulation or full):
            continue
        try:
            parsed = urlsplit(urljoin(url, href.strip()))
            target = parsed._replace(fragment='').geturl()
        except ValueError:
            continue
        if (parsed.scheme != 'https' or not official_source(target) or target in seen
                or target == urlsplit(url)._replace(fragment='').geturl()
                or parsed.path.lower().endswith('.xml')
                or re.search(r'/(?:privacy|cookies?|accessibility|copyright|contact|terms|policies)(?:[/.-]|$)', parsed.path, re.I)):
            continue
        seen.add(target)
        links.append({'url': target, 'title': label, 'observed_label': label,
                      'observed_href': href, 'observed_title': node.get('title')})
        if len(links) == 4:
            break
    return links


def embedded_pdf(data, url):
    """Return only one PDF explicitly embedded in the downloaded HTML."""
    targets = set()
    for node in BeautifulSoup(data, 'html.parser').select('iframe,embed,object'):
        for attribute in ('src', 'data-src', 'data'):
            value = node.get(attribute)
            if not isinstance(value, str) or not value.strip():
                continue
            target = urlsplit(urljoin(url, value.strip()))
            if target.path.lower().endswith('.pdf'):
                targets.add(target._replace(fragment='').geturl())
    if len(targets) == 1:
        target = targets.pop()
        if urlsplit(target).scheme == 'https':
            return target
    return None


def read_page(ctx, row):
    folder = ctx.directory / 'reads' / uuid4().hex
    folder.mkdir(parents=True)
    queries=[q for q in row.get('read_queries',[]) if isinstance(q,str)]
    write(folder / 'request.json', {'url': row['url'], 'channel': CHANNEL, 'read_queries': queries})
    started = time.monotonic()
    pages, http, error = [], [], None
    current, retries, redirects = row['url'], 0, 0
    followed_embedded = followed_full_document = False
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 SearchWorthyOR/1.4.2',
                            'Accept': 'text/html,application/xhtml+xml,application/pdf,text/plain;q=0.8,*/*;q=0.5',
                            'Accept-Encoding': 'gzip, deflate', 'Accept-Language': 'en-US,en;q=0.8'})
    try:
        while True:
            ctx.reserve('read', url=current, channel=CHANNEL, physical_retry=retries, redirect_attempt=redirects)
            public_url(current)
            if ctx.remaining() <= 0:
                raise BudgetExhausted('wall_seconds')
            attempt = {'url': current, 'status': None, 'content_type': None}
            http.append(attempt)
            timer = None
            response = None
            try:
                remaining = ctx.remaining()
                response = session.get(current, allow_redirects=False, stream=True, verify=certifi.where(),
                                       timeout=(min(10., remaining / 2), min(30., remaining / 2)))
                attempt.update(status=response.status_code, content_type=response.headers.get('Content-Type', ''), final_url=response.url)
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirects >= 5 or not response.headers.get('Location'):
                        raise ValueError('PAGE_REDIRECT_FAILURE: invalid redirect or redirect limit')
                    current = urljoin(current, response.headers['Location'])
                    redirects += 1
                    continue
                def abort():
                    try:
                        response.raw._fp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                    except (AttributeError, OSError):
                        response.close()
                timer = threading.Timer(max(.001, ctx.remaining()), abort)
                timer.daemon = True
                timer.start()
                raw_path = folder / f'http_{len(http)}.bin'
                attempt['raw_path'] = str(raw_path)
                total = 0
                with raw_path.open('wb') as stream:
                    for chunk in response.iter_content(chunk_size=8192):
                        if ctx.remaining() <= 0:
                            raise BudgetExhausted('wall_seconds')
                        total += len(chunk)
                        if total > 8000000:
                            raise ValueError('PAGE_NOT_READABLE: response exceeds 8000000 bytes')
                        stream.write(chunk)
                attempt['bytes'] = total
                if ctx.remaining() <= 0:
                    raise BudgetExhausted('wall_seconds')
                if response.status_code in RETRYABLE and retries == 0:
                    retries += 1
                    continue
                if response.status_code >= 400:
                    raise ValueError(f'PAGE_HTTP_{response.status_code}: HTTP {response.status_code}')
                raw = raw_path.read_bytes()
                extraction={}
                try:
                    title, text, backend = extract(raw, attempt['content_type'], response.url,
                        queries=queries,remaining=ctx.remaining,details=extraction)
                except ValueError as exc:
                    if followed_embedded or followed_full_document:
                        raise
                    if str(exc).startswith('PAGE_DIRECTORY_ONLY:'):
                        target = full_document(raw, response.url)
                        if not target:
                            raise
                        attempt.update(extraction_error=str(exc), full_document_url=target['url'],
                                       observed_href=target['observed_href'], observed_label=target['observed_label'],
                                       transition='FULL_DOCUMENT')
                        current, followed_full_document = target['url'], True
                        continue  # Another counted READ, with the original case deadline.
                    if not str(exc).startswith('PAGE_EMPTY_CONTENT: HTML'):
                        raise
                    target = embedded_pdf(raw, response.url)
                    if not target:
                        raise
                    attempt.update(extraction_error=str(exc), embedded_pdf_url=target,
                                   transition='EMBEDDED_PDF')
                    current, followed_embedded = target, True
                    continue  # The next iteration reserves another READ under the same deadline.
                if ctx.remaining() <= 0:
                    raise BudgetExhausted('wall_seconds')
                links = official_rule_links(raw, response.url) if backend == 'beautifulsoup_html' else extraction.pop('links', [])
                pages.append({'url': response.url, 'requested_url': row['url'], 'final_url': response.url,
                              'title': title or row.get('title', ''), 'visible_text': text, 'backend': backend,
                              'channel': CHANNEL, 'source_kind': 'EXTERNAL', 'content_type': attempt['content_type'],
                              'raw_path': str(raw_path),
                              'extraction': extraction,
                              'links': links})
                break
            except requests.RequestException as exc:
                attempt['error'] = type(exc).__name__ + ': ' + str(exc)
                if retries == 0 and ctx.remaining() > 0:
                    retries += 1
                    continue
                raise
            finally:
                if timer:
                    timer.cancel()
                if response is not None:
                    response.close()
    except BudgetExhausted as exc:
        error = 'READ_BUDGET_EXHAUSTED: ' + str(exc)
        raise
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        if isinstance(exc, requests.exceptions.Timeout):
            error = 'PAGE_TIMEOUT: ' + error
        elif isinstance(exc, requests.exceptions.SSLError):
            error = 'PAGE_TLS_FAILURE: ' + error
        elif isinstance(exc, requests.exceptions.ConnectionError):
            error = 'PAGE_REMOTE_DISCONNECT: ' + error
    finally:
        session.close()
        match = re.search(r'PAGE_[A-Z0-9_]+', error or '')
        failure = None if pages else (match[0] if match else 'PAGE_READ_FAILURE')
        attempts = [{'requested_url': row['url'], 'final_url': http[-1].get('final_url') if http else None,
                     'status': http[-1]['status'] if http else None, 'backend': CHANNEL,
                     'readable': bool(pages), 'failure_type': failure, 'failure_detail': error,
                     'http_requests': len(http), 'wall_seconds': time.monotonic() - started}]
        write(folder / 'response.json', {'pages': pages, 'attempts': attempts, 'http': http})
        record = {**attempts[0], 'channel': CHANNEL, 'response_path': str(folder / 'response.json'),
                  'llm_calls': 0, 'total_tokens': 0}
        with (ctx.directory / 'read_calls.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        ctx.event('READ_COMPLETE' if pages else 'READ_FAILED', **record)
    return pages, attempts
