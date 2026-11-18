# CipherStego Android

Aplikasi Android native Kotlin untuk demonstrasi perlindungan PDF dan steganografi citra sesuai proposal penelitian. Pemrosesan dirancang berjalan lokal pada perangkat.

## Status saat ini

**Langkah aktif: 3 — Implementasi Sequential LSB.** UI native, navigasi Kirim/Terima/Evaluasi, pemilih berkas SAF, metadata PDF, validasi PNG RGB 24-bit, preview, input passphrase, dan estimasi kapasitas telah dilaporkan selesai pada langkah UI/file handling.

**Cryptographic engine (Langkah 2):** implementasi PBKDF2-HMAC-SHA256, HKDF-SHA256, AES-256-GCM, SHA-256, dan serializer header kini tersedia pada `core/crypto` dan `core/stego/header`. Unit test lokal berhasil dijalankan. Engine belum dihubungkan ke UI dan belum ada implementasi LSB; roadmap Langkah 3 tetap menjadi pekerjaan steganografi berikutnya.

Crypto/stego/evaluasi hanya boleh ditandai selesai setelah implementasi dan bukti verifikasinya tersedia. Tombol yang belum memiliki fungsi harus tetap nonaktif atau menyatakan fitur belum tersedia; jangan tampilkan hasil simulasi.

## Arsitektur

Project menggunakan Kotlin, Jetpack Compose, Material 3, dan satu Gradle module `:app`. ViewModel/StateFlow mengelola state UI. Pemilihan dan pembacaan berkas menggunakan Storage Access Framework, `ContentResolver`, dan content URI tanpa izin storage luas.

```text
app/src/main/java/id/cipherstego/android/
├── core/crypto/       # PBKDF2, HKDF, AES-GCM, format header
├── core/stego/        # Sequential LSB lalu Key-Based Randomized LSB
├── core/files/        # SAF, metadata, validasi berkas, kapasitas
├── core/evaluation/   # metrik kualitas dan steganalisis
├── feature/workflow/  # ViewModel dan state alur aplikasi
├── ui/theme/          # tema Compose
└── MainActivity.kt    # UI dan navigasi
```

Pada struktur tersebut, `core/crypto` kini berisi cryptographic engine Langkah 2. `core/stego` dan `core/evaluation` tetap merupakan area untuk roadmap mendatang; cek status berdasarkan source dan hasil verifikasi.

## Spesifikasi proposal yang tidak boleh berubah

- AES-256-GCM; nonce 12 byte; tag 16 byte.
- PBKDF2-HMAC-SHA256, 600.000 iterasi, salt 16 byte.
- HKDF-SHA256 untuk pemisahan kunci.
- Header 32 byte: salt 16 byte + nonce 12 byte + panjang ciphertext 4 byte big-endian; seluruh header menjadi AAD. Panjang ciphertext mencakup tag GCM. Header disisipkan pada 256 slot RGB LSB pertama sesuai proposal.
- SHA-256 digunakan untuk pembandingan eksperimen, bukan autentikasi.
- Randomized LSB memakai HMAC-SHA256 berbasis counter, Fisher–Yates, dan rejection sampling sesuai proposal.
- PNG input harus benar-benar RGB 24-bit: bit depth 8 dan color type 2. Jangan mengubah nilai kanal piksel pada jalur steganografi.
- Kapasitas mengikuti `8 × (32 + L) ≤ W × H × 3`, dengan `L` mencakup ciphertext dan tag GCM.

### Parameter implementasi kriptografi

Proposal mensyaratkan pemisahan kunci dengan HKDF-SHA256, tetapi tidak menetapkan nilai label konteks, panjang `K_pos`, atau salt untuk tahap HKDF. Implementasi saat ini mendokumentasikan pilihan protokol berikut: label UTF-8 `CipherStego/v1/encryption-key` dan `CipherStego/v1/position-key`; `K_enc` dan `K_pos` masing-masing 32 byte; PBKDF2 salt 16 byte yang sama dipakai sebagai salt HKDF-Extract. Perubahan parameter ini perlu diperlakukan sebagai perubahan protokol berversi.

Passphrase diteruskan ke `PBEKeySpec` tanpa normalisasi atau transformasi aplikasi; Android JCA provider menggunakan konvensi UTF-8 untuk `PBKDF2WithHmacSHA256`. Jangan mengubah passphrase secara diam-diam.

Urutan kanal, bit order, dan byte contract lainnya harus diambil dari proposal/reference implementation dan dibuktikan dengan test vector; jangan menebaknya. Proposal referensi pada mesin ini: `D:\coding\Proposal Projek Akhir Kripto\Proposal_Tugas_Akhir_Keamanan_Data_Revisi_Final.md`.

## Roadmap

1. **Native UI dan file handling — selesai dilaporkan.** Layar kirim/terima/evaluasi, SAF PDF/PNG, preview, metadata, validasi dasar, passphrase UI, dan estimasi kapasitas.
2. **Cryptographic engine — selesai di source.** PBKDF2-HMAC-SHA256, HKDF-SHA256, AES-256-GCM, SHA-256, dan serializer header tersedia beserta unit test. Belum terintegrasi dengan UI atau LSB.
3. **Sequential LSB — aktif.** Penyisipan dan pembacaan header, ekstraksi payload, round-trip, batas kapasitas, serta uji masukan invalid.
4. **Key-Based Randomized LSB.** HMAC-SHA256 counter generator, Fisher–Yates, rejection sampling, dan determinisme posisi penyisipan/ekstraksi.
5. **Integrasi sender/receiver.** Enkripsi, embedding, extraction, autentikasi, dan penyimpanan PDF hasil pemulihan.
6. **Evaluation & Benchmark.** MSE, PSNR, SSIM, waktu embedding/extraction, chi-square, dan RS analysis.
7. **Pengujian dan finalisasi APK.** Uji alur pada perangkat, kegagalan autentikasi, performa, serta hasil eksperimen.

## Hasil pengujian yang diketahui

Run terbaru: `.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug` berhasil; 16 unit test selesai, dan APK debug dibuat. Pengujian ini mencakup vektor PBKDF2/HKDF, AES-GCM round-trip serta penolakan autentikasi, header, dan SHA-256. Pengujian runtime pada Android fisik/emulator tidak dijalankan pada milestone ini. Laporan sebelumnya menyebut navigasi, pembatalan SAF picker, dan kasus kapasitas RGB 100×100 lolos; pemilihan PDF/PNG nyata, penolakan color mode, dan preview dengan fixture belum diverifikasi.

## Toolchain dan build

Toolchain pada project saat ini tercatat di konfigurasi Gradle: AGP 9.5.1, Gradle Wrapper 9.9.1, Compose Compiler plugin 2.3.21, Compose BOM 2026.09.00, compile SDK 37, target SDK 36, dan min SDK 26. Pastikan Android Studio menggunakan JDK yang kompatibel dan Android SDK Platform 37 tersedia.

Buka folder project Android ini di Android Studio, tunggu Gradle Sync, lalu jalankan konfigurasi `app`. Dari PowerShell:

```powershell
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
.\gradlew.bat :app:assembleDebug
.\gradlew.bat :app:testDebugUnitTest
```

Jangan commit `local.properties` karena berisi path SDK lokal.

