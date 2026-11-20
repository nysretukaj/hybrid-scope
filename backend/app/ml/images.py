"""Images from the sources: find them in feeds, download them safely, prepare them for the vision model.

Safety: only http(s) URLs collected from the feeds are fetched (never a URL typed by a visitor),
every redirect hop must resolve to a public address (no requests into the local network), the
download stops at IMAGE_MAX_BYTES, and the bytes must decode as a real image.
"""
import base64
import io
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx

from .. import config

_IMG_TAG = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
_IMAGE_EXT = re.compile(r"\.(?:jpe?g|png|gif|webp)(?:$|\?)", re.I)


class ImageError(ValueError):
    """The image cannot be used (too big, not an image, blocked address...)."""


def image_from_entry(entry: dict) -> str | None:
    """The main picture of an RSS/Atom entry: media:content, media:thumbnail, an image enclosure or an <img>."""
    for key in ("media_content", "media_thumbnail"):
        for m in entry.get(key) or []:
            url = (m or {}).get("url")
            if url and (str(m.get("medium", "image")) == "image" or _IMAGE_EXT.search(url)):
                return url
    for link in entry.get("links") or []:
        if str(link.get("rel")) == "enclosure" and str(link.get("type", "")).startswith("image/") and link.get("href"):
            return link["href"]
    for field in ("summary", "description", "content"):
        value = entry.get(field)
        html = value[0].get("value", "") if isinstance(value, list) and value else str(value or "")
        m = _IMG_TAG.search(html)
        if m:
            return m.group(1)
    return None


def clean_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    p = urlparse(url)
    return url[:1000] if p.scheme in ("http", "https") and p.netloc else None


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def fetch(url: str, max_redirects: int = 3) -> bytes:
    """Download an image from a source, following at most a few redirects, all to public hosts."""
    current = clean_url(url)
    if not current:
        raise ImageError("not an http(s) URL")
    with httpx.Client(timeout=15, headers={"User-Agent": config.USER_AGENT}, follow_redirects=False) as client:
        for _ in range(max_redirects + 1):
            host = urlparse(current).hostname or ""
            if not _public_host(host):
                raise ImageError("address is not public")
            with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    current = clean_url(urljoin(current, resp.headers.get("location", "")))
                    if not current:
                        raise ImageError("bad redirect")
                    continue
                resp.raise_for_status()
                ctype = resp.headers.get("content-type", "")
                if ctype and not ctype.startswith("image/"):
                    raise ImageError(f"not an image ({ctype.split(';')[0]})")
                data = bytearray()
                for chunk in resp.iter_bytes():
                    data.extend(chunk)
                    if len(data) > config.IMAGE_MAX_BYTES:
                        raise ImageError("image is too large")
                return bytes(data)
    raise ImageError("too many redirects")


def prepare(data: bytes) -> tuple[str, str]:
    """Check that the bytes are a real image, shrink it and return (base64 JPEG for the model, small preview)."""
    from PIL import Image, UnidentifiedImageError  # imported here: only needed when images are analysed

    if len(data) > config.IMAGE_MAX_BYTES:
        raise ImageError("image is too large")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()  # detects truncated or fake files
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageError("the file is not a valid image") from exc
    if img.width * img.height > 40_000_000:
        raise ImageError("image dimensions are too large")

    def encode(side: int, quality: int) -> str:
        copy = img.copy()
        copy.thumbnail((side, side))
        buf = io.BytesIO()
        copy.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    return encode(config.IMAGE_MAX_SIDE, 85), encode(320, 70)


def decode_upload(b64: str) -> bytes:
    """An image sent by the browser as base64 (optionally a data: URL)."""
    if "," in b64[:100] and b64.lstrip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    if len(b64) > config.IMAGE_MAX_BYTES * 4 // 3 + 16:
        raise ImageError("image is too large")
    try:
        return base64.b64decode(b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ImageError("the upload is not valid base64") from exc
