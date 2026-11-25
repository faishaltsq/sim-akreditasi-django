"""F8.2 — aturan "asesmen awal terisi" untuk deep-link tombol SOAP dasbor.

Matriks §5 (Bagian F) memberi satu tombol SOAP dua target: Langkah 2 bila
asesmen awal perawat (Langkah 1–6) belum terisi, Langkah 8 bila sudah terisi.
Aturan itu ditulis **satu kali** di sini dan dipakai dua tempat:

* ``rajal_dashboard`` menentukan target tautan tombol SOAP per baris;
* ``igd_finalization.missing_rajal_sections`` menentukan langkah mana yang
  masih kurang sebelum finalisasi.

Definisi "minimal terisi" tidak dikarang: sebuah langkah dianggap terisi bila
``draft_payload``-nya memuat **satu nilai saja** yang tidak kosong. Itu
predikat yang sudah dipakai penjaga finalisasi sejak F1, jadi tombol dan
gerbang finalisasi tidak dapat berbeda pendapat.

Langkah yang dikecualikan (``exemptions['step_N']``) dihitung terpenuhi,
persis seperti di penjaga finalisasi: pengecualian resmi berarti langkah itu
tidak lagi dituntut.
"""
from dataclasses import dataclass

from pasien.workflow_schemas import RAJAL_JANTUNG_STEP_NUMBERS

#: Langkah "asesmen awal perawat" yang menentukan target tombol SOAP.
EARLY_STEP_NUMBERS = tuple(number for number in RAJAL_JANTUNG_STEP_NUMBERS if number <= 6)

#: Target saat Langkah 1–6 belum minimal terisi — Skrining & cara datang.
SOAP_ENTRY_STEP = 2
#: Target saat Langkah 1–6 sudah minimal terisi — Diagnosis & rencana.
SOAP_CLINICAL_STEP = 8

_EMPTY = (None, '', [], {})

def step_minimally_filled(values):
    """True bila satu nilai pada langkah ini tidak kosong.

    ``values`` adalah isi ``draft_payload['<langkah>']``. Nilai kosong yang
    diakui sama dengan penjaga finalisasi: ``None``, string kosong, daftar
    kosong, dan objek kosong.
    """
    if not isinstance(values, dict):
        return False
    return any(value not in _EMPTY for value in values.values())

@dataclass(frozen=True)
class PoliCompleteness:
    """Hasil penilaian Langkah 1–6 untuk satu episode POLI-JANTUNG."""

    filled_steps: tuple
    missing_steps: tuple

    @property
    def complete(self):
        return not self.missing_steps

    @property
    def soap_step(self):
        """Langkah tujuan tombol SOAP: 8 bila lengkap, 2 bila belum."""
        return SOAP_CLINICAL_STEP if self.complete else SOAP_ENTRY_STEP

def poli_completeness(workflow):
    """Nilai Langkah 1–6 episode; ``workflow=None`` berarti belum ada isian."""
    draft = (workflow.draft_payload or {}) if workflow is not None else {}
    exemptions = (workflow.exemptions or {}) if workflow is not None else {}
    filled, missing = [], []
    for number in EARLY_STEP_NUMBERS:
        if f'step_{number}' in exemptions or step_minimally_filled(draft.get(str(number))):
            filled.append(number)
        else:
            missing.append(number)
    return PoliCompleteness(tuple(filled), tuple(missing))
