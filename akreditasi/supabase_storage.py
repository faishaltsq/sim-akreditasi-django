import os
import requests
from django.conf import settings
from django.core.files.storage import default_storage


def upload_to_supabase_storage(file_obj, filename, folder="bukti"):
    supabase_url = getattr(settings, 'SUPABASE_URL', '')
    supabase_key = getattr(settings, 'SUPABASE_KEY', '')
    bucket = getattr(settings, 'SUPABASE_BUCKET', 'bukti-akreditasi')

    clean_name = os.path.basename(filename).replace(' ', '_')
    storage_path = f"{folder}/{clean_name}"

    if supabase_url and supabase_key:
        try:
            auth_token = supabase_key
            if not auth_token or auth_token.startswith('sb_publishable_') or not auth_token.startswith('eyJ'):
                auth_token = (
                    getattr(settings, 'SUPABASE_ANON_KEY', '')
                    or os.environ.get('SUPABASE_ANON_KEY', '')
                    or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd3YWV1emJiZGF3YmVrcm1ydmZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODE4OTYsImV4cCI6MjEwNDY1Nzg5Nn0.5XJVOJif2MGjIpQSvk49erTmdCBk621MzAjtXw9b6RU'
                )
            endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{storage_path}"
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "apiKey": auth_token,
                "Content-Type": getattr(file_obj, 'content_type', 'application/octet-stream'),
                "x-upsert": "true",
            }
            file_obj.seek(0)
            file_data = file_obj.read()

            response = requests.post(endpoint, headers=headers, data=file_data, timeout=15)
            if response.status_code in (200, 201):
                public_url = f"{supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}/{storage_path}"
                return {
                    'success': True,
                    'url': public_url,
                    'is_cloud': True,
                    'path': storage_path
                }
        except Exception as e:
            print(f"[Supabase Upload Error]: {e}")

    try:
        file_obj.seek(0)
        saved_path = default_storage.save(f"bukti/{clean_name}", file_obj)
        local_url = default_storage.url(saved_path)
        return {
            'success': True,
            'url': local_url,
            'is_cloud': False,
            'path': saved_path
        }
    except Exception as e:
        print(f"[Local Storage Error]: {e}")
        return {'success': False, 'url': '', 'is_cloud': False, 'error': str(e)}
