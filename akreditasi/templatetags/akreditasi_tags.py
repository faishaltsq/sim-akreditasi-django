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
