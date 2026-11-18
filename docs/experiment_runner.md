# Experiment runner

Runner berada di `backend/experiments/`. Ia tidak menjadi bagian dari API atau UI dan tidak mengubah format payload maupun primitive kriptografi/steganografi. Setiap run memiliki direktori unik dan semua file dibuat dengan mode eksklusif; hasil lama tidak ditimpa.

## Perbedaan cakupan S1

Spesifikasi singkat Milestone 8 menyebut S1 hanya Randomized LSB. Proposal resmi menyebut 30 pasangan diuji pada Sequential dan Randomized, total 60 proses, dengan target pemulihan 100% pada kedua metode. Proposal menjadi sumber kebenaran, sehingga runner menjalankan S1 pada kedua metode dan mencatat konflik tersebut.

## Pasangan data dan waktu

Runner menyiapkan satu ciphertext/header per PDF untuk lima pengukuran enkripsi dengan salt/nonce berbeda. Hasil pengukuran pertama menjadi payload pasangan; payload yang sama digunakan untuk ketiga cover dan kedua metode. Pada tiap kondisi, tiap metode menerima salinan file cover identik yang berbeda. Primitive selalu mengembalikan citra baru. Cover, header, dan ciphertext SHA-256 diperiksa dan dicatat.

Runner melakukan satu warm-up per metode sebelum pengukuran. Lima waktu embedding dan lima waktu extraction dicatat satu per satu. CSV juga memuat mean dan simpangan baku sampel (ddof=1) untuk setiap fase. Enkripsi diukur lima kali per payload dan dicatat sebagai fase bersama, bukan sebagai lima observasi per metode. Key derivation selama penerimaan, permutasi, operasi LSB, extraction, dan dekripsi disimpan dalam kolom fase terpisah. Waktu diambil dengan `perf_counter_ns`; warm-up tidak masuk hasil.

Header, salt, nonce, panjang ciphertext, hash ciphertext, hash stego, dan alokasi bit aktual per kanal tercatat. Pada Sequential, alokasi kanal dihitung dari slot berurutan yang benar-benar dipakai. Pada Randomized, runner menghitung histogram kanal dari prefix permutasi yang digunakan untuk ciphertext, ditambah slot header. Penghitungan posisi ini tidak masuk waktu operasi. Passphrase diminta tanpa echo dan tidak ditulis; key tidak pernah diserialisasi.

## Skenario keamanan

S1, S2, dan S5 memakai seluruh matriks 10 PDF × 3 cover × 2 metode. Kontrol chi-square/RS cover-only disimpan satu kali per cover. Randomized LSB tetap diberi label eksploratif untuk interpretasi prefiks chi-square. S3 dan lima varian S4 dijalankan sebagai pemeriksaan fungsional pada satu pasangan P01/C1, untuk kedua metode. S4 mengubah bit ciphertext, salt, nonce, panjang ciphertext yang valid-range, serta panjang di luar kapasitas; status format/capacity dibedakan dari kegagalan GCM.

RS menyimpan cover bias, estimasi stego, estimasi koreksi, status/alasan, dan perbandingan bit aktual per kanal. Estimator invalid tetap `null`; nilai tidak dipotong ke rentang. Sequential dicatat dengan catatan interpretasi karena RS lebih sesuai untuk penyisipan tersebar.

## Statistik dan batas klaim

Ringkasan formal membandingkan 30 kondisi berpasangan dengan Wilcoxon signed-rank, α=0,05, dan koreksi Holm untuk tujuh keluarga metrik/detektor yang diuji. Lima pengulangan waktu diringkas sebagai mean dan simpangan baku per kondisi sebelum Wilcoxon, bukan dianggap sampel independen. Efek rank-biserial dan interval bootstrap 95% atas kondisi berpasangan dilaporkan. H1 mengikuti margin proposal: MSE relatif 5%, PSNR ±0,23 dB, SSIM ±0,005; kesetaraan hanya didukung jika ketiga CI berada di dalam seluruh margin. Hasil tetap studi kasus atas sepuluh PDF dan tiga cover.

## Urutan perintah

```powershell
python -m backend.experiments.runner preflight
python -m backend.experiments.runner pilot
python -m backend.experiments.runner run --pilot-report experiment_data/reports/<pilot-run-id>.json --confirm-formal-run
```

Preflight membuat `experiment_data/dataset_manifest.json`, tidak membuat file dataset contoh. Dataset harus lengkap dan privacy review harus merujuk ke fingerprint manifest. Pilot hanya menguji P01/C1 pada kedua metode dan tidak menghasilkan analisis inferensial. Run formal baru berjalan setelah pilot report untuk fingerprint yang sama lulus integrity, kualitas, dan pemeriksaan keamanan. Tidak ada run formal otomatis setelah pilot.
