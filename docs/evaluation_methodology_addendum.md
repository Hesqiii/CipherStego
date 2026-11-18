# Addendum Metodologi Evaluation Engine

Dokumen ini menetapkan konfigurasi operasional untuk implementasi metrik pada Milestone 7. Dokumen ini tidak mengubah proposal resmi. Jika proposal resmi kelak menetapkan parameter yang berbeda, tim harus menyelaraskan implementasi dan meminta persetujuan perubahan sebelum eksperimen formal.

## MSE, PSNR, dan SSIM

Semua metrik memakai array RGB 8-bit dengan dimensi sama. MSE dirata-ratakan atas seluruh piksel dan kanal. PSNR memakai `MAX=255`; untuk `MSE=0`, API mengembalikan nilai `null` dengan status `infinite` karena hasil matematisnya tak hingga.

SSIM dihitung tepat dengan konfigurasi berikut:

```python
structural_similarity(
    cover, stego, data_range=255, channel_axis=-1,
    gaussian_weights=True, sigma=1.5,
    use_sample_covariance=False, K1=0.01, K2=0.03,
)
```

Pustaka `scikit-image` dipatok pada versi 0.26.0. Fungsi memproses setiap kanal RGB dan mengembalikan rata-rata kanal. Gaussian sigma 1,5 menghasilkan jendela baku 11×11; karena itu kedua dimensi gambar harus sekurangnya 11 piksel. [Dokumentasi API scikit-image](https://scikit-image.org/docs/stable/api/skimage.metrics.html?highlight=compare_mse).

## Chi-square pair-of-values

Analisis dilakukan terpisah untuk kanal merah, hijau, dan biru. Setiap kanal diratakan secara row-major. Untuk setiap prefiks 1% hingga 100%, jumlah sampel adalah `ceil(width × height × persentase / 100)`.

Histogram intensitas memasangkan bin `(0,1), (2,3), …, (254,255)`. Di bawah hipotesis kesetaraan frekuensi pasangan, nilai harapan untuk intensitas genap dalam satu kelompok adalah setengah jumlah frekuensi kelompok itu. Pasangan berurutan digabung dari intensitas rendah ke tinggi sampai frekuensi harapan melebihi 4. Kelompok sisa di akhir digabung dengan kelompok sebelumnya. Statistiknya `Σ((O−E)²/E)` dan derajat bebas `k−1`, dengan `k` jumlah kelompok setelah penggabungan. Jika kurang dari dua kelompok tersedia atau nilai harapan nol, hasil diberi status `not_estimable` dan tidak diperlakukan sebagai p-value.

API menyimpan kedua ekor secara terpisah: p-value ekor atas untuk uji PoV konvensional dan p-value ekor bawah sebagai indikator underdispersion yang diharapkan pada embedding LSB. Koreksi Holm diterapkan pada p-value ekor bawah untuk keluarga tetap 300 uji per gambar (3 kanal × 100 prefiks), `α=0.05`. Uji yang tidak dapat dihitung memakai nilai 1 hanya saat membentuk keluarga Holm; API mempertahankan nilai p-value dan nilai terkoreksi sebagai `null` untuk hasil tersebut.

Hasil cover dan stego dilaporkan terpisah sebagai kontrol dan sampel. Indikator prefiks adalah eksploratif. Khusus Randomized LSB, prefiks tidak mewakili seluruh citra dan tidak boleh ditafsirkan sebagai bukti deteksi seluruh gambar. Keterbatasan ini sejalan dengan pembahasan uji PoV untuk embedding tersebar pada Westfeld dan Pfitzmann, sehingga laporan menyebut hasilnya sebagai kemungkinan indikator, bukan klasifikasi pasti. [Westfeld & Pfitzmann (1999)](https://users.ece.cmu.edu/~adrian/487-s06/westfeld-pfitzmann-ihw99.pdf).

## RS analysis

Setiap kanal dianalisis sendiri memakai grup 2×2 yang tidak tumpang tindih. Gambar dipotong hanya untuk analisis bila lebar atau tingginya ganjil; penyisipan dan citra sumber tidak berubah. Urutan grup piksel adalah TL, TR, BL, BR. Mask `M=[[1,0],[0,1]]` dan `−M` menggunakan transformasi bertanda `F1` dan `F−1`: nilai sementara dapat menjadi −1 atau 256 dan tidak di-clip. Fungsi diskriminasi adalah jumlah selisih absolut piksel bertetangga pada urutan grup. Grup diklasifikasikan R, S, atau U berdasarkan perubahan fungsi diskriminasi.

Kurva R/S dihitung pada citra asli dan citra yang seluruh kanalnya diberi transformasi F1. Empat selisih ternormalisasi itu dimasukkan ke persamaan kuadrat RS; estimator memilih akar real dengan nilai absolut terkecil, lalu menghitung `p = z/(z−0.5)`. Persamaan degenerat, akar non-real, nilai non-finite, atau `p` di luar `[0,1]` ditolak tanpa clipping. Pemetaan panjang pesan memakai `p × width × height` bit per kanal.

Untuk setiap kanal, estimasi cover menjadi koreksi bias awal: `p_corrected=(p_stego−p_cover)/(1−p_cover)`. Koreksi ditolak jika tidak stabil atau keluar `[0,1]`. Perkiraan total hanya diberikan jika estimasi tiga kanal dapat dipakai; nilainya adalah jumlah perkiraan per kanal. API membandingkan hasil dengan jumlah aktual bit yang disisipkan, yaitu `8 × (32 + ciphertext_length)`, termasuk tag GCM dalam panjang ciphertext. RS sensitif terhadap pola cover, noise, dan asumsi model; estimasi ini bukan pengukuran ground truth. Konfigurasi grup, mask, dan estimator mengikuti Fridrich, Goljan, dan Du (2001), dengan persamaan estimator kuantitatif dari Fridrich et al. (2003). [Fridrich et al. (2001)](https://dde.binghamton.edu/publications/acm_2001_03.pdf), [Fridrich et al. (2003)](https://ws.binghamton.edu/fridrich/Research/mms100.pdf).

## Batas interpretasi

Endpoint evaluasi menjalankan satu operasi embed dan recover aktual untuk satu request. Ini memverifikasi alur perangkat lunak, bukan eksperimen proposal. Hasil dari tiga citra cover dan kombinasi payload penelitian, kontrol, pengulangan waktu, analisis pasangan, serta uji statistik tetap perlu dikumpulkan pada milestone eksperimen berikutnya. Tidak ada angka eksperimen yang ditulis atau disimulasikan oleh addendum ini.
