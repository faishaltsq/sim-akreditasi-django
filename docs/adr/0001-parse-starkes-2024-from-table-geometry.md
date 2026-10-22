# ADR 0001 — Parse STARKES 2024 from ruled-table geometry

**Status:** Accepted (2026-10-22)
**Context repo:** `sim-akreditasi-django`
**Supersedes:** the pypdf plain-text parser in
`akreditasi/management/commands/import_instrumen_2024.py` (pre-2026-10-22)

## Context

The 2024 Kemenkes instrument (`instrumen standar survey akreditasi  rs 2024.pdf`,
415 pages) is a typeset PDF whose Elemen-Penilaian tables are *ruled* tables.
The pre-existing importer extracted text with `pypdf.extract_text()` and split
it with regexes over concatenated lines. That approach produced a fixture with
three structural defects, all confirmed by inspection:

1. **Column mixing.** Description, evidence detail and score were concatenated,
   so EP descriptions carried the evidence letter and the score scale inline —
   e.g. `"... oleh Pemilik. R Penetapan Representasi ... 10 - 0"`.
   88 of 783 fixture EPs ended in a score token.
2. **Missing chapters.** `PROGNAS` was absent entirely; `HPK` had 7 of 13
   standards, `SKP` 3 of 8, `PPI` 16 of 19. 34 standards present in the PDF
   were missing from the fixture.
3. **Evidence sub-rows counted as EPs.** A single EP spans several grid rows
   (one per evidence item) with a merged description cell; the old parser
   treated each sub-row as a separate EP.

Plain text cannot disambiguate these because the disambiguating information is
geometric: which column a run sits in, and which band it belongs to.

## Decision

Parse the PDF from **table geometry**, not from text order.

- **Ruling lines come from `page.rects`, not `page.lines`.** The instrument
  draws borders as thin filled rectangles (`height <= 2.5pt` for horizontal
  rules, `width <= 2.5pt` for vertical). `page.lines` is empty on these pages.
- **A table is a maximal run of horizontal rules linked by vertical rules.**
  Rows are merged with a 2.0 pt tolerance; columns are the vertical rules that
  span at least half the table's height.
- **A logical EP is one band between two consecutive horizontal rules**, never
  a text line. Its description cell may wrap over many lines and its marker
  column may list several RDWOS letters; both belong to that one EP.
- **An EP marker is valid only as the first token of the description cell.**
  Prose such as `"... meliputi poin a) sampai i) ..."` therefore cannot open a
  row. Numeric markers (`1)`, `2)`) are equally valid — SKP and PROGNAS use
  them.
- **The evidence column is located structurally.** A narrow column
  (< 45 pt) immediately left of the `Kelengkapan Bukti` header carries the
  RDWOS letters. Tables that continue on a later page sometimes drop that
  narrow column, leaving the letter at the head of the evidence cell; the
  parser recovers it there.
- **The parse is pure and Django-free** (`akreditasi/instrumen_2024.py`) so it
  can be unit-tested without a database.
- **The import consumes a versioned golden fixture by default**
  (`fixtures/standar_akreditasi_2024.json`), with `--pdf-path` available to
  re-derive it. The fixture records the source PDF's SHA-256 so the provenance
  of every row is auditable.

### Tolerances

| Constant | Value | Reason |
|---|---|---|
| `RULE_TOL` | 2.0 pt | rules for one border are emitted as 2–3 abutting segments |
| `WORD_TOL` | 3.0 pt | words on one visual line differ by < 1 pt in `top` |
| `MIN_BAND` | 4.0 pt | bands thinner than this are collapsed rules, not rows |
| `MARKER_COL_MAX` | 45 pt | a wider column left of `Kelengkapan Bukti` is the description |

## Consequences

**Positive**

- Every EP's description, evidence types and score come from their own cells.
  Contamination is now structurally impossible, and `validate()` asserts it
  (score tokens, column headers, trailing evidence letters).
- Full chapter coverage: 16/16 chapters, 227 standards, 800 EPs — versus 194
  standards and 783 EPs with 34 standards missing and `PROGNAS` absent.
- The fixture is byte-for-byte reproducible from the PDF
  (SHA-256 `e619c42c…`), so a diff in the fixture means a real content change.
- Parsing is fast (~0.8 s for 415 pages once the extraction is cached) and the
  import needs no PDF at deploy time.

**Negative / accepted costs**

- Adds `pdfplumber` as a dependency, used only when re-deriving the fixture.
  The runtime import path reads JSON and needs neither `pdfplumber` nor
  `pypdf`.
- The geometry constants are tuned to this PDF. A re-typeset instrument would
  require re-verifying them — which is exactly what the golden fixture and its
  tests exist to catch.
- `PKPO 3` has no EP table of its own (its elemen penilaian are published
  under PKPO 3.1–3.3), so it is excluded from the fixture. `StandardItem` is
  per-EP, so a zero-EP standard is not representable.

## Verification

`akreditasi/tests_instrumen_2024.py` — 34 tests, all passing:

- **Fixture contract (18 tests):** 16 chapters present, no legacy prefixes,
  `ep_count` matches `eps`, unique letters, no score contamination, no column
  header leak, no trailing evidence letter, every EP carries an RDWOS type,
  provenance recorded, known previously-missing standards present.
- **Geometry (6 tests):** score/evidence separated from description, multiple
  evidence types per band, prose markers ignored, numeric markers supported,
  page-break continuation merged correctly, typographic variants
  (`Eleman Penilaian`, `Elemen Penelitian`) do not lose a table.
- **Import command (10 tests):** dry run writes nothing, every fixture EP is
  created, import is idempotent, `EvidenceReq` types match the source,
  chapter linkage correct, `--category` scoped, unknown chapter rejected,
  missing/corrupt fixture rejected, `--prune` removes stale EPs.

## Alternatives rejected

- **Keep the text parser and post-process the contamination.** The defects are
  not recoverable by regex: telling an evidence letter from a sentence letter,
  or a sub-row from an EP, requires the grid.
- **`pdfplumber.find_tables()`.** It infers edges and merges cells differently
  from the printed grid; on these pages it does not expose the narrow RDWOS
  column, which is precisely the column the parse depends on.
- **`pymupdf` / `pypdfium2` word extraction.** Viable for words, but neither
  exposes the ruling rectangles as directly as `page.rects`, so grid
  reconstruction would be guesswork.
- **Hardcode the standards in Python.** 800 EPs would be unmaintainable and
  unauditable against the source.
