"""Reviewed professional prices; unknown never means free."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.exceptions import ValidationError


def decimal_value(value, *, quantity=False):
    try:
        if isinstance(value, (bool, float)):
            raise ValueError
        result = Decimal(str(value))
        ceiling = Decimal('999999.99') if quantity else Decimal('9999999999.99')
        if not result.is_finite() or result < 0 or result > ceiling or (quantity and not result):
            raise ValueError
        if result != result.quantize(Decimal('.01')):
            raise ValueError
        return result.quantize(Decimal('.01'))
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValidationError('Nominal/kuantitas tidak valid atau melebihi presisi.') from exc


def price_breakdown(sarana, pelayanan, quantity):
    sarana, pelayanan = decimal_value(sarana), decimal_value(pelayanan)
    quantity = decimal_value(quantity, quantity=True)
    unit = decimal_value(sarana + pelayanan)
    subtotal = unit * quantity
    if subtotal > Decimal('999999999999.99'):
        raise ValidationError('Subtotal melebihi kapasitas penyimpanan.')
    return {'jasa_sarana': sarana, 'jasa_pelayanan': pelayanan, 'quantity': quantity,
            'unit_total': unit, 'subtotal': subtotal.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)}


def quote_professional_service(visit, context, service, *, at, quantity=Decimal('1'), for_update=False):
    from django.db.models import Q
    from klinis.models import LayananProfesional, TarifLayananProfesi
    from sdm.services.professional_care import business_date, locked
    from pasien.services.igd_actions import digest
    day=business_date(at)
    if context['service_id']!=service.pk or context['unit_id']!=visit.unit_kerja_id:
        raise ValidationError('Contexte layanan/unit tidak sesuai.')
    service=locked(LayananProfesional.objects.filter(pk=service.pk),for_update).get()
    if not service.is_active or not service.reviewed_at or not service.reviewed_by_id:
        raise ValidationError('Sumber layanan tidak aktif.')
    quantity=decimal_value(quantity,quantity=True)
    if context.get('limits_policy'):
        from sdm.professional_policy import enforce_limits
        enforce_limits(context['limits_policy'],visit,day,quantity)
    qs=TarifLayananProfesi.objects.filter(service=service,unit_id=visit.unit_kerja_id,profession_id=context['profession_id'],grade_id=context['grade_id'],payor=visit.penjamin,review_state='APPROVED',is_active=True,valid_from__lte=day).filter(Q(valid_until__isnull=True)|Q(valid_until__gte=day))
    prices=list(locked(qs,for_update)[:2])
    if len(prices)>1:raise ValidationError('Tarif ambigu; perlu peninjauan.')
    price=prices[0] if prices else None
    quote={'price_id':None,'price_version':None,'service_id':service.pk,'service_source':service.source_version,
           'business_date':day.isoformat(),'payor':visit.penjamin,'unit_id':visit.unit_kerja_id,
           'profession_id':context['profession_id'],'grade_id':context['grade_id'],'quantity':quantity,
           'status':'UNPRICED','unit_total':None,'subtotal':None,'jasa_sarana':None,'jasa_pelayanan':None,
           'professional_context':context}
    if price:
        price.full_clean()
        quote.update(price_breakdown(price.jasa_sarana,price.jasa_pelayanan,quantity),price_id=price.pk,price_version=price.version,status='FREE' if price.is_free else 'POSTED',price_source=price.source_version)
    quote['fingerprint']=digest(quote)
    return quote
