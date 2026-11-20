# APM-BPJS Multi-Channel Admission — Implementation Plan

- **Date:** 2026-11-19
- **Analysis:** `docs/superpowers/specs/2026-11-19-apm-bpjs-multichannel-gap-analysis.md`
- **Source requirement:** `PRD_FSD_Modul_Admisi_Mandiri_APM_BPJS_ARima_Revisi.docx` (BL-01..BL-12, RSK-APM-01..04)
- **Goal:** turn the existing on-site kiosk into the PRD's multi-channel module: no-login mobile booking from home, BPJS referral validation and claim-compliance blocking, doctor examination-time estimation with dynamic shift, three WhatsApp templates, biometric gate with 3-strike escalation, isolated IGD fast-track, and `LOG_RISIKO_APM` telemetry into ARima.
- **Non-goals:** rewriting the existing kiosk UI from scratch, replacing `RisikoUnit` PDCA register, e-claim/klaim submission flows, SatuSehat encounter sync, billing/tariff changes.

## Decisions applied

| ID | Decision |
|---|---|
| D1 | All BPJS calls go through `pasien/services/bpjs_vclaim.py`. `pasien/bpjs.py` stays as a thin shim delegating to it, so `pasien/views.py:3153-3166` and existing tests keep working. |
| D2 | The mobile channel is a separate route set guarded by a signed capability token (`django.core.signing`, salt `apm-mobile`), never a login session. Same pattern already proven for receipts (`apm_views.py:449`). |
| D3 | One pure estimation function in `pasien/services/estimasi.py` used by mobile, kiosk, thermal receipt, and WhatsApp. No second copy of the formula anywhere. |
| D4 | Biometrics is an adapter (`BiometricGateway`) with `simulated` and `device` modes; the vendor protocol is not invented. `simulated` mode must be visibly marked in UI and must not be claimed as compliance evidence. |
| D5 | WhatsApp goes through a provider abstraction (`FonnteProvider`, `WabaCloudProvider`) with 3 retries, per-number throttle, and an idempotency key per `(kunjungan, jenis_pesan, estimasi_versi)`. |
| D6 | Bridging failure is fail-closed: no SEP is issued, the user sees an explicit `BRIDGING_DOWN` state, `RSK-APM-04` is logged, and the patient is routed to the admission counter. No silent fallback to simulated SEP. |
| D7 | `LogRisikoApm` is append-only. Aggregation into `RisikoUnit` is a separate, explicit action — never an automatic write into the accreditation register. |
| D8 | Dynamic configuration lives in the database (`KonfigurasiApm`, `KonfigurasiBiometrikPoli`), not in `settings.py` and not hardcoded in templates. |

## Invariants (must hold at every phase boundary)

1. **No regression on the existing kiosk.** `pasien.tests_apm_*` and `pasien.tests_pendaftaran_integrasi` stay green after every phase.
2. **No fabricated clinical/financial identifiers.** A SEP number, referral number, or BPJS queue number is either the real bridged value or explicitly marked simulated with `mode` surfaced to the caller. `pasien/views.py:1670` must stop generating SEP numbers.
3. **Identity rule unchanged.** Every lookup and mutation still requires the two-identifier match (`_matches_identity`, `apm_views.py:23`) plus CSRF on POST.
4. **Single writer per fact.** `allocate_queue_number` remains the only ticket allocator; `update_task_id` remains the only Task ID writer; SEP issuance happens in exactly one service function.
5. **Green workspace per phase.** Each phase ends with the affected modules passing and `makemigrations --check --dry-run` clean.
6. **Every phase that touches patient-facing latency logs it.** If a phase affects registration time, it emits `LogRisikoApm`/duration fields it needs, or the SLA claim is not made.

---

## Execution ledger

| Phase | Status | Evidence |
|---|---|---|
| 0.1 baseline | ✅ done | `39 tests, OK, 1.996 s` (2026-11-19, `--keepdb`) |
| 0.2 regression script | ✅ done | `scripts/apm_regression.sh` — **243 tests, OK, 47.2 s** + `makemigrations --check` → `No changes detected` |
| 0.3 VClaim contract fixtures | ✅ done | `pasien/fixtures/vclaim/` — 8 JSON (rujukan FKTP/RS/not-found, SEP ok/meta-error, antrean add/updatewaktu, peserta aktif/nonaktif) |
| 1 data foundation | ✅ done | `RujukanBpjs`, `KonfigurasiApm`, `KonfigurasiBiometrikPoli`, `AppendOnlyModel` + `LogBiometrik` + `LogRisikoApm`, 11 new `KunjunganPasien` fields, `uniq_sep_per_visit` partial unique index; migrations 0033/0035 |
| 2 VClaim service | ✅ done | `pasien/services/bpjs_vclaim.py` (`BridgingError`, HMAC, XOR envelope decrypt, `validasi_peserta`, `validasi_rujukan`, `terbitkan_sep` on `/SEP/2.0/insert`, `daftar_antrean_bpjs` on `/antrean/add`, `mapping_jadwal`); `pasien/bpjs.py` reduced to a shim; `cetak_sep` no longer fabricates numbers (409 + `*** SIMULASI ***` watermark) |
| 3 IGD fast-track | ✅ done | `POST /pasien/apm/api/igd-fasttrack/` (nama saja, tanpa rujukan/biometrik, ukur durasi, `RSK-APM-01`), tombol merah di beranda kiosk, migration 0034 `MERAH`→`KRITIS` |
| 4 referral gate | ✅ done | `pasien/services/rujukan.py` (`parse_nomor_rujukan`, `parse_qr_rujukan`, `evaluate_rujukan`, precedence pinned), `POST /apm/api/rujukan/validasi/`, BPJS rajal blocked in `services/pendaftaran.py` with `RSK-APM-02`/`RSK-APM-04` |
| 5 estimation engine | ✅ done | `pasien/services/estimasi.py` (`hitung_estimasi`, clamp `T_buka_rs`, `Delta_geser`, `EstimasiOverflow`), `recompute_for_schedule` + `manage.py geser_jadwal`, late check-in re-estimation + Templat 3 |
| 6 mobile portal | ✅ done | `pasien/mobile_views.py` + `/pasien/mandiri/*` (verifikasi dua-faktor, capability token, jadwal, booking, tiket, QR SVG), signed QR accepted by kiosk check-in |
| 7 WhatsApp | ✅ done | 3 PRD templates verbatim, multi-RS name from `RumahSakitProfile.name`, masking, Fonnte/WABA/SIMULASI providers, retry w/ backoff, idempotency key, per-(number, template) throttle |
| 8 SEP at check-in | ✅ done | `_proses_bpjs_checkin`: antrean → SEP → Task ID 3 → Templat 2; fail-closed sets `sep_mode='GAGAL'`, no SEP printed, `RSK-APM-04` |
| 9 biometric gate | ✅ done | `pasien/services/biometrik.py` adapter (`SIMULASI` marked, `DEVICE` raises), `POST /apm/api/biometrik/`, server-side gate in check-in, 3-strike helpdesk ticket + `RSK-APM-03` |
| 10 public hardening | ✅ done | `pasien/services/throttle.py` + `ThrottleCounter` (migration 0036), 429 + `Retry-After`, `services/masking.py` on public JSON, global kiosk idle timer + `POST /apm/api/sesi/reset/`, bridging-down screen path |
| 11 risk & indicators | ✅ done | `services/indikator.py` (median/p90 registration, SEP live/sim/gagal, biometric compliance, referral blocks, WA delivery), `manage.py apm_indikator`, staff-only `/pasien/apm/indikator/` |

**Deviations from the written plan (deliberate, each covered by a test):**
1. `Pasien.tanggal_lahir` became nullable (migration 0035) — emergency registration must not fabricate a birth date; `Pasien.umur` already guarded `None`.
2. `KunjunganPasien.tanggal_kunjungan` is filled in `save()` (naive datetimes from legacy callers are tolerated via `timezone.is_naive`).
3. WhatsApp throttle keys on `(number, jenis_pesan)` so SEP and shift notifications in one check-in do not block each other.
4. Template 1 carries one extra trailing line with the T-60 cancellation link (existing ARima feature); the PRD body itself is verbatim and pinned by tests.
5. Referral OCR is out of scope this cycle: intake is typed 19-digit or QR payload; OCR needs a standardized referral layout.
6. Mobile booking is same-day only until `KonfigurasiApm.booking_hari_ke_depan` is set (>0) and future-date queries are audited.

---

## Production verification (2026-11-20, Vercel + Supabase `sim-akreditasi`)

Deploy = `git push origin master` → Vercel production build (~31 s). `config/wsgi.py:_auto_migrate()` applies pending migrations on cold start, so migrations 0033–0036 landed without a manual step (`django_migrations` verified via Supabase).

Live checks against `https://sim-akreditasi-django.vercel.app`:

| Check | Result |
|---|---|
| `GET /pasien/apm/` | 200, `Cache-Control: no-store`, berisi tombol IGD + biometrik + `IDLE_DETIK = 90` |
| `GET /pasien/mandiri/` | 200, form verifikasi tampil |
| `GET /pasien/apm/api/jadwal-dokter/` | 200, 4 jadwal (JTG/ANA/INT/THT) setelah seed |
| `GET /pasien/apm/indikator/` | 302 (staf-only) |
| `GET /pasien/apm/api/sesi/reset/`, `/api/biometrik/` | 405 (POST-only) |
| `GET /admin-sikai-7f3d/login/` | 200 |
| `POST /apm/api/igd-fasttrack/` | 200, `IGD-001`/`IGD-002`, triage MERAH, 0.11 s |
| Mobile: verifikasi → booking UMUM | 302 → tiket 200, antrean `ANK-001`, QR SVG 78 KB |
| Mobile: booking BPJS tanpa rujukan | 409 `RUJUKAN_WAJIB` + `RSK-APM-02` |
| Mobile: booking BPJS + rujukan dummy | 302; check-in 200 dengan `sep.success=false`, `NOT_CONFIGURED`, jalur `LOKET_ADMISI`, `sep_mode='GAGAL'` (fail-closed terbukti di produksi) |
| Biometrik: booking POLI_THT → check-in | 409 `BIOMETRIK_BELUM_VALID` → verifikasi `VALID` (mode SIMULASI) → check-in 200, `THT-001` |

Data seed produksi (dummy): 4 jadwal dokter dengan kode poli/dokter BPJS, 4 aturan wajib biometrik (THT, MATA, JANTUNG, REHAB_MEDIK), `KonfigurasiApm` diset eksplisit (07:00 / 30 / 15 / 90 s / 3x / FONNTE / retry 3). Belum ada kredensial `BPJS_*` maupun `FONNTE_TOKEN` di Vercel, sehingga seluruh jalur bridging/WA berjalan simulasi dan SEP sengaja tidak terbit.

---

## Phase 0 — Baseline & safety net (no behaviour change)

### 0.1 Record the baseline

```
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test \
  pasien.tests_apm_models pasien.tests_apm_views pasien.tests_apm_security \
  pasien.tests_apm_whatsapp pasien.tests_apm_bpjs_tasks pasien.tests_apm_queue \
  pasien.tests_apm_ui --keepdb --noinput
```

Measured 2026-11-19: **Ran 39 tests, OK, 1.996 s**. Any later run deviating from this count is a regression signal, not a flake.

### 0.2 Pin the regression set

Add `scripts/apm_regression.sh` (bash, repo-relative) running the command above plus `pasien.tests_pendaftaran_integrasi`. Every phase gate calls it. Do not add it to CI until Phase 3 lands.

### 0.3 Lock the fixture contract for VClaim

Create `pasien/fixtures/vclaim/` (not `pasien/tests/` — `pasien/tests.py` already exists as a module, so a package of that name cannot coexist) with recorded-shape JSON for: `Rujukan/Peserta`, `Rujukan/RS/Peserta`, `Rujukan/List/Peserta`, `SEP/2.0/insert` (success + `metaData.code != 200`), `antrean/add`, `antrean/updatewaktu`. These are **contract shapes**, not captured production data: no real patient identifiers, `noKartu`/`noRujukan` replaced with synthetic values. All later live-mode tests run against these.

**Exit criteria:** regression script exists, is executable, and passes.

---

## Phase 1 — Data foundation (BL-02/03/05/08/09/12 prerequisites)

### Task 1.1 `RujukanBpjs` model

**Files:** `pasien/models.py`, `pasien/migrations/0033_apm_bpjs_multichannel.py`, `pasien/tests_apm_rujukan.py`

**Interfaces:**
- Consumes: `Pasien`
- Produces: `RujukanBpjs` with fields `pasien` (FK), `no_rujukan` (CharField 32, unique, db_index), `jenis_rujukan` (`FKTP`/`ANTAR_FKRTL`/`KONTROL`/`RS`), `tgl_rujukan` (DateField), `tgl_kunjungan_rencana` (DateField, null), `ppk_rujukan` (CharField 20), `nama_ppk_rujukan`, `ppk_tujuan` (CharField 20), `poli_tujuan_bpjs` (CharField 10), `diagnosa_awal` (CharField 10), `nama_diagnosa_awal`, `status_validasi` (`VALID`/`KEDALUWARSA`/`BEDA_PPK`/`TIDAK_DITEMUKAN`/`TIDAK_AKTIF`), `alasan_tolak` (TextField), `raw_response` (JSONField), `divalidasi_pada` (DateTimeField), `divalidasi_oleh_kanal` (`MOBILE`/`KIOSK`/`LOKET`/`SISTEM`).
- Produces: `RujukanBpjs.masa_berlaku_hari()` returning `(tgl_kunjungan - tgl_rujukan).days`, and a `STATUS` property that never recomputes validity from `timezone.now()` inside a template.

**Test-first:**
```python
def test_rujukan_90_hari_dihitung_dari_tanggal_kunjungan(self):
    r = RujukanBpjs(..., tgl_rujukan=date(2026, 8, 1), tgl_kunjungan_rencana=date(2026, 11, 1))
    self.assertEqual(r.masa_berlaku_hari(), 92)
    self.assertEqual(r.status_dari_aturan(ppk_rs='0123R001'), 'KEDALUWARSA')

def test_rujukan_beda_ppk_menang_atas_kedaluwarsa(self):
    # order of precedence must be explicit and pinned
```
Pin the precedence order: `TIDAK_DITEMUKAN → TIDAK_AKTIF → BEDA_PPK → KEDALUWARSA → VALID`. Write the test that fails if someone reorders it.

### Task 1.2 Extend `KunjunganPasien`

**Produces on `KunjunganPasien`:** `rujukan` (FK `RujukanBpjs`, null), `no_sep` (CharField 40, blank, db_index), `sep_terbit_pada`, `sep_mode` (`LIVE`/`SIMULASI`/`GAGAL`), `no_referensi_antrean` (CharField 40), `estimasi_versi` (PositiveSmallInteger default 0), `delta_geser_menit` (SmallInteger default 0), `biometrik_status` (`TIDAK_WAJIB`/`MENUNGGU`/`VALID`/`GAGAL`/`ESKALASI`), `registrasi_mulai_at`, `registrasi_selesai_at`, `tanggal_kunjungan` (DateField, null, db_index).

**Constraint:** `UniqueConstraint(fields=['no_sep'], condition=Q(no_sep__gt=''), name='uniq_sep_per_visit')` — idempotency for SEP (D6/BL-07).

**Test-first:** a visit with the same `no_sep` twice raises `IntegrityError`; `tanggal_kunjungan` defaults to `tanggal_masuk__date` in `save()` when null but is never overwritten once set.

### Task 1.3 Configuration models

**Produces:** `KonfigurasiApm` (singleton-ish, per `RumahSakitProfile`): `t_buka_rs` (TimeField default 07:00), `buffer_tiba_menit` (default 30), `ambang_geser_notif_menit` (default 15), `idle_timeout_detik` (default 90, validators 60..90), `biometrik_maks_percobaan` (default 3), `booking_hari_ke_depan` (default 0), `wa_provider`, `wa_retry_maks` (default 3).

**Produces:** `KonfigurasiBiometrikPoli`: `poliklinik` (choices `POLIKLINIK_CHOICES`), `wajib_biometrik`, `usia_min_pengecualian`, `usia_max_pengecualian`, `pengecualian_status_peserta` (JSON list), `aktif`. **`unique_together = ('poliklinik',)` for active rows** — enforce in `clean()`, because Django cannot express partial unique on booleans portably across SQLite/Postgres.

**Produces:** `LogBiometrik` and `LogRisikoApm` (append-only; override `save()` to reject updates on non-null `pk`).

### Task 1.4 Admin + seed

**Files:** `pasien/admin.py`, `pasien/management/commands/seed_konfigurasi_apm.py`

Seed: `KonfigurasiApm` row, biometric rows for `POLI_THT`, `POLI_MATA`, `POLI_JANTUNG`, `REHAB_MEDIK` (per PRD), and a `--force` flag that never overwrites edited values without it.

**Exit criteria:** migration applies on a fresh DB and on `--keepdb`; `makemigrations --check --dry-run` clean; regression script green.

---

## Phase 2 — VClaim service rewrite (BL-02/03/07/BL-11 foundation)

### Task 2.1 `pasien/services/bpjs_vclaim.py`

**Interfaces:**
- Produces: `class BridgingError(Exception)` with `.status` in `('TIMEOUT','HTTP_ERROR','META_ERROR','NOT_CONFIGURED')`, `.meta_code`, `.meta_message`, `.raw`.
- Produces: `def call(path, method='GET', payload=None, timeout=10) -> dict` — builds HMAC headers, decodes the BPJS `response` XOR+base64 envelope when `metaData.code == '200'`, and **raises `BridgingError` instead of returning a fabricated success**.
- Produces: `def validasi_rujukan(no_rujukan, kode_ppk_rs, tanggal_kunjungan) -> dict` calling `Rujukan/Peserta/{no}` then falling back to `Rujukan/RS/Peserta/{no}` when the first returns an empty `response` (referral to hospital), mapping into `RujukanBpjs` field names.
- Produces: `def validasi_peserta(no_kartu, tanggal) -> dict` (`/Peserta/nokartu/{no}/tgl/{tgl}`).
- Produces: `def terbitkan_sep(kunjungan) -> dict` calling **`/SEP/2.0/insert`** with the full payload: `noKartu`, `tglSep`, `ppkPelayanan`, `jnsPelayanan`, `klsRawat`, `noMR`, `rujukan.noRujukan/asalRujukan/tglRujukan/ppkRujukan`, `catatan`, `diagnosa.kode`, `poliTujuan`, `klaim`, `dpjpLayan`.
- Produces: `def daftar_antrean_bpjs(kunjungan) -> dict` calling `/antrean/add` with the v2 field set (`kodebooking`, `jenispasien`, `nomorkartu`, `nik`, `nohp`, `kodepoli`, `namapoli`, `pasienbaru`, `norm`, `tanggalperiksa`, `kodedokter`, `jampraktek`, `jeniskunjungan`, `nomorreferensi`/`nomorrujukan`), returning `kodebooking` + queue number.
- Produces: `def jadwal_dokter_bpjs(kodepoli, tanggal) -> list` (`/jadwaldokter/kodepoli/{kode}/tanggal/{date}`).
- Produces: `def health() -> dict`.

**Test-first (live mode forced with `override_settings`):**
```python
def test_meta_data_non_200_raises_bridging_error(self):
    with self.assertRaises(BridgingError) as ctx:
        with mocked_response(self.FIXTURE_rujukan_not_found):
            validasi_rujukan('1234567890123456789', '0123R001', date.today())
    self.assertEqual(ctx.exception.status, 'META_ERROR')
    self.assertEqual(ctx.exception.meta_code, '201')

def test_timeout_is_not_swallowed_into_a_valid_referral(self):
    ...
def test_simulated_mode_marks_mode_and_never_claims_valid(self):
    ...
```
The second test is the one that matters: the current code (`bpjs.py:111-128, 168-178`) swallows every exception and returns a plausible simulated result.

### Task 2.2 Retire fabricated SEP, shim old callers

**Files:** `pasien/bpjs.py`, `pasien/views.py`

- `bpjs.buat_sep(kunjungan)` delegates to `bpjs_vclaim.terbitkan_sep`, persists `no_sep`/`sep_mode`, and returns `mode`.
- `cetak_sep` (`views.py:1670`) renders `k.no_sep` and prints a visible `*** SIMULASI ***` watermark when `k.sep_mode != 'LIVE'`; if `no_sep` is empty it refuses with 409 and a message instead of inventing one.
- `ambil_antrean` delegates to `daftar_antrean_bpjs` (dead-code payload deleted).

**Test-first:** `test_cetak_sep_refuses_when_no_sep_absent`, `test_cetak_sep_marks_simulation`, `test_buat_sep_persists_no_sep_and_mode`, `test_legacy_buat_sep_still_returns_dict_contract`.

### Task 2.3 Poli / doctor BPJS mapping

**Produces:** `JadwalDokterPoli.kode_poli_bpjs` (CharField 10), `JadwalDokterPoli.kode_dokter_bpjs` (PositiveBigInteger, null), `JadwalDokterPoli.jam_praktek_bpjs` property (`"HH:MM-HH:MM"`).

**Test-first:** a schedule without `kode_poli_bpjs` refuses BPJS registration with a typed error (`MAPPING_MISSING`), instead of sending `"INT"`/`"0000000"` defaults.

**Exit criteria:** every live-mode path either returns real data or raises `BridgingError`; zero code paths fabricate SEP/referral numbers; regression script green.

---

## Phase 3 — IGD Fast-Track isolation (BL-01, RSK-APM-01)

### Task 3.1 Emergency endpoint

**Files:** `pasien/apm_views.py`, `pasien/urls.py`, `templates/pasien/apm/kiosk.html`, `pasien/tests_apm_igd_fasttrack.py`

**Produces:** `POST /pasien/apm/api/igd-fasttrack/` accepting the minimum viable identity (`nama_lengkap` required; `tanggal_lahir` optional; `nik`/`no_bpjs`/`no_wa` optional). Behaviour:
1. No referral validation, no biometric check, no schedule lookup, no `_matches_identity` requirement.
2. Resolves the patient by `nik`/`no_bpjs` when provided **and** the name matches loosely; otherwise creates a placeholder patient (`nama_lengkap` + `no_rm` `RM-IGD-{YYYYMMDD}-{seq}`) flagged `is_igd_placeholder` (add field in Phase 1 migration if not already; if narrowed, use `catatan_admisi='REGISTRASI_DARURAT'`).
3. Creates `KunjunganPasien` with `jenis_kunjungan='IGD'`, `flag_khusus='KRITIS'`, `triage='MERAH'`, `status_antrean='MENUNGGU'`, `registrasi_mulai_at`/`registrasi_selesai_at` set.
4. Writes `LogRisikoApm(kode_risiko='RSK-APM-01', kanal='KIOSK')`.
5. Returns `target_terpenuhi = (selesai - mulai) <= 120` seconds and surfaces it in the response.
6. Fires the existing `format_notifikasi_igd` WhatsApp + nurse-station alert.

> Note: existing kiosk sets `flag_khusus='MERAH'`, but `FLAG_KHUSUS_CHOICES` (`models.py:364`) is `NORMAL/AMBULANS/KRITIS` — `'MERAH'` is not a valid choice value and is only tolerated because Django does not validate on `save()`. Fix to `'KRITIS'` and add a data migration rewriting existing rows.

**Test-first:** `test_fasttrack_requires_only_name`, `test_fasttrack_bypasses_referral_and_biometrics`, `test_fasttrack_sets_triage_merah_and_kritis_flag`, `test_fasttrack_logs_rsk_apm_01`, `test_fasttrack_records_registration_duration`, `test_fasttrack_is_rate_limited_later_in_phase_10` (skipped until Phase 10).

### Task 3.2 Beranda kiosk

Move the IGD button to the welcome screen as a full-width red block **above** the three entry buttons, with copy: "GAWAT DARURAT — langsung ke IGD, tanpa rujukan & tanpa antrean poli". Remove the current instruction text (`kiosk.html:24`) that requires identity first. Keep the identity form for the outpatient paths only.

**Exit criteria:** IGD registration completes with a single name field; no referral/biometric call occurs on that path (assert with mocked services that raise if called); duration is measured and returned; `flag_khusus='KRITIS'` data migration applied.

---

## Phase 4 — Referral compliance gate (BL-02, BL-03, RSK-APM-02)

### Task 4.1 Referral intake

**Files:** new `pasien/services/rujukan.py`, `pasien/apm_views.py`, `templates/pasien/apm/*`, `pasien/tests_apm_rujukan_gate.py`

**Produces:** `parse_nomor_rujukan(raw) -> str` accepting 19 digits (strip spaces/dashes) and rejecting anything else with `RujukanFormatError`. **OCR of the referral photo is not in scope for this phase** — the PRD allows "scan QR / upload / type"; implement typed 19-digit + QR payload parsing (`parse_qr_rujukan` reading `noRujukan`/`noKartu` keys or plain digits) now, and add OCR as a follow-up task behind the existing KTP OCR pipeline only if the referral letter format is standardized. Record this scoping decision explicitly.

**Produces:** `evaluate_rujukan(rujukan, kode_ppk_rs, tanggal_kunjungan) -> HasilValidasi` — pure function over a `RujukanBpjs`-shaped object returning `(status, alasan, boleh_lanjut, jalur_alternatif)`.

**Test-first (table-driven, one test per PRD row):**
| Case | Expected |
|---|---|
| referral 91 days old | `KEDALUWARSA`, `boleh_lanjut=False`, `jalur_alternatif='PERBARUI_FKTP'` |
| referral exactly 90 days | `VALID` |
| `ppk_tujuan != kode_ppk_rs` | `BEDA_PPK`, alternative `'LOKET_INFORMASI'`, message names the recorded facility |
| referral absent in VClaim | `TIDAK_DITEMUKAN`, alternative `'LOKET_INFORMASI'` |
| participant inactive | `TIDAK_AKTIF`, alternative `'LOKET_ADMISI'` |
| bridging timeout | `BRIDGING_DOWN`, `boleh_lanjut=False`, `RSK-APM-04` logged, alternative `'LOKET_ADMISI'` |

### Task 4.2 Enforce at booking

**Produces:** `/pasien/apm/api/rujukan/validasi/` (POST, CSRF, dual-identity not required pre-booking but rate-limited in Phase 10) returning the `HasilValidasi` plus masked participant name.

**Produces:** in `apm_api_daftar`, when `penjamin == 'BPJS'` and `jenis_layanan == 'RAJAL'`:
- require a `rujukan` that evaluates `VALID` for the chosen `tanggal_kunjungan`;
- lock `diagnosa_awal`, `ppk_rujukan`, `tgl_rujukan` into the visit (`diagnosa_masuk`, and new read-only fields surfaced in templates);
- otherwise return `409` with `{status, alasan, jalur_alternatif}` and log `RSK-APM-02`.

**Test-first:** `test_bpjs_booking_blocked_without_valid_referral`, `test_expired_referral_returns_409_and_logs_rsk_apm_02`, `test_umum_booking_unaffected`, `test_locked_fields_cannot_be_overridden_by_request_body` (POST `diagnosa_masuk='X'` must not survive).

**Exit criteria:** no BPJS outpatient visit can be created without a `VALID` referral; every block writes exactly one `LogRisikoApm` row; the alternative path is rendered, not just a string.

---

## Phase 5 — Estimation engine (BL-05)

### Task 5.1 Pure function

**Files:** new `pasien/services/estimasi.py`, `pasien/models.py` (delegate), `pasien/tests_estimasi.py`

**Produces:**
```python
@dataclass(frozen=True)
class Estimasi:
    mulai_praktik: time
    nomor_antrean: int
    durasi_menit: int
    delta_geser_menit: int
    t_periksa: time
    t_tiba: time
    tiba_di_clamp: bool
    versi: int

def hitung_estimasi(*, t_mulai, n, d_rata, delta_geser=0, t_buka_rs, buffer_tiba=30) -> Estimasi
```
Rules pinned by tests:
- `t_periksa = t_mulai + (n-1)*d_rata + delta_geser`
- `t_tiba = max(t_periksa - buffer, t_buka_rs)` — clamp, `tiba_di_clamp=True` when it fires
- `n >= 1`, `d_rata >= 1`, `delta_geser` may be negative but `t_periksa >= t_mulai` is **not** enforced (a doctor starting early is legitimate) — instead assert `t_periksa >= 00:00` and that day-rollover beyond `23:59` raises `EstimasiOverflow`
- midnight/day-rollover handled by working on `datetime.combine` + `date`, never on bare `time`

**Test-first:** the PRD's own worked example (`08:00, N=5, D=10 → 08:40, tiba 08:10`), the clamp case (`N=1, 08:00 → tiba 07:30` must become `t_buka_rs`), the shift case (`delta=15`), and `test_model_and_service_agree` asserting `JadwalDokterPoli.hitung_estimasi_jam` delegates to the service (not a second implementation).

### Task 5.2 Persist version and recompute on shift

**Produces:** `services/estimasi.recompute_for_schedule(jadwal, tanggal, delta_geser, alasan) -> list[KunjunganPasien]` — recomputes only for visits with `status_antrean='MENUNGGU'` and not yet called, bumps `estimasi_versi`, writes `delta_geser_menit`, and queues `PERGESERAN_JADWAL` WhatsApp **only when `abs(delta) >= ambang_geser_notif_menit`**.

**Produces:** admin action / management command `geser_jadwal --jadwal <id> --tanggal <date> --delta 20` to be used by the clinic nurse; guard against negative quota.

**Test-first:** already-called visits untouched; `delta=14` sends no message; `delta=15` sends exactly one per visit; `estimasi_versi` increments monotonically; rerunning the same delta is idempotent (same version, no duplicate WA — depends on Phase 7 idempotency key; until then assert `WhatsAppLog` count).

### Task 5.3 Late check-in

**Produces:** in check-in, when `now > t_periksa` and the visit is still `MENUNGGU`, recompute the estimate against the **last active queue position in the polyclinic** and return `estimasi_baru` + `terlambat=True`; print/notify the adjusted estimate.

**Exit criteria:** one formula in the codebase; kiosk ticket, thermal receipt, and WhatsApp all show identical `t_periksa`/`t_tiba` for the same visit (assert by rendering all three in one test).

---

## Phase 6 — Mobile no-login portal (BL-04)

### Task 6.1 Routes and capability

**Files:** `pasien/mobile_views.py`, `pasien/urls.py`, `templates/pasien/mobile/*`, `pasien/tests_apm_mobile.py`

**Produces:** `POST /pasien/mandiri/verifikasi/` — inputs `identitas` (NIK or No. BPJS), `tanggal_lahir`, `no_wa`. On success returns a signed capability token (salt `apm-mobile`, payload `{pasien_id, no_wa_hash, issued_at}`) plus masked name. **Failure response is always the same generic message and the same status** (reuse the pattern from `tests_apm_security.test_wrong_identity_and_unknown_identifier_have_same_response`).

**Produces:** `GET /pasien/mandiri/` (form), `GET /pasien/mandiri/jadwal/?token=`, `POST /pasien/mandiri/booking/`, `GET /pasien/mandiri/tiket/?token=`, `GET /pasien/mandiri/qr/<signed>/`.

Rules pinned by tests:
- token is required on every step after verification and is bound to the `pasien_id` that requested it (cross-patient replay → 403);
- token expiry = end of the scheduled visit's clinic hours (`jam_selesai`) + 2 h, never indefinite;
- `no_wa` must be re-verified before booking mutates anything;
- mobile booking reuses `apm_api_daftar` logic through a shared service, **not** a second implementation of patient resolution (extract `services/pendaftaran.py:daftarkan()` in this phase and have both views call it).

### Task 6.2 QR check-in binding

**Produces:** QR payload = signed compact token containing `kode_booking` + `pasien_id` + expiry, rendered with the existing `QrCodeWidget` path (`apm_views.py:455`). Kiosk check-in must accept either the QR payload or the plain `kode_booking`, and must reject a QR whose signature or expiry fails with the same 403 as an unknown code.

**Test-first:** `test_qr_with_valid_signature_checks_in`, `test_tampered_qr_rejected`, `test_expired_qr_rejected`, `test_plain_booking_code_still_works`, `test_qr_bound_to_other_visit_rejected`.

**Exit criteria:** a patient can complete verification → schedule → booking → ticket → kiosk check-in against a scratch SQLite DB driven by a browser, with no login and no duplicate patient record; the `pasien` row count is unchanged for an existing patient.

---

## Phase 7 — WhatsApp: 3 templates, provider abstraction, retry (BL-06)

### Task 7.1 Provider layer

**Files:** new `pasien/services/wa_provider.py`, rewrite `pasien/services/whatsapp.py`, `pasien/tests_apm_whatsapp.py`

**Produces:** `send(nomor, pesan, *, idempotency_key, provider=None) -> SendResult` with:
- provider selected by `KonfigurasiApm.wa_provider` (`FONNTE` default, `WABA` optional);
- normalization to `62…`, rejection of non-Indonesian length (test: `'12345'`, `'+62 812-3456-7890'`, `'0812 3456 7890'` all resolve correctly or fail loudly);
- retry max 3 with 1 s/3 s/7 s backoff, recorded as `percobaan` on `WhatsAppLog`;
- per-number throttle (default 1 message / 5 s, 20 / hour) — exceeding it returns `THROTTLED` without calling the provider;
- `idempotency_key` unique index on `WhatsAppLog` so a retried request never double-sends.

### Task 7.2 Templates from the PRD, verbatim

**Produces:** `format_konfirmasi_booking(kunjungan)`, `format_konfirmasi_checkin_sep(kunjungan)`, `format_pergeseran_jadwal(kunjungan, estimasi_lama, estimasi_baru)` matching PRD §2B-3 word-for-word, with variables:
- `{{nama_rs}}` from `RumahSakitProfile.name` (delete the hardcoded string at `whatsapp.py:56`),
- `{{nama_pasien_masked}}` (first 3 chars + `***`), `{{nomor_sep_masked}}` (last 4 visible),
- `{{blok_peringatan_biometrik}}` non-empty **only** when `KonfigurasiBiometrikPoli` says the polyclinic requires biometrics and the patient is not exempt,
- `{{estimasi_jam_periksa}}`/`{{waktu_anjuran_tiba}}` from Phase 5's `Estimasi` object.

**Test-first:** `test_template_1_verbatim`, `test_template_2_verbatim`, `test_template_3_verbatim` (string equality against a fixture copied from the PRD text), `test_multi_rs_name_comes_from_profile` (two profiles → two different first lines), `test_masking_never_leaks_full_identity`, `test_biometric_block_empty_for_non_biometric_poly`.

**Exit criteria:** three templates, three triggers (booking, check-in+SEP, shift ≥ 15 min), idempotent, masked, multi-RS. The old `format_tiket_wa` may remain as an alias only if a test pins its output to Template 1.

---

## Phase 8 — SEP issuance & Antrean Online at check-in (BL-07)

### Task 8.1 Check-in → SEP → queue

**Produces:** in the kiosk check-in flow, for `penjamin='BPJS'`:
1. re-read the stored `RujukanBpjs` (never re-ask the patient);
2. `daftar_antrean_bpjs()` **before** SEP (BPJS requires the `kodebooking` to exist), persist `no_referensi_antrean` and use the returned BPJS queue number when it differs from the local ticket (store both, display local, send BPJS's to BPJS);
3. `terbitkan_sep()` → persist `no_sep`; on `BridgingError` set `sep_mode='GAGAL'`, log `RSK-APM-04`, render the fallback screen (Phase 10) and **do not print a SEP**;
4. print SEP + queue number, then Task ID 3;
5. send Template 2.

**Idempotency pinned by tests:** double-submit returns the same `no_sep` and the same `kodebooking`; a retry after a `GAGAL` never creates a second SEP; `no_sep` uniqueness constraint is enforced at DB level (Phase 1 Task 1.2).

**Test-first:** `test_checkin_issues_sep_once`, `test_duplicate_submit_returns_same_sep`, `test_sep_failure_blocks_print_and_logs_risk`, `test_task3_only_after_sep_success`, `test_bpjs_queue_number_used_in_addantrean_payload`.

### Task 8.2 Read-only clinical fields in UI

**Produces:** in kiosk reschedule / mobile ticket screens, `diagnosa_awal`, `ppk_rujukan`, `tgl_rujukan` render as locked text; server ignores them if present in POST (assert explicitly).

**Exit criteria:** a BPJS check-in produces exactly one SEP and one Antrean Online registration per visit, visible in `WhatsAppLog` + `AntreanBpjsTaskLog`.

---

## Phase 9 — Biometric gate & 3-strike escalation (BL-08, BL-09, RSK-APM-03)

### Task 9.1 Adapter

**Produces:** `pasien/services/biometrik.py`
```python
class BiometricGateway:
    def verify(self, *, pasien, metode, perangkat_id=None) -> BiometricResult
```
- `simulated` mode: deterministic pseudo-score from `(pasien.no_rm, attempts)`; **always** returns `mode='SIMULASI'`, and the kiosk screen must show a badge "MODE SIMULASI — bukan bukti kepatuhan".
- `device` mode: raises `NotImplementedError` with a message naming the missing vendor protocol document until §7.1 of the analysis is resolved. Do not invent a protocol.

### Task 9.2 Gate and escalation

**Produces:** in the kiosk flow, if `KonfigurasiBiometrikPoli` requires biometrics and the patient is not exempt (age/status):
- `Cetak SEP` button disabled server-side: the print endpoint itself returns `409 BIOMETRIK_BELUM_VALID` (client-side disabling alone is not a gate);
- attempts counted in the kiosk session and persisted in `LogBiometrik`;
- after `biometrik_maks_percobaan` failures: stop the flow, issue a priority helpdesk ticket (`HSD-{YYYYMMDD}-{seq}` via the same counter mechanism), write `LogBiometrik(hasil='ESKALASI')` + `LogRisikoApm('RSK-APM-03')`, send an escalation WhatsApp, and set `biometrik_status='ESKALASI'`.

**Test-first:** `test_non_biometric_poli_prints_without_verification`, `test_biometric_poli_blocks_print_server_side`, `test_exempt_by_age_skips_gate`, `test_three_failures_issue_helpdesk_ticket`, `test_helpdesk_ticket_logged_as_rsk_apm_03`, `test_simulated_mode_is_marked_and_blocks_uat_claim`.

**Exit criteria:** BL-08/09 demonstrable end-to-end in `simulated` mode; UAT evidence explicitly labelled simulation-only.

---

## Phase 10 — Public-surface hardening (BL-10, BL-11)

### Task 10.1 Throttling

**Produces:** `pasien/services/throttle.py` — DB-backed counter (`ThrottleCounter(scope, key, window_start, count)`) usable under both SQLite and Postgres without new dependencies (no `django-ratelimit`).
Limits: verify 5/10 min per IP+identifier; referral validation 10/10 min per IP; booking 5/hour per identity; check-in 10/10 min per IP; cancel 10/hour per token.

**Test-first:** limit exceeded → `429` with `Retry-After`; a different identity is not affected; window rolls over deterministically with `freezegun`-free `timezone` override.

### Task 10.2 Masking everywhere

**Produces:** `mask_nik`, `mask_nama`, `mask_nomor_hp`, `mask_no_sep` in `pasien/services/masking.py`; applied to **all** public JSON responses (verification, referral validation, booking, check-in, ticket). Test: `test_no_public_response_contains_full_nik_or_bpjs` iterating every public endpoint and asserting a regex miss.

### Task 10.3 Idle timeout global

**Produces:** kiosk JS timer driven by `KonfigurasiApm.idle_timeout_detik` with a 15 s warning + "Saya masih di sini" button; on expiry calls `POST /pasien/apm/api/sesi/reset/` which clears server-side session state and returns 204. Also `Cache-Control: no-store` on all kiosk responses.

**Test-first (server-side, Django test client):** `/apm/api/sesi/reset/` requires CSRF, is POST-only, and any subsequent use of a stale capability token is rejected.

### Task 10.4 Bridging-down UX

**Produces:** a shared `BridgingDown` screen used by booking and check-in: explicit message, incident reference id, `RSK-APM-04` log, "Hubungi loket admisi" path, and **no retry loop** that could double-issue.

**Exit criteria:** every public endpoint is throttled and masked; kiosk has a global idle timeout; bridging failure never produces a SEP.

---

## Phase 11 — Risk log & quality indicators (BL-12)

### Task 11.1 Wiring

**Produces:** `LogRisikoApm` writes for every trigger in the PRD table; a `kode_risiko` choice enforced by `CheckConstraint`; a `pemicu` short code per trigger (`IGD_FASTTRACK`, `RUJUKAN_KEDALUWARSA`, `RUJUKAN_BEDA_PPK`, `RUJUKAN_TIDAK_DITEMUKAN`, `PESERTA_TIDAK_AKTIF`, `BIOMETRIK_GAGAL_3X`, `BRIDGING_TIMEOUT`, `WA_GAGAL`, `RATE_LIMIT`, `SESI_KIOSK_TERBUKA`).

**Test-first:** one test per trigger asserting exactly one row with the right `kode_risiko` and `kanal`, and `test_log_risiko_is_append_only` (update attempt raises).

### Task 11.2 Indicators

**Produces:** `/pasien/apm/indikator/` (staff-only) computing:
- median & p90 `registrasi_selesai_at - registrasi_mulai_at` per channel (IGD target ≤ 120 s, SEP ≤ 180 s);
- biometric compliance rate = `VALID / (VALID+GAGAL+ESKALASI)` per polyclinic;
- referral block counts per `status_validasi` per day;
- WA delivery rate by `jenis_pesan` and provider.

**Produces:** management command `apm_indikator --bulan YYYY-MM` emitting JSON, so the ARima quality dashboard can consume it without a hardcoded template.

**Exit criteria:** every PRD risk code appears in a real test; indicators compute from real rows (no placeholder zeros); the report path is documented for the quality unit.

---

## Task → PRD traceability

| PRD | Phase | Guarding tests |
|---|---|---|
| BL-01 | 3 | `tests_apm_igd_fasttrack` (6 tests) |
| BL-02 | 2, 4 | `tests_apm_rujukan`, `tests_apm_rujukan_gate` |
| BL-03 | 4 | `test_expired_referral_returns_409_and_logs_rsk_apm_02` |
| BL-04 | 6 | `tests_apm_mobile` (token, QR, no-duplicate) |
| BL-05 | 5 | `tests_estimasi` |
| BL-06 | 7 | `tests_apm_whatsapp` (3 verbatim templates) |
| BL-07 | 2, 8 | SEP idempotency + antrean payload |
| BL-08 | 9 | biometric gate server-side |
| BL-09 | 9 | 3-strike escalation |
| BL-10 | 10 | throttle + masking + idle |
| BL-11 | 2, 10 | `BridgingError` + `BridgingDown` |
| BL-12 | 11 | one test per `kode_risiko` |

## Full gate (release)

```
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py test \
  pasien akreditasi --keepdb --noinput
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
DATABASE_URL='' DJANGO_DEBUG=true .venv/Scripts/python.exe manage.py collectstatic --noinput
```

Plus HTTP smoke (200) on: `/pasien/apm/`, `/pasien/mandiri/`, `/pasien/antrean/display/`, `/pasien/apm/indikator/` (302 to login without session).

## Rollback

| Phase | Rollback |
|---|---|
| 1 | Additive columns only; revert migration 0033 after confirming no UI reads them |
| 2 | Restore `pasien/bpjs.py` from git; shim means callers are untouched |
| 3 | Remove the beranda button + endpoint; `flag_khusus` data migration is reversible (`KRITIS`→`MERAH`) |
| 4 | Feature flag `APM_REQUIRE_RUJUKAN` (default on after UAT) drops booking to legacy behaviour without code revert |
| 5 | `estimasi.py` is additive; `hitung_estimasi_jam` can fall back to the old one-liner |
| 6 | Route set is separate; disable by removing the two URL entries |
| 7 | `KonfigurasiApm.wa_provider='SIMULASI'` restores logging-only mode |
| 8 | Flag `APM_AUTO_SEP` off → visits register but SEP issuance returns to manual counter flow |
| 9 | `KonfigurasiBiometrikPoli.aktif=False` for all rows disables the gate without code change |
| 10 | Throttle limits raised via config; masking can be relaxed per field (not per endpoint) only with sign-off |
| 11 | Telemetry only; deleting the report route loses nothing clinical |

## Risk register

| Risk | Mitigation |
|---|---|
| SEP duplication under retry | DB unique constraint + `no_sep` short-circuit before the API call |
| Wrong BPJS payload shape (v1 vs v2 drift) | Phase 0 fixtures; a `--verify-bridging` management command that hits sandbox and fails loudly |
| Future-dated bookings break "today" filters | `tanggal_kunjungan` separated in Phase 1; audit every `tanggal_masuk__date` query in Phase 6 and pin with tests |
| Biometric compliance overstated in UAT | `mode='SIMULASI'` badge + explicit UAT note; no indicator counts simulated as `VALID` |
| Idle timeout hurts elderly patients | 90 s ceiling with 15 s warning and an explicit "still here" affordance |
| WA double-send after retry | `idempotency_key` unique index, not application-only check |
| Rate limiting locks out a shared hospital NAT | throttle key is `IP + identifier`, windowed, with 429 + `Retry-After` and an admin allowlist |
| Referral OCR unreliable | Out of scope; typed/QR intake only until a standardized referral layout exists |

## Open decisions blocking go-live (from analysis §7)

1. Vendor biometric protocol → BL-08/09 stay `simulated`.
2. Production VClaim + Antrean Online credentials → live smoke test is a release gate, not a task.
3. `BPJS_KODE_PPK` real value + polyclinic/doctor BPJS code mapping.
4. ICD-10 master vs bridged string.
5. WhatsApp provider (Fonnte vs WABA Cloud) — decides template approval work.
6. Whether future-date booking is allowed and how far ahead.