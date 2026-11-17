"""Unit tests for the DeepSeek-backed KTP OCR field extractor."""
from unittest import mock

from django.test import TestCase

from sdm.services import ktp_ocr


class ExtractKtpFieldsTests(TestCase):
    def _ai(self, data):
        return {'success': True, 'data': data, 'error': None}

    def _enable_ai(self):
        from akreditasi.system_models import SystemConfig
        config = SystemConfig.get_solo()
        config.ai_enabled = True
        config.ai_api_key = 'test-key-sk-12345'  # repository contract: any sk- token
        config.save()

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_happy_path_maps_all_fields(self, ai):
        self._enable_ai()
        ai.return_value = self._ai({
            'nik': '3204012509880003',
            'nama': 'Rina Kartika',
            'ttl': 'Bandung, 25-09-1988',
            'gender': 'P',
            'alamat': 'Jl. Melati No. 3 RT/RW 002/005, Cibaduyut, Bandung, Jawa Barat',
        })
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields['nik'], '3204012509880003')
        self.assertEqual(fields['nama_lengkap'], 'Rina Kartika')
        self.assertEqual(fields['tempat_lahir'], 'Bandung')
        self.assertEqual(fields['tanggal_lahir'], '1988-09-25')
        self.assertEqual(fields['gender'], 'PEREMPUAN')
        self.assertIn('Melati', fields['alamat'])

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_failure_returns_empty_strings(self, ai):
        ai.return_value = {'success': False, 'data': None, 'error': 'timeout'}
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields, {key: '' for key in ktp_ocr.KTP_OCR_FIELDS})

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_garbage_mapping_is_tolerated(self, ai):
        ai.return_value = self._ai({'nik': 12345, 'unexpected': 'x'})
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields['nik'], '')            # non-16-digit dropped
        self.assertEqual(fields['nama_lengkap'], '')

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_oversized_nik_is_returned_as_is(self, ai):
        """17 digits pass through raw; finalize validation is the gate, not OCR."""
        self._enable_ai()
        ai.return_value = self._ai({'nik': '32040125098800031'})
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        self.assertEqual(fields['nik'], '32040125098800031')

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_disabled_ai_short_circuits(self, ai):
        from akreditasi.system_models import SystemConfig
        config = SystemConfig.get_solo()
        config.ai_enabled = False
        config.save()
        fields = ktp_ocr.extract_ktp_fields(b'\xff\xd8\xffstub', actor=None)
        ai.assert_not_called()
        self.assertEqual(fields, {key: '' for key in ktp_ocr.KTP_OCR_FIELDS})

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_image_travels_as_a_content_part_not_as_prompt_text(self, ai):
        """The data URL must go through image_data_url, never into the prompt.

        Base64 inside the text prompt is invisible to the model's vision tower,
        so the extraction silently returned '' for every field.
        """
        self._enable_ai()
        ai.return_value = self._ai({'nik': '3204012509880003'})
        jpeg = b'\xff\xd8\xff\xe0' + b'\x00' * 16

        ktp_ocr.extract_ktp_fields(jpeg, actor=None)

        kwargs = ai.call_args.kwargs
        self.assertTrue(kwargs['image_data_url'].startswith('data:image/jpeg;base64,'))
        prompt = ai.call_args.args[0]
        self.assertNotIn('base64', prompt)
        self.assertNotIn('data:image', prompt)

    @mock.patch.object(ktp_ocr, '_call_deepseek')
    def test_png_upload_is_labelled_png(self, ai):
        self._enable_ai()
        ai.return_value = self._ai({})
        png = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b'\x00' * 16

        ktp_ocr.extract_ktp_fields(png, actor=None)

        self.assertTrue(ai.call_args.kwargs['image_data_url'].startswith('data:image/png;base64,'))
