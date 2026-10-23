import hashlib
import io
import json
import unittest
import uuid

import requests

from sdm.storage_backend import PrivateStorageError, StoredPrivateObject, SupabasePrivateStorage


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", content=b"", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = content
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def iter_content(self, chunk_size):
        yield self.content

    def close(self):
        return None


class FakeSession:
    def __init__(self, response=None, exception=None):
        self.response = response or FakeResponse(200, {})
        self.exception = exception
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.exception:
            raise self.exception
        return self.response


PDF = b"%PDF-1.7\nsynthetic"
PNG = b"\x89PNG\r\n\x1a\nsynthetic"
JPEG = b"\xff\xd8\xff\xe0synthetic\xff\xd9"


class PrivateStorageTests(unittest.TestCase):
    def storage(self, session=None, **kwargs):
        return SupabasePrivateStorage(
            base_url="https://project.supabase.co", api_key="secret-key",
            bucket="private-hr", session=session or FakeSession(), **kwargs
        )

    def test_upload_supported_signatures_hash_and_metadata(self):
        for filename, mime, content in (("a.pdf", "application/pdf", PDF),
                                        ("a.png", "image/png", PNG),
                                        ("a.jpg", "image/jpeg", JPEG)):
            with self.subTest(filename=filename):
                session = FakeSession(FakeResponse(200))
                result = self.storage(session).upload(
                    io.BytesIO(content), owner_id=str(uuid.uuid4()), sensitivity="personnel",
                    filename=filename, content_type=mime,
                )
                self.assertIsInstance(result, StoredPrivateObject)
                self.assertEqual(result.sha256, hashlib.sha256(content).hexdigest())
                self.assertEqual(result.size_bytes, len(content))
                self.assertEqual(result.content_type, mime)
                self.assertNotIn("public_url", result.__dataclass_fields__)
                method, url, opts = session.calls[0]
                self.assertEqual(method, "POST")
                self.assertIn("personnel/", url)
                self.assertEqual(opts["headers"]["x-upsert"], "false")
                self.assertEqual(opts["headers"]["Content-Type"], mime)
                self.assertFalse(opts["allow_redirects"])

    def test_nonzero_cursor_reads_remaining_bytes(self):
        stream = io.BytesIO(b"skip" + PDF)
        stream.seek(4)
        result = self.storage().upload(stream, owner_id=str(uuid.uuid4()), sensitivity="health",
                                       filename="scan.pdf", content_type="application/pdf")
        self.assertEqual(result.sha256, hashlib.sha256(PDF).hexdigest())

    def test_reject_invalid_upload_inputs_without_request(self):
        samples = [("x.png", "application/pdf", PDF), ("x.pdf", "application/pdf", PNG),
                   ("x.html", "text/html", b"<html>"), ("x.pdf", "application/pdf", b"")]
        for filename, mime, data in samples:
            session = FakeSession()
            with self.subTest(filename=filename), self.assertRaises(PrivateStorageError):
                self.storage(session).upload(io.BytesIO(data), owner_id=str(uuid.uuid4()),
                                             sensitivity="personnel", filename=filename,
                                             content_type=mime)
            self.assertEqual(session.calls, [])

    def test_invalid_owner_sensitivity_oversize_and_unsupported_stream(self):
        for owner, sensitivity in (("../id", "personnel"), (str(uuid.uuid4()), "unknown")):
            with self.assertRaises(PrivateStorageError):
                self.storage().upload(io.BytesIO(PDF), owner_id=owner, sensitivity=sensitivity,
                                      filename="x.pdf", content_type="application/pdf")
        with self.assertRaises(PrivateStorageError):
            self.storage(max_bytes=3).upload(io.BytesIO(PDF), owner_id=str(uuid.uuid4()),
                                             sensitivity="personnel", filename="x.pdf",
                                             content_type="application/pdf")
        class NoRead:
            pass
        with self.assertRaises(PrivateStorageError):
            self.storage().upload(NoRead(), owner_id=str(uuid.uuid4()), sensitivity="health")

    def test_duplicate_filenames_get_distinct_keys_and_upload_failure_sanitized(self):
        session = FakeSession()
        store = self.storage(session)
        keys = [store.upload(io.BytesIO(PDF), owner_id=str(uuid.uuid4()), sensitivity="personnel",
                             filename="same.pdf", content_type="application/pdf").storage_key
                for _ in range(2)]
        self.assertNotEqual(keys[0], keys[1])
        for status in (400, 500, 302):
            session = FakeSession(FakeResponse(status, text="secret-key private payload"))
            with self.assertRaises(PrivateStorageError) as caught:
                self.storage(session).upload(io.BytesIO(PDF), owner_id=str(uuid.uuid4()),
                    sensitivity="personnel", filename="x.pdf", content_type="application/pdf")
            self.assertNotIn("secret-key", str(caught.exception))
            self.assertNotIn("private payload", str(caught.exception))
        session = FakeSession(exception=requests.Timeout("secret-key response body"))
        with self.assertRaises(PrivateStorageError) as caught:
            self.storage(session).upload(io.BytesIO(PDF), owner_id=str(uuid.uuid4()),
                sensitivity="personnel", filename="x.pdf", content_type="application/pdf")
        self.assertNotIn("secret-key", str(caught.exception))

    def test_signed_url_parsing_and_validation(self):
        key = f"personnel/{uuid.uuid4()}/{uuid.uuid4()}.pdf"
        for payload in ({"signedURL": f"/storage/v1/object/sign/private-hr/{key}?token=x"},
                        {"signedUrl": f"https://project.supabase.co/storage/v1/object/sign/private-hr/{key}?token=x"}):
            session = FakeSession(FakeResponse(200, payload))
            url = self.storage(session).create_signed_download(key)
            self.assertTrue(url.startswith("https://project.supabase.co/storage/v1/object/sign/private-hr/"))
            self.assertEqual(session.calls[0][2]["json"]["expiresIn"], 60)
            self.assertFalse(session.calls[0][2]["allow_redirects"])

    def test_signed_url_without_storage_prefix_is_normalized(self):
        """Supabase returns "/object/sign/..." — the servable path needs /storage/v1."""
        key = f"personnel/{uuid.uuid4()}/{uuid.uuid4()}.pdf"
        payload = {"signedURL": f"/object/sign/private-hr/{key}?token=x"}

        url = self.storage(FakeSession(FakeResponse(200, payload))).create_signed_download(key)

        self.assertEqual(
            url,
            f"https://project.supabase.co/storage/v1/object/sign/private-hr/{key}?token=x",
        )

    def test_signed_url_rejects_bad_ttl_keys_and_response(self):
        key = f"health/{uuid.uuid4()}/{uuid.uuid4()}.pdf"
        for ttl in (0, -1, 301, True, 60.0, '60'):
            session = FakeSession()
            with self.assertRaises(PrivateStorageError):
                self.storage(session).create_signed_download(key, expires_in=ttl)
            self.assertEqual(session.calls, [])
        for bad in ("../x", f"personnel/{uuid.uuid4()}/x.pdf", key + "?x=y",
                    key.replace("/", "%2f"), f"personnel/{uuid.uuid4()}/{uuid.uuid4()}.pdf/../x"):
            with self.assertRaises(PrivateStorageError):
                self.storage().create_signed_download(bad)
        for payload in ({"signedURL": "https://evil.example/x"},
                        {"signedURL": "//evil.example/x"}, {"signedURL": "../private/x"},
                        [], {"bad": "shape"}):
            with self.assertRaises(PrivateStorageError):
                self.storage(FakeSession(FakeResponse(200, payload))).create_signed_download(key)
        with self.assertRaises(PrivateStorageError):
            self.storage(FakeSession(FakeResponse(200, ValueError("bad JSON")))).create_signed_download(key)

    def test_delete_removes_only_valid_opaque_object_keys(self):
        key = f"personnel/{uuid.uuid4()}/{uuid.uuid4()}.pdf"
        session = FakeSession()
        self.storage(session).delete(key)

        method, url, opts = session.calls[0]
        self.assertEqual(method, 'DELETE')
        self.assertIn(f'/storage/v1/object/private-hr/{key}', url)
        self.assertFalse(opts['allow_redirects'])

        invalid_session = FakeSession()
        with self.assertRaises(PrivateStorageError):
            self.storage(invalid_session).delete('../private/x.pdf')
        self.assertEqual(invalid_session.calls, [])

    def test_private_object_verification_checks_bytes_and_metadata(self):
        content = PDF
        key = f"personnel/{uuid.uuid4()}/{uuid.uuid4()}.pdf"
        session = FakeSession(FakeResponse(
            200,
            content=content,
            headers={"Content-Type": "application/pdf"},
        ))

        result = self.storage(session).verify_private_object(
            key,
            expected_sha256=hashlib.sha256(content).hexdigest(),
            expected_size=len(content),
            expected_content_type="application/pdf",
        )

        self.assertEqual(result.storage_key, key)
        self.assertEqual(result.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(result.size_bytes, len(content))
        self.assertEqual(result.content_type, "application/pdf")
        self.assertEqual(session.calls[0][0], "GET")
        self.assertFalse(session.calls[0][2]["allow_redirects"])

    def test_private_object_verification_rejects_metadata_mismatch(self):
        key = f"personnel/{uuid.uuid4()}/{uuid.uuid4()}.pdf"
        session = FakeSession(FakeResponse(
            200,
            content=PDF,
            headers={"Content-Type": "application/pdf"},
        ))

        with self.assertRaises(PrivateStorageError):
            self.storage(session).verify_private_object(
                key,
                expected_sha256="0" * 64,
                expected_size=len(PDF),
                expected_content_type="application/pdf",
            )


    def test_anonymous_policy_probe_accepts_denial_and_rejects_public_access(self):
        key = f"personnel/{uuid.uuid4()}/{uuid.uuid4()}.pdf"

        denied = FakeSession(FakeResponse(403, text='private provider detail'))
        self.assertTrue(self.storage(denied).verify_anonymous_denial(key))
        self.assertNotIn('headers', denied.calls[0][2])

        exposed = FakeSession(FakeResponse(200, content=PDF))
        with self.assertRaises(PrivateStorageError):
            self.storage(exposed).verify_anonymous_denial(key)

    def test_constructor_rejects_invalid_configuration(self):
        for values in ({"base_url": "http://example.com"}, {"bucket": "../bucket"},
                       {"timeout_seconds": 0}, {"max_bytes": 0}):
            opts = dict(base_url="https://project.supabase.co", api_key="k", bucket="b")
            opts.update(values)
            with self.assertRaises(PrivateStorageError):
                SupabasePrivateStorage(**opts)


if __name__ == "__main__":
    unittest.main()
