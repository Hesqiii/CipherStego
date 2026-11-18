# CipherStego — aplikasi web lokal

Aplikasi akademik lokal untuk demonstrasi pengamanan PDF dan steganografi PNG sesuai proposal penelitian. Backend memakai FastAPI dan Uvicorn serta mengikat ke `127.0.0.1`. Tidak ada unggahan ke cloud.

## Status milestone

**Milestone 1 — Python Backend Foundation: selesai.** FastAPI menyajikan frontend lokal, health check merespons status nyata, dan router placeholder tersedia.

**Milestone 2 — Cryptographic Engine: selesai.** Modul PBKDF2-HMAC-SHA256, HKDF-SHA256, AES-256-GCM, header payload 32 byte, dan SHA-256 sudah dibuat serta diuji. Engine kini digunakan oleh sender/receiver backend.

**Milestone 3 — Sequential LSB: selesai.** Modul menerima PNG truecolor RGB 8-bit, menyisipkan header 32 byte diikuti ciphertext, lalu mengekstrak keduanya tanpa dekripsi. Modul mengembalikan gambar baru dan tidak mengubah file cover.

**Milestone 4 — Sender/Receiver backend vertical slice: selesai.** `POST /api/embed` mengenkripsi PDF dan menyisipkan payload ke PNG. `POST /api/extract` mengekstrak payload, memeriksa tag AES-GCM, lalu mengembalikan PDF hanya jika autentikasi berhasil. Endpoint alias `/api/sender` dan `/api/receiver` juga tersedia. Operasi berlangsung di memori; input PNG sementara dihapus setelah pemrosesan.

**Milestone 5 — Key-Based Randomized LSB engine: selesai.** Header tetap ditempatkan pada 256 slot pertama; permutasi penuh HMAC-counter/Fisher–Yates hanya mencakup slot setelah header. Modul menerima `K_pos` dari pemanggil dan tidak melakukan enkripsi/dekripsi.

**Milestone 6 — API dan UI Randomized LSB: selesai.** Sender dan receiver menerima mode `sequential` atau `randomized`. Sender memakai satu hasil derivasi PBKDF2/HKDF untuk AES dan K_pos. Receiver membaca header secara sequential, menurunkan key material sekali, mengekstrak ciphertext dengan K_pos, lalu memvalidasi AES-GCM sebelum mengembalikan PDF. Metadata melaporkan waktu total serta waktu permutasi dan operasi LSB secara terpisah untuk mode Randomized.

**Milestone 7 — Evaluation Engine: engine dan integrasi satu-sampel selesai.** API evaluasi menjalankan satu embedding dan extraction aktual, lalu menghitung MSE, PSNR, SSIM, PoV chi-square per kanal, dan RS per kanal dengan koreksi bias awal dari cover. Ini belum menggantikan eksperimen formal proposal dengan dataset, kontrol, pengulangan, dan analisis pasangan.

**Milestone 8 — Experiment runner: runner dan preflight disiapkan; eksperimen belum dapat dijalankan.** Folder dataset belum memuat P01–P10 dan C1–C3. Lihat [panduan experiment runner](docs/experiment_runner.md). Proposal resmi menetapkan S1 untuk kedua metode; instruksi ringkas Milestone 8 menyebut Randomized saja, sehingga runner mengikuti proposal dan mempertahankan cakupan kedua metode.

Frontend disajikan dari `frontend/`; asetnya tetap HTML/CSS/JavaScript lokal tanpa CDN. Folder `app/` lama dipertahankan untuk referensi dan tidak disajikan karena berisi source Python lama. UI tidak diubah pada Milestone 2.

## Status frontend

Frontend vanilla kini terhubung ke sender dan receiver pada origin yang sama. Pengguna dapat memilih PDF/PNG, melihat kapasitas, memilih Sequential atau Key-Based Randomized LSB, melihat preview stego-PNG, serta mengunduh PNG atau PDF pulih. Validasi browser hanya pemeriksaan awal; backend mengulang validasi sebelum memproses file.

`GET /api/health` dan kedua metode sender/receiver tersedia di UI. Halaman evaluasi belum menjadi dashboard dan tidak menampilkan data simulasi. API evaluasi menerima satu PDF, cover PNG, passphrase, dan mode; ia menjalankan operasi aktual dan mengembalikan MSE, PSNR, SSIM, chi-square, RS, serta waktu aktual. File inspection dan tamper simulation masih mengembalikan HTTP 501.

Project Android di `android/` tetap disimpan sebagai prototipe yang dipause. Jangan lanjutkan fitur Android atau menghapusnya.

## Keputusan cryptographic engine

- PBKDF2-HMAC-SHA256 memakai 600.000 iterasi, salt 16 byte, dan menghasilkan master key 32 byte. Passphrase diubah ke UTF-8 tanpa trim, case-fold, atau normalisasi Unicode.
- HKDF-SHA256 menurunkan dua key 32 byte dengan label domain terpisah: `cipherstego/v1/encryption` dan `cipherstego/v1/position`. Proposal hanya meminta label berbeda; label dan panjang ini adalah keputusan implementasi untuk versi `v1`.
- HKDF memakai `salt=None`; RFC 5869 mendefinisikannya setara salt nol sepanjang HashLen. Master key masukan HKDF sudah merupakan keluaran pseudorandom PBKDF2. Jangan ubah label atau salt policy tanpa perubahan versi/desain yang terdokumentasi.
- AES-GCM memakai key 32 byte, nonce acak 12 byte dan tag 16 byte. Nonce dibangkitkan dari CSPRNG sistem operasi. Enkripsi membentuk header lebih dahulu; serialisasi header 32 byte yang sama dipakai sebagai AAD. Ciphertext yang dikembalikan mencakup tag.
- Header: salt 16 byte, nonce 12 byte, dan panjang ciphertext unsigned 32-bit big-endian. Panjang minimal 16 byte karena harus memuat tag, dan harus sama dengan panjang ciphertext aktual.
- SHA-256 menghasilkan digest 32 byte atau hex, serta mendukung hashing file streaming. Hash ini hanya untuk perbandingan eksperimen, bukan autentikasi.
- Python tidak menjamin penghapusan aman key/passphrase dari memori. Kode tidak mencetak atau memasukkan key ke repr model, tetapi immutable `bytes`, garbage collector, dan salinan internal library membuat zeroization yang terjamin tidak dapat diklaim.

## Sequential LSB

- Loader hanya menerima PNG 8-bit truecolor (color type 2) dengan mode RGB; grayscale, RGBA, palette/indexed, JPEG, dan format lain ditolak. Tidak ada konversi mode otomatis.
- Traversal memakai piksel row-major, kanal R lalu G lalu B, dan bit MSB-first per byte. Satu bit payload menggantikan satu LSB kanal warna.
- Kapasitas diperiksa sebelum embedding dengan `8 * (32 + ciphertext_length) <= width * height * 3`. Panjang ciphertext mencakup tag GCM 16 byte.
- `embed_sequential` dan `extract_sequential` hanya menerima path PNG yang lolos validasi file. Embedding mengembalikan objek gambar baru dan mempertahankan dimensi; `save_rgb_png` menyimpan hasil tanpa konversi mode. Extraction hanya mengambil header dan ciphertext; autentikasi/dekripsi tetap tugas crypto receiver.
- Resolusi citra tidak dipaksakan oleh primitive ini agar kapasitas dapat diuji pada fixture kecil. Dataset eksperimen proposal tetap menggunakan tiga PNG RGB 1920 × 1080.

## Key-Based Randomized LSB

- `backend/core/steganography/randomized_lsb.py` menyediakan `embed_randomized`, `extract_randomized`, dan `fisher_yates_permutation`. Ia memakai strict PNG loader, format header, capacity check, dan exception yang sama seperti Sequential LSB; tidak memanggil AES atau API.
- Modul hanya memulihkan byte ciphertext. Kunci posisi yang salah dapat menghasilkan byte yang berbeda; caller tetap wajib meminta AES-GCM mengautentikasi payload sebelum merilis plaintext.
- Caller memperoleh `K_pos` melalui `derive_keys(passphrase, header.salt).position_key`. Output HKDF Milestone 2 adalah 32 byte dengan `HKDF_POSITION_INFO = b"cipherstego/v1/position"`. Extraction membaca salt pada header berurutan lebih dahulu. Modul menerima `K_pos` sebagai argumen dan tidak menyimpan atau menurunkannya sendiri.
- Untuk blok ke-`i`, generator menghitung `HMAC-SHA256(K_pos, I2OSP(i, 8))`. `I2OSP` di sini adalah bilangan unsigned 64-bit big-endian, mulai dari counter 0 dan naik satu per digest. Byte digest dikonsumsi berurutan; setiap kata indeks adalah 8 byte big-endian. Byte sisa tetap berada di buffer. Counter overflow ditolak, tidak wrap ke nol.
- `randbelow(bound)` menetapkan `limit = 2^64 - (2^64 mod bound)`. Kata 64-bit yang nilainya `>= limit` ditolak; kata yang diterima dipetakan dengan modulo. Domain yang diterima berukuran kelipatan `bound`, sehingga tiap indeks memiliki jumlah preimage sama.
- Fisher–Yates penuh berjalan dari `i = count - 1` ke `1`, memilih `j` seragam pada `[0, i]`, lalu menukar `i` dan `j`. `count` adalah semua slot RGB setelah header. Prefix permutasi sepanjang `8 * ciphertext_length` dipakai untuk ciphertext, dengan offset 256. Indeks header tidak masuk permutasi.
- Permutasi disimpan sebagai NumPy `uint32` (4 byte per posisi), bukan Python integer list. Pada PNG 1920 × 1080 terdapat 6.220.800 slot RGB dan 6.220.544 slot permutasi sesudah header, sehingga array permutasi memerlukan tepat 24.882.176 byte (23,73 MiB). Operasi prefix posisi dilakukan in-place untuk menghindari array indeks kedua; buffer citra dan bit payload menambah kebutuhan memori di atas angka permutasi ini.
- Parameter counter 64-bit big-endian, urutan pembacaan kata, serta representasi `uint32` dipakai sebagai keputusan implementasi yang terdokumentasi karena proposal lengkap tidak tersedia di workspace. Sumber lama `app/crypto_engine.py` juga memakai counter big-endian 64-bit, stream digest berbuffer, rejection sampling, dan full Fisher–Yates; label HKDF lama tidak dipakai karena key derivation aktif di `backend/core/crypto/` menjadi sumber K_pos.
- Pemeriksaan performa awal pada PNG RGB 1920×1080 (2.073.600 piksel) di mesin pengembangan: embedding 28,723 s, termasuk permutasi 28,521 s dan penulisan LSB 0,214 ms; extraction 34,644 s, termasuk permutasi 34,412 s dan pembacaan payload 0,113 ms. Peak working set proses Python terukur 100,89 MiB, naik 57,68 MiB dari baseline proses. Angka ini adalah satu pengukuran implementasi, bukan hasil benchmark penelitian. Hasilnya menguatkan bahwa rekonstruksi Fisher–Yates penuh mendominasi waktu operasi Randomized.

## Evaluation Engine

- `POST /api/evaluate` dan alias `/api/evaluation` melakukan satu embedding dan extraction aktual dengan `mode` Sequential atau Randomized. Request memakai `pdf`, `cover`, `passphrase`, dan `mode`. Endpoint mengukur total embed/extract dari service operasi, bukan angka benchmark buatan. Untuk Randomized, waktu permutasi dan operasi LSB tersedia terpisah; field tersebut `null` untuk Sequential karena service belum mencatat subfase Sequential.
- MSE merata-ratakan kuadrat selisih seluruh piksel dan tiga kanal RGB: `Σ(I−S)² / (M×N×3)`. Piksel RGB 8-bit diproses dalam urutan kanal yang sama dan nilai selisih diperluas sebelum dikuadratkan agar tidak overflow.
- PSNR memakai `10 log10(255² / MSE)` dengan MAX=255. Jika MSE=0, hasil matematisnya tak hingga; API mengembalikan `value: null` dan `status: "infinite"` agar JSON tetap valid.
- SSIM memakai `scikit-image==0.26.0`, Gaussian weights, sigma 1.5, data range 255, kovarians populasi, konstanta K1/K2 0.01/0.03, dan rata-rata kanal RGB. Konfigurasi window baku memerlukan dimensi minimum 11×11.
- Chi-square memasangkan PoV `(0,1), (2,3), …`, menguji prefiks 1–100% per kanal, menggabungkan nilai harapan sampai lebih besar dari 4, menyimpan p-value dua ekor secara terpisah, dan memakai Holm untuk 300 uji per gambar. Hasil cover dan stego dihitung terpisah. Hasil prefiks Randomized LSB bersifat eksploratif, bukan klaim deteksi seluruh citra.
- RS memakai grup 2×2 disjoint dan mask M/−M per kanal. Estimator menolak akar, koreksi bias awal cover, atau nilai yang tidak stabil tanpa clipping. Perkiraan total dibandingkan dengan jumlah bit yang benar-benar disisipkan.
- Parameter dan batas interpretasi dijelaskan di [addendum metodologi](docs/evaluation_methodology_addendum.md). Satu request bukan pengganti 30 pasangan tiap metode, kontrol cover, lima pengulangan waktu, atau analisis statistik eksperimen formal.

## Prasyarat dan setup

- Windows 10/11.
- Python 3.14.x tersedia melalui `python`.
- Akses internet diperlukan sekali untuk mengunduh paket.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Jalankan aplikasi

```powershell
.\run.bat
```

Buka `http://127.0.0.1:8765`. Health check: `http://127.0.0.1:8765/api/health`. Hentikan server dengan `Ctrl+C`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip check
```

Preflight dataset dan jalankan pilot (setelah dataset tersedia) dengan:

```powershell
.\.venv\Scripts\python.exe -m backend.experiments.runner preflight
.\.venv\Scripts\python.exe -m backend.experiments.runner pilot
```

Runner akan berhenti jika dataset belum lengkap atau belum ada privacy review manual. Run formal memerlukan pilot report lulus dan konfirmasi eksplisit.

Tes mencakup vektor PBKDF2 dan RFC 5869 HKDF, AES-GCM dan autentikasi, header dan hashing, Sequential LSB, serta Randomized LSB: HMAC counter known-answer, buffering, counter overflow, rejection sampling dan threshold matematis, permutasi Fisher–Yates known-answer, round-trip, kapasitas batas, posisi header, preservasi bit non-LSB, dimensi, dan file sumber. Evaluation Engine menguji MSE/PSNR/SSIM, PoV pooling, kedua ekor chi-square dan koreksi Holm, status estimator RS, validasi citra, integrasi API kedua mode, serta pencatatan waktu aktual. Experiment runner diuji untuk validasi manifest, gate privasi, alokasi bit per kanal, statistik berpasangan, dan penolakan S3/S4.

## Batas API pada milestone ini

- `GET /api/health` — status lokal nyata.
- `POST /api/embed` atau `/api/sender` — JSON berisi `pdf`, `cover`, `passphrase`, dan `mode: "sequential" | "randomized"` (default `sequential`). File memakai pasangan `name` dan `data` Base64. Respons mengandung `filename`, `png_base64`, dan metadata `mode` aktual.
- `POST /api/extract` atau `/api/receiver` — JSON berisi `stego`, `passphrase`, dan `mode: "sequential" | "randomized"` (default `sequential`). Respons PDF (`pdf_base64`) hanya diberikan setelah tag AES-GCM valid.
- `POST /api/evaluate` atau `/api/evaluation` — satu evaluasi aktual dengan `pdf`, `cover`, `passphrase`, dan `mode`; respons memisahkan MSE, PSNR, SSIM, hasil chi-square/RS beserta status, waktu, dan hash pemulihan.
- File inspection dan tamper simulation tetap placeholder HTTP 501. Mode selain dua nilai yang didukung ditolak oleh validasi request HTTP 422.
- Backend menerima PDF maksimal 600 KiB, PNG maksimal 16 MiB, gambar maksimal 8 megapiksel, dan request body maksimal 24 MiB. PDF diperiksa signature/EOF, PNG divalidasi sebagai PNG RGB 8-bit; batas frontend bukan pengganti validasi server.
- Request salah bentuk mendapat HTTP 422; file melebihi batas mendapat HTTP 413; passphrase salah atau stego yang berubah mendapat HTTP 400 dengan pesan gabungan. Detail input dan passphrase tidak dikembalikan.
- Frontend mengirim JSON Base64 hanya ke endpoint relatif lokal. Passphrase tidak masuk ke `localStorage`, `sessionStorage`, atau log; hasil sebelumnya dibersihkan saat input terkait berubah dan URL unduhan dicabut saat hasil dibersihkan.
- PDF hasil tidak ditampilkan di browser. Receiver hanya menyediakan tautan unduh setelah backend mengembalikan `authenticated: true` sesudah pemeriksaan tag GCM.
- Sender/receiver API dan UI mendukung Sequential serta Key-Based Randomized LSB.
- Evaluation Engine tersedia untuk satu sampel. Eksperimen dataset dan benchmark formal belum dimulai.

## Roadmap

1. Python Backend Foundation — selesai.
2. Cryptographic Engine — selesai secara standalone.
3. Sequential LSB — selesai secara standalone.
4. Key-Based Randomized LSB engine — selesai sebagai modul mandiri.
5. Integrasi sender/receiver ke UI — selesai untuk Sequential dan Key-Based Randomized LSB.
6. Evaluation Engine — MSE/PSNR/SSIM, chi-square, dan RS tersedia untuk satu sampel; belum menggantikan eksperimen formal.
7. Eksperimen dan finalization — runner tersedia; preflight menemukan dataset penelitian belum disediakan. Pilot dan matriks formal belum dijalankan.

Proposal penelitian adalah sumber kebenaran spesifikasi. Jangan mengubah jumlah sampel, kombinasi eksperimen, metrik, algoritma, atau parameter cryptography tanpa revisi proposal yang disetujui.
