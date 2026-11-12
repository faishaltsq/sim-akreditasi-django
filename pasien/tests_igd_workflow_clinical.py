from pasien import tests_igd_workflow as fixtures


class IgdClinicalStepsTest(fixtures.IgdWorkflowTest):
    def test_allergy_and_local_examination_round_trip(self):
        from pasien.services.igd_assessment_workflow import save_step
        w = save_step(self.visit.pk, self.user, 3, {'skrining_alergi_status': 'TIDAK_DIKETAHUI'}, 0)
        marker = {'side': 'FRONT', 'x': 0.4, 'y': 0.3, 'label': 'Luka uji', 'kind': 'LUKA'}
        save_step(self.visit.pk, self.user, 6, {'fisik_lokalis': 'Luka lengan', 'penanda_anatomi': [marker]}, w.version)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.skrining_alergi_status, 'TIDAK_DIKETAHUI')
        self.assertEqual(self.visit.penanda_anatomi, [marker])

    def test_anatomical_coordinates_are_validated(self):
        from pasien.services.igd_assessment_workflow import save_step
        with self.assertRaises(ValueError):
            save_step(self.visit.pk, self.user, 6, {'penanda_anatomi': [{'side':'FRONT','x':2,'y':0.3,'label':'X','kind':'LUKA'}]}, 0)

    def test_morse_and_mst_are_computed_from_complete_answers(self):
        from pasien.services.igd_assessment_workflow import save_step
        detail = {'jatuh_riwayat':25,'jatuh_diagnosis':15,'jatuh_alat':0,'jatuh_infus':20,'jatuh_jalan':10,'jatuh_mental':0}
        save_step(self.visit.pk, self.user, 5, {'skrining_jatuh_detail':detail, 'skrining_gizi_detail':{'berat_badan':2,'nafsu_makan':1}}, 0)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.skrining_jatuh_skor, 70)
        self.assertEqual(self.visit.skrining_jatuh_grade, 'TINGGI')
        self.assertEqual(self.visit.skrining_gizi_mst, 3)

    def test_master_mode_rejects_unknown_code(self):
        from pasien.services.igd_assessment_workflow import save_step
        with self.assertRaises(ValueError):
            save_step(self.visit.pk,self.user,8,{'diagnosis_mode':'MASTER','diagnosa_masuk':'NOT.EXISTS'},0)

    def test_ai_provenance_cannot_be_forged(self):
        from pasien.services.igd_assessment_workflow import save_step
        with self.assertRaises(ValueError):
            save_step(self.visit.pk,self.user,8,{'diagnosis_mode':'AI','diagnosa_masuk':'R50.9'},0)
