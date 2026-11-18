"""Command-line preflight, single-pair pilot, and gated formal experiment runner."""

from __future__ import annotations

import argparse
from getpass import getpass
import json
import sys
from pathlib import Path
from typing import Any

from backend.experiments.dataset import build_dataset_manifest, write_manifest
from backend.experiments.engine import DatasetNotReadyError, run_matrix

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPERIMENT_DIR = PROJECT_ROOT / "experiment_data"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Tidak dapat membaca JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Dokumen JSON harus berupa object: {path}")
    return value


def _current_manifest(experiment_dir: Path, manifest_path: Path) -> dict[str, Any]:
    saved = _read_json(manifest_path)
    current = build_dataset_manifest(experiment_dir / "dataset")
    if current["privacy_review"]["dataset_fingerprint"] != saved.get("privacy_review", {}).get("dataset_fingerprint"):
        raise DatasetNotReadyError("Hash dataset berubah sejak manifest; jalankan preflight ulang dan tinjau privasi lagi.")
    if not current["ready_for_pilot"]:
        raise DatasetNotReadyError("Dataset belum siap: lengkapi P01–P10, C1–C3, format, dan privacy review.")
    if saved.get("ready_for_pilot") is not True:
        raise DatasetNotReadyError("Manifest tersimpan belum menyatakan dataset siap; jalankan preflight --replace-manifest.")
    return current


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cipherstego-experiment")
    parser.add_argument("--experiment-dir", type=Path, default=DEFAULT_EXPERIMENT_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight", help="Audit dataset dan tulis manifest tanpa menjalankan eksperimen.")
    preflight.add_argument("--replace-manifest", action="store_true", help="Ganti manifest lama secara eksplisit.")
    pilot = subparsers.add_parser("pilot", help="Jalankan satu pasangan P01/C1 dengan kedua metode.")
    pilot.add_argument("--manifest", type=Path)
    formal = subparsers.add_parser("run", help="Jalankan matriks formal setelah pilot ditinjau.")
    formal.add_argument("--manifest", type=Path)
    formal.add_argument("--pilot-report", type=Path, required=True)
    formal.add_argument("--confirm-formal-run", action="store_true", help="Konfirmasi eksplisit menjalankan matriks penuh.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    experiment_dir = args.experiment_dir.resolve()
    dataset_dir = experiment_dir / "dataset"
    default_manifest = experiment_dir / "dataset_manifest.json"
    if args.command == "preflight":
        manifest = build_dataset_manifest(dataset_dir)
        try:
            write_manifest(manifest, default_manifest, replace=args.replace_manifest)
        except FileExistsError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps({
            "manifest": default_manifest.as_posix(),
            "dataset_format_valid": manifest["dataset_format_valid"],
            "ready_for_pilot": manifest["ready_for_pilot"],
            "missing_payload_ids": manifest["missing_payload_ids"],
            "missing_cover_ids": manifest["missing_cover_ids"],
            "invalid_payload_ids": manifest["invalid_payload_ids"],
            "invalid_cover_ids": manifest["invalid_cover_ids"],
            "privacy_review": manifest["privacy_review"]["status"],
        }, ensure_ascii=False, indent=2))
        return 0 if manifest["ready_for_pilot"] else 2

    manifest_path = (args.manifest or default_manifest).resolve()
    try:
        manifest = _current_manifest(experiment_dir, manifest_path)
    except (ValueError, DatasetNotReadyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.command == "pilot":
        passphrase = getpass("Passphrase eksperimen (tidak disimpan): ")
        if not passphrase:
            print("Passphrase tidak boleh kosong.", file=sys.stderr)
            return 2
        report = run_matrix(
            manifest=manifest,
            dataset_dir=dataset_dir,
            experiment_data_dir=experiment_dir,
            passphrase=passphrase,
            pilot=True,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["integrity_all_passed"] and report["security_checks_all_rejected"] else 1

    if not args.confirm_formal_run:
        print("Matriks formal memerlukan --confirm-formal-run setelah hasil pilot ditinjau.", file=sys.stderr)
        return 2
    try:
        pilot_report = _read_json(args.pilot_report.resolve())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if (
        pilot_report.get("run_type") != "pilot"
        or pilot_report.get("dataset_fingerprint") != manifest["privacy_review"]["dataset_fingerprint"]
        or pilot_report.get("integrity_all_passed") is not True
        or pilot_report.get("quality_all_finite") is not True
        or pilot_report.get("security_checks_all_rejected") is not True
    ):
        print("Pilot report tidak lulus atau tidak merujuk ke dataset yang sama.", file=sys.stderr)
        return 2
    passphrase = getpass("Passphrase eksperimen yang sama dengan pilot (tidak disimpan): ")
    if not passphrase:
        print("Passphrase tidak boleh kosong.", file=sys.stderr)
        return 2
    report = run_matrix(
        manifest=manifest,
        dataset_dir=dataset_dir,
        experiment_data_dir=experiment_dir,
        passphrase=passphrase,
        pilot=False,
        pilot_report=pilot_report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["integrity_all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
