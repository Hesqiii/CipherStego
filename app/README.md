# CipherStego — aplikasi demo lokal

Aplikasi web lokal untuk menjelaskan alur pengamanan PDF pada proposal: AES-256-GCM, PBKDF2-HMAC-SHA256, HKDF, header 32 byte, dan penyisipan LSB sekuensial atau acak berbasis kunci.

## Menjalankan

1. Pasang Python 3.12.
2. Buat dan aktifkan virtual environment pada folder ini.
3. Pasang dependensi dengan `python -m pip install -r requirements.txt`.
4. Jalankan `python app.py`.
5. Buka `http://127.0.0.1:8765` di browser.
6. Hentikan server dengan `Ctrl+C`.

Server hanya terikat ke `127.0.0.1`. Berkas diproses di memori; aplikasi tidak menyimpan PDF, citra, ataupun passphrase. Hindari berkas berisi data pribadi saat demonstrasi.

## Batas demo

- PDF dibatasi 600 KiB dan PNG dibatasi 8 juta piksel; citra harus RGB 24-bit.
- Header 32 byte berisi salt 16 byte, nonce 12 byte, dan panjang ciphertext 4 byte. Tag GCM 16 byte berada di akhir ciphertext. Seluruh header menjadi AAD.
- Metode penyisipan tidak disimpan di header. Penerima harus memilih metode yang sama dengan pengirim.
- Tombol contoh tamper mengubah satu bit pada salt di header untuk menunjukkan kegagalan verifikasi. Citra asli tidak diubah.
- Fingerprint SHA-256 ditampilkan untuk pembandingan uji. Tag AES-GCM yang mengautentikasi ciphertext dan AAD; hash tidak membuktikan identitas pengirim.
- Halaman Evaluasi membandingkan satu pasangan berkas dan satu ulangan. Hitungan chi-square histogram dan RS yang ditampilkan bersifat eksploratif, bukan keputusan bahwa gambar aman dari steganalisis. Hasilnya tidak menggantikan 10 payload × 3 cover dan lima ulangan yang direncanakan dalam proposal.
- Randomized LSB menyusun permutasi penuh dengan Fisher–Yates dan HMAC-SHA256 berbasis pencacah. Pada citra besar proses ini dapat memerlukan waktu.

## Isi folder

- `app.py` — server loopback dan API lokal.
- `crypto_engine.py` — derivasi kunci, AES-GCM, penyisipan/ekstraksi, serta metrik.
- `index.html`, `styles.css`, `app.js` — tiga layar aplikasi.
- `requirements.txt` — versi dependensi yang direncanakan.
