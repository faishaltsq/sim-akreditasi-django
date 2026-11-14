from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import Pasien, KunjunganPasien


class ProfessionalCareCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from klinis.models import LayananProfesional, PemetaanKewenanganLayanan
        from sdm.models import (Pegawai, MasterProfesiPegawai, MasterJenjangProfesi, KatalogTindakan,
                                PengajuanKredensial, KeputusanKredensial, PenugasanKlinis,
                                RincianKewenangan, ClinicalActionCode, PrivilegeSnapshot)
        cls.unit = UnitKerja.objects.get_or_create(code='IGD', defaults={'name':'IGD','level':2})[0]
        cls.user = User.objects.create_user('professional-qa')
        UserProfile.objects.update_or_create(user=cls.user, defaults={'role':'STAF_NAKES','profesi':'DOKTER_UMUM','unit_kerja':cls.unit})
        cls.patient = Pasien.objects.create(no_rm='QA-PROF', nama_lengkap='Sintetis Profesional', tanggal_lahir='1990-01-01', jenis_kelamin='L')
        cls.visit = KunjunganPasien.objects.create(pasien=cls.patient, no_kunjungan='QA-PROF',jenis_kunjungan='IGD',tanggal_masuk=timezone.now(),unit_kerja=cls.unit)
        cls.profession = MasterProfesiPegawai.objects.create(code='QA-DOK',nama='Dokter QA',keluarga='MEDIS',reviewed_by=cls.user,reviewed_at=timezone.now())
        cls.grade = MasterJenjangProfesi.objects.create(profesi=cls.profession,kode='QA1',nama='QA Grade',urutan=1)
        cls.employee = Pegawai.objects.create(akun=cls.user,nama_lengkap='PPA Sintetis',kategori='PPA',profesi_master=cls.profession,jenjang_master=cls.grade,data_origin='MANUAL')
        cls.catalogue = KatalogTindakan.objects.create(kode='QA-CARE',nama='Layanan QA',jenjang=cls.grade,tingkat_supervisi='M')
        today=timezone.localdate()
        cls.application=PengajuanKredensial.objects.create(employee=cls.employee,unit_kerja=cls.unit,status='DISETUJUI')
        cls.decision=KeputusanKredensial.objects.create(pengajuan=cls.application,outcome='DISETUJUI',decided_by=cls.user)
        cls.spk=PenugasanKlinis.objects.create(employee=cls.employee,unit_kerja=cls.unit,decision=cls.decision,nomor_spk='QA-SPK',berlaku_mulai=today-timedelta(days=2),berlaku_sampai=today+timedelta(days=2),issued_by=cls.user)
        cls.privilege=RincianKewenangan.objects.create(pengajuan=cls.application,catalog_item=cls.catalogue,kewenangan='QA',status_spk='DISETUJUI_MANDIRI')
        cls.action_code=ClinicalActionCode.objects.get_or_create(code='professional_care',defaults={'label':'Pelayanan profesional'})[0]
        cls.snapshot=PrivilegeSnapshot.objects.create(pegawai=cls.employee,unit_kerja=cls.unit,action_code=cls.action_code,valid_from=today-timedelta(days=2),valid_until=today+timedelta(days=2),source_decision=cls.spk,granted_by=cls.user)
        cls.service=LayananProfesional.objects.create(code='QA.CARE',name='Layanan QA',group='MEDICAL',authority_kind='CLINICAL',source_version='qa-fixture',reviewed_by=cls.user,reviewed_at=timezone.now(),is_active=True)
        cls.mapping=PemetaanKewenanganLayanan.objects.create(service=cls.service,catalog_item=cls.catalogue,source_version='qa-fixture',reviewed_by=cls.user,reviewed_at=timezone.now(),is_active=True)

    def context(self, **kwargs):
        from sdm.services.professional_care import resolve_professional_context
        return resolve_professional_context(self.user,self.visit,self.service,at=timezone.now(),**kwargs)

    def mentor(self):
        from sdm.models import Pegawai,PengajuanKredensial,KeputusanKredensial,PenugasanKlinis,RincianKewenangan,PrivilegeSnapshot
        user=User.objects.create_user('qa-mentor')
        UserProfile.objects.update_or_create(user=user,defaults={'role':'STAF_NAKES','profesi':'DOKTER_UMUM','unit_kerja':self.unit})
        employee=Pegawai.objects.create(akun=user,nama_lengkap='Pembimbing sintetis',kategori='PPA',profesi_master=self.profession,jenjang_master=self.grade,data_origin='MANUAL')
        application=PengajuanKredensial.objects.create(employee=employee,unit_kerja=self.unit,status='DISETUJUI')
        decision=KeputusanKredensial.objects.create(pengajuan=application,outcome='DISETUJUI',decided_by=self.user)
        spk=PenugasanKlinis.objects.create(employee=employee,unit_kerja=self.unit,decision=decision,nomor_spk='QA-MENTOR-SPK',berlaku_mulai=timezone.localdate(),issued_by=self.user)
        RincianKewenangan.objects.create(pengajuan=application,catalog_item=self.catalogue,kewenangan='QA',status_spk='DISETUJUI_MANDIRI')
        PrivilegeSnapshot.objects.create(pegawai=employee,unit_kerja=self.unit,action_code=self.action_code,valid_from=timezone.localdate(),source_decision=spk)
        return employee
