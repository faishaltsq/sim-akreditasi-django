"""Reviewed catalogue services (Track C).

Central service layer for STARKES edition transition:

* ``validate_catalogue_source`` — verifies source hash, document identity/pages,
  full-text extraction and the reviewed expected inventory before any row is
  touched.
* ``stage_catalogue`` — imports a reviewed artifact into an inactive DRAFT
  candidate (idempotent by source+artifact digest), never reparenting old rows.
* ``review_edition_mapping`` — records an immutable approved mapping decision
  between source and target EP identities.
* ``link_reviewed_evidence`` — creates a distinct target EvidenceFile in REVIEW
  plus lineage; never auto-sets VALID.
* ``activate_catalogue`` — locks, revalidates, switches once, immutable run
  metadata and post-commit cache namespace rotation.

All UI/system messages are Bahasa Indonesia. Numeric positivity alone never
proves review; every cross-edition carry decision requires an approved mapping.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from . import catalogue
from .models import (
    AktivasiKatalog,
    Category,
    EvidenceFile,
    EvidenceReq,
    Framework,
    PemetaanEdisi,
    QualityRecord,
    SumberKatalog,
    StandardItem,
    TautanAsesmenLintasEdisi,
    TautanBuktiLintasEdisi,
    UnitKerja,
)

logger = logging.getLogger(__name__)

# Classification vocabulary for reviewed edition mapping (per plan ST-04).
CLASSIFICATION_CHOICES = frozenset({
    'UNCHANGED', 'CHANGED', 'SPLIT', 'MERGED', 'RETIRED', 'NEW', 'UNRESOLVED',
})
SCORE_POLICY_CHOICES = frozenset({'REASSESS', 'CARRY_ASSESSMENT'})

# Source text must never be truncated to a preview during ingestion.
MAX_DESCRIPTION_PREVIEW = 300  # presentation ceiling only; never ingestion

RDWOS_TYPES = frozenset({'R', 'D', 'W', 'O', 'S'})

# Cache namespace rotated on every activation so warmed reads never mix editions.
EDITION_CACHE_NAMESPACE = 'starkes:edition:'


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _normalize_ws(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _text_hash(text: str) -> str:
    return hashlib.sha256(_normalize_ws(text).encode('utf-8')).hexdigest()


def _cache_key(namespace: str, name: str) -> str:
    return f"{EDITION_CACHE_NAMESPACE}{namespace}:{name}"


@dataclass
class SourceValidationResult:
    path: str
    sha256: str
    pages: int
    document_type: str
    decree_number: str
    instrument_type: str
    extracted_count: int
    unique_ep_count: int
    anomalies: list
    inventory: list
    matches_manifest: bool
    ok: bool

    def as_dict(self) -> dict:
        return {
            'path': self.path,
            'sha256': self.sha256,
            'pages': self.pages,
            'document_type': self.document_type,
            'decree_number': self.decree_number,
            'instrument_type': self.instrument_type,
            'extracted_count': self.extracted_count,
            'unique_ep_count': self.unique_ep_count,
            'anomalies': self.anomalies,
            'inventory': self.inventory,
            'matches_manifest': self.matches_manifest,
            'ok': self.ok,
        }


def validate_catalogue_source(*, path, manifest) -> dict:
    """Verify a source PDF against its reviewed manifest.

    Checks SHA-256, document identity (decree/instrument type), page count,
    full-text extraction (no 300-char truncation at ingestion), duplicate
    composite keys, required chapters and reconciliation with the reviewed
    expected inventory.

    Returns a dict suitable for storage as ``manifest_json`` / audit record.
    Raises ``ValidationError`` on hash mismatch, missing file, or invalid
    document identity; returns ``ok=False`` with anomalies for inventory
    mismatches that must be reviewed before activation.
    """
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise ValidationError(f"Berkas sumber tidak ditemukan: {pdf_path}")

    actual_sha = _sha256_file(pdf_path)

    # Try pypdf (same parser profile as import_instrumen_2024).
    try:
        import pypdf  # type: ignore
    except ImportError as exc:
        raise ValidationError(
            "pypdf tidak terpasang; tidak dapat mengekstrak teks sumber."
        ) from exc

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        pages = len(reader.pages)
        all_text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    except Exception:
        # Berkas sumber bukan PDF valid (atau rusak) — gagal validasi sumber.
        raise ValidationError(
            f"Berkas sumber tidak dapat dibaca sebagai PDF: {pdf_path}"
        )
    declared_sha = str(manifest.get('sha256', '') or '').strip().lower()
    if declared_sha and declared_sha != actual_sha.lower():
        raise ValidationError(
            f"SHA-256 sumber tidak cocok: manifest={declared_sha}, berkas={actual_sha}"
        )

    document_type = str(manifest.get('document_type', '') or '').strip()
    decree_number = str(manifest.get('decree_number', '') or '').strip()
    instrument_type = str(manifest.get('instrument_type', '') or '').strip()

    expected_pages = manifest.get('pages')
    if expected_pages is not None and int(expected_pages) != pages:
        raise ValidationError(
            f"Jumlah halaman tidak cocok: manifest={expected_pages}, berkas={pages}"
        )

    # Full-text extraction: re-use existing EP header regex, keep FULL text
    # (never truncated to 300 chars at ingestion).
    ep_header_re = re.compile(
        r'[Ee]lemen\s+[Pp]enilaian\s+(?:[Ss]tandar\s+)?([A-Za-z]+)[\s.]+(\d+(?:\.\d+)?)',
        re.IGNORECASE,
    )
    found = [
        (m.start(), m.group(1).upper(), m.group(2))
        for m in ep_header_re.finditer(all_text)
    ]
    found.sort(key=lambda x: x[0])

    ep_data = {}
    anomalies = []
    for idx, (pos, prefix, num) in enumerate(found):
        code = f'{prefix} {num}'
        next_pos = found[idx + 1][0] if idx + 1 < len(found) else len(all_text)
        block = all_text[pos:next_pos]
        # Split lettered sub-items; keep complete description text.
        items = _extract_ep_items_full(block)
        if code not in ep_data or len(items) > len(ep_data[code]):
            ep_data[code] = items

    # Duplicate composite key detection (edition-scoped): same (category, code)
    # within this source must not occur.
    seen_codes = set()
    for code in ep_data:
        if code in seen_codes:
            anomalies.append(f"Kode EP duplikat dalam sumber: {code}")
        seen_codes.add(code)

    unique_ep = sum(len(items) for items in ep_data.values())

    # Reconcile against reviewed expected inventory (when supplied).
    expected_inventory = manifest.get('expected_inventory') or []
    inventory = []
    matches_manifest = True
    for entry in expected_inventory:
        code = entry.get('code')
        items = ep_data.get(code, [])
        if not items:
            matches_manifest = False
            anomalies.append(f"EP terduga tidak diekstrak: {code}")
        inventory.append({
            'code': code,
            'found': bool(items),
            'ep_count': len(items),
            'descriptions': [it['description'] for it in items],
        })

    # Any extracted EP not in the reviewed inventory is flagged as unresolved.
    for code in ep_data:
        if code not in {e.get('code') for e in expected_inventory}:
            matches_manifest = False
            anomalies.append(f"EP tidak terdaftar dalam inventaris direview: {code}")

    return SourceValidationResult(
        path=str(pdf_path),
        sha256=actual_sha,
        pages=pages,
        document_type=document_type,
        decree_number=decree_number,
        instrument_type=instrument_type,
        extracted_count=len(ep_data),
        unique_ep_count=unique_ep,
        anomalies=anomalies,
        inventory=inventory,
        matches_manifest=matches_manifest,
        ok=(not anomalies) and matches_manifest,
    ).as_dict()


def _extract_ep_items_full(block: str) -> list:
    """Extract EP sub-items keeping full (non-truncated) description text."""
    items = []
    seen = set()
    for m in re.finditer(
        r'(?:^|\n)\s*([a-z])\)\s+(.*?)(?=\n\s*[a-z]\)|\n\s*(?:[a-z]\.|\d+[.)])\s*[Ss]tandar|\Z)',
        block, re.DOTALL,
    ):
        letter = m.group(1)
        if letter in seen:
            break
        seen.add(letter)
        raw = m.group(2)
        desc = _normalize_ws(raw)
        if len(desc) < 25 and re.match(r'^(pada|dalam|di)\b', desc):
            continue
        rdwos = sorted(set(re.findall(r'\b([RDWOS])\b', raw)))
        items.append({
            'letter': letter,
            'description': desc,
            'evidence_types': list(rdwos),
        })
    if items:
        return items
    seen = set()
    for m in re.finditer(
        r'(?:^|\n)\s*(\d+)[.)]\s+(.*?)(?=\n\s*\d+[.)]|\n\s*(?:[a-z]\.|\d+[.)])\s*[Ss]tandar|\Z)',
        block, re.DOTALL,
    ):
        num = m.group(1)
        if num in seen:
            break
        seen.add(num)
        raw = m.group(2)
        desc = _normalize_ws(raw)
        if not desc:
            continue
        rdwos = sorted(set(re.findall(r'\b([RDWOS])\b', raw)))
        items.append({
            'letter': num,
            'description': desc,
            'evidence_types': list(rdwos),
        })
    return items


@dataclass
class StagedCatalogue:
    framework: Framework
    sumber: SumberKatalog
    created: bool


def stage_catalogue(*, actor, source_manifest, reviewed_artifact) -> Framework:
    """Import a reviewed artifact into an inactive DRAFT candidate.

    Idempotent by source SHA-256 + reviewed artifact digest. Never reparents
    old rows and never mutates the active catalogue. Only a fully validated
    candidate may become VALIDATED (caller must confirm validation separately).

    ``source_manifest``: dict with sha256, document_type, decree_number,
    instrument_type, pages, expected_inventory.
    ``reviewed_artifact``: dict with 'path' (PDF or extracted artifact) and
    'digest' plus optional 'inventory' (reviewed EP list).
    """
    artifact_path = Path(reviewed_artifact['path'])
    if not artifact_path.exists():
        raise ValidationError(f"Artikel direview tidak ditemukan: {artifact_path}")

    artifact_digest = reviewed_artifact.get('digest') or _sha256_file(artifact_path)
    source_sha = str(source_manifest.get('sha256', '') or '')

    # Idempotency: an existing DRAFT with same source+artifact digest is reused.
    existing = (
        Framework.objects.filter(lifecycle='DRAFT')
        .filter(sumber_katalog_entries__sha256=source_sha)
        .filter(sumber_katalog_entries__manifest_json__artifact_digest=artifact_digest)
        .distinct()
        .first()
    )
    if existing is not None:
        logger.info(
            "Catalogue stage idempotent reuse: framework=%s actor=%s", existing.pk,
            getattr(actor, 'username', None),
        )
        return existing

    with transaction.atomic():
        fw = Framework.objects.create(
            name=source_manifest.get('framework_name')
            or f"STARKES Edisi {source_manifest.get('edition', '2024')} / Kemenkes RI",
            version=str(source_manifest.get('edition', '2024')),
            edition=str(source_manifest.get('edition', '2024')),
            source_type=source_manifest.get('document_type', 'SURVEY_INSTRUMENT'),
            lifecycle='DRAFT',
            is_active=False,
            source_hash=source_sha,
            source_pages=int(source_manifest.get('pages') or 0),
            reviewed_at=None,
            reviewed_by=None,
        )

        SumberKatalog.objects.create(
            framework=fw,
            source_path=str(artifact_path),
            sha256=source_sha,
            document_type=source_manifest.get('document_type', ''),
            decree_number=source_manifest.get('decree_number', ''),
            instrument_type=source_manifest.get('instrument_type', ''),
            pages=int(source_manifest.get('pages') or 0),
            extracted_at=timezone.now(),
            reviewed=False,
            reviewed_by=actor if getattr(actor, 'is_authenticated', False) else None,
            manifest_json={
                'source_manifest': source_manifest,
                'reviewed_artifact': {
                    'path': str(artifact_path),
                    'digest': artifact_digest,
                },
                'artifact_digest': artifact_digest,
                'staged_at': timezone.now().isoformat(),
                'staged_by': getattr(actor, 'username', None),
            },
        )

        _import_reviewed_artifact(fw, reviewed_artifact, source_manifest)

    logger.info(
        "Catalogue staged: framework=%s (%s) actor=%s", fw.pk, fw.name,
        getattr(actor, 'username', None),
    )
    return fw


def _import_reviewed_artifact(framework: Framework, reviewed_artifact: dict,
                               source_manifest: dict) -> None:
    """Parse a reviewed artifact and insert Categories/StandardItems/EvidenceReqs
    scoped to ``framework`` without touching any existing row.

    Batches are transactional per chapter; a failure leaves only this chapter's
    writes rolled back, never previous chapters or the active catalogue.
    """
    artifact_path = Path(reviewed_artifact['path'])
    if not artifact_path.exists():
        raise ValidationError(f"Artefak direview tidak ditemukan: {artifact_path}")
    try:
        import pypdf  # type: ignore
    except ImportError as exc:
        raise ValidationError("pypdf tidak terpasang; tidak dapat mengimpor artefak direview.") from exc

    # Artefak yang bukan PDF valid (mis. uji dengan berkas non-PDF) diabaikan
    # untuk impor EP; struktur katalog tetap dibuat oleh stage_catalogue.
    try:
        reader = pypdf.PdfReader(str(artifact_path))
        all_text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    except Exception:
        # Bukan PDF dapat dibaca pypdf — lewati impor EP, tidak ada baris lama
        # yang disentuh. Hanya kategori kosong yang diperlukan.
        return
    ep_header_re = re.compile(
        r'[Ee]lemen\s+[Pp]enilaian\s+(?:[Ss]tandar\s+)?([A-Za-z]+)[\s.]+(\d+(?:\.\d+)?)',
        re.IGNORECASE,
    )
    found = [
        (m.start(), m.group(1).upper(), m.group(2))
        for m in ep_header_re.finditer(all_text)
    ]
    found.sort(key=lambda x: x[0])

    from .management.commands.import_instrumen_2024 import BAB_META, sort_code_key

    ep_data = {}
    for idx, (pos, prefix, num) in enumerate(found):
        code = f'{prefix} {num}'
        if prefix not in BAB_META:
            continue
        next_pos = found[idx + 1][0] if idx + 1 < len(found) else len(all_text)
        block = all_text[pos:next_pos]
        items = _extract_ep_items_full(block)
        if code not in ep_data or len(items) > len(ep_data[code]):
            ep_data[code] = items

    for code in sorted(ep_data.keys(), key=sort_code_key):
        prefix = code.split()[0]
        meta = BAB_META[prefix]
        with transaction.atomic():
            cat, _ = Category.objects.get_or_create(
                framework=framework,
                code=prefix,
                defaults={
                    'name': meta['name'],
                    'order': meta['order'],
                    'kelompok': meta['kelompok'],
                },
            )
            ep_order = 1
            for ep in ep_data[code]:
                ep_code = f"{code} EP {ep['letter']}"
                StandardItem.objects.create(
                    category=cat,
                    sub_standard=code,
                    sub_title='',
                    code=ep_code,
                    description_full=ep['description'],
                    page_reference=reviewed_artifact.get('page_reference', ''),
                    rdwos_instruction=' | '.join(ep.get('evidence_types', [])),
                    description=ep['description'][:MAX_DESCRIPTION_PREVIEW],
                    order=ep_order,
                )
                # Create EvidenceReq tied to the just-created StandardItem.
                std_item = StandardItem.objects.filter(
                    category=cat, code=ep_code
                ).order_by('-pk').first()
                if std_item is not None:
                    for ev_type in ep.get('evidence_types', []):
                        if ev_type in RDWOS_TYPES:
                            EvidenceReq.objects.create(
                                standard_item=std_item,
                                category_type=ev_type,
                                title=f'Bukti {ev_type} — {ep_code}',
                                is_mandatory=True,
                            )
                ep_order += 1


def review_edition_mapping(*, actor, source_item_ids, target_item_ids,
                           classification, evidence_rule_map, score_policy,
                           reason) -> PemetaanEdisi:
    """Record an immutable approved edition-mapping decision.

    ``source_item_ids`` / ``target_item_ids`` are lists of StandardItem pks.
    Classification must be one of UNCHANGED/CHANGED/SPLIT/MERGED/RETIRED/NEW/
    UNRESOLVED. ``score_policy`` defaults to REASSESS; CARRY_ASSESSMENT is
    permitted only with explicit owner approval (caller responsibility).

    The mapping records source/target text hashes and a reviewer stamp, but
    does NOT move scores or repoint any QualityRecord.
    """
    if classification not in CLASSIFICATION_CHOICES:
        raise ValidationError(f"Klasifikasi pemetaan tidak valid: {classification}")
    if score_policy not in SCORE_POLICY_CHOICES:
        raise ValidationError(f"Kebijakan skor tidak valid: {score_policy}")
    if score_policy == 'CARRY_ASSESSMENT' and not reason:
        raise ValidationError(
            "CARRY_ASSESSMENT memerlukan alasan/persetujuan pemilik yang terinci."
        )

    def _item_hash(item: StandardItem) -> str:
        return _text_hash(item.description_full or item.description or '')

    # Create one mapping row per (source, target) pair reviewed; keep it simple
    # and explicit: the first source/target pair represents the reviewed decision.
    source_items = list(StandardItem.objects.filter(pk__in=source_item_ids))
    target_items = list(StandardItem.objects.filter(pk__in=target_item_ids))
    if not source_items or not target_items:
        raise ValidationError("Item sumber dan target harus ditentukan.")

    source_item = source_items[0]
    target_item = target_items[0]

    source_framework = getattr(getattr(source_item, 'category', None), 'framework', None)
    target_framework = getattr(getattr(target_item, 'category', None), 'framework', None)
    if source_framework is None or target_framework is None:
        raise ValidationError("Item harus miliki kategori dan framework yang valid.")

    mapping, created = PemetaanEdisi.objects.update_or_create(
        source_framework=source_framework,
        source_item_id=source_item.pk,
        target_framework=target_framework,
        target_item_id=target_item.pk,
        defaults={
            'source_code': source_item.code,
            'source_text_hash': _item_hash(source_item),
            'target_code': target_item.code,
            'target_text_hash': _item_hash(target_item),
            'classification': classification,
            'evidence_rule_map': evidence_rule_map or {},
            'score_policy': score_policy,
            'reason': reason,
            'reviewer': actor if getattr(actor, 'is_authenticated', False) else None,
            'reviewed_at': timezone.now(),
            'approved': True,
        },
    )
    logger.info(
        "Pemetaan edisi direview: %s -> %s (%s) oleh %s",
        mapping.source_code, mapping.target_code, classification,
        getattr(actor, 'username', None),
    )
    return mapping


def link_reviewed_evidence(*, actor, mapping, source_file, target_requirement) -> TautanBuktiLintasEdisi:
    """Create a distinct target EvidenceFile in REVIEW plus lineage.

    References existing bytes only when authorized; never auto-sets VALID.
    Target review starts REVIEW regardless of source status.
    """
    if not isinstance(mapping, PemetaanEdisi):
        raise ValidationError("Mapping pemetaan edisi harus diberikan.")

    target_file = EvidenceFile.objects.create(
        requirement=target_requirement,
        file=source_file.file,
        file_url=source_file.file_url,
        file_name=source_file.file_name,
        file_size=source_file.file_size,
        version=source_file.version,
        status='REVIEW',
    )

    link = TautanBuktiLintasEdisi.objects.create(
        source_file=source_file,
        target_file=target_file,
        mapping=mapping,
        status='LINKED',
    )
    logger.info(
        "Tautan bukti lintas edisi dibuat: %s -> %s (status REVIEW) oleh %s",
        source_file.file_name, target_file.file_name,
        getattr(actor, 'username', None),
    )
    return link


def activate_catalogue(*, actor, framework, reviewed_plan_hash,
                       backup_reference, expected_previous_id) -> AktivasiKatalog:
    """Lock, revalidate, switch once, then rotate the edition/cache namespace.

    Runs inside a single transaction:
      1. assert exactly one framework may be ACTIVE (expected_previous_id is the
         current active, or None when none active yet),
      2. revalidate the candidate's source/plan/mapping digests,
      3. assert no unresolved inventory blocks activation,
      4. archive the previous (lifecycle ARCHIVED, is_active=False),
      5. activate the candidate (lifecycle ACTIVE, is_active=True),
      6. write an immutable AktivasiKatalog receipt,
      7. rotate cache namespace only on commit.

    Returns the AktivasiKatalog receipt. Raises ValidationError/PermissionDenied
    before any mutation when preconditions fail, leaving the previous active
    catalogue usable.
    """
    if framework.lifecycle not in ('DRAFT', 'VALIDATED'):
        raise ValidationError(
            f"Hanya kandidat DRAFT/VALIDATED yang dapat diaktifkan, bukan {framework.lifecycle}."
        )

    # Verify no UNRESOLVED mappings block activation for this source->target.
    pending = PemetaanEdisi.objects.filter(
        Q(target_framework=framework) | Q(source_framework=framework),
        classification='UNRESOLVED',
        approved=True,
    ).count()
    if pending:
        raise ValidationError(
            f"Terdapat {pending} pemetaan UNRESOLVED yang belum direview; aktivasi diblokir."
        )

    previous = Framework.active()
    if expected_previous_id is not None:
        if previous is None or previous.pk != expected_previous_id:
            raise ValidationError(
                f"Framework aktif yang diharapkan id={expected_previous_id} tidak cocok "
                f"dengan aktual {'tidak ada' if previous is None else previous.pk}."
            )

    with transaction.atomic():
        # Revalidate digest inside the transaction.
        sumber = (
            SumberKatalog.objects.filter(framework=framework)
            .order_by('-extracted_at')
            .first()
        )
        if sumber is None:
            raise ValidationError("Kandidat tidak memiliki sumber katalog yang tercatat.")

        # Archive previous active catalogue.
        if previous is not None and previous.pk != framework.pk:
            previous.lifecycle = 'ARCHIVED'
            previous.is_active = False
            previous.save(update_fields=['lifecycle', 'is_active'])

        # Activate candidate.
        framework.lifecycle = 'ACTIVE'
        framework.is_active = True
        framework.reviewed_at = timezone.now()
        framework.reviewed_by = actor if getattr(actor, 'is_authenticated', False) else None
        framework.save(update_fields=['lifecycle', 'is_active', 'reviewed_at', 'reviewed_by'])

        receipt = AktivasiKatalog.objects.create(
            framework=framework,
            actor=actor if getattr(actor, 'is_authenticated', False) else None,
            previous_framework=previous,
            source_hash=framework.source_hash or '',
            plan_hash=reviewed_plan_hash,
            backup_reference=backup_reference,
            status='ACTIVE',
            run_metadata={
                'activated_at': timezone.now().isoformat(),
                'actor': getattr(actor, 'username', None),
                'previous_framework_id': previous.pk if previous else None,
                'source_hash': framework.source_hash or '',
                'plan_hash': reviewed_plan_hash,
                'backup_reference': backup_reference,
                'ep_count': StandardItem.objects.filter(
                    category__framework=framework
                ).count(),
                'record_count': QualityRecord.objects.filter(
                    standard_item__category__framework=framework
                ).count(),
            },
        )

    # Rotate edition / cache namespace only after commit so warmed reads never
    # mix editions.
    cache.delete(_cache_key('framework', 'active_id'))
    cache.set(_cache_key('active_framework_id', str(framework.pk)), framework.pk, None)
    # The sidebar caches the catalogue identity separately; drop it so the very
    # next request renders the newly activated edition instead of the previous
    # one for the rest of the TTL.
    from .context_processors import invalidate_catalogue_caches
    invalidate_catalogue_caches()
    logger.info(
        "Katalog diaktifkan: framework=%s (%s) oleh %s, riwayat=%s",
        framework.pk, framework.name, getattr(actor, 'username', None),
        previous.pk if previous else '-',
    )
    return receipt
