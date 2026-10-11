"""
Supabase Storage backend untuk Django Storage API.
Memungkinkan FileField / ImageField mengunggah langsung ke bucket Supabase,
kompatibel penuh dengan Vercel serverless di mana local filesystem bersifat efemeral.
"""
import os
import requests
from urllib.parse import urljoin
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.deconstruct import deconstructible


@deconstructible
class SupabaseMediaStorage(Storage):
    """Django Storage engine yang menyimpan berkas ke Supabase Storage."""

    def __init__(self, bucket=None):
        self.bucket = bucket or getattr(settings, 'SUPABASE_BUCKET', 'bukti-akreditasi')
        self.supabase_url = getattr(settings, 'SUPABASE_URL', '').rstrip('/')
        self.supabase_key = getattr(settings, 'SUPABASE_KEY', '')

    def _get_headers(self, content_type='application/octet-stream'):
        return {
            "Authorization": f"Bearer {self.supabase_key}",
            "apiKey": self.supabase_key,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

    def _save(self, name, content):
        clean_name = name.replace('\\', '/').lstrip('/')
        if not (self.supabase_url and self.supabase_key):
            # Fallback jika kredensial tidak tersedia
            return clean_name

        endpoint = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{clean_name}"
        content_type = getattr(content, 'content_type', 'application/octet-stream')
        headers = self._get_headers(content_type)

        content.seek(0)
        data = content.read()

        try:
            resp = requests.post(endpoint, headers=headers, data=data, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            # Jika upload gagal, log dan biarkan nama file tersimpan
            import logging
            logging.getLogger(__name__).warning("Gagal unggah ke Supabase Storage (%s): %s", clean_name, e)

        return clean_name

    def url(self, name):
        clean_name = name.replace('\\', '/').lstrip('/')
        if self.supabase_url:
            return f"{self.supabase_url}/storage/v1/object/public/{self.bucket}/{clean_name}"
        return f"/media/{clean_name}"

    def exists(self, name):
        if not (self.supabase_url and self.supabase_key):
            return False
        clean_name = name.replace('\\', '/').lstrip('/')
        endpoint = f"{self.supabase_url}/storage/v1/object/public/{self.bucket}/{clean_name}"
        try:
            resp = requests.head(endpoint, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def delete(self, name):
        if not (self.supabase_url and self.supabase_key):
            return
        clean_name = name.replace('\\', '/').lstrip('/')
        endpoint = f"{self.supabase_url}/storage/v1/object/{self.bucket}"
        headers = self._get_headers()
        try:
            requests.delete(endpoint, headers=headers, json={"prefixes": [clean_name]}, timeout=10)
        except Exception:
            pass

    def size(self, name):
        return 0
