# Synthetic PDF payload generator

This tool creates the ten fictional PDF payloads from the proposal. It uses a fixed seed (`20261118`) and deterministic PDF metadata. The PDFs contain generated Indonesian text, tables, vector graphs, small illustrations, or low-resolution synthetic scan pages. No real people, identity numbers, private addresses, or real organizations are used.

## Install and run

From the project root, install the generator dependencies into the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r tools\dataset_creation\requirements.txt
.\.venv\Scripts\python.exe tools\dataset_creation\generate_pdfs.py
```

By default, the generator writes only `P01.pdf` through `P10.pdf` to `experiment_data\dataset\pdf\`. A size and validation report is written to `experiment_data\reports\pdf_generation_report.json`.

Existing target PDFs or the report cause the generator to stop. Use `--force` only when intentionally replacing those named outputs. Use `--output-dir`, `--report`, and `--seed` to select another output location, report path, or content seed.

The report records actual byte and KiB sizes, page counts, characteristics, SHA-256 digests, and basic PDF validation. It always marks privacy review as `manual_review_required`. A person must inspect every generated document before creating or refreshing the dataset manifest and privacy attestation. This script does not run preflight, pilot, or research experiments.
