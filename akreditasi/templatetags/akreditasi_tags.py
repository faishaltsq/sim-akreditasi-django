from django import template

register = template.Library()


@register.filter
def rupiah(value):
    try:
        value = float(value)
        if value == 0:
            return "Rp 0"
        return f"Rp {value:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


@register.filter
def evidence_badge_class(category_type):
    badges = {
        'R': 'badge-r',
        'D': 'badge-d',
        'W': 'badge-w',
        'O': 'badge-o',
        'S': 'badge-s',
    }
    return badges.get(str(category_type).upper(), 'bg-secondary')


@register.filter
def score_class(score):
    score = int(score) if score is not None else 0
    if score >= 10:
        return 'score-10'
    elif score >= 5:
        return 'score-5'
    return 'score-0'


@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (ZeroDivisionError, ValueError, TypeError):
        return 0


@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def pct(value, total):
    try:
        return round((float(value) / float(total)) * 100)
    except (ZeroDivisionError, ValueError, TypeError):
        return 0


@register.filter(is_safe=True)
def render_fmea_cards(text):
    """Render Failure Mode FMEA menjadi kartu visual bernomor urut jelas."""
    import re
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    if not text or not str(text).strip():
        return ""
    text = str(text).strip()
    parts = re.split(r"(?:^|\n+)(?=(?:\d+[\.\)]\s*(?:Mode Kegagalan:?|MODE KEGAGALAN:?)?|MODE KEGAGALAN\s*\d*:?))", text, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return mark_safe(f'<div class="p-2 bg-white rounded border font-monospace" style="font-size:.78rem; white-space:pre-wrap;">{escape(text)}</div>')

    items = []
    for idx, part in enumerate(parts, 1):
        reEfek = r"(?:\n\s*|\s{2,})(?:a\.\s*)?Efek(?:\s+Potensial)?\s*:"
        rePenyebab = r"(?:\n\s*|\s{2,})(?:b\.\s*)?(?:Akar\s+Masalah(?:\s*[\/\-]\s*Penyebab)?|Penyebab(?:\s*[\/\-]\s*Akar\s+Masalah)?|Penyebab(?:\s+Potensial)?)\s*:"
        reBarrier = r"(?:\n\s*|\s{2,})(?:c\.\s*)?(?:Barrier(?:\s*[\/\-]\s*Kontrol)?(?:\s+Pencegahan)?|Kontrol(?:\s+Pencegahan)?)\s*:"

        mEfek = re.search(reEfek, part, re.IGNORECASE)
        mPenyebab = re.search(rePenyebab, part, re.IGNORECASE)
        mBarrier = re.search(reBarrier, part, re.IGNORECASE)

        cuts = []
        if mEfek: cuts.append(("efek", mEfek.start()))
        if mPenyebab: cuts.append(("penyebab", mPenyebab.start()))
        if mBarrier: cuts.append(("barrier", mBarrier.start()))
        cuts.sort(key=lambda x: x[1])

        mode, efek, penyebab, barrier = "", "", "", ""
        if cuts:
            mode = part[:cuts[0][1]].strip()
            for i, (ctype, start_idx) in enumerate(cuts):
                end_idx = cuts[i+1][1] if i + 1 < len(cuts) else len(part)
                seg = part[start_idx:end_idx].strip()
                colon_pos = seg.find(":")
                content = seg[colon_pos+1:].strip() if colon_pos != -1 else seg
                if ctype == "efek": efek = content
                elif ctype == "penyebab": penyebab = content
                elif ctype == "barrier": barrier = content
        else:
            mode = part

        mode = re.sub(r"^\d+[\.\)]\s*", "", mode)
        mode = re.sub(r"^(?:Mode Kegagalan|MODE KEGAGALAN)\s*:\s*", "", mode, flags=re.IGNORECASE).strip()
        items.append((idx, mode, efek, penyebab, barrier))

    html = []
    for idx, mode, efek, penyebab, barrier in items:
        card = [
            f'<div class="card border mb-2" style="border-radius:8px; border-color:#e2e8f0; overflow:hidden;">',
            f'  <div class="card-header py-1 px-3 d-flex align-items-center gap-2 border-bottom" style="background:#f8fafc;">',
            f'    <span class="badge bg-primary px-2 py-0.5 font-monospace" style="font-size:.72rem;">Mode #{idx}</span>',
            f'    <span class="fw-bold text-dark" style="font-size:.82rem;">{escape(mode)}</span>',
            f'  </div>',
            f'  <div class="card-body p-2 bg-white d-flex flex-column gap-1">'
        ]
        if efek:
            card.append(f'    <div class="p-2 rounded" style="background:#fef2f2; border-left:3.5px solid #ef4444; font-size:.78rem;">'
                        f'      <div class="fw-bold text-danger mb-0.5"><i class="bi bi-exclamation-triangle-fill me-1"></i>a. Efek Potensial:</div>'
                        f'      <div class="text-dark" style="white-space:pre-wrap;">{escape(efek)}</div>'
                        f'    </div>')
        if penyebab:
            card.append(f'    <div class="p-2 rounded" style="background:#fffbeb; border-left:3.5px solid #f59e0b; font-size:.78rem;">'
                        f'      <div class="fw-bold text-warning-emphasis mb-0.5"><i class="bi bi-diagram-2 me-1"></i>b. Akar Masalah / Penyebab:</div>'
                        f'      <div class="text-dark" style="white-space:pre-wrap;">{escape(penyebab)}</div>'
                        f'    </div>')
        if barrier:
            card.append(f'    <div class="p-2 rounded" style="background:#f0fdf4; border-left:3.5px solid #22c55e; font-size:.78rem;">'
                        f'      <div class="fw-bold text-success mb-0.5"><i class="bi bi-shield-check me-1"></i>c. Barrier / Kontrol Pencegahan:</div>'
                        f'      <div class="text-dark" style="white-space:pre-wrap;">{escape(barrier)}</div>'
                        f'    </div>')
        card.append('  </div>')
        card.append('</div>')
        html.append("".join(card))
    return mark_safe("".join(html))


@register.filter(is_safe=True)
def render_rca_whys(text):
    """Render 5-Whys RCA menjadi daftar terstruktur bernomor urut jelas."""
    import re
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    if not text or not str(text).strip():
        return ""
    lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    if not lines:
        return ""

    html = ['<div class="d-flex flex-column gap-1">']
    for idx, line in enumerate(lines, 1):
        clean = re.sub(r"^\d+[\.\)]\s*", "", line)
        clean = re.sub(r"^Mengapa\s*\d*\s*[\:\-]?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^\(Akar Masalah Utama\)\s*[\:\-]?\s*", "", clean, flags=re.IGNORECASE).strip()
        is_root = (idx == len(lines)) or ('akar masalah utama' in line.lower())
        bg_col = "#fef2f2" if is_root else "#f8fafc"
        border_col = "#ef4444" if is_root else "#cbd5e1"
        badge_cls = "bg-danger" if is_root else "bg-secondary"
        lbl = f"Akar Masalah #{idx}" if is_root else f"Mengapa #{idx}"

        html.append(f'<div class="p-1.5 px-2 rounded d-flex align-items-start gap-2" style="background:{bg_col}; border-left:3px solid {border_col}; font-size:.78rem;">'
                    f'  <span class="badge {badge_cls} font-monospace" style="font-size:.68rem;">{lbl}</span>'
                    f'  <div class="text-dark" style="white-space:pre-wrap;">{escape(clean or line)}</div>'
                    f'</div>')
    html.append('</div>')
    return mark_safe("".join(html))


@register.filter(is_safe=True)
def render_structured_plan(value):
    """
    Render dense action plans (1. ... 2. ...) or bulleted lists into structured, readable steps
    sesuai rekomendasi tata letak laporan risiko standar STARKES/PMKP.
    """
    import re
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    if not value or not str(value).strip():
        return mark_safe('<span class="text-muted fst-italic">—</span>')

    text = str(value).strip()

    # Detect numbered list: 1. ... 2. ... (baik dalam 1 baris maupun multi-baris)
    num_pattern = r'(?:^|\s+)(?=\d+[\.\)]\s+)'
    parts = [p.strip() for p in re.split(num_pattern, text) if p.strip()]

    if len(parts) > 1 or re.match(r'^\d+[\.\)]\s+', text):
        out = ['<div class="action-plan-container d-flex flex-column gap-2">']
        for p in parts:
            m = re.match(r'^(\d+)[\.\)]\s*(.*)', p, re.DOTALL)
            if m:
                step_num, content = m.group(1), m.group(2).strip()
            else:
                step_num, content = "", p

            # Deteksi sub-poin jika dipisahkan oleh titik dua dengan kalimat lanjutan, atau baris baru
            sub_bullets = [s.strip() for s in re.split(r'\n+|\r\n+|;\s*', content) if s.strip()]

            out.append(
                f'<div class="plan-step-item d-flex align-items-start gap-2" style="font-size:0.8rem; line-height:1.5;">'
            )
            if step_num:
                out.append(
                    f'<span class="badge bg-teal-subtle text-teal fw-bold border border-teal-subtle step-badge px-1.5 py-0.5" '
                    f'style="font-size:0.7rem; min-width:24px; text-align:center;">{step_num}</span>'
                )
            if len(sub_bullets) > 1:
                out.append('<div class="flex-grow-1">')
                out.append(f'<div class="fw-semibold text-dark mb-1">{escape(sub_bullets[0])}</div>')
                out.append('<ul class="mb-0 ps-3 text-muted" style="font-size:0.77rem; list-style-type:circle;">')
                for sub in sub_bullets[1:]:
                    clean_sub = re.sub(r'^[•\-\*]\s*', '', sub).strip()
                    if clean_sub:
                        out.append(f'<li>{escape(clean_sub)}</li>')
                out.append('</ul>')
                out.append('</div>')
            else:
                out.append(f'<div class="flex-grow-1 text-dark">{escape(content)}</div>')
            out.append('</div>')
        out.append('</div>')
        return mark_safe("".join(out))

    # Detect bullet points: • or - or *
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) > 1 and any(l.startswith(('•', '-', '*')) for l in lines):
        out = ['<ul class="mb-0 ps-3" style="font-size:0.8rem; line-height:1.5;">']
        for line in lines:
            clean_line = re.sub(r'^[•\-\*]\s*', '', line).strip()
            if clean_line:
                out.append(f'<li class="mb-1 text-dark">{escape(clean_line)}</li>')
        out.append('</ul>')
        return mark_safe("".join(out))

    # Default fallback dengan linebreaksbr & line-height proporsional
    return mark_safe(f'<div style="font-size:0.8rem; line-height:1.5; word-break:break-word;">{escape(text)}</div>')

