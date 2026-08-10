"""Object storage for payment screenshots, on Cloudflare R2.

Two decisions worth stating, because both are load-bearing.

**The bucket is private and there are no permanent URLs.** A UPI payment
screenshot typically shows the payer's handle, their phone number and their
bank. A public object URL for that would be a permanent, guessable-if-leaked
disclosure of somebody's payment details, so every read is a freshly signed URL
that expires in minutes. What is stored in the database is the key, never a
URL - a stored URL either rots when it expires or, worse, does not.

**boto3 signs; httpx transfers.** Signing is a local HMAC and makes no network
call, so the synchronous client is safe to use in an async handler. The upload
is a real network round trip, and doing that through boto3 would block the
event loop for the duration - so the signed URL is handed to httpx, which is
already a dependency and is async throughout.
"""

from __future__ import annotations

import uuid
from typing import Final

import boto3
import httpx
from botocore.client import Config

from ..settings import Settings

# R2 ignores the region but SigV4 requires one in the signature, and "auto" is
# what Cloudflare's own documentation uses.
_REGION: Final = "auto"

# Long enough to open the panel and look, short enough that a URL copied out of
# a browser's history is useless by the time anyone finds it.
VIEW_URL_TTL_SECONDS: Final = 300

_UPLOAD_URL_TTL_SECONDS: Final = 120

# The allowlist is on content type *and* magic bytes; see `sniff_image_type`.
# Extensions come from here rather than from the uploaded filename, which the
# user controls and which is therefore not evidence of anything.
EXTENSION_FOR: Final[dict[str, str]] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

_MAGIC: Final[tuple[tuple[bytes, str], ...]] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


class R2Error(RuntimeError):
    """The object store refused or was unreachable."""


def sniff_image_type(data: bytes) -> str | None:
    """The real type of `data`, or None if it is not an image we accept.

    The declared `Content-Type` on an upload is whatever the client chose to
    send, so it is a hint and not a fact. This reads the bytes instead: a file
    named `proof.png`, declared `image/png`, containing a PDF or an HTML page
    with a script tag is refused here rather than stored and later served back
    to the operator's browser.
    """
    for prefix, content_type in _MAGIC:
        if data.startswith(prefix):
            return content_type
    # WebP is a RIFF container: "RIFF" then four bytes of length, then "WEBP".
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def new_key(content_type: str) -> str:
    """A fresh object key. Never derived from the uploaded filename.

    A user-supplied name could collide with another user's, could carry path
    separators, and would leak whatever the file was called on their machine.
    A random key has none of those properties and no meaning at all, which is
    the point.
    """
    return f"payments/{uuid.uuid4()}.{EXTENSION_FOR.get(content_type, 'bin')}"


def _client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name=_REGION,
        config=Config(signature_version="s3v4"),
    )


def presigned_view_url(settings: Settings, key: str) -> str:
    """A short-lived URL that reads one object. Local computation only."""
    return _client(settings).generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket, "Key": key},
        ExpiresIn=VIEW_URL_TTL_SECONDS,
    )


async def upload(settings: Settings, *, key: str, data: bytes, content_type: str) -> None:
    """Put one object, by signing locally and transferring over httpx.

    Raises `R2Error` on anything other than success, so the caller can record
    a failed upload rather than writing a database row that points at an object
    which is not there.
    """
    url = _client(settings).generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.r2_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=_UPLOAD_URL_TTL_SECONDS,
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.put(url, content=data, headers={"Content-Type": content_type})
    except httpx.HTTPError as exc:
        raise R2Error(f"could not reach object storage: {exc}") from exc

    if response.status_code >= 400:
        raise R2Error(f"object storage refused the upload: {response.status_code}")
