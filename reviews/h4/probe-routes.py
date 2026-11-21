"""Read-only route inventory. Tokens here are synthetic, except the existing H4 request."""
import concurrent.futures
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import urllib.parse
import subprocess
import tempfile


def probe(url):
    chain = []
    for _ in range(6):
        with tempfile.TemporaryDirectory() as temp:
            headers_path, body_path = Path(temp) / 'headers', Path(temp) / 'body'
            result = subprocess.run(['curl', '-sS', '--max-time', '15', '-D', str(headers_path), '-o', str(body_path), '--url', url], capture_output=True)
            if result.returncode:
                chain.append({'url': url, 'curl_exit': result.returncode})
                break
            headers = headers_path.read_text().splitlines()
            status = int([line for line in headers if line.startswith('HTTP/')][-1].split()[1])
            values = dict(line.split(': ', 1) for line in headers if ': ' in line)
            values = {k.lower(): v for k, v in values.items()}
            body = body_path.read_bytes()
        location = values.get('location')
        chain.append({'url': url, 'status': status, 'location': location,
                      'body_sha256': hashlib.sha256(body).hexdigest(),
                      'worker_version': values.get('x-worker-version')})
        if not location or status not in (301, 302, 303, 307, 308):
            break
        url = urllib.parse.urljoin(url, location)
    return chain


if __name__ == '__main__':
    urls = [
        'https://review.aditor.ai/o', 'https://review.aditor.ai/d/aditor',
        'https://review.aditor.ai/u/h4-invalid-token',
        'https://review.aditor.ai/review/h4-invalid-review',
        'https://review.aditor.ai/share/h4-invalid-token',
        'https://feedback.aditor.ai/r/Q7JENfgm6yPkL2Q8Q_N9bKUkGU_bZPFT',
        'https://feedback.aditor.ai/s/h4-invalid-token',
        'https://feedback.aditor.ai/share/h4-invalid-token',
        'https://feedback.aditor.ai/handin', 'https://feedback.aditor.ai/whop',
        'https://understanding-afterwards-capability-greater.trycloudflare.com/r/D4AqM7yHJfHrymXSBXnOAaTbztVhvxPx',
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(probe, urls))
    Path(__file__).with_name('evidence').joinpath('routes-live.json').write_text(
        json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'chains': rows}, indent=2) + '\n')
    for row in rows:
        print(row[0]['url'], [(r.get('status'), r.get('location')) for r in row])
