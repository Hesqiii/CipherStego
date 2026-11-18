# CipherStego Android — panduan project

## Tujuan dan cara bekerja

CipherStego adalah aplikasi Android native untuk demonstrasi perlindungan PDF dengan AES-256-GCM dan penyembunyian payload pada citra PNG RGB 24-bit menggunakan LSB. Semua pemrosesan berkas harus lokal di perangkat.

Sebelum mengubah kode:

1. Baca `README.md`, instruksi `AGENTS.md` yang berlaku, dan proposal penelitian: `D:\coding\Proposal Projek Akhir Kripto\Proposal_Tugas_Akhir_Keamanan_Data_Revisi_Final.md`. Jika path tersebut tidak tersedia di mesin lain, minta atau temukan salinan proposal sebelum mengubah format algoritma.
2. Periksa implementasi aktual serta perubahan kerja yang sudah ada. Jangan membuat ulang project atau menghapus fungsi yang sudah bekerja.
3. Pastikan cakupan pekerjaan sesuai langkah roadmap aktif di README. Jangan melompat ke integrasi fitur yang belum diminta.
4. Jika status dokumen bertentangan dengan source, laporkan perbedaannya dan jadikan source serta bukti build/test sebagai kondisi aktual.
5. Jalankan hanya build/test yang relevan dengan perubahan, lalu laporkan perintah dan hasil yang benar-benar diamati. Jangan mengarang hasil, berkas, atau keberhasilan proses.

## Kondisi dan langkah aktif

Pemilik project menyatakan pekerjaan sekarang berada di **Langkah 3 — Sequential LSB**. UI native, navigasi tiga bagian, SAF, metadata/validasi PDF dan PNG, preview PNG, passphrase UI, serta estimasi kapasitas merupakan pekerjaan Langkah 1 yang sudah dilaporkan selesai.

Sebelum mengerjakan Langkah 3, periksa apakah cryptographic engine Langkah 2 benar-benar tersedia. Inspeksi source terakhir belum menemukan paket `core/crypto`, sementara README sebelumnya menyebut engine itu belum dibuat. Jangan mengasumsikan Langkah 2 selesai: cari implementasi dan test yang relevan. Jika belum ada, jelaskan bahwa itu prasyarat dan jangan diam-diam memperluas cakupan Langkah 3.

## Batas spesifikasi penelitian

Jangan mengubah desain proposal. Spesifikasi yang harus dipertahankan dan diverifikasi terhadap proposal sebelum implementasi:

- AES-256-GCM, nonce 12 byte, tag autentikasi 16 byte.
- PBKDF2-HMAC-SHA256 dengan 600.000 iterasi dan salt 16 byte.
- HKDF-SHA256 untuk pemisahan kunci.
- Header 32 byte: salt 16 byte, nonce 12 byte, panjang ciphertext 4 byte big-endian; header menjadi AAD. Panjang ciphertext mencakup tag GCM. Pada citra, header menempati 256 slot RGB LSB pertama sesuai proposal.
- SHA-256 hanya untuk perbandingan hasil eksperimen, bukan autentikasi.
- Sequential LSB adalah metode pembanding. Pastikan susunan byte header, urutan kanal RGB, bit order, posisi header, serta aturan payload sama dengan proposal dan test/reference implementation. Jangan menebak kontrak byte-level yang tidak terdokumentasi.
- Key-Based Randomized LSB adalah Langkah 4: HMAC-SHA256 counter generator, Fisher–Yates, rejection sampling, dan urutan posisi deterministik yang sama saat ekstraksi.

## Arsitektur dan keamanan

- Pertahankan Kotlin, Jetpack Compose, Material 3, satu Gradle module `:app`, dan pemisahan paket yang ada.
- Gunakan ViewModel dengan StateFlow dan coroutine untuk pekerjaan I/O/komputasi; jangan memproses berkas besar pada main thread.
- Gunakan Storage Access Framework dan `ContentResolver` untuk URI. Jangan menganggap `content://` sebagai filesystem path dan jangan menambah izin storage luas.
- Jangan log atau menyimpan passphrase. Bersihkan state sementara saat meninggalkan alur yang sesuai.
- Jangan menerbitkan PDF hasil dekripsi sebelum autentikasi GCM berhasil. Jangan mengaktifkan tombol proses sebelum fungsinya benar-benar tersedia.
- Jangan mengonversi PNG unsupported lalu menyatakannya valid RGB 24-bit. Jaga piksel asli untuk jalur LSB mendatang.

## Verifikasi yang diharapkan

Untuk perubahan Sequential LSB, verifikasi round-trip byte payload dan header, batas kapasitas, input invalid/kapasitas tidak cukup, serta determinisme ekstraksi. Tambahkan test vector sesuai kontrak proposal sebelum menghubungkan UI. Untuk perubahan UI atau file handling, verifikasi perilaku SAF, cancellation, validasi tipe/isi, dan tidak adanya output palsu. Catat pengujian yang belum dapat dijalankan.

