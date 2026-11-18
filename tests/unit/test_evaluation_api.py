import base64
import hashlib
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app

client = TestClient(app)


def _file(name: str, data: bytes) -> dict[str, str]:
    return {"name": name, "data": base64.b64encode(data).decode("ascii")}


def _pdf() -> bytes:
    return b"%PDF-1.7\nevaluation fixture\n%%EOF\n"


def _png(mode: str = "RGB") -> bytes:
    image = Image.new(mode, (96, 80), (40, 80, 120) if mode == "RGB" else (40, 80, 120, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("mode", ["sequential", "randomized"])
def test_evaluation_api_runs_real_pair_and_returns_metrics_and_timings(mode: str) -> None:
    pdf = _pdf()
    response = client.post(
        "/api/evaluate",
        json={
            "pdf": _file("source.pdf", pdf),
            "cover": _file("cover.png", _png()),
            "passphrase": "correct horse battery staple",
            "mode": mode,
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["mode"] == mode
    assert (result["width"], result["height"]) == (96, 80)
    assert result["source_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert result["recovered_sha256"] == result["source_sha256"]
    assert result["recovery_matches"] is True
    assert result["metrics"]["mse"]["value"] > 0
    assert result["metrics"]["mse"]["unit"] == "pixel_value^2"
    assert result["metrics"]["psnr"]["status"] == "finite"
    assert result["metrics"]["psnr"]["unit"] == "dB"
    assert result["metrics"]["ssim"]["value"] is not None
    assert result["scikit_image_version"] == "0.26.0"
    assert result["unavailable_metrics"] == {}
    assert result["chi_square"]["cover"]["family_size"] == 300
    assert result["chi_square"]["stego"]["family_size"] == 300
    assert set(result["rs_analysis"]["channels"]) == {"red", "green", "blue"}
    assert result["rs_analysis"]["actual_embedded_bits"] == 8 * (32 + len(pdf) + 16)

    timings = result["timings"]
    assert timings["evaluation_total_ms"] >= timings["embedding_total_ms"]
    assert timings["evaluation_total_ms"] >= timings["extraction_total_ms"]
    if mode == "randomized":
        assert timings["embedding_permutation_ms"] >= 0
        assert timings["extraction_permutation_ms"] >= 0
        assert timings["embedding_lsb_ms"] >= 0
        assert timings["extraction_lsb_ms"] >= 0
    else:
        assert timings["embedding_permutation_ms"] is None
        assert timings["extraction_permutation_ms"] is None


@pytest.mark.parametrize("cover", [b"", b"not PNG", _png("RGBA")])
def test_evaluation_api_rejects_invalid_cover(cover: bytes) -> None:
    response = client.post(
        "/api/evaluation",
        json={
            "pdf": _file("source.pdf", _pdf()),
            "cover": _file("cover.png", cover or b" "),
            "passphrase": "correct horse battery staple",
            "mode": "sequential",
        },
    )

    assert response.status_code == 422
    assert "metrics" not in response.json()


def test_evaluation_api_rejects_unknown_mode() -> None:
    response = client.post(
        "/api/evaluate",
        json={
            "pdf": _file("source.pdf", _pdf()),
            "cover": _file("cover.png", _png()),
            "passphrase": "correct horse battery staple",
            "mode": "unknown",
        },
    )

    assert response.status_code == 422


def test_evaluation_api_rejects_images_too_small_for_ssim_window() -> None:
    small = Image.new("RGB", (30, 10), (40, 80, 120))
    output = BytesIO()
    small.save(output, format="PNG")
    response = client.post(
        "/api/evaluate",
        json={
            "pdf": _file("source.pdf", b"%PDF-1.7\n%%EOF\n"),
            "cover": _file("cover.png", output.getvalue()),
            "passphrase": "correct horse battery staple",
            "mode": "sequential",
        },
    )

    assert response.status_code == 422
    assert "11×11" in response.json()["detail"]
