#!/usr/bin/env bash
# APM-BPJS regression gate — plan docs/superpowers/plans/2026-11-19-apm-bpjs-multichannel.md (Phase 0)
# Baseline 2026-11-19: 39 tests, OK, 1.996s (sebelum Phase 1) → kini 73 tests.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/Scripts/python.exe"
if [ ! -x "$PY" ]; then
  PY="python"
fi

DATABASE_URL='' DJANGO_DEBUG=true "$PY" manage.py test \
  pasien.tests_apm_models \
  pasien.tests_apm_views \
  pasien.tests_apm_security \
  pasien.tests_apm_whatsapp \
  pasien.tests_apm_bpjs_tasks \
  pasien.tests_apm_queue \
  pasien.tests_apm_ui \
  pasien.tests_apm_rujukan \
  pasien.tests_apm_rujukan_gate \
  pasien.tests_apm_bpjs_vclaim \
  pasien.tests_apm_igd_fasttrack \
  pasien.tests_apm_mobile \
  pasien.tests_apm_biometrik \
  pasien.tests_apm_whatsapp_templates \
  pasien.tests_apm_hardening \
  pasien.tests_estimasi \
  pasien.tests_pendaftaran_integrasi \
  --keepdb --noinput

DATABASE_URL='' DJANGO_DEBUG=true "$PY" manage.py makemigrations --check --dry-run