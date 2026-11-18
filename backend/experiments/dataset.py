"""Dataset preflight and non-destructive manifest creation."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

PDF_IDS = tuple(f"P{i:02d}" for i in range(1, 11))
COVER_IDS = ("C1", "C2", "C3")
MIN_PDF_BYTES = 10 * 1024
MAX_PDF_BYTES = 600 * 1024
EXPECTED_COVER_SIZE = (1920, 1080)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matching_file(directory: Path, code: str, suffix: str) -> tuple[Path | None, str | None]:
    if not directory.is_dir():
        return None, f"Folder dataset tidak ditemukan: {directory.as_posix()}"
    pattern = re.compile(rf"^{re.escape(code)}(?:$|[ _.-])", re.IGNORECASE)
    matches = sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == suffix and pattern.match(path.stem)
    )
    if not matches:
        return None, f"Berkas dengan kode {code} belum tersedia."
    if len(matches) > 1:
        return None, f"Ada {len(matches)} berkas yang memakai kode {code}; harus tepat satu."
    return matches[0], None


def _pdf_record(code: str, directory: Path) -> dict[str, Any]:
    path, lookup_error = _matching_file(directory, code, ".pdf")
    record: dict[str, Any] = {
        "sample_id": code,
        "filename": path.name if path else None,
        "sha256": None,
        "size_bytes": None,
        "dimensions": None,
        "color_mode": None,
        "privacy_review": "manual_review_required",
        "status": "missing" if path is None else "invalid",
        "reason": lookup_error,
    }
    if path is None:
        return record
    data = path.read_bytes()
    record["size_bytes"] = len(data)
    record["sha256"] = sha256_file(path)
    issues: list[str] = []
    if not data.startswith(b"%PDF-"):
        issues.append("Signature PDF tidak valid.")
    if b"%%EOF" not in data[-4096:]:
        issues.append("Penanda akhir PDF %%EOF tidak ditemukan pada 4 KiB terakhir.")
    if not MIN_PDF_BYTES <= len(data) <= MAX_PDF_BYTES:
        issues.append(f"Ukuran harus 10–600 KiB; aktual {len(data)} byte.")
    if issues:
        record["reason"] = " ".join(issues)
    else:
        record["status"] = "valid_format_privacy_unreviewed"
        record["reason"] = "Format valid; sensitivitas isi harus disahkan secara manual."
    return record


def _cover_record(code: str, directory: Path) -> dict[str, Any]:
    path, lookup_error = _matching_file(directory, code, ".png")
    record: dict[str, Any] = {
        "sample_id": code,
        "filename": path.name if path else None,
        "sha256": None,
        "size_bytes": None,
        "dimensions": None,
        "color_mode": None,
        "status": "missing" if path is None else "invalid",
        "reason": lookup_error,
    }
    if path is None:
        return record
    data = path.read_bytes()
    record["size_bytes"] = len(data)
    record["sha256"] = sha256_file(path)
    issues: list[str] = []
    if len(data) < 29 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        issues.append("Signature/struktur IHDR PNG tidak valid.")
    else:
        record["dimensions"] = [int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")]
        bit_depth, color_type = data[24], data[25]
        try:
            with Image.open(path) as image:
                record["color_mode"] = image.mode
                image.verify()
        except (OSError, SyntaxError, UnidentifiedImageError) as exc:
            issues.append(f"PNG tidak dapat dibaca: {type(exc).__name__}.")
        if bit_depth != 8 or color_type != 2:
            issues.append(f"Harus PNG RGB 24-bit (8-bit/channel, color type 2); aktual depth={bit_depth}, type={color_type}.")
        if record["dimensions"] != list(EXPECTED_COVER_SIZE):
            issues.append(f"Resolusi harus 1920×1080; aktual {record['dimensions']}.")
        if record["color_mode"] != "RGB":
            issues.append(f"Mode warna harus RGB; aktual {record['color_mode']}.")
    if issues:
        record["reason"] = " ".join(issues)
    else:
        record["status"] = "valid"
        record["reason"] = None
    return record


def build_dataset_manifest(dataset_dir: Path) -> dict[str, Any]:
    """Inspect expected P01–P10 and C1–C3 without changing source files."""
    dataset_dir = dataset_dir.resolve()
    pdf_dir = dataset_dir / "pdf"
    cover_dir = dataset_dir / "cover_images"
    payloads = [_pdf_record(code, pdf_dir) for code in PDF_IDS]
    covers = [_cover_record(code, cover_dir) for code in COVER_IDS]
    valid_files = all(item["status"] == "valid_format_privacy_unreviewed" for item in payloads) and all(
        item["status"] == "valid" for item in covers
    )
    dataset_fingerprint = hashlib.sha256(
        json.dumps(
            [(item["sample_id"], item["sha256"]) for item in payloads + covers],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    privacy_reviewed = False
    privacy_review_path = dataset_dir / "privacy_review.json"
    if privacy_review_path.is_file():
        try:
            privacy_review = json.loads(privacy_review_path.read_text(encoding="utf-8"))
            privacy_reviewed = (
                privacy_review.get("reviewed") is True
                and privacy_review.get("dataset_fingerprint") == dataset_fingerprint
            )
        except (OSError, json.JSONDecodeError, AttributeError):
            privacy_reviewed = False
    if privacy_reviewed:
        for item in payloads:
            if item["status"] == "valid_format_privacy_unreviewed":
                item["status"] = "valid"
                item["reason"] = None
    unassigned = _unassigned_files(pdf_dir, cover_dir)
    excluded_fixtures = _known_workspace_fixtures(dataset_dir.parent.parent)
    ready = valid_files and privacy_reviewed and not unassigned
    return {
        "manifest_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root": dataset_dir.name,
        "requirements": {
            "payloads": {"count": 10, "min_bytes": MIN_PDF_BYTES, "max_bytes": MAX_PDF_BYTES},
            "covers": {"count": 3, "format": "PNG RGB 24-bit", "dimensions": list(EXPECTED_COVER_SIZE)},
        },
        "privacy_review": {
            "status": "reviewed" if privacy_reviewed else "required_manual_attestation",
            "review_file": "privacy_review.json",
            "dataset_fingerprint": dataset_fingerprint,
            "note": "Automated checks cannot establish that PDF contents contain no personal or sensitive data.",
        },
        "dataset_format_valid": valid_files and not unassigned,
        "ready_for_pilot": ready,
        "payloads": payloads,
        "covers": covers,
        "missing_payload_ids": [item["sample_id"] for item in payloads if item["status"] == "missing"],
        "invalid_payload_ids": [item["sample_id"] for item in payloads if item["status"] not in {"valid_format_privacy_unreviewed", "missing"}],
        "missing_cover_ids": [item["sample_id"] for item in covers if item["status"] == "missing"],
        "invalid_cover_ids": [item["sample_id"] for item in covers if item["status"] not in {"valid", "missing"}],
        "unassigned_files": unassigned,
        "excluded_non_dataset_files": excluded_fixtures,
    }


def _known_workspace_fixtures(project_root: Path) -> list[dict[str, Any]]:
    """Record the known M6 test artifacts without treating them as study data."""
    folder = project_root / ".m6-test-artifacts"
    records: list[dict[str, Any]] = []
    if not folder.is_dir():
        return records
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".png"}:
            continue
        record: dict[str, Any] = {
            "filename": path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "dimensions": None,
            "color_mode": None,
            "status": "excluded_test_fixture",
            "reason": "Artefak pengujian milestone lama; bukan sampel penelitian terdaftar.",
        }
        if path.suffix.lower() == ".png":
            try:
                with Image.open(path) as image:
                    record["dimensions"] = [image.width, image.height]
                    record["color_mode"] = image.mode
                if record["dimensions"] != list(EXPECTED_COVER_SIZE):
                    record["reason"] += " Resolusi tidak sesuai spesifikasi cover 1920×1080."
            except (OSError, SyntaxError, UnidentifiedImageError):
                record["reason"] += " Format gambar tidak valid."
        elif record["size_bytes"] < MIN_PDF_BYTES:
            record["reason"] += " Ukuran PDF di bawah batas 10 KiB."
        records.append(record)
    return records


def _unassigned_files(pdf_dir: Path, cover_dir: Path) -> list[str]:
    found: list[str] = []
    for directory, suffix, assigned in (
        (pdf_dir, ".pdf", PDF_IDS),
        (cover_dir, ".png", COVER_IDS),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() != suffix:
                continue
            if not any(re.match(rf"^{re.escape(code)}(?:$|[ _.-])", path.stem, re.IGNORECASE) for code in assigned):
                found.append(path.name)
    return found


def write_manifest(manifest: dict[str, Any], target: Path, *, replace: bool = False) -> None:
    """Write a manifest without replacing an older audit by default."""
    if target.exists() and not replace:
        raise FileExistsError(f"Manifest sudah ada; tidak ditimpa: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if replace:
        target.write_text(data, encoding="utf-8")
        return
    with target.open("x", encoding="utf-8", newline="\n") as output:
        output.write(data)
