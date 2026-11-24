# Recon: Kapabilitas Eksisting untuk Modul RME Poli Jantung & Pembuluh Darah

Sumber spesifikasi: `C:/Users/cubeb/Downloads/Modul_RME_Polispesialis_Jantung_ARIMA_v2.1_Lengkap.docx` (v2.1).
Matriks field-per-field spesifikasi sudah ada di `docs/plans/2026-11-24-poli-jantung-matriks-spesifikasi.md`; dokumen ini **hanya** inventaris kode eksisting + gap.
Sifat dokumen: read-only recon. Tidak ada perubahan kode, migrasi, atau data.
Semua klaim memakai `path:line`. Bila tidak ditemukan, ditulis **TIDAK DITEMUKAN**.

---

## A. Ringkasan eksekutif

1. Unit `POLI-JANTUNG` **sudah ada** sebagai `UnitKerja` dan sudah dipetakan dari `POLI_JANTUNG` (`akreditasi/layanan_unit.py:26-27`), tetapi dasbor antrean poli **tidak** memakai peta itu untuk otorisasi (`pasien/views.py:1308-1318`).
2. Dasbor `rajal` adalah tabel antrean + 4 modal aksi, bukan modul RME: `SOAP`, `Penunjang`, `Pulang`, dropdown (Ranap/Booking/Consent/Konsul/Cetak) (`templates/pasien/rajal_dashboard.html:305-361`).
3. Tombol SOAP di dasbor **tidak pernah menyimpan** karena nama field template (`soap_s`..`soap_p`) tidak dibaca view (`subjektif`..`plan`) — `templates/pasien/rajal_dashboard.html:386-398` vs `pasien/views.py:1512-1520`.
4. Tombol Penunjang di dasbor memakai **free-text + tarif hardcode 150k/250k**, melewati katalog 3 tingkat yang sudah ada (`templates/pasien/rajal_dashboard.html:424-455`, `pasien/views.py:1467-1505`).
5. Pola acuan yang matang **sudah ada**: 11 langkah IGD ber-versi, idempoten, append-only (`pasien/forms_igd_workflow.py:12-27`, `pasien/services/igd_assessment_workflow.py:61-160`, `pasien/services/igd_actions.py:195-246`) — tetapi default **nonaktif** (`config/settings.py:47`).
6. Asesmen awal rawat jalan hari ini = satu halaman 4 tab yang menulis langsung ke kolom `KunjunganPasien`, tanpa versi/tanda tangan (`templates/pasien/_asesmen_awal_wizard.html:19-43`, `pasien/views.py:2028-2200`).
7. TTV tersimpan di `KunjunganPasien` (satu set terakhir) dan time-series hanya di `IgdVitalObservation` (`pasien/models.py:424-431`, `pasien/models.py:1458-1477`). MAP/IMT **TIDAK DITEMUKAN**; NEWS-2 sudah ada (`pasien/models.py:660-720`).
8. Katalog penunjang 3 tingkat + 94 item aktif (termasuk Troponin/EKG/Echo) sudah ter-seed, tetapi status order hanya 3 nilai dan nilai kritis hanya boolean+catatan (`klinis/expansion_models.py:6-40`, `pasien/models.py:1012-1029`).
9. CPPT punya stack profesional penuh (revisi immutable, verifikasi DPJP berbasis kredensial), tetapi jalur rajal masih memakai penulis legacy yang menerima `profesi`/`nama_ppa` dari form (`pasien/services/professional_cppt.py:1-176` vs `pasien/views.py:558-570`).
10. Katalog obat **kosong di DB** (0 kelas/generik/produk) dan tidak ada mesin interaksi obat; resep terstruktur hanya bisa dibuat dari alur IGD (`resep_buat` → `get_visit` menolak non-IGD).
11. Katalog akreditasi aktif adalah **STARKES 2022**, bukan 2024; fixture/cutover 2024 sudah tersedia (`fixtures/standar_akreditasi_2024.json`, `akreditasi/management/commands/starkes_2024_cutover.py`).
12. AI = HTTP langsung ke DeepSeek dengan sanitasi + audit, opt-in per modul; belum ada endpoint AI untuk poli jantung (`akreditasi/ai_service.py:105-190`, `akreditasi/system_models.py:60-61`).

**Keputusan arsitektur tunggal terbesar:** memperluas mesin alur `IgdAssessmentWorkflow` menjadi alur asesmen generik (satu keluarga model + `save_step`/`perform_action` + guard) versus membuat keluarga model baru `PoliJantungWorkflow`. Rekomendasi: **generalisasi**, karena 5 model + service + guard + test sudah ada dan idempotensi/versi/digest-nya sudah teruji; kloning akan menduplikasi 3 mekanisme paling rawan (versi optimistik, replay `request_id`, append-only revision).

---

## B. Peta kapabilitas eksisting

| Kapabilitas | Status | Bukti (file:line) | Catatan |
|---|---|---|---|
| Dasbor antrean poli (`/pasien/rajal/`) | Sudah | `pasien/views.py:1308-1368`; `templates/pasien/rajal_dashboard.html:221-226` | Filter `?poli=` via `poliklinik__icontains` |
| Hitung antrean per poli | Sebagian | `pasien/views.py:1326-1335` | Memakai `label[:15]`, bukan kode; baris ber-kode (`POLI_ANAK`) tidak terhitung (data dev: `pasien_kunjunganpasien` memuat keduanya) |
| Cakupan status di antrean | Sebagian | `pasien/views.py:1312-1315` | Hanya `DAFTAR`/`ASESMEN`; pasien `PENUNJANG`/`TINDAKAN`/`DISPOSISI` hilang dari papan |
| Tombol `+ Pendaftaran Baru` | Sebagian | `templates/pasien/rajal_dashboard.html:50-52` | Hanya tautan ke dasbor pendaftaran, bukan modal registrasi + auto No. Kunjungan |
| Tombol `SOAP` | Rusak | `templates/pasien/rajal_dashboard.html:374-399` vs `pasien/views.py:1512-1520` | Nama field tidak cocok → selalu gagal senyap (`messages.error`) |
| Tombol `Penunjang` | Sebagian | `templates/pasien/rajal_dashboard.html:424-455`; `pasien/views.py:1467-1505` | Free-text, tarif hardcode, tidak ada katalog/CITO critical flag dari UI |
| Tombol `Pulang`/SKDP | Sudah | `templates/pasien/rajal_dashboard.html:460-512`; `pasien/views.py:1541-1580` | `discharge_patient` + nomor SKDP |
| Dropdown Ranap/Booking/Consent/Konsul | Sudah | `templates/pasien/rajal_dashboard.html:319-361` | Modal masing-masing ke `kunjungan_disposisi`, `booking_kamar_buat`, `general_consent_simpan` |
| Ikon `Detail` (panel longitudinal) | Sebagian | `templates/pasien/rajal_dashboard.html:364-366` | Hanya tautan `kunjungan_detail`; tidak ada tren TTV/LVEF, badge alergi, daftar GDMT |
| Status antrean 4 state | Sudah | `pasien/models.py:371-379`; `pasien/views.py:1374-1388` | `MENUNGGU/DIPANGGIL/SEDANG_DILAYANI/SELESAI` |
| Validasi DPJP sebelum `Dilayani` | Belum | `pasien/views.py:1374-1388` | Tidak ada cek `dpjp` |
| Scoping unit pada dasbor rajal | Belum | `pasien/views.py:1310-1318` | Tidak memanggil `scope_kunjungan_qs`; hanya `@require_patient_module('rajal')` (`pasien/views.py:1306-1307`) |
| Asesmen awal rajal (form) | Sebagian | `templates/pasien/asesmen_awal_form.html:8,78`; `templates/pasien/_asesmen_awal_wizard.html:19-43` | 4 tab, satu POST, tanpa versi/tanda tangan |
| Wizard ber-versi 11 langkah | Sudah (IGD) | `pasien/forms_igd_workflow.py:12-27`; `pasien/services/igd_assessment_workflow.py:61-160` | Default nonaktif (`config/settings.py:47`) |
| TTV pada kunjungan | Sudah | `pasien/models.py:424-431` | Satu set nilai terakhir |
| TTV time-series + koreksi | Sudah (IGD) | `pasien/models.py:1458-1477`; `pasien/services/igd_assessment_workflow.py:143-150` | Immutable, `corrects` FK |
| MAP otomatis | Belum | — | **TIDAK DITEMUKAN** |
| IMT otomatis / klasifikasi Asia-Pasifik | Belum | — | **TIDAK DITEMUKAN** (BB/TB juga tidak ada di `KunjunganPasien`) |
| NEWS-2 (EWS) | Sudah | `pasien/models.py:653-720`; dipakai `pasien/views.py:1167` | Hanya IGD yang menampilkan |
| Morse Fall Scale | Sudah | `pasien/forms_igd_workflow.py:107-118`; `pasien/tests_morse.py:1-40` | Skor+grade diturunkan dari detail JSON |
| Status merokok / Indeks Brinkman | Belum | — | **TIDAK DITEMUKAN** |
| Skrining kehamilan/menyusui terstruktur | Belum | `pasien/igd_workflow_views.py:190` | Hanya field persiapan order (`pregnancy`) |
| Katalog penunjang 3 tingkat | Sudah | `klinis/expansion_models.py:6-40`; `klinis/services/penunjang_catalogue.py:12-26` | Level 1→2→3; `ItemPenunjang.group` wajib level 3 |
| Item kardiologi di katalog | Sudah | `klinis/data/penunjang_catalogue.json:334,726,822` | Troponin/CK-MB/NT-proBNP, Echo, EKG 12-Lead (aktif di DB) |
| Order penunjang ber-katalog | Sudah (IGD) | `pasien/services/penunjang_orders.py:8-54` | Validasi persiapan, snapshot hierarki, batch UUID |
| Status order DRAFT/BATAL | Belum | `pasien/models.py:1012-1016` | Hanya `ORDERED/PROSES/SELESAI` |
| Timestamp order & terima hasil | Sebagian | `pasien/models.py:1026-1036` | `created_at` + `result_recorded_at`; tidak ada timestamp "dilaporkan ke DPJP" |
| Nilai kritis: alert + read-back | Sebagian | `pasien/models.py:1027-1029`; `pasien/forms_igd_operations.py:88-101` | Boolean + catatan; read-back/penerima/jam lapor **TIDAK DITEMUKAN** |
| Billing otomatis dari order katalog | Belum | `pasien/services/penunjang_orders.py:1-54` | Tidak membuat `BillingItem` sama sekali |
| Tarif tindakan per penjamin | Sebagian | `klinis/services/tarif.py:5-52` | `tarif_bpjs`/`tarif_umum`; tidak ada `KelompokLayanan` untuk RAJAL/POLI_JANTUNG |
| Tarif penunjang per item | Belum | `klinis/expansion_models.py:28-40` | `ItemPenunjang` tidak punya harga |
| CPPT multiprofesi (model) | Sudah | `pasien/models.py:845-895` | SOAP/ADIME/SPIRITUAL + `status`/`version` |
| Penulis CPPT legacy (rajal) | Sebagian | `pasien/views.py:558-570`; `templates/pasien/kunjungan_detail.html:470-520` | Profesi & nama diketik bebas, `verifikasi_dpjp` checkbox |
| CPPT revisi + verifikasi DPJP | Sudah (IGD, flag) | `pasien/services/professional_cppt.py:96-176`; `pasien/professional_care_models.py:22-84` | Digest, revision immutable, otoritas kredensial |
| Batas verifikasi DPJP ≤ 24 jam | Belum | — | **TIDAK DITEMUKAN**; tidak ada `timedelta(hours=24)` pada verifikasi |
| Resep elektronik terstruktur | Sebagian | `pasien/models.py:1045-1107`; `pasien/services/prescriptions.py:197-274` | Hanya jalur IGD (`pasien/views.py:700-709` + `get_visit` menolak non-IGD) |
| Katalog obat aktif | Belum (data) | `klinis/data/medication_catalogue.json:1-30`; DB: 0 kelas/generik/produk | Importer ada: `klinis/management/commands/import_medication_catalogue.py` |
| Interaksi obat otomatis | Belum | `pasien/services/medication_safety.py:16-62` | Hanya alergi, duplikasi zat, overlap kelas, PPRA |
| Alergi terstruktur | Sebagian | `pasien/expansion_models.py:13-21`; DB: 0 baris | Dipakai `pasien/services/medication_safety.py:24-27` |
| Formularium | Sebagian | `klinis/expansion_models.py:121-128`; `klinis/services/medication_catalogue.py:30-37` | Filter ada, data 0 baris |
| EP otomatis untuk asesmen | Sebagian | `klinis/models.py:208-220`; `pasien/views.py:2189-2223` | 4 aturan (`ARK 1`, `PAP 3`, `PAP 8`, `SKP 1`), bukan 7 bab |
| EP otomatis untuk tindakan | Sudah | `klinis/services/ep_tindakan.py:1-35`; 17 aturan di DB | Resolver + wildcard |
| STARKES 2024 sebagai katalog aktif | Belum | DB `akreditasi_framework`: aktif = edisi 2022 | Fixture + cutover tersedia |
| Dokumen bukti + ekspor PDF | Sebagian | `akreditasi/models.py:339-448`; PDF hanya `pasien/pdf_utils.py`, `akreditasi/mutu_laporan.py:1566-1580` | Tidak ada ekspor PDF per-EP/bukti |
| Indikator mutu + PDCA | Sudah | `akreditasi/risiko_models.py:586-641,743-765`; `akreditasi/models.py:362-415` | `IndikatorMutu`, `CatatanIndikator`, `QualityRecord` |
| AI drafting | Sebagian | `akreditasi/ai_service.py:105-190`; `klinis/services/ai_igd.py:14-50` | DeepSeek langsung, opt-in `ai_enable_igd`; tanpa endpoint poli |
| RBAC unit scoping | Sebagian | `pasien/unit_scope.py:1-100`; `pasien/decorators.py:8-39` | Ada, tetapi tidak dipakai dasbor rajal |
| Konvensi uji | Sudah | 161 modul uji ber-`TestCase`; `STRAYS.md:8-10` | Django `TestCase`, bukan pytest |
| Harness QA/browser | Sudah | `qa/runner.py:1-20`; `qa/run_all.sh`; `qa/clinical_expansion_browser.py:1-10` | Shard salinan DB + Playwright |

---

## C. Peta model data

| Model | Field penting | Dipakai di | Relevansi 10 langkah |
|---|---|---|---|
| `Pasien` (`pasien/models.py:21-131`) | `no_rm`, `nik`, `nama_lengkap`, `tanggal_lahir`, `jenis_kelamin`, `alamat`, `no_hp`, `no_bpjs`, `alergi_obat`, `alergi_lain`, `umur`/`usia` property | `pasien/views.py:340-405`; header `templates/pasien/igd_workflow.html:22` | L1 identitas; L3 alergi; L9 badge alergi |
| `KunjunganPasien` (`pasien/models.py:298-578`) | `no_kunjungan`, `jenis_kunjungan` (IGD/RAJAL/RANAP), `dpjp`, `poliklinik`, `unit_kerja`, `penjamin` (UMUM/BPJS/ASURANSI), `status`, `nomor_antrean`, `status_antrean`, `ttv_*`, `keadaan_umum`, `kesadaran`, `anamnesis_rps/rpd/rpk/obat`, `fisik_*`, `skrining_*`, `cara_datang`, `disposisi_*` | `pasien/views.py:1308-1368`, `2028-2200`; `pasien/forms_igd_workflow.py:12-27` | L1–L6, L10 (semua field asesmen hari ini ada di sini) |
| `AsesmenRisikoKlinis` (`pasien/models.py:809-836`) | `jenis` (JATUH_MORSE/NYERI/NUTRISI/…), `skor`, `grade`, `temuan`, `intervensi` | Hanya seed (`pasien/management/commands/seed_pasien_data.py:189-215`) + hitung KPI (`akreditasi/kontrol_data.py:246`) | L5 — **tidak** dipakai form asesmen; duplikat representasi |
| `CPPT` (`pasien/models.py:845-895`) | `format_code`, `structured_content`, `professional_snapshot`, `status` (LEGACY/DRAFT/SIGNED), `version`, `profesi`, `nama_ppa`, `subjektif/objektif/asesmen/plan`, `verifikasi_dpjp` | `pasien/views.py:558-570`; `pasien/services/professional_cppt.py` | L9 CPPT multiprofesi |
| `CpptRevision` (`pasien/professional_care_models.py:22-32`) | `note`, `version`, `snapshot`, `digest`, `author`, `reason` | `pasien/services/professional_cppt.py:114-116` | L9/L10 addendum |
| `VerifikasiCppt` (`pasien/professional_care_models.py:58-66`) | `revision` (1:1), `verifier`, `assignment`, `assignment_snapshot`, `digest`, `request_id` | `pasien/services/professional_cppt.py:169-176` | L9 verifikasi DPJP |
| `PenugasanDpjpEpisode` (`pasien/professional_care_models.py:34-56`) | `visit`, `doctor`, `unit`, `assignment_type`, `valid_from/until`, `source_version` | `pasien/services/professional_cppt.py:138-157` | L1/L9 kredensial DPJP |
| `PembatalanTagihan` (`pasien/professional_care_models.py:68-84`) | `item` (1:1 BillingItem), `action`, `amount`, `reason`, `request_id` | `pasien/services/professional_billing.py` | L9 void beralasan |
| `BillingItem` (`pasien/models.py:897-948`) | `kategori` (JASA_MEDIS/OBAT/LAB/RADIOLOGI/KAMAR/ADMIN/LAINNYA), `nama_item`, `kuantitas`, `harga_satuan`, `kode_icd`, `sumber` (MANUAL/ASESMEN/FARMASI/PROFESI), `is_void`, `subtotal` | `klinis/services/tarif.py:62-140`; `pasien/services/prescriptions.py:264-267`; `pasien/services/igd_actions.py:152-155` | L7/L8/L9 billing |
| `OrderPenunjang` (`pasien/models.py:994-1038`) | `catalogue_item`, `catalogue_snapshot`, `batch_id`, `preparation`, `diagnosis`, `destination`, `jenis`, `nama_pemeriksaan`, `prioritas`, `status`, `hasil_pemeriksaan`, `result_recorded_at`, `is_critical_value`, `critical_value_catatan` | `pasien/services/penunjang_orders.py`; `penunjang_results.py` | L7 |
| `ResepElektronik` (`pasien/models.py:1045-1087`) | `no_resep`, `jenis_resep`, `status` (DRAFT/DIKIRIM/DISPENSING/SELESAI/BATAL), `version`, `serving_unit`, `submitted_snapshot`, `policy_version`, `financial_pending` | `pasien/services/prescriptions.py:197-274` | L8/L9 e-resep |
| `ResepDetail` (`pasien/models.py:1089-1127`) | `product`, `product_snapshot`, `regimen`, `quantity_decimal`, `reference_price`, `billing_item` (1:1) | `pasien/services/prescriptions.py:264-267` | L8/L9 tarif obat |
| `AlergiPasienTerstruktur` (`pasien/expansion_models.py:13-21`) | `pasien`, `ingredient_code`, `therapy_class_code`, `reaction`, `active` | `pasien/services/medication_safety.py:24-27` | L3/L8 kontraindikasi |
| `MedicationSafetyReview` (`pasien/expansion_models.py:24-31`) | `resep`, `digest`, `policy_version`, `findings`, `acknowledgements` | `pasien/services/prescriptions.py:193` | L8 gate kirim resep |
| `TindakanAsesmen` (`pasien/models.py:1336-1420`) | `jenis/kode/nama`, `tarif`, `tarif_acuan`, `tarif_penjamin`, `quantity`, `execution_status` (LEGACY/PLANNED/PERFORMED/CANCELLED), `execution_team`, `standard_item`, `ep_status`, `billing_item` | `pasien/asesmen_tindakan.py`; `pasien/services/igd_actions.py:64-190` | L9 tindakan + EP + billing |
| `KorelasiEpAsesmen` (`pasien/models.py:1288-1308`) | `kunjungan`, `standard_item`, `status` (TERPENUHI/BELUM/NA), `catatan`, `diverifikasi_oleh/pada` | `pasien/views.py:2189-2223`, `2642-2668` | L10 bukti EP per kunjungan |
| `LampiranAsesmen` (`pasien/models.py:1310-1330`) | `jenis` (ASESMEN/PENUNJANG/RUJUKAN/LAINNYA), `file`, `nama_asli`, `ukuran`, `diunggah_oleh/pada` | `pasien/services/igd_attachments.py:73-103` | L7/L8/L9 unggah dokumen |
| `IgdAssessmentWorkflow` (`pasien/models.py:1443-1456`) | `kunjungan` (1:1), `origin_unit`, `status` (DRAFT/FINAL), `version`, `last_step`, `schema_version`, `signatures`, `exemptions` | `pasien/services/igd_assessment_workflow.py`; `igd_actions.py` | L1–L10 pola acuan |
| `IgdVitalObservation` (`pasien/models.py:1458-1477`) | `phase` (INITIAL/EVALUATION), `observed_at`, `data` JSON, `corrects` | `pasien/services/igd_assessment_workflow.py:143-150` | L4 time-series TTV |
| `IgdAssessmentRevision` (`pasien/models.py:1479-1497`) | `revision`, `snapshot`, `reason`, `signed_by/at` | `pasien/services/igd_finalization.py:19-39` | L10 finalisasi/addendum |
| `IgdWorkflowAction` (`pasien/models.py:1499-1510`) | `request_id`, `operation`, `digest`, `actor`, `result` (unique per workflow) | `pasien/services/igd_actions.py:219-224,242-243` | Idempotensi semua aksi |
| `KategoriPenunjang` (`klinis/expansion_models.py:6-18`) | `kode`, `nama`, `level` (1/2/3), `parent`, `active` | `klinis/services/penunjang_catalogue.py:44-70` | L7 katalog 3 tingkat |
| `ItemPenunjang` (`klinis/expansion_models.py:28-40`) | `kode`, `nama`, `group` (level 3), `jenis_order`, `destination`, `active`, `preparation_schema`, `variants`, `is_panel` | `klinis/services/penunjang_catalogue.py:7-42`; `penunjang_orders.py` | L7 item order |
| `ProdukFarmasi` / `GenerikObat` / `KelasTerapiObat` (`klinis/expansion_models.py:56-94`) | `kode`, `nama`, `flags`, `price`, `active`, `source_version`, `reviewed_by` | `klinis/services/medication_catalogue.py:5-39` | L8/L9 e-resep |
| `KeanggotaanFormularium` (`klinis/expansion_models.py:121-128`) | `produk`, `jenis` (FORNAS/RS), `valid_from/to` | `klinis/services/medication_catalogue.py:30-37` | L8 formularium |
| `MedicationPolicy` (`klinis/expansion_models.py:131-137`) | `version`, `rules` JSON, `active` | `pasien/services/medication_safety.py:4-5` | L8 kebijakan PPRA |
| `StandardItem` (`akreditasi/models.py:309-337`) | `category`, `sub_standard`, `code`, `description`, `order` | `pasien/views.py:369-378`; `pasien/services/igd_actions.py:130-140` | L10 EP |
| `QualityRecord` (`akreditasi/models.py:362-415`) | `standard_item` (1:1), `unit`, `score`, `action_plan`, `pic`, `budget_*` | `akreditasi/views.py` matriks PDCA | L10 PDCA per EP |
| `EvidenceReq`/`EvidenceFile` (`akreditasi/models.py:339-360,417-448`) | `category_type` (R/D/W/O/S), `file`, `status` | `akreditasi/views.py` upload bukti | L10 dokumen bukti |
| `IndikatorMutu`/`CatatanIndikator` (`akreditasi/risiko_models.py:586-641,743-765`) | `jenis` (INM/IMRS/IMU), `numerator/denominator`, `target_nilai`, `nilai_capaian` | `akreditasi/indikator_views.py`; `mutu_laporan.py` | L10 indikator mutu unit |
| `InsidenKeselamatan` (`akreditasi/risiko_models.py:530-583`) | `jenis` (KNC/KTD/KTC/KPC/SENTINEL), `keparahan`, `status_investigasi` | `akreditasi/risiko_views.py` | L10 pelaporan insiden |

### 3a. `POLIKLINIK_CHOICES` dan `DPJP_POLI_MAP`

- `POLIKLINIK_CHOICES` berisi 17 entri; entri pertama `('POLI_JANTUNG', 'Poli Jantung & Pembuluh Darah')` (`pasien/models.py:228-229`).
- `DPJP_CHOICES` memuat dua dokter jantung: `dr. Faisal, Sp.JP` dan `dr. Bambang, Sp.JP, FIHA` (`pasien/models.py:249-250`).
- `DPJP_POLI_MAP['POLI_JANTUNG'] = ('dr. Faisal, Sp.JP', 'dr. Bambang, Sp.JP, FIHA')` (`pasien/models.py:277-278`).
- **Jawaban:** ya, entri "Poli Jantung & Pembuluh Darah" sudah ada, baik sebagai pilihan poliklinik maupun pemetaan DPJP. Unit kerjanya `POLI-JANTUNG` (id 136, parent `POLI-PD`) dan dipetakan di `akreditasi/layanan_unit.py:26-27`.
- Catatan konsistensi: `KunjunganPasien.poliklinik` **tanpa `choices`** dan diisi tiga bentuk berbeda (label, kode, teks bebas) — didokumentasikan sendiri di `akreditasi/layanan_unit.py:6-20` dan terlihat di data dev (satu baris `POLI_ANAK`, satu baris `Poli Penyakit Dalam`).

---

## D. Peta route & template

| URL name | Path | Template | Fungsi |
|---|---|---|---|
| `pasien:rajal_dashboard` | `/pasien/rajal/` | `templates/pasien/rajal_dashboard.html` | Antrean poli + modal aksi (`pasien/urls.py:68`; `pasien/views.py:1308`) |
| `pasien:rajal_antrean_status` | `/pasien/rajal/kunjungan/<pk>/antrean/` | — (redirect) | Ubah `status_antrean`; `SEDANG_DILAYANI` → `status=ASESMEN` (`pasien/urls.py:69`; `pasien/views.py:1374-1388`) |
| `pasien:rajal_soap_simpan` | `/pasien/rajal/kunjungan/<pk>/soap/` | — (redirect) | Penulis SOAP legacy; **field mismatch** (`pasien/urls.py:70`; `pasien/views.py:1512-1538`) |
| `pasien:pendaftaran_dashboard` | `/pasien/pendaftaran/` | `templates/pasien/pendaftaran_dashboard.html` | Registrasi pasien lama/baru, pilih poli + DPJP (`pasien/urls.py:57`; `pasien/views.py:771`; form `templates/pasien/pendaftaran_dashboard.html:260-285,595-615`) |
| `pasien:pendaftaran_route` | `/pasien/pendaftaran/<pk>/route/` | — (redirect) | Routing ke poli/IGD, set `poliklinik` + `nomor_antrean` (`pasien/views.py:996-1040`) |
| `pasien:pendaftaran_ttv_simpan` | `/pasien/pendaftaran/kunjungan/<pk>/ttv/` | — (redirect) | Simpan TTV di loket (`pasien/views.py:1390-1415`) |
| `pasien:kunjungan_detail` | `/pasien/kunjungan/<pk>/` | `templates/pasien/kunjungan_detail.html` | ERM per kunjungan: asesmen, CPPT, billing, resep |
| `pasien:kunjungan_asesmen_awal` | `/pasien/kunjungan/<pk>/asesmen-awal/` | `templates/pasien/asesmen_awal_form.html` (+ `_asesmen_awal_wizard.html`) | Form asesmen awal 4 tab (`pasien/urls.py:39`; `pasien/views.py:340-405`) |
| `pasien:igd_asesmen_awal_save` | `/pasien/kunjungan/<pk>/asesmen-awal-igd/` | — (redirect) | Penulis field asesmen (`pasien/views.py:2028-2200`) |
| `pasien:cppt_tambah` | `/pasien/kunjungan/<pk>/cppt/` | — (redirect) | Penulis CPPT legacy (`pasien/urls.py:40`; `pasien/views.py:558-570`) |
| `pasien:billing_tambah` | `/pasien/kunjungan/<pk>/billing/` | — (redirect) | Tambah item billing manual (`pasien/views.py:576-590`) |
| `pasien:resep_buat` | `/pasien/kunjungan/<pk>/resep/buat/` | — (redirect/400) | Dialihkan ke komposer IGD langkah 8 (`pasien/views.py:700-709`) |
| `pasien:order_penunjang_buat` | `/pasien/kunjungan/<pk>/order-penunjang/` | — (redirect) | Order free-text + billing hardcode (`pasien/views.py:1467-1505`) |
| `pasien:kunjungan_disposisi` | `/pasien/kunjungan/<pk>/disposisi/` | — (redirect) | Pulang/PAPS/Ranap/Rujuk/Konsul (`pasien/views.py:1541-1601`) |
| `pasien:igd_workflow` | `/pasien/kunjungan/<pk>/asesmen-igd/?step=N` | `templates/pasien/igd_workflow.html` | Wizard 11 langkah (`pasien/urls.py:19`; `pasien/igd_workflow_views.py:41-257`) |
| `pasien:igd_workflow_draft` | `.../langkah/<step>/draft/` | — (JSON) | Simpan draft per langkah (`pasien/igd_workflow_views.py:207-230`) |
| `pasien:igd_workflow_action` | `.../aksi/` | — (JSON) | Semua aksi idempoten (`pasien/igd_workflow_views.py:232-264`; `pasien/services/igd_actions.py:195-246`) |
| `pasien:igd_workflow_finalize` / `_addendum` | `.../finalisasi/`, `.../addendum/` | — (JSON) | Tanda tangan + finalisasi + addendum (`pasien/services/igd_finalization.py:155-190`) |
| `pasien:igd_workflow_ai` | `.../saran-ai/` | — (JSON) | Saran ICD/SDKI/SLKI/SIKI + tiket tervalidasi (`pasien/igd_workflow_views.py:281-304`) |
| `pasien:igd_workflow_resume` | `.../resume/` | `templates/pasien/igd_workflow_resume.html` | Snapshot final + digest (`pasien/igd_workflow_views.py:350-389`) |
| `pasien:ancillary_worklist` / `ancillary_result` | `/pasien/penunjang/`, `/pasien/penunjang/<pk>/hasil/` | `templates/pasien/laboratorium_dashboard.html` | Worklist unit pelaksana + input hasil (`pasien/urls.py:13-14`) |
| `pasien:cetak_resume_igd` | `.../cetak-resume-igd/` | `templates/pasien/cetak_resume_igd.html` | Resume IGD (HTML print) |
| `pasien:cetak_skdp` / `cetak_spri` | `.../cetak-skdp/`, `.../cetak-spri/` | `cetak_skdp.html`, `cetak_spri.html` | Surat kontrol & pengantar ranap |
| `pasien:resume_pdf` | `.../resume-pdf/` | `pasien/pdf_utils.py` | Satu-satunya PDF klinis per kunjungan (reportlab) |
| `pasien:igd_dashboard` | `/pasien/igd/` | `templates/pasien/igd_dashboard.html` | Dasbor IGD, EWS, aksi cepat |

---

## E. Pola acuan yang harus ditiru

### E.1 Model (5 tabel, satu keluarga)

1. **Header alur** `IgdAssessmentWorkflow` — 1:1 ke kunjungan (`OneToOneField`, `PROTECT`), `status` DRAFT/FINAL, `version` (optimistic lock), `last_step`, `schema_version`, `signatures` JSON, `exemptions` JSON, `origin_unit` (`pasien/models.py:1443-1456`).
2. **Observasi time-series** `IgdVitalObservation` — `phase` (INITIAL/EVALUATION), `observed_at` terpisah dari `recorded_at`, `data` JSON, `corrects` self-FK; `save()` menolak update dan `delete()` menolak hapus (`pasien/models.py:1458-1477`).
3. **Revisi append-only** `IgdAssessmentRevision` — `snapshot` penuh + `reason` + `signed_by/at`, unique `(workflow, revision)`, tolak update/delete (`pasien/models.py:1479-1497`).
4. **Log aksi idempoten** `IgdWorkflowAction` — unique `(workflow, request_id)`, menyimpan `operation`, `digest` payload, `result` (`pasien/models.py:1499-1510`).
5. **Bukti pelayanan immutable** (`ImmutableCareRecord`): `CpptRevision`, `VerifikasiCppt`, `PembatalanTagihan` menolak update/delete di level model (`pasien/professional_care_models.py:6-20`).

### E.2 Service layer (satu pintu tulis)

- `get_visit(pk, user, write=, lock=)` → ambil kunjungan + workflow, `select_for_update`, lalu `authorize_visit` (`pasien/services/igd_assessment_workflow.py:50-59`).
- `authorize_visit` memisahkan **modul** (`profile.get_allowed_patient_modules()`), **unit** (`get_unit_scope`/`can_read_kunjungan`), **profesi** (`CLINICAL_PROFESSIONS`), **status episode** (`PULANG/RUJUK/MENINGGAL/BATAL` read-only), dan `role == 'ASESOR'` read-only (`pasien/services/igd_assessment_workflow.py:28-49`).
- `save_step(pk, user, step, payload, version)`:
  - whitelist field per langkah (`set(payload) - set(STEPS[step][1])` → tolak) (`:63`);
  - tolak tulis bila `status == 'FINAL'` (`:80`);
  - **cek versi**: `expected != workflow.version` → `WorkflowConflict` (`:86`);
  - validasi lewat `form_for_step` + `prepare_value` (merge nilai tersimpan) (`:101-105`);
  - turunkan field (GCS total, Morse skor/grade, MST) (`:128-141`);
  - tulis observasi TTV baru bila ada perubahan, dengan `phase` dan `corrects` (`:143-150`);
  - `version += 1`, `signatures = {}` (tanda tangan lama gugur) (`:151-155`);
  - `AuditLog` per simpan (`:156-158`).
- `perform_action(pk, user, operation, payload, version, request_id)`:
  - registry `HANDLERS` (`order_batch`, `prescription_save/submit`, `diagnosis_set`, `order`, `cppt`, `plan_action`, `execute`, `cancel_action`, `order_result`) (`pasien/services/igd_actions.py:191`);
  - **replay**: `request_id` sama + `digest` sama + aktor sama → kembalikan `result` lama dengan `replayed=True` (`:219-224`);
  - **konflik**: `request_id` sama tetapi payload/aktor beda → `WorkflowConflict` (`:222-223`);
  - blokir operasi non-addendum saat `FINAL` (`:227-228`);
  - tulis `IgdWorkflowAction` + `AuditLog` (`:242-245`).
- `sign()` menyimpan tanda tangan per bagian (`MEDIS`/`KEPERAWATAN`) dengan `content_digest = digest(clinical_snapshot(...))`; perubahan isi berikutnya menggugurkan tanda tangan (`stale_signatures`) (`pasien/services/igd_finalization.py:41-63`; `pasien/igd_workflow_views.py:138-140`).
- `finalize()` memeriksa `missing_sections()` (11 bagian: triage, anamnesis, primary survey, TTV awal, skrining, fisik, diagnosis, 3S, penunjang, asesmen, evaluasi) dengan mekanisme `exemptions` beralasan (`pasien/services/igd_finalization.py:64-84,155-190`).
- `addendum()` menulis revisi baru tanpa menimpa snapshot lama (`pasien/services/igd_finalization.py:177-190`; `pasien/models.py:1479-1497`).

### E.3 Guard kompatibilitas penulis lama

- `legacy_workflow_guard` dipasang **deklaratif** dengan membungkus `urlpatterns` berdasarkan nama view (`pasien/urls.py:150-161`).
- Efek: bila episode punya workflow, penulis lama ditolak `409`; pengecualian hanya untuk perawatan lanjutan setelah FINAL (RANAP/RAJAL) dengan profesi + unit tujuan yang sah (`pasien/services/igd_assessment_workflow.py:162-194`).
- Ini mekanisme yang membuat migrasi bertahap aman: **satu definisi guard, banyak view lama**.

### E.4 Pola profesional (CPPT + billing)

- Penulis CPPT terstruktur memvalidasi field per format (SOAP/ADIME/SPIRITUAL) (`pasien/services/professional_cppt.py:13-29`).
- Setiap catatan punya `version` + `CpptRevision` ber-`digest`; verifikasi DPJP membandingkan digest revisi dengan isi saat ini (`pasien/services/professional_cppt.py:166`).
- Otoritas verifikasi DPJP tidak memakai field teks: harus `Pegawai` aktif → profesi ditinjau → `PenugasanKlinis` disetujui → `PrivilegeSnapshot` dengan `action_code='verify_cppt'` → `PenugasanDpjpEpisode` tunggal & bukan self-assigned (`pasien/services/professional_cppt.py:138-157`).
- Billing profesional: `TindakanAsesmen` → `BillingItem` dengan `professional_price_snapshot`; koreksi hanya lewat `PembatalanTagihan` beralasan (`pasien/models.py:897-948`; `klinis/services/tarif.py:62-140`).

---

## F. Matriks gap Langkah 1–10

### Langkah 1 — Identitas, kepesertaan, penjamin

| Aspek | Kondisi |
|---|---|
| Ada | `Pasien` lengkap (NIK, no_hp, alamat, BPJS) (`pasien/models.py:51-81`); `KunjunganPasien.penjamin` 3 nilai (`:304-308`); `dpjp` + `poliklinik` (`:334-335`); pendaftaran memilih poli+DPJP berfilter (`templates/pasien/pendaftaran_dashboard.html:260-285`, `pasien/views.py:996-1040`); bridging BPJS (`pasien/bridging_services.py`, `pasien/bpjs.py`) |
| Hilang | No. kunjungan format `RJ-JTG-YYYYMMDD-0001` (sekarang `REG-YYYYMMDD-NNNN`, `pasien/models.py:136-158`); `jenis_kunjungan` klinis (Baru/Kontrol/Konsul/Post-Ranap) — yang ada hanya IGD/RAJAL/RANAP (`:299-303`); asal rujukan & status SEP terstruktur (hanya `no_sep`/`sep_mode`, `:411-413`); validasi DPJP wajib sebelum `Dilayani` (`pasien/views.py:1374-1388`); dropdown DPJP masih konstanta Python, bukan master SDM (`pasien/models.py:248-275`) |
| Harus dibangun | Field/choice jenis kunjungan klinis; validasi DPJP↔poli dari `DPJP_POLI_MAP` atau SDM; generator nomor kunjungan ber-prefix poli |
| Model diperluas | `KunjunganPasien` (jangan model baru); `PREFIX_POLI` di `pasien/services/antrean.py:6-12` sudah punya `JTG` |

### Langkah 2 — Skrining, cara datang, red flags

| Aspek | Kondisi |
|---|---|
| Ada | `cara_datang` 4 pilihan (`pasien/models.py:484-489,514`); triage ATS/ESI + kategori 1–5 (`:497-511,519-521`); triase warna IGD (`:322-327`) |
| Hilang | Red flags kardiovaskular (5 opsi), keputusan alur (Poli vs IGD Cito), timestamp skrining, indikator door-to-ECG ≤10 menit — **TIDAK DITEMUKAN** |
| Harus dibangun | Field red flag + timestamp + turunan SLA; banner + tombol transfer IGD |
| Model diperluas | `KunjunganPasien` (pola `triase_*` yang sudah ada) atau `IgdVitalObservation`-style event untuk timestamp |

### Langkah 3 — Anamnesis & riwayat kardiovaskular

| Aspek | Kondisi |
|---|---|
| Ada | `anamnesis_rps/rpd/rpk/obat` (`:441-444`); `rpd_checklist` JSON (`:541`); `skrining_alergi_status` + `alergi_asesmen` (`:452-454`); alergi terstruktur per zat/kelas (`pasien/expansion_models.py:13-21`) |
| Hilang | Karakteristik & penjalaran nyeri terstruktur (hanya `nyeri_karakteristik` teks 50 char, `:437`); multi-select riwayat jantung (PJK/PCI/HF/AF/katup/bawaan); faktor risiko (HT/DM/dislipidemia/riwayat keluarga/obesitas); status merokok + Brinkman; status kehamilan/menyusui; rekonsiliasi obat rutin kardiovaskular — **TIDAK DITEMUKAN** |
| Harus dibangun | Field terstruktur (JSON atau kolom) untuk riwayat/faktor risiko/rokok/kehamilan; UI multi-select |
| Model diperluas | `KunjunganPasien` (pola `skrining_gizi_detail`/`skrining_jatuh_detail` JSON yang sudah dipakai) |

### Langkah 4 — TTV, MAP, antropometri

| Aspek | Kondisi |
|---|---|
| Ada | 6 TTV + GCS + NRS (`:424-431`); time-series IGD (`:1458-1477`); NEWS-2 (`:660-720`); batas validasi (`pasien/forms_igd_workflow.py:42-46`) |
| Hilang | MAP, IMT + klasifikasi Asia-Pasifik, BB/TB, delta BB antar kunjungan, irama nadi terstruktur (ada `nadi_irama` hanya untuk IGD, `:529`), alert hipoksia/takikardia/bradikardia eksplisit — **TIDAK DITEMUKAN** |
| Harus dibangun | Properti turunan (MAP/IMT/kategori) + field BB/TB + ambang alert |
| Model diperluas | `KunjunganPasien` (BB/TB) + properti seperti `hitung_news_score` |

### Langkah 5 — Biopsikososial, spiritual, skrining

| Aspek | Kondisi |
|---|---|
| Ada | `status_psikososial`, `status_spiritual`, `status_emosional`, `kebutuhan_spiritual` (`:450-451,536-538`); Morse (`pasien/forms_igd_workflow.py:106-118`); MST (`:119-127`); `fungsional_adl` (`:438`) |
| Hilang | Skrining gizi/nutrisi terhubung rekomendasi dietisien; dukungan sosial/keluarga terstruktur; Get Up & Go — **TIDAK DITEMUKAN** |
| Harus dibangun | Opsi terstruktur + turunan intervensi |
| Model diperluas | `KunjunganPasien` + `skrining_jatuh_detail`/`skrining_gizi_detail` |

### Langkah 6 — Pemeriksaan fisik kardiovaskular

| Aspek | Kondisi |
|---|---|
| Ada | `keadaan_umum`, `kesadaran`, `fisik_head_to_toe` (7 organ), `secondary_survey_detail`, `fisik_lokalis`, `penanda_anatomi` (maks 100 marker, koordinat 0–1) (`:435-436,439-458`; validasi `pasien/forms_igd_workflow.py:91-99`); editor anatomi di `templates/pasien/_igd_physical_exam_form.html` |
| Hilang | Iktus kordis, BJ I/II + murmur (derajat/lokasi), gallop, bunyi napas/ronki/wheezing terstruktur, JVP, edema derajat, CRT/pulsasi perifer; kanvas jantung & ekstremitas khusus kardiologi — **TIDAK DITEMUKAN** |
| Harus dibangun | Sekumpulan pilihan fisik kardio + (opsional) kanvas bertanda |
| Model diperluas | `fisik_head_to_toe`/`secondary_survey_detail` JSON (pola `physical_exam.GENERAL_CHOICES`, `pasien/physical_exam.py`) |

### Langkah 7 — Penunjang, order 3 tingkat, nilai kritis

| Aspek | Kondisi |
|---|---|
| Ada | Katalog 3 tingkat + aktivasi + persiapan wajib (`klinis/services/penunjang_catalogue.py:1-70`; `klinis/data/penunjang_activation.json:1-30`); 94 item aktif; Troponin/EKG/Echo tersedia; order batch tervalidasi (`pasien/services/penunjang_orders.py:8-54`); worklist unit + input hasil (`pasien/services/penunjang_results.py:1-79`); banner nilai kritis di dasbor rajal (`templates/pasien/rajal_dashboard.html:58-108`) |
| Hilang | Status `DRAFT`/`BATAL`; timestamp order & terima hasil terpisah sudah ada tetapi **jam lapor DPJP + penerima + read-back tidak ada**; interpretasi klinis EKG/TTE terpisah dari status; tarif penunjang (tidak ada harga di `ItemPenunjang`); billing otomatis dari order katalog; quick-order bundle (7 `is_panel` yang ada bukan paket kardio) |
| Harus dibangun | Status order 4 nilai + timestamp lapor + read-back; field interpretasi + LVEF; harga per item/penjamin; hook billing |
| Model diperluas | `OrderPenunjang` (status/interpretasi/read-back); `ItemPenunjang` (harga) atau tabel tarif penunjang |

### Langkah 8 — Diagnosis & rencana tata laksana

| Aspek | Kondisi |
|---|---|
| Ada | `DiagnosisKunjungan` (primary unique aktif) (`pasien/models.py:1422-1433`); ICD-10/ICD-9/SDKI/SLKI/SIKI master (DB: 172/170/22 pemetaan); saran deterministik (`klinis/services/saran.py:14-70`); AI kandidat + tiket tervalidasi (`klinis/services/ai_igd_targets.py:1-30`; `pasien/igd_workflow_views.py:290-297`); tindakan ICD-9 + tarif per penjamin (`klinis/services/tarif.py:20-52`); e-resep terstruktur (`pasien/services/prescriptions.py:197-274`) |
| Hilang | NYHA/CCS/stratifikasi risiko; rencana tindak lanjut terstruktur (rawat jalan/ranap/rujuk); GDMT shortcut + penyesuaian dosis; edukasi terstruktur + bukti PDF bertanda tangan; jadwal kontrol → e-SKDP otomatis dari form; resep untuk RAJAL (komposer hanya IGD) |
| Harus dibangun | Field klasifikasi fungsional + rencana; jalur resep non-IGD; paket edukasi + ekspor bukti |
| Model diperluas | `KunjunganPasien`/`DiagnosisKunjungan` + `ResepElektronik` (jangan model resep baru) |

### Langkah 9 — CPPT multiprofesi & billing

| Aspek | Kondisi |
|---|---|
| Ada | `CPPT` multi-format + status/version (`:845-895`); revisi immutable + verifikasi DPJP (`professional_cppt.py`); pelaksanaan profesional + void (`pasien/services/igd_actions.py:64-190`; `professional_billing.py`); billing item per kategori (`:897-948`); unggah lampiran ber-hash (`pasien/services/igd_attachments.py:73-103`) |
| Hilang | TTE (tanda tangan gambar/PIN); auto-save lokal & layout tablet; handwriting; quick-chips; tarik TTV terbaru ke O; ringkasan penunjang otomatis di CPPT; viewer gambar jantung/ekstremitas di CPPT; verifikasi DPJP ≤24 jam; CPPT rajal memakai penulis legacy (profesi diketik) |
| Harus dibangun | Jalur CPPT profesional untuk RAJAL; deadline verifikasi; komponen O otomatis |
| Model diperluas | `CPPT` + `CpptRevision`/`VerifikasiCppt` (sudah ada) |

### Langkah 10 — Evaluasi akhir, disposisi, mutu

| Aspek | Kondisi |
|---|---|
| Ada | `discharge_patient` + `DischargeRecord` (kondisi, resume, edukasi, obat, kontrol, SKDP) (`pasien/models.py:739-767,950-992`); `kunjungan_disposisi` 5 aksi (`pasien/views.py:1541-1601`); bed booking + `bed_management` (`views.py`; `templates/pasien/bed_management.html`); cetak SPRI/SKDP/resume; `KorelasiEpAsesmen` per kunjungan; indikator mutu + PDCA + insiden |
| Hilang | Kondisi akhir + respons terapi terstruktur untuk RAJAL (yang ada `KONDISI_AKHIR_CHOICES` khusus IGD, `:497-502`); TTV pulang khusus; panel versi/waktu; laporan risiko unit otomatis dari dropdown; ekspor PDF bukti EP per kunjungan; penguncian RME rajal (tidak ada workflow → tidak ada FINAL) |
| Harus dibangun | Field evaluasi akhir rajal + kunci + addendum; ekspor bukti |
| Model diperluas | `KunjunganPasien`/`DischargeRecord` + workflow (lihat G-1) |

---

## G. Risiko teknis & keputusan arsitektur

1. **Duplikasi mesin alur.** Membuat `PoliJantungWorkflow` baru akan menggandakan versi optimistik, replay `request_id`, digest tanda tangan, dan guard. **Rekomendasi:** generalisasi `IgdAssessmentWorkflow` (tambah penanda jenis alur + skema langkah) dan pakai ulang `save_step`/`perform_action`; jangan bikin keluarga model kedua (`pasien/models.py:1443-1510`).
2. **Penulis ganda.** `cppt_tambah`, `rajal_soap_simpan`, `order_penunjang_buat`, `igd_asesmen_awal_save` menulis langsung ke model tanpa versi/digest. Bila alur baru hidup berdampingan, data akan bercabang. **Rekomendasi:** perluas `_WORKFLOW_GUARDED_VIEWS` (`pasien/urls.py:150-161`) agar penulis lama ditutup untuk episode yang sudah punya alur, dan perbaiki dulu bug field SOAP.
3. **`poliklinik` tanpa FK.** Nilai bercampur kode/label/teks bebas (`akreditasi/layanan_unit.py:6-20`; data dev). Setiap filter `icontains` rapuh dan hitungan per poli salah untuk baris ber-kode (`pasien/views.py:1333`). **Rekomendasi:** jangan menambah logika string baru; pakai `layanan_unit.visit_unit_code`/`unit_kerja` sebagai sumber otorisasi, dan pertimbangkan FK `unit_layanan` bila plan menyentuh registrasi.
4. **Tidak ada tarif untuk RAJAL.** `_kelompok_for` jatuh ke `KelompokLayanan.kode == 'RAJAL'` yang tidak ada (DB hanya IGD/JANTUNG-inap/PARU/…), sehingga `resolve()` → `None` dan tidak ada billing (`klinis/services/tarif.py:5-52`). **Rekomendasi:** putuskan lebih dulu apakah poli jantung memakai `KelompokLayanan` baru atau tarif per-item; tanpa itu Langkah 7/9 tidak bisa menagih.
5. **Katalog obat kosong.** DB: 0 kelas/generik/produk; importer ada tetapi belum dijalankan (`klinis/management/commands/import_medication_catalogue.py`). Tanpa data, e-resep GDMT mustahil. **Rekomendasi:** jadikan seeding katalog obat prasyarat, bukan tugas UI.
6. **Tidak ada mesin interaksi obat.** `evaluate_prescription` hanya alergi/duplikasi/overlap/PPRA (`pasien/services/medication_safety.py:16-62`). Spesifikasi menjanjikan cek interaksi + kontraindikasi kehamilan. **Rekomendasi:** perluas `MedicationPolicy.rules` + `flags` produk; jangan bikin tabel interaksi terpisah tanpa data source.
7. **Katalog akreditasi 2022 aktif.** Klaim "pemetaan otomatis STARKES 2024" tidak berlaku sampai cutover dijalankan (`fixtures/standar_akreditasi_2024.json`; `akreditasi/management/commands/starkes_2024_cutover.py:1-30`). **Rekomendasi:** jangan menulis kode EP dengan kode sub-standar 2024 sebelum katalog aktif; gunakan `AturanEpAsesmen`/`AturanEpTindakan` sebagai lapisan pemetaan.
8. **Fitur unggulan default mati.** `IGD_WORKFLOW_ENABLED` dan `IGD_PROFESSIONAL_CARE_ENABLED` default `false` (`config/settings.py:47-48`), sehingga wizard/CPPT profesional 404 atau ditolak. **Rekomendasi:** keputusan rilis harus eksplisit per modul; jangan mengandalkan flag yang sama untuk poli jantung.
9. **Klaim "sudah ada" mudah salah.** Beberapa tombol ada tetapi tidak berfungsi (SOAP rajal), beberapa model ada tetapi kosong (alergi terstruktur, formularium, katalog obat), beberapa ada tetapi hanya untuk IGD (resep, time-series TTV, workflow). **Rekomendasi:** acceptance criteria plan harus diuji lewat HTTP/DB, bukan keberadaan simbol.
10. **Uji regresi besar tapi tanpa pytest.** 161 modul uji ber-`TestCase` dengan `manage.py test`; harness QA memakai salinan DB + Playwright (`qa/runner.py:1-20`). **Rekomendasi:** ikuti konvensi `TestCase` + `ProfessionalCareCase` (`pasien/professional_test_support.py:1-30`); jangan menambah pytest.

---

## H. Daftar file yang kemungkinan disentuh

```
pasien/models.py
pasien/forms_igd_workflow.py
pasien/forms_igd_operations.py
pasien/igd_workflow_views.py
pasien/views.py
pasien/urls.py
pasien/decorators.py
pasien/unit_scope.py
pasien/physical_exam.py
pasien/triage.py
pasien/services/igd_assessment_workflow.py
pasien/services/igd_actions.py
pasien/services/igd_finalization.py
pasien/services/igd_planning.py
pasien/services/igd_diagnoses.py
pasien/services/penunjang_orders.py
pasien/services/penunjang_results.py
pasien/services/prescriptions.py
pasien/services/medication_safety.py
pasien/services/professional_cppt.py
pasien/services/professional_billing.py
pasien/services/igd_attachments.py
pasien/services/antrean.py
pasien/professional_care_models.py
pasien/expansion_models.py
pasien/pdf_utils.py
klinis/models.py
klinis/expansion_models.py
klinis/services/penunjang_catalogue.py
klinis/services/tarif.py
klinis/services/professional_tariffs.py
klinis/services/medication_catalogue.py
klinis/services/ai_igd.py
klinis/services/ai_igd_targets.py
klinis/services/ep_tindakan.py
klinis/services/saran.py
klinis/data/penunjang_catalogue.json
klinis/data/penunjang_activation.json
klinis/data/medication_catalogue.json
klinis/data/master_tarif.py
akreditasi/models.py
akreditasi/risiko_models.py
akreditasi/layanan_unit.py
akreditasi/ai_service.py
akreditasi/system_models.py
akreditasi/mutu_laporan.py
templates/pasien/rajal_dashboard.html
templates/pasien/pendaftaran_dashboard.html
templates/pasien/kunjungan_detail.html
templates/pasien/asesmen_awal_form.html
templates/pasien/_asesmen_awal_wizard.html
templates/pasien/igd_workflow.html
templates/pasien/_igd_ancillary_order.html
templates/pasien/_igd_medication_composer.html
templates/pasien/_igd_professional_cppt.html
templates/pasien/_igd_professional_execution.html
templates/pasien/_igd_physical_exam_form.html
templates/pasien/igd_workflow_resume.html
templates/pasien/cetak_skdp.html
templates/pasien/cetak_spri.html
templates/pasien/cetak_resume_igd.html
static/js/igd-assessment-workflow.js
static/js/igd-clinical-controls.js
static/js/igd-clinical-expansion.js
static/js/igd-professional-execution.js
static/js/igd-professional-cppt.js
static/js/igd-diagnosis-plan.js
static/js/igd-physical-exam.js
config/settings.py
docs/plans/2026-11-24-poli-jantung-matriks-spesifikasi.md
```
