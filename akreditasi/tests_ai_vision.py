"""Contract tests for image (vision) input on the DeepSeek channel.

The OCR services used to paste a base64 data URL into the *text* prompt. The
model never receives pixels that way, so every extraction came back empty.
These tests pin the payload shape that actually works: an ``image_url``
content part, with the MIME type matching the bytes.
"""
import base64
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from akreditasi import ai_service


PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
JPEG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 32


class BuildImageDataUrlTests(TestCase):
    def test_png_keeps_its_own_mime(self):
        url = ai_service.build_image_data_url(PNG_BYTES)
        self.assertTrue(url.startswith('data:image/png;base64,'))
        self.assertEqual(base64.b64decode(url.split(',', 1)[1]), PNG_BYTES)

    def test_jpeg_is_labelled_jpeg(self):
        self.assertTrue(ai_service.build_image_data_url(JPEG_BYTES).startswith('data:image/jpeg;base64,'))

    def test_empty_bytes_produce_no_url(self):
        self.assertEqual(ai_service.build_image_data_url(b''), '')


class CallDeepseekVisionTests(TestCase):
    def setUp(self):
        from akreditasi.system_models import SystemConfig
        config = SystemConfig.get_solo()
        config.ai_enabled = True
        config.ai_api_key = 'sk-vision-test-key'
        config.ai_model_name = 'deepseek-chat'
        config.save()

    @patch('akreditasi.ai_service.requests.post')
    def test_image_is_sent_as_content_part(self, mock_post):
        response = MagicMock()
        response.json.return_value = {'choices': [{'message': {'content': json.dumps({'nik': '3174092508930007'})}}]}
        mock_post.return_value = response

        url = ai_service.build_image_data_url(JPEG_BYTES)
        result = ai_service._call_deepseek('Baca KTP ini.', image_data_url=url)

        self.assertTrue(result['success'])
        sent = mock_post.call_args.kwargs['json']
        user_message = sent['messages'][1]
        self.assertIsInstance(user_message['content'], list)
        parts = {part['type']: part for part in user_message['content']}
        self.assertEqual(set(parts), {'text', 'image_url'})
        self.assertEqual(parts['image_url']['image_url']['url'], url)
        self.assertEqual(parts['text']['text'], 'Baca KTP ini.')

    @patch('akreditasi.ai_service.requests.post')
    def test_text_only_call_stays_a_plain_string(self, mock_post):
        response = MagicMock()
        response.json.return_value = {'choices': [{'message': {'content': json.dumps({'ok': True})}}]}
        mock_post.return_value = response

        ai_service._call_deepseek('Ringkas dokumen ini.')

        sent = mock_post.call_args.kwargs['json']
        self.assertEqual(sent['messages'][1]['content'], 'Ringkas dokumen ini.')

    @patch('akreditasi.ai_service.requests.post')
    def test_no_base64_leaks_into_the_prompt_text(self, mock_post):
        response = MagicMock()
        response.json.return_value = {'choices': [{'message': {'content': json.dumps({'ok': True})}}]}
        mock_post.return_value = response

        ai_service._call_deepseek('Baca KTP.', image_data_url=ai_service.build_image_data_url(JPEG_BYTES))

        sent = mock_post.call_args.kwargs['json']
        text_part = sent['messages'][1]['content'][0]['text']
        self.assertNotIn('base64', text_part)
        self.assertNotIn('data:image', text_part)
