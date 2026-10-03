"""Private render transport. URLs and secrets never come from editor input."""
from contextlib import contextmanager
import httpx
from ..config import settings


def configured():
    return bool(settings.mixer_iterations_url and settings.mixer_iterations_secret)


def connection(path):
    base = settings.mixer_iterations_url.rstrip('/')
    if not configured() or not base.startswith('https://'):
        raise RuntimeError('Automatic assembly is not connected yet.')
    return base + '/api/internal/iterations' + path, {'authorization': f'Bearer {settings.mixer_iterations_secret}'}


def call(method, path, payload):
    url, headers = connection(path)
    r = httpx.request(method, url, headers=headers, timeout=30, follow_redirects=False,
                      **({'json': payload} if method == 'POST' else {'params': payload}))
    r.raise_for_status()
    return r.json()


@contextmanager
def output(job_id, identity):
    from urllib.parse import quote
    url, headers = connection(f'/jobs/{quote(job_id, safe="")}/file')
    with httpx.stream('GET', url, headers=headers, params=identity, timeout=120, follow_redirects=False) as r:
        r.raise_for_status()
        yield r
