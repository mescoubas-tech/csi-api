# services/http_fetch.py
import asyncio
import random
from typing import Optional, Tuple

import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}

CF_BAD_GATEWAY_SIGNATURES = (
    "<title>502 Bad Gateway</title>",
    ">cloudflare<",
)

class FetchError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, body_preview: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body_preview = body_preview

def looks_like_cloudflare_502(text: str) -> bool:
    low = text.lower()
    return any(sig in low for sig in CF_BAD_GATEWAY_SIGNATURES)

async def fetch_text(
    url: str,
    timeout_s: float = 20.0,
    max_retries: int = 4,
    connect_timeout_s: float = 10.0,
) -> Tuple[str, int, dict]:
    """
    Récupère l'URL avec retries + backoff + HTTP/2 + UA headers.
    Retourne (text, status_code, headers)
    Lève FetchError si échec.
    """
    async with httpx.AsyncClient(
        http2=True,
        headers=DEFAULT_HEADERS,
        timeout=httpx.Timeout(timeout_s, connect=connect_timeout_s),
        follow_redirects=True,
    ) as client:
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = await client.get(url)
                text = resp.text or ""
                # Si Cloudflare 502 (ou page HTML d'erreur), on considère que c'est un échec transitoire
                if resp.status_code >= 500 or looks_like_cloudflare_502(text):
                    raise FetchError(
                        f"Upstream error {resp.status_code}",
                        status_code=resp.status_code,
                        body_preview=text[:400],
                    )
                return text, resp.status_code, dict(resp.headers)
            except (httpx.RequestError, FetchError) as exc:
                last_exc = exc
                # backoff exponentiel + jitter court
                if attempt < max_retries:
                    sleep_s = (2 ** (attempt - 1)) + random.uniform(0, 0.6)
                    await asyncio.sleep(sleep_s)
                else:
                    break

        # Si on est ici, tous les essais ont échoué
        if isinstance(last_exc, FetchError):
            raise last_exc
        raise FetchError(str(last_exc) if last_exc else "Unknown fetch error")
