# Audit Dataset PDF CipherStego

Waktu audit (UTC): 2026-11-18T16:04:35.377053+00:00

## Hasil

- Ditemukan tepat P01-P10 pada experiment_data/dataset/pdf/.
- Kesepuluh PDF dapat dibuka secara strict oleh pypdf dan seluruh 55 halaman berhasil dirender ke PNG.
- Ukuran, SHA-256, jumlah halaman, dan karakteristik cocok dengan laporan generasi.
- Tidak ditemukan path lokal dalam metadata atau teks hasil ekstraksi; tidak terdeteksi alamat email atau rangkaian angka 11 digit atau lebih.
- Pemeriksaan sumber generator dan isi menunjukkan materi fiktif. Pemeriksaan otomatis ini bukan pengganti tinjauan manusia.
- P08 dan P10 adalah halaman pindai sintetis berupa gambar RGB penuh 850 x 1202 piksel (sekitar 110 dpi), satu gambar per halaman.
- Metadata PDF konsisten: author Data sintetis, subject Konten fiktif untuk pengujian lokal, creator CipherStego synthetic dataset generator; creation/modification date 2000-01-01T00:00:00+00:00. Judul berbeda sesuai ID. Tidak ada path berkas lokal.
- Privasi tetap manual_review_required untuk semua payload.

## Ukuran dan kapasitas

Rasio dihitung sebagai 8 * (ukuran PDF + 32 byte header + 16 byte tag GCM) / (1920 * 1080 * 3) * 100%.

| ID | Target KiB | Aktual byte | Aktual KiB | Selisih KiB | Halaman | Rasio kapasitas | Validasi |
|---|---:|---:|---:|---:|---:|---:|---|
| P01 | 10 | 17682 | 17.268 | +7.268 | 1 | 2.2801% | valid |
| P02 | 25 | 24562 | 23.986 | -1.014 | 3 | 3.1649% | valid |
| P03 | 50 | 48542 | 47.404 | -2.596 | 12 | 6.2487% | valid |
| P04 | 100 | 99211 | 96.886 | -3.114 | 5 | 12.7648% | valid |
| P05 | 150 | 158372 | 154.660 | +4.660 | 5 | 20.3729% | valid |
| P06 | 200 | 209125 | 204.224 | +4.224 | 6 | 26.8998% | valid |
| P07 | 300 | 270897 | 264.548 | -35.452 | 7 | 34.8438% | valid |
| P08 | 400 | 367822 | 359.201 | -40.799 | 4 | 47.3084% | valid |
| P09 | 500 | 476338 | 465.174 | -34.826 | 6 | 61.2636% | valid |
| P10 | 600 | 550960 | 538.047 | -61.953 | 6 | 70.8601% | valid |

SHA-256 lengkap, metadata per berkas, objek gambar per halaman, dan rincian render tercatat di [laporan audit JSON](pdf_dataset_audit_report.json).

## Manifest runner

experiment_data/dataset_manifest.json tidak diubah. Manifest yang ada masih menandai P01-P10 sebagai missing dan tinjauan privasi sebagai required_manual_attestation, karena manifest tersebut merekam keadaan sebelum generasi. Sesuai batas audit ini, preflight tidak dijalankan dan manifest tidak ditimpa.

## Tinjauan privasi

Generator memakai teks dan aset sintetis yang diturunkan dari seed tetap, tanpa identitas, alamat pribadi, atau organisasi nyata. Tinjauan privasi manual tetap diperlukan untuk setiap PDF sebelum memperbarui manifest atau menggunakan dataset untuk eksperimen.

Tidak ada PDF yang dibuat ulang atau diubah selama audit. Preflight, pilot, dan eksperimen formal tidak dijalankan.
