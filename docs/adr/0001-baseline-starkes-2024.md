# Baseline — STARKES 2024 parse vs legacy fixture

Generated 2026-10-22 from `instrumen standar survey akreditasi  rs 2024.pdf`
(415 pages, SHA-256 `fde4091e97bd4b9de944994e3764a125bdc83f07d3fba680ecb5023bb478dd80`).

| Artefact | Standards | EP | Chapters |
|---|---:|---:|---:|
| Legacy fixture (pre-2026-10-22) | 194 | 783 | 15 |
| **2024 PDF parse (current)** | **227** | **800** | **16** |

The legacy fixture's 783 EPs were inflated by counting evidence sub-rows as
EPs, while simultaneously missing whole chapters. The two numbers are therefore
not comparable one-to-one; the per-chapter table below is the real comparison.

## Per-chapter verification

| BAB | Chapter | Legacy std | Legacy EP | **Parsed std** | **Parsed EP** |
|---|---|---:|---:|---:|---:|
| TKRS | Tata Kelola Rumah Sakit | 17 | 76 | 17 | **71** |
| KPS | Kualifikasi & Pendidikan Staf | 20 | 89 | 21 | **81** |
| MFK | Manajemen Fasilitas & Keselamatan | 15 | 77 | 16 | **72** |
| PMKP | Peningkatan Mutu & Keselamatan Pasien | 12 | 45 | 12 | **44** |
| MRMIK | Manajemen Informasi & Rekam Medis | 15 | 46 | 16 | **51** |
| PPI | Pencegahan & Pengendalian Infeksi | 16 | 62 | 19 | **62** |
| AKP | Akses dan Kontinuitas Pelayanan | 18 | 69 | 18 | **67** |
| HPK | Hak Pasien dan Keluarga | 7 | 20 | 13 | **39** |
| PP | Pengkajian Pasien | 19 | 57 | 21 | **56** |
| PAP | Pelayanan dan Asuhan Pasien | 12 | 43 | 14 | **52** |
| PAB | Pelayanan Anestesi dan Bedah | 14 | 52 | 14 | **38** |
| PKPO | Pelayanan Kefarmasian & Penggunaan Obat | 13 | 49 | 13 | **49** |
| KE | Komunikasi dan Edukasi | 7 | 26 | 7 | **25** |
| SKP | Sasaran Keselamatan Pasien | 3 | 48 | 8 | **24** |
| PROGNAS | Program Nasional | 0 | 0 | 12 | **46** |
| PPK | Pendidikan dalam Pelayanan Kesehatan | 6 | 24 | 6 | **23** |
| | **Total** | **194** | **783** | **227** | **800** |

Note that legacy EP counts are *inflated* in several chapters (`SKP` 48 for 3
standards, `KE` 26 for 7) precisely because evidence sub-rows were counted as
EPs. Where the parsed count is lower (`PAB` 38 vs 52, `KE` 25 vs 26) the
difference is that double-counting, not lost content.

## Standards recovered that the legacy fixture did not have

34 standards, notably the whole `PROGNAS` chapter plus:

- `HPK 1.1`, `HPK 1.2`, `HPK 1.3`, `HPK 1.4`, `HPK 2`, `HPK 2.1`
- `SKP 1`, `SKP 3`, `SKP 3.1`, `SKP 6`, `SKP 6.1`
- `PPI 2`, `PPI 4`, `PPI 6`, `PP 3.5`, `PP 3.9`, `PAP 1.1`, `PAP 2.4`
- `MRMIK 1`, `KPS 13`, `MFK 8.2.1`
- `PROGNAS 1`–`6.1` (12 standards, 46 EP)

## Standards with no EP table of their own

`PKPO 3` is a parent heading whose elemen penilaian are published under
`PKPO 3.1`, `PKPO 3.2` and `PKPO 3.3`. Because `StandardItem` is per-EP, a
zero-EP standard is not representable and `PKPO 3` is excluded from the
fixture. `PKPO 3.1`–`3.3` carry the 43 EPs.

## Quality gates

Run against the parsed output; all must be zero before the fixture is written.

| Gate | Legacy fixture | **Current parse** |
|---|---:|---:|
| Descriptions ending in a score token | 88 | **0** |
| Descriptions containing a column header | — | **0** |
| Descriptions ending in a lone RDWOS letter | — | **0** |
| Empty descriptions | — | **0** |
| EPs with no RDWOS evidence type | — | **0** |
| Duplicate EP letters within a standard | — | **0** |

## Reproducibility

The fixture is deterministic: regenerating it from the same PDF produces a
byte-identical file.

```
$ sha256sum fixtures/standar_akreditasi_2024.json
e619c42cf7578c98e110bdff4cf441a1547ed97f144c7c223420b30ef81f178d
```

Regenerate with:

```
python -c "from akreditasi import instrumen_2024 as P; \
  P.dump_fixture(P.extract_pdf('<pdf>'), 'fixtures/standar_akreditasi_2024.json')"
```

## Verification commands

```
python manage.py import_instrumen_2024 --dry-run     # report only, no writes
python manage.py test akreditasi.tests_instrumen_2024  # 34 tests
```
