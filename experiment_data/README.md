# Dataset and results

Place the ten proposal PDFs in `dataset/pdf/` using filename prefixes `P01` through `P10`. Place the three proposal PNGs in `dataset/cover_images/` using prefixes `C1` through `C3`. The preflight checks PDF signatures and 10–600 KiB sizes, and checks PNG signature, RGB 24-bit IHDR, RGB mode, and 1920×1080 resolution.

The team must manually inspect every PDF and confirm that it contains no personal or sensitive data. After preflight creates `dataset_manifest.json`, create `dataset/privacy_review.json` with this structure and the exact `dataset_fingerprint` from the manifest:

```json
{
  "reviewed": true,
  "dataset_fingerprint": "paste-the-fingerprint-from-dataset_manifest.json"
}
```

This attestation is tied to file hashes. Replacing any input requires a new preflight and a new privacy review. The runner never creates substitute samples and never overwrites prior run folders.
