"""Executable, explicitly reviewed limits; no free-text interpretation."""
import hashlib
from django.core.exceptions import ValidationError,PermissionDenied
from klinis.services.professional_tariffs import decimal_value


def validate_limits(conditions):
    if not isinstance(conditions,dict) or not conditions or set(conditions)-{'min_age','max_age','max_quantity'}:
        raise ValidationError('Gunakan batas usia/kuantitas terstruktur yang ditinjau; batas lain belum didukung.')
    for key in ('min_age','max_age'):
        value=conditions.get(key)
        if key in conditions and value is None:raise ValidationError('Batas usia eksplisit tidak boleh null.')
        if value is not None and (isinstance(value,bool) or not isinstance(value,int) or not 0<=value<=150):raise ValidationError('Batas usia harus bilangan bulat 0–150.')
    if conditions.get('min_age',0)>conditions.get('max_age',150):raise ValidationError('Rentang usia tidak valid.')
    if 'max_quantity' in conditions:decimal_value(conditions['max_quantity'],quantity=True)
    return conditions


def enforce_limits(policy,visit,day,quantity=None):
    conditions=validate_limits(policy['conditions'])
    dob=visit.pasien._meta.get_field('tanggal_lahir').to_python(visit.pasien.tanggal_lahir)
    if dob is None or dob>day:raise PermissionDenied('Tanggal lahir valid diperlukan untuk mengevaluasi batas mandat.')
    age=day.year-dob.year-((day.month,day.day)<(dob.month,dob.day))
    if age<conditions.get('min_age',0) or age>conditions.get('max_age',150):raise PermissionDenied('Pasien di luar batas mandat yang disetujui.')
    if quantity is not None and 'max_quantity' in conditions and quantity>decimal_value(conditions['max_quantity'],quantity=True):raise PermissionDenied('Kuantitas melebihi batas mandat yang disetujui.')


def limits_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
