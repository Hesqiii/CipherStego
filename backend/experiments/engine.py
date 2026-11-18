"""Paired experiment execution. The caller gates formal runs on a passed pilot."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns
from typing import Any
from uuid import uuid4

import numpy as np
from PIL import Image

from backend.core.crypto.constants import HEADER_BYTES
from backend.core.crypto.exceptions import (
    AuthenticationError,
    CryptoInputError,
    PayloadFormatError,
)
from backend.core.crypto.key_derivation import derive_keys
from backend.core.crypto.models import DerivedKeys, EncryptedPayload
from backend.core.crypto.payload_crypto import decrypt_payload_with_keys, encrypt_payload_with_keys
from backend.core.evaluation.chi_square import analyze_chi_square
from backend.core.evaluation.image_metrics import calculate_visual_metrics, scikit_image_version
from backend.core.evaluation.rs_analysis import CHANNELS, analyze_rs
from backend.core.steganography.exceptions import InsufficientCapacityError, InvalidPayloadError
from backend.core.steganography.header import parse_payload_header
from backend.core.steganography.image_io import load_rgb_png, save_rgb_png
from backend.core.steganography.randomized_lsb import (
    _ciphertext_positions,
    embed_randomized,
    extract_randomized,
)
from backend.core.steganography.sequential_lsb import embed_sequential, extract_sequential

METHODS = ("sequential", "randomized")
REPETITIONS = 5
SCHEMA_VERSION = 1


class DatasetNotReadyError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def _write_csv_new(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _versions() -> dict[str, str]:
    import cryptography
    import numpy
    import PIL
    import scipy

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "cryptography": cryptography.__version__,
        "numpy": numpy.__version__,
        "pillow": PIL.__version__,
        "scipy": scipy.__version__,
        "scikit_image": scikit_image_version(),
    }


def _prepare_payload(
    pdf: bytes, passphrase: str, globally_seen_nonces: set[bytes]
) -> tuple[EncryptedPayload, DerivedKeys, list[float]]:
    samples: list[float] = []
    selected: tuple[EncryptedPayload, DerivedKeys] | None = None
    for index in range(REPETITIONS):
        started = perf_counter_ns()
        encrypted, keys = encrypt_payload_with_keys(passphrase, pdf)
        elapsed_ms = (perf_counter_ns() - started) / 1_000_000
        if encrypted.header.nonce in globally_seen_nonces:
            raise RuntimeError("Nonce duplikat muncul dalam pengukuran enkripsi eksperimen.")
        globally_seen_nonces.add(encrypted.header.nonce)
        samples.append(elapsed_ms)
        if index == 0:
            selected = encrypted, keys
    assert selected is not None
    return selected[0], selected[1], samples


def _embed(mode: str, cover_path: Path, encrypted: EncryptedPayload, keys: DerivedKeys, timings: dict[str, float]):
    if mode == "sequential":
        return embed_sequential(
            cover_path, encrypted.header_bytes, encrypted.ciphertext, timings=timings
        )
    return embed_randomized(
        cover_path,
        encrypted.header_bytes,
        encrypted.ciphertext,
        keys.position_key,
        timings=timings,
    )


def _extract(mode: str, stego_path: Path, keys: DerivedKeys, timings: dict[str, float]):
    if mode == "sequential":
        return extract_sequential(stego_path, timings=timings)
    return extract_randomized(stego_path, keys.position_key, timings=timings)


def _channel_bit_counts(mode: str, total_slots: int, ciphertext_length: int, position_key: bytes) -> dict[str, int]:
    header_slots = HEADER_BYTES * 8
    ciphertext_bits = ciphertext_length * 8
    if mode == "sequential":
        slots = np.arange(header_slots + ciphertext_bits, dtype=np.uint64)
    else:
        available = total_slots - header_slots
        positions = _ciphertext_positions(available, ciphertext_bits, position_key)
        slots = np.concatenate(
            (np.arange(header_slots, dtype=np.uint64), positions.astype(np.uint64, copy=False))
        )
    counts = np.bincount((slots % 3).astype(np.int64), minlength=3)
    return {name: int(counts[index]) for index, name in enumerate(CHANNELS)}


def _change_header(stego: Image.Image, header: bytes) -> Image.Image:
    pixels = np.asarray(stego, dtype=np.uint8).copy()
    slots = pixels.reshape(-1)
    bits = np.unpackbits(np.frombuffer(header, dtype=np.uint8), bitorder="big")
    slots[: HEADER_BYTES * 8] = (slots[: HEADER_BYTES * 8] & 0xFE) | bits
    return Image.fromarray(pixels)


def _tamper_scenario(
    mode: str,
    stego: Image.Image,
    encrypted: EncryptedPayload,
    keys: DerivedKeys,
    scenario: str,
) -> tuple[Image.Image, str]:
    pixels = np.asarray(stego, dtype=np.uint8).copy()
    slots = pixels.reshape(-1)
    header = bytearray(encrypted.header_bytes)
    if scenario == "ciphertext_bit":
        if mode == "sequential":
            target = HEADER_BYTES * 8
        else:
            positions = _ciphertext_positions(
                slots.size - HEADER_BYTES * 8,
                len(encrypted.ciphertext) * 8,
                keys.position_key,
            )
            target = int(positions[0])
        slots[target] ^= np.uint8(1)
        return Image.fromarray(pixels), "ciphertext_bit"
    if scenario == "salt":
        header[0] ^= 1
    elif scenario == "nonce":
        header[16] ^= 1
    elif scenario == "length_valid":
        new_length = encrypted.header.ciphertext_length + 1
        header[28:32] = new_length.to_bytes(4, "big")
    elif scenario == "length_over_capacity":
        maximum = slots.size // 8 - HEADER_BYTES
        new_length = min((1 << 32) - 1, maximum + 1)
        header[28:32] = new_length.to_bytes(4, "big")
    else:
        raise ValueError(f"Unknown tamper scenario: {scenario}")
    return _change_header(Image.fromarray(pixels), bytes(header)), scenario


def _run_tamper_check(
    mode: str,
    image: Image.Image,
    passphrase: str,
    filename: str,
    workspace: Path,
    case_id: str,
    scenario: str,
) -> dict[str, Any]:
    target = workspace / f"{case_id}_{scenario}.png"
    save_rgb_png(image, target)
    try:
        # The same production receiver validates length, reconstructs positions,
        # authenticates the header/ciphertext, and releases no bytes on failure.
        from backend.services.receiver_service import recover_pdf

        recovered = recover_pdf(target.read_bytes(), passphrase, target.name, mode)
        return {
            "scenario": scenario,
            "status": "unexpected_pdf_created",
            "failure_stage": None,
            "pdf_created": bool(recovered.pdf_base64),
            "error_type": None,
        }
    except AuthenticationError as exc:
        return {
            "scenario": scenario,
            "status": "rejected",
            "failure_stage": "gcm_authentication",
            "pdf_created": False,
            "error_type": type(exc).__name__,
        }
    except InsufficientCapacityError as exc:
        return {
            "scenario": scenario,
            "status": "rejected",
            "failure_stage": "capacity_validation",
            "pdf_created": False,
            "error_type": type(exc).__name__,
        }
    except (InvalidPayloadError, PayloadFormatError, CryptoInputError) as exc:
        return {
            "scenario": scenario,
            "status": "rejected",
            "failure_stage": "format_validation",
            "pdf_created": False,
            "error_type": type(exc).__name__,
        }


def _security_scenarios(
    mode: str,
    stego: Image.Image,
    encrypted: EncryptedPayload,
    keys: DerivedKeys,
    passphrase: str,
    source_name: str,
    workspace: Path,
    case_id: str,
) -> dict[str, Any]:
    wrong_passphrase = passphrase[:-1] + ("x" if passphrase[-1] != "x" else "y")
    wrong_result = _run_tamper_check(
        mode, stego, wrong_passphrase, source_name, workspace, case_id, "wrong_passphrase"
    )
    tamper_results = []
    for scenario in ("ciphertext_bit", "salt", "nonce", "length_valid", "length_over_capacity"):
        changed, name = _tamper_scenario(mode, stego, encrypted, keys, scenario)
        result = _run_tamper_check(mode, changed, passphrase, source_name, workspace, case_id, name)
        tamper_results.append(result)
    return {"wrong_passphrase": wrong_result, "tampering": tamper_results}


def run_condition(
    *,
    mode: str,
    cover_path: Path,
    cover_id: str,
    cover_sha256: str,
    payload_id: str,
    pdf_data: bytes,
    pdf_sha256: str,
    passphrase: str,
    encrypted: EncryptedPayload,
    keys: DerivedKeys,
    encryption_times_ms: list[float],
    actual_bits_by_channel: dict[str, int],
    output_path: Path,
    include_security_scenarios: bool,
    warmup_state: dict[str, bool],
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cover_before = cover_path.read_bytes()
    parsed_header = parse_payload_header(encrypted.header_bytes)
    if parsed_header.ciphertext_length != len(encrypted.ciphertext):
        raise RuntimeError("Eksperimen menerima panjang ciphertext/header yang tidak cocok.")
    with tempfile.TemporaryDirectory(prefix="cipherstego-pair-") as temp_name:
        temp = Path(temp_name)
        method_cover = temp / f"cover_{mode}.png"
        method_cover.write_bytes(cover_before)
        if _sha256(method_cover.read_bytes()) != cover_sha256:
            raise RuntimeError("Salinan cover untuk metode ini tidak identik dengan cover sumber.")
        warmup_path = temp / "warmup.png"
        if not warmup_state[mode]:
            warmup_timings: dict[str, float] = {}
            warmup_image = _embed(mode, method_cover, encrypted, keys, warmup_timings)
            save_rgb_png(warmup_image, warmup_path)
            warmup_keys = derive_keys(passphrase, parsed_header.salt)
            warmup_extract_timings: dict[str, float] = {}
            recovered = _extract(mode, warmup_path, warmup_keys, warmup_extract_timings)
            if decrypt_payload_with_keys(recovered.header, recovered.ciphertext, warmup_keys) != pdf_data:
                raise RuntimeError("Warm-up round-trip tidak cocok.")
            warmup_state[mode] = True

        embedding_repetitions: list[dict[str, float | int]] = []
        first_stego: Image.Image | None = None
        first_png_hash: str | None = None
        first_array: np.ndarray | None = None
        for repetition in range(1, REPETITIONS + 1):
            phase: dict[str, float] = {}
            started = perf_counter_ns()
            stego = _embed(mode, method_cover, encrypted, keys, phase)
            total_ms = (perf_counter_ns() - started) / 1_000_000
            if first_stego is None:
                first_stego = stego.copy()
                save_rgb_png(first_stego, output_path)
                png_data = output_path.read_bytes()
                first_png_hash = _sha256(png_data)
                with Image.open(output_path) as decoded:
                    first_array = np.asarray(decoded, dtype=np.uint8).copy()
            else:
                candidate = temp / f"repeat_{repetition}.png"
                save_rgb_png(stego, candidate)
                if _sha256(candidate.read_bytes()) != first_png_hash:
                    raise RuntimeError("Embedding deterministik menghasilkan PNG berbeda pada pengulangan.")
            embedding_repetitions.append(
                {
                    "repetition": repetition,
                    "embedding_total_ms": total_ms,
                    "permutation_ms": phase.get("permutation_ms", 0.0),
                    "lsb_operation_ms": phase.get("embedding_ms", total_ms),
                }
            )

        assert first_stego is not None and first_array is not None and first_png_hash is not None
        extraction_repetitions: list[dict[str, float | int]] = []
        integrity_matches: list[bool] = []
        stego_path = output_path
        recovered_bytes: bytes | None = None
        for repetition in range(1, REPETITIONS + 1):
            kdf_started = perf_counter_ns()
            receiver_keys = derive_keys(passphrase, parsed_header.salt)
            kdf_ms = (perf_counter_ns() - kdf_started) / 1_000_000
            phase = {}
            started = perf_counter_ns()
            extracted = _extract(mode, stego_path, receiver_keys, phase)
            extraction_ms = (perf_counter_ns() - started) / 1_000_000
            decrypt_started = perf_counter_ns()
            recovered = decrypt_payload_with_keys(extracted.header, extracted.ciphertext, receiver_keys)
            decrypt_ms = (perf_counter_ns() - decrypt_started) / 1_000_000
            matched = _sha256(recovered) == pdf_sha256 and recovered == pdf_data
            integrity_matches.append(matched)
            if not matched:
                raise RuntimeError(f"Integritas gagal pada {payload_id}/{cover_id}/{mode}.")
            recovered_bytes = recovered
            extraction_repetitions.append(
                {
                    "repetition": repetition,
                    "key_derivation_ms": kdf_ms,
                    "extraction_total_ms": extraction_ms,
                    "permutation_ms": phase.get("permutation_ms", 0.0),
                    "lsb_operation_ms": phase.get("extraction_ms", extraction_ms),
                    "image_load_ms": phase.get("image_load_ms", 0.0),
                    "decryption_ms": decrypt_ms,
                }
            )
        assert recovered_bytes is not None

        with Image.open(cover_path) as source_image:
            cover_array = np.asarray(source_image, dtype=np.uint8).copy()
        visual = calculate_visual_metrics(cover_array, first_array)
        chi_stego = analyze_chi_square(first_array)
        actual_by_channel = actual_bits_by_channel
        actual_total_bits = 8 * (HEADER_BYTES + len(encrypted.ciphertext))
        if sum(actual_by_channel.values()) != actual_total_bits:
            raise RuntimeError("Jumlah slot per kanal tidak sama dengan bit payload yang disisipkan.")
        rs = analyze_rs(cover_array, first_array, actual_total_bits)
        rs["method_interpretation"] = (
            "RS lebih sesuai untuk penyisipan tersebar; interpretasikan estimasi Sequential secara terbatas."
            if mode == "sequential"
            else "RS estimasi panjang pesan dan bukan klasifikasi deteksi tunggal."
        )
        for channel_name, estimate in rs["channels"].items():
            estimate["actual_embedded_bits"] = actual_by_channel[channel_name]
            actual_estimate = estimate.get("corrected_estimated_bits")
            estimate["absolute_error_bits"] = (
                abs(actual_estimate - actual_by_channel[channel_name])
                if actual_estimate is not None
                else None
            )
            estimate["relative_error"] = (
                estimate["absolute_error_bits"] / actual_by_channel[channel_name]
                if estimate["absolute_error_bits"] is not None and actual_by_channel[channel_name]
                else None
            )
        if _sha256(cover_path.read_bytes()) != cover_sha256:
            raise RuntimeError("Cover sumber berubah selama eksperimen.")

        security = None
        if include_security_scenarios:
            security = _security_scenarios(
                mode,
                first_stego,
                encrypted,
                keys,
                passphrase,
                output_path.name,
                temp,
                f"{payload_id}_{cover_id}_{mode}",
            )

        return {
            "payload_id": payload_id,
            "cover_id": cover_id,
            "mode": mode,
            "repetition_count": REPETITIONS,
            "source": {
                "sha256": pdf_sha256,
                "size_bytes": len(pdf_data),
            },
            "cover": {
                "sha256": cover_sha256,
                "dimensions": [int(cover_array.shape[1]), int(cover_array.shape[0])],
                "color_mode": "RGB",
            },
            "payload_crypto": {
                "salt_hex": encrypted.header.salt.hex(),
                "nonce_hex": encrypted.header.nonce.hex(),
                "header_hex": encrypted.header_bytes.hex(),
                "ciphertext_length_bytes": len(encrypted.ciphertext),
                "ciphertext_sha256": _sha256(encrypted.ciphertext),
                "embedded_bits_total": actual_total_bits,
                "embedded_bits_by_channel": actual_by_channel,
                "passphrase_or_key_recorded": False,
            },
            "stego": {
                "filename": output_path.name,
                "sha256": first_png_hash,
            },
            "integrity": {
                "recovered_sha256": _sha256(recovered_bytes),
                "all_repetitions_match": all(integrity_matches),
                "recovery_rate": sum(integrity_matches) / len(integrity_matches),
            },
            "quality": {
                "mse": visual.mse,
                "psnr_db": None if not np.isfinite(visual.psnr_db) else visual.psnr_db,
                "ssim": visual.ssim,
                "psnr_status": "infinite" if not np.isfinite(visual.psnr_db) else "finite",
            },
            "timing": {
                "encryption_ms_per_payload_repetition": encryption_times_ms,
                "embedding_repetitions": embedding_repetitions,
                "extraction_repetitions": extraction_repetitions,
                "embedding_mean_ms": float(np.mean([row["embedding_total_ms"] for row in embedding_repetitions])),
                "embedding_sd_ms": float(np.std([row["embedding_total_ms"] for row in embedding_repetitions], ddof=1)),
                "extraction_mean_ms": float(np.mean([row["extraction_total_ms"] for row in extraction_repetitions])),
                "extraction_sd_ms": float(np.std([row["extraction_total_ms"] for row in extraction_repetitions], ddof=1)),
            },
            "chi_square": {"stego": chi_stego},
            "rs_analysis": rs,
            "security_scenarios": security,
            "software": _versions(),
        }


def run_matrix(
    *,
    manifest: dict[str, Any],
    dataset_dir: Path,
    experiment_data_dir: Path,
    passphrase: str,
    pilot: bool,
    pilot_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one pilot condition or the 30 paired conditions for both methods."""
    if not manifest.get("ready_for_pilot"):
        raise DatasetNotReadyError("Dataset belum lengkap/valid atau privacy review belum disahkan.")
    if not passphrase:
        raise ValueError("Passphrase eksperimen tidak boleh kosong.")
    if not pilot and (
        pilot_report is None
        or pilot_report.get("run_type") != "pilot"
        or pilot_report.get("dataset_fingerprint") != manifest["privacy_review"]["dataset_fingerprint"]
        or pilot_report.get("integrity_all_passed") is not True
        or pilot_report.get("quality_all_finite") is not True
        or pilot_report.get("security_checks_all_rejected") is not True
    ):
        raise DatasetNotReadyError("Matriks formal memerlukan pilot lulus untuk fingerprint dataset yang sama.")
    run_id = ("pilot-" if pilot else "formal-") + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    run_root = experiment_data_dir / "raw" / run_id
    run_root.mkdir(parents=True, exist_ok=False)
    _json_new(run_root / "dataset_manifest.json", manifest)
    for scenario in ("S1", "S2", "S3", "S4", "S5", "stego", "cover_controls"):
        (run_root / scenario).mkdir(parents=True, exist_ok=False)
    summary_dir = experiment_data_dir / "summaries" / run_id
    summary_dir.mkdir(parents=True, exist_ok=False)

    pdf_by_id = {item["sample_id"]: dataset_dir / "pdf" / item["filename"] for item in manifest["payloads"]}
    cover_by_id = {item["sample_id"]: dataset_dir / "cover_images" / item["filename"] for item in manifest["covers"]}
    payload_ids = ["P01"] if pilot else [f"P{i:02d}" for i in range(1, 11)]
    cover_ids = ["C1"] if pilot else ["C1", "C2", "C3"]
    passphrases: dict[str, str] = {}
    encrypted_payloads: dict[str, tuple[EncryptedPayload, DerivedKeys, list[float], bytes]] = {}
    used_nonces: set[bytes] = set()
    for payload_id in payload_ids:
        pdf_data = pdf_by_id[payload_id].read_bytes()
        expected_pdf_hash = next(
            item["sha256"] for item in manifest["payloads"] if item["sample_id"] == payload_id
        )
        if _sha256(pdf_data) != expected_pdf_hash:
            raise DatasetNotReadyError(f"Hash {payload_id} berubah setelah preflight.")
        passphrases[payload_id] = passphrase
        encrypted, keys, encryption_times = _prepare_payload(
            pdf_data, passphrases[payload_id], used_nonces
        )
        encrypted_payloads[payload_id] = (
            encrypted,
            keys,
            encryption_times,
            pdf_data,
        )

    condition_results: list[dict[str, Any]] = []
    warmup_state = {mode: False for mode in METHODS}
    slot_count_cache: dict[tuple[str, str], dict[str, int]] = {}
    for payload_id in payload_ids:
        encrypted, keys, encryption_times, pdf_data = encrypted_payloads[payload_id]
        pdf_sha = _sha256(pdf_data)
        for cover_id in cover_ids:
            cover_path = cover_by_id[cover_id]
            cover_hash = _sha256(cover_path.read_bytes())
            expected_cover_hash = next(
                item["sha256"] for item in manifest["covers"] if item["sample_id"] == cover_id
            )
            if cover_hash != expected_cover_hash:
                raise DatasetNotReadyError(f"Hash {cover_id} berubah setelah preflight.")
            # The same prepared header/ciphertext and cover bytes feed both methods.
            pair_id = f"{payload_id}_{cover_id}"
            for mode in METHODS:
                cache_key = (payload_id, mode)
                if cache_key not in slot_count_cache:
                    with Image.open(cover_path) as image:
                        total_slots = image.width * image.height * 3
                    slot_count_cache[cache_key] = _channel_bit_counts(
                        mode,
                        total_slots,
                        len(encrypted.ciphertext),
                        keys.position_key,
                    )
                stego_path = run_root / "stego" / f"{pair_id}_{mode}.png"
                row = run_condition(
                    mode=mode,
                    cover_path=cover_path,
                    cover_id=cover_id,
                    cover_sha256=cover_hash,
                    payload_id=payload_id,
                    pdf_data=pdf_data,
                    pdf_sha256=pdf_sha,
                    passphrase=passphrases[payload_id],
                    encrypted=encrypted,
                    keys=keys,
                    encryption_times_ms=encryption_times,
                    actual_bits_by_channel=slot_count_cache[cache_key],
                    output_path=stego_path,
                    include_security_scenarios=(payload_id == payload_ids[0] and cover_id == cover_ids[0]),
                    warmup_state=warmup_state,
                )
                row["pair_id"] = pair_id
                condition_results.append(row)

    # A single baseline per cover avoids treating a repeated cover as an independent control.
    controls: list[dict[str, Any]] = []
    for cover_id in cover_ids:
        path = cover_by_id[cover_id]
        with Image.open(path) as image:
            pixels = np.asarray(image, dtype=np.uint8).copy()
        controls.append(
            {
                "cover_id": cover_id,
                "cover_sha256": _sha256(path.read_bytes()),
                "chi_square": analyze_chi_square(pixels),
                "rs_cover_baseline": analyze_rs(pixels, pixels.copy(), 0),
            }
        )

    scenario_rows = {
        "S1": [
            {key: row[key] for key in ("pair_id", "payload_id", "cover_id", "mode", "source", "stego", "integrity", "payload_crypto")}
            for row in condition_results
        ],
        "S2": [
            {"pair_id": row["pair_id"], "payload_id": row["payload_id"], "cover_id": row["cover_id"], "mode": row["mode"], **row["quality"]}
            for row in condition_results
        ],
        "S3": [
            {"pair_id": row["pair_id"], "mode": row["mode"], **row["security_scenarios"]["wrong_passphrase"]}
            for row in condition_results if row["security_scenarios"] is not None
        ],
        "S4": [
            {"pair_id": row["pair_id"], "mode": row["mode"], **case}
            for row in condition_results if row["security_scenarios"] is not None
            for case in row["security_scenarios"]["tampering"]
        ],
        "S5": condition_results,
    }
    for scenario, rows in scenario_rows.items():
        _json_new(run_root / scenario / "results.json", rows)
    _json_new(run_root / "cover_controls" / "baseline_results.json", controls)
    summary = _summaries(condition_results, pilot=pilot)
    _json_new(summary_dir / "paired_statistics.json", summary)
    _write_csv_new(
        summary_dir / "quality_metrics.csv",
        [
            {"pair_id": row["pair_id"], "payload_id": row["payload_id"], "cover_id": row["cover_id"], "mode": row["mode"], **row["quality"]}
            for row in condition_results
        ],
    )
    _write_csv_new(
        summary_dir / "timing_metrics.csv",
        _timing_csv_rows(condition_results),
    )
    _write_csv_new(
        summary_dir / "integrity_results.csv",
        [
            {"pair_id": row["pair_id"], "payload_id": row["payload_id"], "cover_id": row["cover_id"], "mode": row["mode"], **row["integrity"]}
            for row in condition_results
        ],
    )
    _write_csv_new(
        summary_dir / "chi_square_results.csv",
        _chi_csv_rows(condition_results, controls),
    )
    _write_csv_new(
        summary_dir / "rs_analysis_results.csv",
        _rs_csv_rows(condition_results, controls),
    )
    run_report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_type": "pilot" if pilot else "formal",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_fingerprint": manifest["privacy_review"]["dataset_fingerprint"],
        "dataset_manifest_sha256": _sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")),
        "pilot_report_sha256": (
            _sha256(json.dumps(pilot_report, sort_keys=True).encode("utf-8"))
            if pilot_report is not None
            else None
        ),
        "formal_experiment": not pilot,
        "condition_count": len({row["pair_id"] for row in condition_results}),
        "method_result_count": len(condition_results),
        "method_count": len(METHODS),
        "warmup_per_method": 1,
        "timed_repetitions_per_condition_method": REPETITIONS,
        "results_path": run_root.relative_to(experiment_data_dir).as_posix(),
        "summary_path": summary_dir.relative_to(experiment_data_dir).as_posix(),
        "passphrase_or_secret_material_recorded": False,
        "software": _versions(),
        "integrity_all_passed": all(row["integrity"]["all_repetitions_match"] for row in condition_results),
        "quality_all_finite": all(
            math_is_finite(row["quality"]["mse"]) and math_is_finite(row["quality"]["ssim"])
            for row in condition_results
        ),
        "security_checks": [case for row in condition_results if row["security_scenarios"] for case in [row["security_scenarios"]["wrong_passphrase"], *row["security_scenarios"]["tampering"]]],
        "security_checks_all_rejected": all(
            case["status"] == "rejected"
            for row in condition_results if row["security_scenarios"]
            for case in [row["security_scenarios"]["wrong_passphrase"], *row["security_scenarios"]["tampering"]]
        ),
    }
    report_dir = experiment_data_dir / "reports"
    _json_new(report_dir / f"{run_id}.json", run_report)
    return run_report


def math_is_finite(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and bool(np.isfinite(value))


def _summaries(rows: list[dict[str, Any]], *, pilot: bool) -> dict[str, Any]:
    from backend.experiments.statistics import holm_adjust, paired_wilcoxon_summary

    by_pair = {row["pair_id"]: {} for row in rows}
    for row in rows:
        by_pair[row["pair_id"]][row["mode"]] = row
    if pilot:
        return {
            "status": "not_run_pilot_has_one_condition",
            "wilcoxon": None,
            "confidence_intervals": None,
            "interpretation": "Pilot memverifikasi alur saja; tidak cukup untuk inferensi berpasangan.",
        }
    fields = (
        "mse_relative_difference",
        "psnr_difference_db",
        "ssim_difference",
        "embedding_mean_difference_ms",
        "extraction_mean_difference_ms",
        "chi_detection_difference",
        "rs_relative_error_difference",
    )
    pair_vectors: dict[str, tuple[list[float], list[float]]] = {
        name: ([], []) for name in fields
    }
    for pair_id in sorted(by_pair):
        pair = by_pair[pair_id]
        if set(pair) != set(METHODS):
            continue
        seq, rnd = pair["sequential"], pair["randomized"]
        observations: dict[str, tuple[float | None, float | None]] = {
            "mse_relative_difference": (
                0.0 if seq["quality"]["mse"] == 0 else 0.0,
                None if seq["quality"]["mse"] == 0 else rnd["quality"]["mse"] / seq["quality"]["mse"] - 1.0,
            ),
            "psnr_difference_db": (seq["quality"]["psnr_db"], rnd["quality"]["psnr_db"]),
            "ssim_difference": (seq["quality"]["ssim"], rnd["quality"]["ssim"]),
            "embedding_mean_difference_ms": (seq["timing"]["embedding_mean_ms"], rnd["timing"]["embedding_mean_ms"]),
            "extraction_mean_difference_ms": (seq["timing"]["extraction_mean_ms"], rnd["timing"]["extraction_mean_ms"]),
            "chi_detection_difference": (
                None if seq["chi_square"]["stego"]["possible_embedding_indicator"] is None else float(seq["chi_square"]["stego"]["possible_embedding_indicator"]),
                None if rnd["chi_square"]["stego"]["possible_embedding_indicator"] is None else float(rnd["chi_square"]["stego"]["possible_embedding_indicator"]),
            ),
            "rs_relative_error_difference": (
                seq["rs_analysis"]["relative_error"], rnd["rs_analysis"]["relative_error"]
            ),
        }
        for name, (left_value, right_value) in observations.items():
            if left_value is not None and right_value is not None:
                pair_vectors[name][0].append(float(left_value))
                pair_vectors[name][1].append(float(right_value))

    results: dict[str, Any] = {}
    p_values: list[float | None] = []
    for name in fields:
        left_values, right_values = pair_vectors[name]
        if len(left_values) < 2:
            result = {"status": "insufficient_pairs", "n_pairs": len(left_values), "p_value": None}
        else:
            result = paired_wilcoxon_summary(left_values, right_values)
        results[name] = result
        p_values.append(result.get("p_value"))
    adjusted = holm_adjust(p_values)
    for name, p_adjusted in zip(fields, adjusted):
        results[name]["holm_adjusted_p_value"] = p_adjusted

    h1_margins = {
        "mse_relative_difference": 0.05,
        "psnr_difference_db": 0.23,
        "ssim_difference": 0.005,
    }
    h1_checks = {}
    for name, margin in h1_margins.items():
        result = results[name]
        low = result.get("ci95_mean_difference_low")
        high = result.get("ci95_mean_difference_high")
        h1_checks[name] = bool(
            low is not None and high is not None and low >= -margin and high <= margin
        )
    return {
        "status": "computed",
        "alpha": 0.05,
        "wilcoxon": results,
        "multiple_comparison_method": "Holm step-down over 7 metric/detector families",
        "h1_equivalence": {
            "margins": h1_margins,
            "metric_ci_checks": h1_checks,
            "equivalence_supported": all(h1_checks.values()),
            "interpretation": "Tidak mendukung kesetaraan bila satu atau lebih CI 95% tidak seluruhnya berada di dalam marginnya.",
        },
        "h2_direction": "Nilai mean_paired_difference negatif pada chi_detection_difference berarti proporsi indikator Randomized lebih rendah dalam kondisi berpasangan.",
        "unit_of_analysis": "30 payload-cover paired conditions; five timing repetitions first summarized as mean and sample SD per condition",
        "confidence_interval": "Deterministic 20,000-resample percentile bootstrap over paired conditions; report is not a population claim beyond fixed dataset.",
        "generalization_limit": "Three fixed cover images and ten fixed payloads; interpret as paired case study only.",
    }


def _timing_csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen_encryption: set[str] = set()
    for row in rows:
        payload_id = row["payload_id"]
        if payload_id not in seen_encryption:
            for repetition, value in enumerate(row["timing"]["encryption_ms_per_payload_repetition"], 1):
                output.append({"pair_id": None, "payload_id": payload_id, "cover_id": None, "mode": "shared_crypto_prep", "phase": "encryption_total_including_kdf", "repetition": repetition, "duration_ms": value})
            enc = row["timing"]["encryption_ms_per_payload_repetition"]
            output.append({"pair_id": None, "payload_id": payload_id, "cover_id": None, "mode": "shared_crypto_prep", "phase": "encryption_total_including_kdf", "repetition": "summary", "duration_ms": float(np.mean(enc)), "sd_ms": float(np.std(enc, ddof=1))})
            seen_encryption.add(payload_id)
        for phase, key in (("embedding", "embedding_repetitions"), ("extraction", "extraction_repetitions")):
            for repetition in row["timing"][key]:
                for metric, value in repetition.items():
                    if metric != "repetition":
                        output.append({"pair_id": row["pair_id"], "payload_id": payload_id, "cover_id": row["cover_id"], "mode": row["mode"], "phase": metric, "repetition": repetition["repetition"], "duration_ms": value})
            for metric in [key for key in row["timing"][key][0] if key != "repetition"]:
                values = [repetition[metric] for repetition in row["timing"][key]]
                output.append({"pair_id": row["pair_id"], "payload_id": payload_id, "cover_id": row["cover_id"], "mode": row["mode"], "phase": metric, "repetition": "summary", "duration_ms": float(np.mean(values)), "sd_ms": float(np.std(values, ddof=1))})
    return output


def _chi_csv_rows(rows: list[dict[str, Any]], controls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for control in controls:
        for test in control["chi_square"]["tests"]:
            output.append({"scope": "cover_control", "pair_id": None, "payload_id": None, "cover_id": control["cover_id"], "mode": None, **test})
    for row in rows:
        for test in row["chi_square"]["stego"]["tests"]:
            output.append({"scope": "stego", "pair_id": row["pair_id"], "payload_id": row["payload_id"], "cover_id": row["cover_id"], "mode": row["mode"], **test})
    return output


def _rs_csv_rows(rows: list[dict[str, Any]], controls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for control in controls:
        for channel, estimate in control["rs_cover_baseline"]["channels"].items():
            output.append({"scope": "cover_control", "pair_id": None, "payload_id": None, "cover_id": control["cover_id"], "mode": None, "channel": channel, **estimate})
    for row in rows:
        for channel, estimate in row["rs_analysis"]["channels"].items():
            output.append({"scope": "stego", "pair_id": row["pair_id"], "payload_id": row["payload_id"], "cover_id": row["cover_id"], "mode": row["mode"], **estimate})
    return output
