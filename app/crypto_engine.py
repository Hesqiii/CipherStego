"""Cryptographic and image operations for the local CipherStego demo."""

from __future__ import annotations

import hashlib
import hmac
import io
import os
import struct
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from scipy.stats import chi2
from skimage.metrics import structural_similarity

HEADER_BYTES = 32
HEADER_BITS = HEADER_BYTES * 8
SALT_BYTES = 16
NONCE_BYTES = 12
TAG_BYTES = 16
PBKDF2_ITERATIONS = 600_000
MAX_PDF_BYTES = 600 * 1024
MAX_PIXELS = 8_000_000


class InputError(ValueError):
    """A user-correctable input or format error."""


class AuthenticationError(ValueError):
    """The ciphertext, header, or passphrase failed AEAD verification."""


def safe_name(name: str, fallback: str) -> str:
    clean = Path(name or fallback).name
    return clean or fallback


def _read_rgb_png(raw: bytes) -> np.ndarray:
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise InputError("Berkas penampung harus berupa PNG.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG" or image.mode != "RGB":
                raise InputError("Citra harus PNG RGB 24-bit tanpa kanal alfa.")
            if image.width < 64 or image.height < 64:
                raise InputError("Resolusi citra minimal 64 × 64 piksel untuk demo ini.")
            if image.width * image.height > MAX_PIXELS:
                raise InputError("Resolusi citra melebihi batas demo 8 juta piksel.")
            return np.asarray(image, dtype=np.uint8).copy()
    except InputError:
        raise
    except Exception as exc:
        raise InputError("PNG tidak dapat dibaca. Pilih citra PNG RGB yang valid.") from exc


def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    if not isinstance(passphrase, str) or not passphrase:
        raise InputError("Masukkan passphrase.")
    password = passphrase.encode("utf-8")
    master = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    ).derive(password)
    encryption_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"CipherStego:v1:encryption"
    ).derive(master)
    position_key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"CipherStego:v1:position"
    ).derive(master)
    return encryption_key, position_key


class HMACCounterStream:
    """Deterministic HMAC-SHA256 counter stream with unbiased randbelow."""

    def __init__(self, key: bytes):
        self.key = key
        self.counter = 0
        self.buffer = b""
        self.offset = 0

    def _u64(self) -> int:
        if self.offset + 8 > len(self.buffer):
            self.buffer = hmac.new(
                self.key, self.counter.to_bytes(8, "big"), hashlib.sha256
            ).digest()
            self.counter += 1
            self.offset = 0
        value = int.from_bytes(self.buffer[self.offset : self.offset + 8], "big")
        self.offset += 8
        return value

    def randbelow(self, bound: int) -> int:
        if bound <= 0:
            raise ValueError("bound must be positive")
        limit = (1 << 64) - ((1 << 64) % bound)
        while True:
            value = self._u64()
            if value < limit:
                return value % bound


def _permutation(count: int, key: bytes) -> np.ndarray:
    if count > 0xFFFFFFFF:
        raise InputError("Kapasitas citra melewati batas indeks demo.")
    positions = np.arange(count, dtype=np.uint32)
    stream = HMACCounterStream(key)
    for i in range(count - 1, 0, -1):
        j = stream.randbelow(i + 1)
        positions[i], positions[j] = positions[j], positions[i]
    return positions


def _embed_ciphertext(cover: np.ndarray, header: bytes, ciphertext: bytes, position_key: bytes, mode: str) -> np.ndarray:
    if mode not in ("randomized", "sequential"):
        raise InputError("Pilih metode Randomized LSB atau Sequential LSB.")
    flat = cover.reshape(-1).copy()
    payload_bits = np.unpackbits(np.frombuffer(ciphertext, dtype=np.uint8))
    available = flat.size - HEADER_BITS
    if available < 0 or payload_bits.size > available:
        raise InputError("Kapasitas PNG tidak cukup untuk header dan ciphertext.")
    header_bits = np.unpackbits(np.frombuffer(header, dtype=np.uint8))
    flat[:HEADER_BITS] = (flat[:HEADER_BITS] & 0xFE) | header_bits
    if mode == "sequential":
        indices = np.arange(HEADER_BITS, HEADER_BITS + payload_bits.size, dtype=np.intp)
    else:
        shuffled = _permutation(available, position_key)
        indices = shuffled[: payload_bits.size].astype(np.intp) + HEADER_BITS
    flat[indices] = (flat[indices] & 0xFE) | payload_bits
    return flat.reshape(cover.shape)


def _png_bytes(pixels: np.ndarray) -> bytes:
    stream = io.BytesIO()
    Image.fromarray(pixels).save(stream, format="PNG", optimize=False)
    return stream.getvalue()


def _make_envelope(pdf: bytes, passphrase: str) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    encryption_key, position_key = _derive_keys(passphrase, salt)
    encrypted_length = len(pdf) + TAG_BYTES
    header = salt + nonce + struct.pack(">I", encrypted_length)
    ciphertext = AESGCM(encryption_key).encrypt(nonce, pdf, header)
    return header, ciphertext, encryption_key, position_key, nonce


def embed(pdf: bytes, cover_bytes: bytes, passphrase: str, mode: str, pdf_name: str = "dokumen.pdf") -> dict:
    if not pdf.startswith(b"%PDF-"):
        raise InputError("Berkas muatan tidak memiliki tanda tangan PDF yang valid.")
    if len(pdf) > MAX_PDF_BYTES:
        raise InputError("Ukuran PDF melewati batas demo 600 KiB.")
    if len(passphrase) < 12:
        raise InputError("Gunakan passphrase minimal 12 karakter.")
    cover = _read_rgb_png(cover_bytes)
    started = perf_counter()
    header, ciphertext, _enc_key, position_key, _nonce = _make_envelope(pdf, passphrase)
    if HEADER_BITS + len(ciphertext) * 8 > cover.size:
        raise InputError("Kapasitas PNG tidak cukup untuk header dan ciphertext.")
    stego = _embed_ciphertext(cover, header, ciphertext, position_key, mode)
    output = _png_bytes(stego)
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    return {
        "png": output,
        "metadata": {
            "source_name": safe_name(pdf_name, "dokumen.pdf"),
            "source_bytes": len(pdf),
            "source_sha256": hashlib.sha256(pdf).hexdigest(),
            "ciphertext_bytes": len(ciphertext),
            "header_bytes": HEADER_BYTES,
            "capacity_bytes": (cover.size - HEADER_BITS) // 8,
            "capacity_used_percent": round((HEADER_BITS + len(ciphertext) * 8) / cover.size * 100, 2),
            "width": int(cover.shape[1]),
            "height": int(cover.shape[0]),
            "mode": mode,
            "elapsed_ms": elapsed_ms,
            "note": "SHA-256 adalah fingerprint uji; autentikasi ciphertext dilakukan oleh tag AES-GCM.",
        },
    }


def _extract_envelope(stego_bytes: bytes, passphrase: str, mode: str) -> tuple[bytes, np.ndarray, dict]:
    stego = _read_rgb_png(stego_bytes)
    flat = stego.reshape(-1)
    if flat.size < HEADER_BITS:
        raise InputError("Citra terlalu kecil untuk memuat header.")
    header = np.packbits(flat[:HEADER_BITS] & 1).tobytes()
    salt = header[:SALT_BYTES]
    nonce = header[SALT_BYTES : SALT_BYTES + NONCE_BYTES]
    encrypted_length = struct.unpack(">I", header[28:32])[0]
    available_bytes = (flat.size - HEADER_BITS) // 8
    if encrypted_length < TAG_BYTES or encrypted_length > available_bytes:
        raise InputError("Field panjang header tidak valid atau melebihi kapasitas PNG.")
    if mode not in ("randomized", "sequential"):
        raise InputError("Pilih metode yang sama dengan metode saat penyisipan.")
    encryption_key, position_key = _derive_keys(passphrase, salt)
    bit_count = encrypted_length * 8
    if mode == "sequential":
        indices = np.arange(HEADER_BITS, HEADER_BITS + bit_count, dtype=np.intp)
    else:
        shuffled = _permutation(flat.size - HEADER_BITS, position_key)
        indices = shuffled[:bit_count].astype(np.intp) + HEADER_BITS
    ciphertext = np.packbits(flat[indices] & 1).tobytes()
    try:
        pdf = AESGCM(encryption_key).decrypt(nonce, ciphertext, header)
    except InvalidTag as exc:
        raise AuthenticationError("Autentikasi gagal. Passphrase salah atau data/header telah berubah.") from exc
    if not pdf.startswith(b"%PDF-"):
        raise AuthenticationError("Tag valid, tetapi payload bukan berkas PDF yang dapat dikenali.")
    return pdf, stego, {"width": int(stego.shape[1]), "height": int(stego.shape[0]), "ciphertext_bytes": encrypted_length}


def extract(stego_bytes: bytes, passphrase: str, mode: str) -> dict:
    started = perf_counter()
    pdf, stego, metadata = _extract_envelope(stego_bytes, passphrase, mode)
    metadata.update({
        "sha256": hashlib.sha256(pdf).hexdigest(),
        "pdf_bytes": len(pdf),
        "elapsed_ms": round((perf_counter() - started) * 1000, 2),
        "mode": mode,
    })
    return {"pdf": pdf, "metadata": metadata}


def _chi_square_pair_test(pixels: np.ndarray) -> dict:
    histogram = np.bincount(pixels.reshape(-1), minlength=256).astype(np.float64)
    even, odd = histogram[0::2], histogram[1::2]
    totals = even + odd
    valid = totals > 0
    expected = totals[valid] / 2.0
    statistic = float(np.sum((even[valid] - expected) ** 2 / expected + (odd[valid] - expected) ** 2 / expected))
    degrees = int(np.count_nonzero(valid))
    p_value = float(chi2.sf(statistic, degrees)) if degrees else 1.0
    return {"statistic": round(statistic, 3), "degrees_freedom": degrees, "p_value": p_value}


def _rs_counts(pixels: np.ndarray) -> dict:
    gray = np.asarray(Image.fromarray(pixels).convert("L"), dtype=np.uint8).reshape(-1)
    usable = gray.size - (gray.size % 4)
    groups = gray[:usable].reshape(-1, 4).astype(np.int16)
    original = np.abs(groups[:, 1:] - groups[:, :-1]).sum(axis=1)
    plus = groups.copy()
    minus = groups.copy()
    positive_mask = np.array([1, 0, 1, 0], dtype=np.int16)
    selected = positive_mask.astype(bool)
    plus[:, selected] = np.clip(plus[:, selected] + np.where(groups[:, selected] % 2 == 0, 1, -1), 0, 255)
    minus[:, selected] = np.clip(minus[:, selected] + np.where(groups[:, selected] % 2 == 0, -1, 1), 0, 255)
    f_plus = np.abs(plus[:, 1:] - plus[:, :-1]).sum(axis=1)
    f_minus = np.abs(minus[:, 1:] - minus[:, :-1]).sum(axis=1)
    return {
        "regular_positive": int(np.count_nonzero(f_plus > original)),
        "singular_positive": int(np.count_nonzero(f_plus < original)),
        "regular_negative": int(np.count_nonzero(f_minus > original)),
        "singular_negative": int(np.count_nonzero(f_minus < original)),
        "groups": int(groups.shape[0]),
        "note": "Hitungan RS dasar untuk perbandingan; bukan estimasi payload atau klaim tak-terdeteksi.",
    }


def tamper_header(stego_bytes: bytes) -> bytes:
    """Flip the first salt bit in the visible header for an integrity demo."""
    pixels = _read_rgb_png(stego_bytes)
    flat = pixels.reshape(-1).copy()
    if flat.size < HEADER_BITS:
        raise InputError("Citra terlalu kecil untuk memuat header.")
    flat[0] ^= 1
    return _png_bytes(flat.reshape(pixels.shape))


def evaluate(pdf: bytes, cover_bytes: bytes, passphrase: str, pdf_name: str = "dokumen.pdf") -> dict:
    if not pdf.startswith(b"%PDF-"):
        raise InputError("Berkas muatan tidak memiliki tanda tangan PDF yang valid.")
    if len(pdf) > MAX_PDF_BYTES:
        raise InputError("Ukuran PDF melewati batas demo 600 KiB.")
    if len(passphrase) < 12:
        raise InputError("Gunakan passphrase minimal 12 karakter.")
    cover = _read_rgb_png(cover_bytes)
    header, ciphertext, encryption_key, position_key, nonce = _make_envelope(pdf, passphrase)
    if HEADER_BITS + len(ciphertext) * 8 > cover.size:
        raise InputError("Kapasitas PNG tidak cukup untuk header dan ciphertext.")
    original_hash = hashlib.sha256(pdf).hexdigest()
    results = []
    for mode in ("sequential", "randomized"):
        started = perf_counter()
        stego = _embed_ciphertext(cover, header, ciphertext, position_key, mode)
        stego_bytes = _png_bytes(stego)
        try:
            recovered, _img, _meta = _extract_envelope(stego_bytes, passphrase, mode)
        except Exception as exc:
            raise RuntimeError(f"Pemulihan internal gagal untuk {mode}: {exc}") from exc
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        delta = cover.astype(np.float64) - stego.astype(np.float64)
        mse = float(np.mean(delta * delta))
        psnr = float("inf") if mse == 0 else 10.0 * np.log10((255.0 * 255.0) / mse)
        ssim = float(structural_similarity(cover, stego, channel_axis=2, data_range=255))
        changed_channels = int(np.count_nonzero(cover.reshape(-1) != stego.reshape(-1)))
        results.append({
            "method": mode,
            "mse": round(mse, 8),
            "psnr_db": round(float(psnr), 3) if np.isfinite(psnr) else None,
            "ssim": round(ssim, 6),
            "changed_channels": changed_channels,
            "chi_square": _chi_square_pair_test(stego),
            "rs": _rs_counts(stego),
            "recovery_matches": hashlib.sha256(recovered).hexdigest() == original_hash,
            "elapsed_ms": elapsed_ms,
        })
    return {
        "source_name": Path(pdf_name or "dokumen.pdf").name,
        "source_bytes": len(pdf),
        "source_sha256": original_hash,
        "width": int(cover.shape[1]),
        "height": int(cover.shape[0]),
        "payload_ciphertext_bytes": len(ciphertext),
        "results": results,
        "note": "Satu pasangan berkas untuk demonstrasi. Hasil ini tidak menggantikan matriks eksperimen 10×3 dan lima ulangan dalam proposal.",
    }
