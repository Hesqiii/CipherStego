from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.dataset_creation.generate_pdfs import (
    DEFAULT_REPORT,
    SPECS,
    _build_pdf,
    generate_dataset,
    validate_pdf,
)


def test_generator_creates_valid_dataset_with_manual_privacy_review(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "dataset" / "pdf"
    report_path = tmp_path / "reports" / "pdf_generation_report.json"

    report = generate_dataset(pdf_dir, report_path)

    assert [row["sample_id"] for row in report["outputs"]] == [spec.sample_id for spec in SPECS]
    assert len(list(pdf_dir.glob("*.pdf"))) == 10
    assert report["privacy_review"]["status"] == "manual_review_required"
    for spec, row in zip(SPECS, report["outputs"], strict=True):
        path = pdf_dir / f"{spec.sample_id}.pdf"
        assert 10 * 1024 <= path.stat().st_size <= 600 * 1024
        assert row["size_bytes"] == path.stat().st_size
        assert row["size_kib"] == round(path.stat().st_size / 1024, 3)
        assert row["page_count"] == spec.pages
        assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert row["privacy_review"] == "manual_review_required"
        assert validate_pdf(path, spec.pages)["status"] == "valid"


def test_generation_is_reproducible_for_fixed_seed(tmp_path: Path) -> None:
    spec = SPECS[3]
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"

    _build_pdf(first, spec, 20261118)
    _build_pdf(second, spec, 20261118)

    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()


def test_existing_outputs_are_not_overwritten_without_force(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    sentinel = pdf_dir / "P01.pdf"
    sentinel.write_bytes(b"keep existing")
    report_path = tmp_path / "report.json"

    with pytest.raises(FileExistsError, match="tidak ditimpa"):
        generate_dataset(pdf_dir, report_path)

    assert sentinel.read_bytes() == b"keep existing"
    assert not report_path.exists()


def test_force_replaces_only_named_dataset_outputs(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    sentinel = pdf_dir / "P01.pdf"
    other = pdf_dir / "notes.txt"
    sentinel.write_bytes(b"old pdf")
    other.write_text("keep", encoding="utf-8")
    report_path = tmp_path / "report.json"

    generate_dataset(pdf_dir, report_path, force=True)

    assert sentinel.read_bytes().startswith(b"%PDF-")
    assert other.read_text(encoding="utf-8") == "keep"
    assert report_path.is_file()


def test_invalid_pdf_is_rejected(tmp_path: Path) -> None:
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a pdf")

    with pytest.raises(ValueError, match="Struktur dasar PDF"):
        validate_pdf(bad_pdf, 1)

