# STARKES 2024 Cutover Runbook

Replacing the 2022 accreditation catalogue (Kepmenkes 1128/2022) with
STARKES 2024 (KMK HK.01.07/MENKES/1596/2024).

Source of truth: `C:\Users\cubeb\Downloads\starkes 2024.pdf` (356 pages).
Parsed result: **794 EP across 16 chapters**, no duplicate codes.

## 1. What the code does

| Step | Behaviour |
|---|---|
| Parse | `import_instrumen_2024` reads the PDF; EP blocks stop at a repeated letter so a standard cannot absorb the next one |
| Import | Upserts 16 `Category` rows and 794 `StandardItem` rows under the 2024 `Framework` |
| Retire | Colliding legacy codes become `<code> [2022]`; the original rows stay queryable for historical audit |
| Move scores | `QualityRecord` rows whose code exists in both editions are re-pointed to the 2024 item (one record per item) |
| Report | Unmatched scores are written to JSON for manual review; nothing is deleted |
| Activate | `Framework.is_active` marks 2024 as the catalogue the UI resolves |

## 2. Rehearsal result (local copy of production data)

```
Scores moved      : 31
Unmatched (manual): 267
Active catalogue  : STARKES Edisi 2024 / KMK HK.01.07/MENKES/1596/2024
EP in active      : 794
QualityRecord     : 298 total, 31 on 2024, 0 duplicates
```

Unmatched by chapter: TKRS 28, KPS 32, MFI 21, PMRIK 14, PPI 27, AKP 23,
HPK 11, PP 16, PAP 19, PAB 20, PKPO 20, KE 7, PROGNAS 5, PPK 6, PMKP 18.

These are EP codes present in 2022 but absent from 2024. Their scores remain
on the archived catalogue until someone maps them manually.

## 3. Cutover steps

The production `DATABASE_URL` is a write-only Vercel secret, so the data import
must run where that variable is available.

```bash
# 1. Backup (Supabase dashboard -> Database -> Backups, or pg_dump)
# 2. Dry-run first
python manage.py import_instrumen_2024 \
  --pdf-path "starkes 2024.pdf" --dry-run

# 3. Apply with score migration and report
python manage.py import_instrumen_2024 \
  --pdf-path "starkes 2024.pdf" \
  --replace \
  --mapping-report var/starkes-2024-mapping.json

# 4. Verify
python manage.py shell -c "
from akreditasi.models import Framework, StandardItem, QualityRecord
fw = Framework.active()
print(fw.name, fw.version)
print('EP', StandardItem.objects.filter(category__framework=fw).count())
print('QR', QualityRecord.objects.filter(standard_item__category__framework=fw).count())
"
```

## 4. Post-cutover checks

1. Sidebar shows 16 chapters (TKRS, KPS, MFK, PMKP, MRMIK, PPI, PPK, AKP, HPK,
   PP, PAP, PAB, PKPO, KE, SKP, PROGNAS).
2. No 500 on `/`, `/control/`, `/dashboard/`, `/rekap-kps/`.
3. `var/starkes-2024-mapping.json` reviewed by the accreditation owner; each
   unmatched row either mapped by hand or accepted as retired.
4. `manage.py test akreditasi sdm accounts` still green.

## 5. Rollback

Re-activate the archived framework and clear the sidebar cache:

```python
from django.core.cache import cache
from akreditasi.models import Framework
Framework.objects.update(is_active=False)
Framework.objects.filter(version__startswith='2022').update(is_active=True)
cache.clear()
```

Scores already moved to 2024 stay on their 2024 rows; the 2022 rows keep their
archived codes. Reversing the move is a separate, reviewed operation.
