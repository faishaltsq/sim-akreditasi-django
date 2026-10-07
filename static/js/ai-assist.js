/**
 * AI Assist Frontend Handler — SIM Akreditasi RS
 *
 * Mengatur interaksi tombol "✨ AI DeepSeek", loading state, modal preview,
 * dan penyalinan hasil rekomendasi ke field form target.
 *
 * KEAMANAN:
 * - Tidak ada API Key yang disimpan/dikenal di client side.
 * - Menggunakan CSRF token resmi Django pada setiap POST fetch.
 */

(function () {
    'use strict';

    // Helper CSRF Django
    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    // Modal Builder Dinamis
    function createOrGetAiModal() {
        let modalEl = document.getElementById('aiAssistModal');
        if (!modalEl) {
            const html = `
            <div class="modal fade" id="aiAssistModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered modal-lg">
                    <div class="modal-content shadow border-0" style="border-radius: 14px; overflow: hidden;">
                        <div class="modal-header text-white" style="background: linear-gradient(135deg, #0f766e, #0d9488);">
                            <div class="d-flex align-items-center gap-2">
                                <span class="badge bg-white text-teal px-2 py-1" style="color: #0f766e !important; font-weight: 700;">
                                    <i class="bi bi-stars me-1"></i>DeepSeek AI
                                </span>
                                <h6 class="modal-title fw-bold mb-0 text-white" id="aiModalTitle">Rekomendasi AI Asisten Cerdas</h6>
                            </div>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body p-4" id="aiModalBody">
                            <div class="text-center py-5" id="aiModalLoading">
                                <div class="spinner-border text-teal mb-3" style="width: 3rem; height: 3rem; color: #0d9488;" role="status"></div>
                                <h6 class="fw-bold text-dark">DeepSeek sedang menganalisis standar akreditasi...</h6>
                                <p class="text-muted small mb-0">Menyesuaikan regulasi KARS STARKES 2022 & keselamatan pasien.</p>
                            </div>
                            <div id="aiModalContent" style="display: none;"></div>
                        </div>
                        <div class="modal-footer bg-light" id="aiModalFooter">
                            <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Tutup</button>
                            <button type="button" class="btn btn-sm btn-teal fw-bold" id="aiModalApplyBtn" style="background:#0d9488; color:white; display:none;">
                                <i class="bi bi-check2-circle me-1"></i>Terapkan ke Formulir
                            </button>
                        </div>
                    </div>
                </div>
            </div>`;
            document.body.insertAdjacentHTML('beforeend', html);
            modalEl = document.getElementById('aiAssistModal');
        }
        return new bootstrap.Modal(modalEl);
    }

    // ── 1. MODUL RISIKO: Tombol Bantu Rencana Mitigasi ────────────────────
    const btnAiMitigasi = document.getElementById('btn-ai-mitigasi');
    if (btnAiMitigasi) {
        btnAiMitigasi.addEventListener('click', async function () {
            // Ambil data dari form risiko
            const unitSelect = document.querySelector('select[name="unit"]');
            const unitName = unitSelect && unitSelect.selectedOptions[0] ? unitSelect.selectedOptions[0].text : '';
            const katSelect = document.querySelector('select[name="kategori_risiko"]');
            const kategoriRisiko = katSelect ? katSelect.value : '';
            const jenisInputs = Array.from(document.querySelectorAll('input[name="jenis_risiko"], textarea[name="jenis_risiko"]'));
            const jenisList = jenisInputs.map(el => el.value.trim()).filter(Boolean);
            const jenisRisiko = jenisList.join('; ');
            const descInput = document.querySelector('textarea[name="deskripsi_risiko"]');
            const deskripsiRisiko = descInput ? descInput.value.trim() : '';
            const masalahInput = document.querySelector('textarea[name="masalah"]');
            const masalah = masalahInput ? masalahInput.value.trim() : '';
            const dataInput = document.querySelector('textarea[name="data"]');
            const dataPendukung = dataInput ? dataInput.value.trim() : '';
            const dampakInput = document.querySelector('select[name="dampak"]') || document.querySelector('input[name="dampak"]');
            const dampak = dampakInput ? dampakInput.value : 3;
            const probInput = document.querySelector('select[name="probabilitas"]') || document.querySelector('input[name="probabilitas"]');
            const probabilitas = probInput ? probInput.value : 3;
            const stratSelect = document.querySelector('select[name="strategi_mitigasi"]');
            const strategi = stratSelect ? stratSelect.value : 'Mitigasi (Reduce)';

            // Konteks Indikator Mutu jika ada
            const indCtx = window._arimaIndikatorContext || null;
            let indDesc = '';
            if (indCtx) {
                indDesc = `Indikator Mutu Terkait: [${indCtx.kode}] ${indCtx.nama} (Target: ${indCtx.target}${indCtx.satuan})`;
            }

            if (!jenisRisiko && !deskripsiRisiko && !indDesc) {
                alert('Silakan pilih Indikator Mutu atau ketik dahulu "Jenis Risiko" / "Deskripsi Risiko" agar AI memiliki konteks.');
                if (jenisInput) jenisInput.focus();
                return;
            }

            const modal = createOrGetAiModal();
            document.getElementById('aiModalTitle').textContent = 'Rekomendasi Rencana Aksi Mitigasi KARS';
            document.getElementById('aiModalLoading').style.display = 'block';
            document.getElementById('aiModalContent').style.display = 'none';
            document.getElementById('aiModalApplyBtn').style.display = 'none';
            modal.show();

            try {
                const resp = await fetch('/ai/mitigasi-risiko/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify({
                        unit_name: unitName,
                        kategori_risiko: kategoriRisiko,
                        jenis_risiko: jenisRisiko || (indCtx ? `Risiko capaian ${indCtx.nama}` : ''),
                        masalah: masalah,
                        data_pendukung: dataPendukung,
                        deskripsi_risiko: deskripsiRisiko + (indDesc ? `\n${indDesc}` : ''),
                        dampak: dampak,
                        probabilitas: probabilitas,
                        strategi: strategi,
                    }),
                });

                const res = await resp.json();
                document.getElementById('aiModalLoading').style.display = 'none';
                const contentEl = document.getElementById('aiModalContent');
                contentEl.style.display = 'block';

                if (!res.success) {
                    contentEl.innerHTML = `
                        <div class="alert alert-warning mb-0">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>
                            <strong>Gagal mendapatkan rekomendasi AI:</strong><br>${res.error || 'Terjadi kesalahan sistem.'}
                        </div>`;
                    return;
                }

                const d = res.data;
                contentEl.innerHTML = `
                    <div class="mb-3 p-3 bg-light rounded border">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="badge bg-teal-subtle text-teal fw-bold">STRATEGI DISARANKAN: ${d.strategi_disarankan || strategi}</span>
                            <span class="badge bg-secondary">Estimasi: ${d.target_durasi_hari || 14} Hari</span>
                        </div>
                        <h6 class="fw-bold text-dark mb-2">Rencana Aksi Mitigasi Terstruktur:</h6>
                        <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.88rem; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0;">${d.rencana_aksi}</pre>
                    </div>
                    ${d.catatan_kars ? `
                    <div class="small text-muted p-2 rounded" style="background:#f8fafc; border-left: 3px solid #0d9488;">
                        <strong><i class="bi bi-info-circle me-1"></i>Catatan Standar STARKES:</strong> ${d.catatan_kars}
                    </div>` : ''}
                `;

                const applyBtn = document.getElementById('aiModalApplyBtn');
                applyBtn.style.display = 'inline-block';
                applyBtn.onclick = function () {
                    const targetTextarea = document.querySelector('textarea[name="rencana_aksi"]');
                    if (targetTextarea) {
                        targetTextarea.value = d.rencana_aksi;
                        targetTextarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        targetTextarea.style.border = '2px solid #0d9488';
                        setTimeout(() => targetTextarea.style.border = '', 2000);
                    }
                    if (d.pj_rekomendasi) {
                        const pjInput = document.querySelector('input[name="pj_mitigasi"]');
                        if (pjInput && !pjInput.value) pjInput.value = d.pj_rekomendasi;
                    }
                    modal.hide();
                };

            } catch (err) {
                document.getElementById('aiModalLoading').style.display = 'none';
                document.getElementById('aiModalContent').style.display = 'block';
                document.getElementById('aiModalContent').innerHTML = `
                    <div class="alert alert-danger mb-0">
                        <i class="bi bi-x-circle-fill me-2"></i>Terjadi kendala jaringan: ${err.message}
                    </div>`;
            }
        });
    }

    // ── 2. MODUL INSIDEN: Tombol Grading Otomatis ─────────────────────────
    const btnAiInsiden = document.getElementById('btn-ai-insiden');
    if (btnAiInsiden) {
        btnAiInsiden.addEventListener('click', async function () {
            const descEl = document.querySelector('textarea[name="deskripsi_kejadian"]');
            const deskripsi = descEl ? descEl.value.trim() : '';
            if (!deskripsi) {
                alert('Harap ketik deskripsi kejadian insiden terlebih dahulu.');
                if (descEl) descEl.focus();
                return;
            }

            const jenisEl = document.querySelector('select[name="jenis_insiden"]');
            const keparahanEl = document.querySelector('select[name="tingkat_keparahan"]');
            const lokasiEl = document.querySelector('input[name="lokasi_kejadian"]');
            const tindakanEl = document.querySelector('textarea[name="tindakan_segera"]');
            const terpaparEl = document.querySelector('input[name="pasien_terpapar"]');

            const modal = createOrGetAiModal();
            document.getElementById('aiModalTitle').textContent = 'Grading Risiko & Rekomendasi Investigasi IKP';
            document.getElementById('aiModalLoading').style.display = 'block';
            document.getElementById('aiModalContent').style.display = 'none';
            document.getElementById('aiModalApplyBtn').style.display = 'none';
            modal.show();

            try {
                const resp = await fetch('/ai/insiden-grading/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                    body: JSON.stringify({
                        jenis_insiden: jenisEl ? jenisEl.value : '',
                        tingkat_keparahan: keparahanEl ? keparahanEl.value : '',
                        lokasi_kejadian: lokasiEl ? lokasiEl.value : '',
                        deskripsi_kejadian: deskripsi,
                        tindakan_segera: tindakanEl ? tindakanEl.value : '',
                        pasien_terpapar: terpaparEl ? terpaparEl.checked : false,
                    }),
                });

                const res = await resp.json();
                document.getElementById('aiModalLoading').style.display = 'none';
                const contentEl = document.getElementById('aiModalContent');
                contentEl.style.display = 'block';

                if (!res.success) {
                    contentEl.innerHTML = `<div class="alert alert-warning">${res.error || 'Gagal.'}</div>`;
                    return;
                }

                const d = res.data;
                const badgeColor = d.grading === 'MERAH' ? 'danger' : d.grading === 'KUNING' ? 'warning text-dark' : d.grading === 'HIJAU' ? 'success' : 'primary';

                contentEl.innerHTML = `
                    <div class="text-center p-3 mb-3 rounded" style="background:#f1f5f9;">
                        <span class="badge bg-${badgeColor} fs-6 px-3 py-2 fw-bold">GRADING REKOMENDASI: ${d.grading}</span>
                        <p class="small text-muted mt-2 mb-0">${d.grading_alasan || ''}</p>
                    </div>
                    <div class="mb-3">
                        <span class="badge bg-dark mb-1">Tingkat Investigasi: ${d.tingkat_investigasi}</span>
                        <h6 class="fw-bold text-dark mt-2 mb-1">Rekomendasi Tindakan Korektif & Preventif:</h6>
                        <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.88rem; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0;">${d.rekomendasi_tindakan}</pre>
                    </div>
                `;

                const applyBtn = document.getElementById('aiModalApplyBtn');
                applyBtn.style.display = 'inline-block';
                applyBtn.onclick = function () {
                    if (tindakanEl && d.rekomendasi_tindakan && !tindakanEl.value) {
                        tindakanEl.value = d.rekomendasi_tindakan;
                    }
                    modal.hide();
                };

            } catch (err) {
                document.getElementById('aiModalLoading').style.display = 'none';
                document.getElementById('aiModalContent').style.display = 'block';
                document.getElementById('aiModalContent').innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
            }
        });
    }

    // ── 3. TEST KONEKSI DEEPSEEK (Pusat Kontrol Sistem) ───────────────────
    const btnTestDeepseek = document.getElementById('btn-test-deepseek');
    if (btnTestDeepseek) {
        btnTestDeepseek.addEventListener('click', async function () {
            const statusEl = document.getElementById('deepseek-test-status');
            if (statusEl) {
                statusEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1 text-teal"></span> Menghubungkan ke server DeepSeek...';
            }
            btnTestDeepseek.disabled = true;

            try {
                const resp = await fetch('/ai/test-connection/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                });
                const res = await resp.json();
                btnTestDeepseek.disabled = false;

                if (res.success) {
                    if (statusEl) {
                        statusEl.innerHTML = `<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>Koneksi OK: ${res.model}</span>`;
                    }
                } else {
                    if (statusEl) {
                        statusEl.innerHTML = `<span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>${res.error}</span>`;
                    }
                }
            } catch (err) {
                btnTestDeepseek.disabled = false;
                if (statusEl) {
                    statusEl.innerHTML = `<span class="badge bg-danger">Error: ${err.message}</span>`;
                }
            }
        });
    }

})();
