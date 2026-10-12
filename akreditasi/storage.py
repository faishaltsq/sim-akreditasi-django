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
        auth_token = self.supabase_key
        # Supabase Storage requires a Compact JWS (JWT) in Authorization: Bearer.
        # sb_publishable_* keys will cause 'Invalid Compact JWS'.
        if not auth_token or auth_token.startswith('sb_publishable_') or not auth_token.startswith('eyJ'):
            auth_token = (
                getattr(settings, 'SUPABASE_ANON_KEY', '')
                or os.environ.get('SUPABASE_ANON_KEY', '')
                or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd3YWV1emJiZGF3YmVrcm1ydmZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODE4OTYsImV4cCI6MjEwNDY1Nzg5Nn0.5XJVOJif2MGjIpQSvk49erTmdCBk621MzAjtXw9b6RU'
            )
        return {
            "Authorization": f"Bearer {auth_token}",
            "apiKey": auth_token,
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
            resp = requests.post(endpoint, headers=headers, data=data, timeout=30)
            if resp.status_code not in (200, 201):
                import logging
                logging.getLogger(__name__).error(
                    "Gagal unggah ke Supabase Storage (%s) HTTP %s: %s",
                    clean_name, resp.status_code, resp.text
                )
        except Exception as e:
            # Jika upload gagal, log dan biarkan nama file tersimpan
            import logging
            logging.getLogger(__name__).error("Gagal koneksi ke Supabase Storage (%s): %s", clean_name, e)

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
