"""Bounded Supabase private-object HTTP mechanics; caller owns authorization and audit."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests


class PrivateStorageError(Exception):
    """Sanitized private-storage failure; contains no provider response details."""


@dataclass(frozen=True)
class StoredPrivateObject:
    storage_key: str
    sha256: str
    size_bytes: int
    content_type: str


@dataclass
class SupabasePrivateStorage:
    base_url: str
    api_key: str = field(repr=False)
    bucket: str
    timeout_seconds: int = 15
    max_bytes: int = 10485760
    signed_url_ttl_seconds: int = 60
    session: object | None = field(default=None, repr=False)

    def __post_init__(self):
        try:
            parsed = urlsplit(self.base_url)
            valid_url = parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
            if parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1"):
                valid_url = not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
        except (ValueError, TypeError):
            valid_url = False
        if not valid_url or not isinstance(self.api_key, str) or not self.api_key or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", self.bucket):
            raise PrivateStorageError("Invalid storage configuration")
        if any(type(v) is not int or v <= 0 for v in (self.timeout_seconds, self.max_bytes)) or type(self.signed_url_ttl_seconds) is not int or not 1 <= self.signed_url_ttl_seconds <= 300:
            raise PrivateStorageError("Invalid storage bounds")
        self.base_url = self.base_url.rstrip("/")
        if self.session is None:
            self.session = requests.Session()

    @staticmethod
    def _mime(filename, declared, data):
        ext = filename.rsplit(".", 1)[-1].lower() if isinstance(filename, str) and "." in filename else ""
        signatures = (("pdf", "application/pdf", data.startswith(b"%PDF-")),
                      ("png", "image/png", data.startswith(b"\x89PNG\r\n\x1a\n")),
                      ("jpg", "image/jpeg", data.startswith(b"\xff\xd8\xff")),
                      ("jpeg", "image/jpeg", data.startswith(b"\xff\xd8\xff")))
        for extension, mime, match in signatures:
            if match and ext == extension and declared == mime:
                return mime
        raise PrivateStorageError("Unsupported or mismatched file")

    def _request(self, method, url, **kwargs):
        try:
            response = self.session.request(method, url, timeout=self.timeout_seconds, allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise PrivateStorageError("Storage request failed") from None
        if not 200 <= response.status_code < 300:
            raise PrivateStorageError("Storage request failed")
        return response

    def upload(self, file_obj, *, owner_id: str, sensitivity: str, filename: str = "", content_type: str = "") -> StoredPrivateObject:
        try:
            if sensitivity not in ("personnel", "health") or str(uuid.UUID(owner_id)) != owner_id:
                raise PrivateStorageError("Invalid object scope")
            data = file_obj.read(self.max_bytes + 1)
            if not isinstance(data, bytes) or not data or len(data) > self.max_bytes:
                raise PrivateStorageError("Invalid file size or stream")
            mime = self._mime(filename, content_type, data)
        except PrivateStorageError:
            raise
        except Exception:
            raise PrivateStorageError("Invalid upload") from None
        key = f"{sensitivity}/{owner_id}/{uuid.uuid4()}.{filename.rsplit('.', 1)[-1].lower()}"
        url = f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
        self._request("POST", url, data=data, headers={"apikey": self.api_key, "Authorization": f"Bearer {self.api_key}", "Content-Type": mime, "x-upsert": "false"})
        return StoredPrivateObject(key, hashlib.sha256(data).hexdigest(), len(data), mime)

    def create_signed_download(self, storage_key: str, *, expires_in: int | None = None) -> str:
        ttl = self.signed_url_ttl_seconds if expires_in is None else expires_in
        match = re.fullmatch(r"(personnel|health)/([0-9a-f-]{36})/([0-9a-f-]{36})\.(pdf|png|jpg|jpeg)", storage_key or "")
        if not match or type(ttl) is not int or not 1 <= ttl <= 300:
            raise PrivateStorageError("Invalid signed-download request")
        try:
            if str(uuid.UUID(match.group(2))) != match.group(2) or str(uuid.UUID(match.group(3))) != match.group(3):
                raise ValueError
        except ValueError:
            raise PrivateStorageError("Invalid signed-download request") from None
        encoded = quote(storage_key, safe="/")
        endpoint = f"{self.base_url}/storage/v1/object/sign/{quote(self.bucket, safe='')}/{encoded}"
        response = self._request("POST", endpoint, json={"expiresIn": ttl}, headers={"apikey": self.api_key, "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            payload = response.json()
            signed = payload.get("signedURL", payload.get("signedUrl")) if isinstance(payload, dict) else None
            if not isinstance(signed, str) or not signed:
                raise ValueError
            result = urljoin(self.base_url + "/", signed)
            parsed, origin = urlsplit(result), urlsplit(self.base_url)
            decoded_path = unquote(parsed.path)
            expected = f"/storage/v1/object/sign/{self.bucket}/{storage_key}"
            if (parsed.scheme, parsed.hostname, parsed.port) != (origin.scheme, origin.hostname, origin.port) or parsed.username or parsed.password or parsed.fragment or decoded_path != expected or not parsed.query:
                raise ValueError
            return result
        except Exception:
            raise PrivateStorageError("Invalid signed URL response") from None

    def verify_private_object(
        self,
        storage_key: str,
        *,
        expected_sha256: str,
        expected_size: int,
        expected_content_type: str,
    ) -> StoredPrivateObject:
        match = re.fullmatch(
            r"(personnel|health)/([0-9a-f-]{36})/([0-9a-f-]{36})\.(pdf|png|jpg|jpeg)",
            storage_key or "",
        )
        if not match or type(expected_size) is not int or not 1 <= expected_size <= self.max_bytes:
            raise PrivateStorageError("Invalid private-object verification request")
        try:
            if any(
                str(uuid.UUID(match.group(index))) != match.group(index)
                for index in (2, 3)
            ):
                raise ValueError
        except ValueError:
            raise PrivateStorageError("Invalid private-object verification request") from None
        if not isinstance(expected_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", expected_sha256
        ):
            raise PrivateStorageError("Invalid private-object verification request")

        endpoint = (
            f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/"
            f"{quote(storage_key, safe='/')}"
        )
        response = self._request(
            "GET",
            endpoint,
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
            },
            stream=True,
        )
        try:
            chunks = []
            size_bytes = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                if not isinstance(chunk, bytes):
                    raise PrivateStorageError("Private-object verification failed")
                size_bytes += len(chunk)
                if size_bytes > min(self.max_bytes, expected_size):
                    raise PrivateStorageError("Private-object verification failed")
                chunks.append(chunk)
            data = b"".join(chunks)
            declared_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
            actual_type = self._mime(
                f"file.{match.group(4)}", declared_type, data
            )
            digest = hashlib.sha256(data).hexdigest()
            if (
                size_bytes != expected_size
                or digest != expected_sha256
                or actual_type != expected_content_type
            ):
                raise PrivateStorageError("Private-object verification failed")
            return StoredPrivateObject(
                storage_key=storage_key,
                sha256=digest,
                size_bytes=size_bytes,
                content_type=actual_type,
            )
        except PrivateStorageError:
            raise
        except Exception:
            raise PrivateStorageError("Private-object verification failed") from None
        finally:
            close = getattr(response, "close", None)
            if close:
                close()


    def verify_anonymous_denial(self, storage_key: str) -> bool:
        match = re.fullmatch(
            r"(personnel|health)/([0-9a-f-]{36})/([0-9a-f-]{36})\.(pdf|png|jpg|jpeg)",
            storage_key or "",
        )
        try:
            if not match or any(
                str(uuid.UUID(match.group(index))) != match.group(index)
                for index in (2, 3)
            ):
                raise ValueError
        except ValueError:
            raise PrivateStorageError("Invalid anonymous-access probe") from None

        endpoint = (
            f"{self.base_url}/storage/v1/object/public/{quote(self.bucket, safe='')}/"
            f"{quote(storage_key, safe='/')}"
        )
        response = None
        try:
            response = self.session.request(
                "GET",
                endpoint,
                timeout=self.timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
            if response.status_code in (400, 401, 403, 404):
                return True
            raise PrivateStorageError("Private object is anonymously accessible")
        except requests.RequestException:
            raise PrivateStorageError("Anonymous-access probe failed") from None
        finally:
            close = getattr(response, 'close', None)
            if close:
                close()

    def delete(self, storage_key: str) -> None:
        match = re.fullmatch(
            r"(personnel|health)/([0-9a-f-]{36})/([0-9a-f-]{36})\.(pdf|png|jpg|jpeg)",
            storage_key or "",
        )
        if not match:
            raise PrivateStorageError("Invalid object-delete request")
        try:
            if any(
                str(uuid.UUID(match.group(index))) != match.group(index)
                for index in (2, 3)
            ):
                raise ValueError
        except ValueError:
            raise PrivateStorageError("Invalid object-delete request") from None

        endpoint = (
            f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/"
            f"{quote(storage_key, safe='/')}"
        )
        self._request(
            "DELETE",
            endpoint,
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
            },
        )
