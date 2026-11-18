import json

from PIL import Image

from backend.experiments.dataset import build_dataset_manifest, write_manifest
import pytest


def test_empty_dataset_reports_every_proposal_code_missing(tmp_path) -> None:
    (tmp_path / "pdf").mkdir()
    (tmp_path / "cover_images").mkdir()

    result = build_dataset_manifest(tmp_path)

    assert result["dataset_format_valid"] is False
    assert result["ready_for_pilot"] is False
    assert result["missing_payload_ids"] == [f"P{i:02d}" for i in range(1, 11)]
    assert result["missing_cover_ids"] == ["C1", "C2", "C3"]


def test_manifest_write_does_not_replace_an_existing_audit_by_default(tmp_path) -> None:
    target = tmp_path / "dataset_manifest.json"
    target.write_text('{"old":true}\n', encoding="utf-8")

    with pytest.raises(FileExistsError, match="tidak ditimpa"):
        write_manifest({"new": True}, target)

    assert target.read_text(encoding="utf-8") == '{"old":true}\n'


def test_preflight_validates_formats_and_requires_fingerprint_bound_privacy_review(tmp_path) -> None:
    pdf_dir = tmp_path / "pdf"
    cover_dir = tmp_path / "cover_images"
    pdf_dir.mkdir(parents=True)
    cover_dir.mkdir(parents=True)
    for index in range(1, 11):
        (pdf_dir / f"P{index:02d}.pdf").write_bytes(
            b"%PDF-1.7\n" + bytes([index]) * (10 * 1024 - 14) + b"%%EOF"
        )
    for code in ("C1", "C2", "C3"):
        Image.new("RGB", (1920, 1080), (30, 60, 90)).save(cover_dir / f"{code}.png", format="PNG")

    initial = build_dataset_manifest(tmp_path)
    assert initial["dataset_format_valid"] is True
    assert initial["ready_for_pilot"] is False
    assert all(row["status"] == "valid_format_privacy_unreviewed" for row in initial["payloads"])

    (tmp_path / "privacy_review.json").write_text(
        json.dumps({"reviewed": True, "dataset_fingerprint": initial["privacy_review"]["dataset_fingerprint"]}),
        encoding="utf-8",
    )
    reviewed = build_dataset_manifest(tmp_path)
    assert reviewed["ready_for_pilot"] is True
    assert all(row["status"] == "valid" for row in reviewed["payloads"])
