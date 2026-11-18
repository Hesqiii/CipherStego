"""End-to-end API checks for the local Sequential LSB vertical slice."""

import base64
import hashlib
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app

client = TestClient(app)


def make_pdf(payload: bytes = b"demo") -> bytes:
    return b"%PDF-1.7\n" + payload + b"\n%%EOF\n"


def make_png(size: tuple[int, int] = (160, 120), color=(37, 82, 119), mode="RGB") -> bytes:
    output = BytesIO()
    Image.new(mode, size, color).save(output, format="PNG")
    return output.getvalue()


def file_json(name: str, data: bytes) -> dict[str, str]:
    return {"name": name, "data": base64.b64encode(data).decode("ascii")}


def embed(pdf: bytes, cover: bytes, *, passphrase="correct horse battery staple", mode="sequential"):
    return client.post(
        "/api/embed",
        json={
            "pdf": file_json("../../private source.pdf", pdf),
            "cover": file_json("cover.png", cover),
            "passphrase": passphrase,
            "mode": mode,
        },
    )


def test_sender_and_receiver_round_trip_returns_original_pdf_only_after_authentication() -> None:
    original = make_pdf(b"known sample payload")
    response = embed(original, make_png())

    assert response.status_code == 200, response.text
    embedded = response.json()
    assert embedded["filename"] == "stego_private_source.png"
    assert embedded["metadata"]["mode"] == "sequential"
    assert embedded["metadata"]["source_bytes"] == len(original)
    assert embedded["metadata"]["ciphertext_bytes"] == len(original) + 16
    assert embedded["metadata"]["source_sha256"] == hashlib.sha256(original).hexdigest()

    stego = base64.b64decode(embedded["png_base64"], validate=True)
    with Image.open(BytesIO(stego)) as image:
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert image.size == (160, 120)

    recovered = client.post(
        "/api/extract",
        json={
            "stego": file_json(embedded["filename"], stego),
            "passphrase": "correct horse battery staple",
            "mode": "sequential",
        },
    )
    assert recovered.status_code == 200, recovered.text
    result = recovered.json()
    assert result["authenticated"] is True
    assert base64.b64decode(result["pdf_base64"], validate=True) == original
    assert result["metadata"]["sha256"] == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize("size", [1, 32, 511, 4096])
def test_api_round_trip_handles_several_pdf_payload_sizes(size: int) -> None:
    original = make_pdf(bytes((index * 37) % 256 for index in range(size)))
    response = embed(original, make_png((400, 300)))
    assert response.status_code == 200, response.text

    embedded = response.json()
    stego = base64.b64decode(embedded["png_base64"], validate=True)
    recovered = client.post(
        "/api/extract",
        json={
            "stego": file_json("stego.png", stego),
            "passphrase": "correct horse battery staple",
        },
    )
    assert recovered.status_code == 200, recovered.text
    assert base64.b64decode(recovered.json()["pdf_base64"], validate=True) == original


def test_sender_rejects_invalid_pdf_and_non_rgb_png() -> None:
    assert embed(b"not a PDF", make_png()).status_code == 422
    assert embed(make_pdf(), make_png(mode="RGBA", color=(37, 82, 119, 255))).status_code == 422


def test_sender_rejects_pdf_that_exceeds_png_capacity() -> None:
    response = embed(make_pdf(b"x" * 2048), make_png((24, 24)))
    assert response.status_code == 422
    assert "tidak muat" in response.json()["detail"]


def test_sender_rejects_files_over_the_documented_size_limit() -> None:
    response = embed(make_pdf(b"x" * (600 * 1024)), make_png())
    assert response.status_code == 413


@pytest.mark.parametrize("mode", ["sequential", "randomized"])
def test_receiver_does_not_return_plaintext_for_wrong_passphrase(mode: str) -> None:
    response = embed(make_pdf(), make_png(), mode=mode)
    stego = base64.b64decode(response.json()["png_base64"])
    rejected = client.post(
        "/api/extract",
        json={
            "stego": file_json("stego.png", stego),
            "passphrase": "incorrect horse battery staple",
            "mode": mode,
        },
    )
    assert rejected.status_code == 400
    assert "pdf_base64" not in rejected.json()
    assert "salah atau" in rejected.json()["detail"]


@pytest.mark.parametrize("mode", ["sequential", "randomized"])
def test_receiver_rejects_modified_payload_without_returning_pdf(mode: str) -> None:
    response = embed(make_pdf(), make_png(), mode=mode)
    image = Image.open(BytesIO(base64.b64decode(response.json()["png_base64"])))
    pixels = bytearray(image.tobytes())
    if mode == "randomized":
        from backend.core.crypto.key_derivation import derive_keys
        from backend.core.steganography.randomized_lsb import HEADER_SLOTS, fisher_yates_permutation
        from backend.core.steganography.header import parse_payload_header

        header = bytes(
                sum(((pixels[index + bit] & 1) << (7 - bit)) for bit in range(8))
            for index in range(0, HEADER_SLOTS, 8)
        )
        parsed_header = parse_payload_header(header)
        key = derive_keys("correct horse battery staple", parsed_header.salt).position_key
        slots = image.width * image.height * 3 - HEADER_SLOTS
        pixels[HEADER_SLOTS + int(fisher_yates_permutation(slots, key)[0])] ^= 1
    else:
        pixels[8 * 32] ^= 1
    changed = Image.frombytes("RGB", image.size, bytes(pixels))
    changed_png = BytesIO()
    changed.save(changed_png, format="PNG")

    rejected = client.post(
        "/api/extract",
        json={
            "stego": file_json("tampered.png", changed_png.getvalue()),
            "passphrase": "correct horse battery staple",
            "mode": mode,
        },
    )
    assert rejected.status_code == 400
    assert "pdf_base64" not in rejected.json()


def test_receiver_rejects_invalid_header() -> None:
    invalid_header = client.post(
        "/api/extract",
        json={
            "stego": file_json("empty.png", make_png((32, 32), color=(0, 0, 0))),
            "passphrase": "long enough passphrase",
        },
    )
    assert invalid_header.status_code == 422


@pytest.mark.parametrize("mode", ["sequential", "randomized"])
def test_each_mode_round_trips_identical_pdf_with_matching_metadata(mode: str) -> None:
    original = make_pdf(b"mode-specific payload" * 3)
    cover = make_png((240, 180))
    cover_hash = hashlib.sha256(cover).digest()
    response = embed(original, cover, mode=mode)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["metadata"]["mode"] == mode
    if mode == "randomized":
        assert result["metadata"]["permutation_ms"] >= 0
        assert result["metadata"]["embedding_ms"] >= 0
    stego = base64.b64decode(result["png_base64"], validate=True)
    with Image.open(BytesIO(stego)) as image:
        assert image.format == "PNG" and image.mode == "RGB"
        assert image.size == (240, 180)

    recovered = client.post(
        "/api/extract",
        json={
            "stego": file_json("stego.png", stego),
            "passphrase": "correct horse battery staple",
            "mode": mode,
        },
    )
    assert recovered.status_code == 200, recovered.text
    recovery = recovered.json()
    restored = base64.b64decode(recovery["pdf_base64"], validate=True)
    assert recovery["metadata"]["mode"] == mode
    if mode == "randomized":
        assert recovery["metadata"]["permutation_ms"] >= 0
        assert recovery["metadata"]["extraction_ms"] >= 0
    assert restored == original
    assert recovery["metadata"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert hashlib.sha256(cover).digest() == cover_hash


def test_sender_and_receiver_reject_invalid_mode() -> None:
    invalid_sender_mode = embed(make_pdf(), make_png(), mode="not-a-method")
    assert invalid_sender_mode.status_code == 422

    source = embed(make_pdf(), make_png(), mode="randomized")
    assert source.status_code == 200
    stego = base64.b64decode(source.json()["png_base64"], validate=True)
    invalid_receiver_mode = client.post(
        "/api/extract",
        json={
            "stego": file_json("stego.png", stego),
            "passphrase": "correct horse battery staple",
            "mode": "unknown",
        },
    )
    assert invalid_receiver_mode.status_code == 422


@pytest.mark.parametrize(
    ("embed_mode", "extract_mode"),
    [("sequential", "randomized"), ("randomized", "sequential")],
)
def test_method_mismatch_never_returns_pdf(embed_mode: str, extract_mode: str) -> None:
    embedded = embed(make_pdf(b"method mismatch"), make_png((240, 180)), mode=embed_mode)
    assert embedded.status_code == 200, embedded.text
    stego = base64.b64decode(embedded.json()["png_base64"], validate=True)
    rejected = client.post(
        "/api/extract",
        json={
            "stego": file_json("mismatch.png", stego),
            "passphrase": "correct horse battery staple",
            "mode": extract_mode,
        },
    )
    assert rejected.status_code in {400, 422}
    assert "pdf_base64" not in rejected.json()


def test_randomized_request_derives_key_material_once_and_never_returns_position_key(monkeypatch) -> None:
    import backend.core.crypto.payload_crypto as payload_crypto
    import backend.services.receiver_service as receiver_service

    sender_calls = 0
    receiver_calls = 0
    derive_sender = payload_crypto.derive_keys
    derive_receiver = receiver_service.derive_keys

    def count_sender(*args, **kwargs):
        nonlocal sender_calls
        sender_calls += 1
        return derive_sender(*args, **kwargs)

    def count_receiver(*args, **kwargs):
        nonlocal receiver_calls
        receiver_calls += 1
        return derive_receiver(*args, **kwargs)

    monkeypatch.setattr(payload_crypto, "derive_keys", count_sender)
    embedded = embed(make_pdf(b"one derivation"), make_png((240, 180)), mode="randomized")
    assert embedded.status_code == 200, embedded.text
    assert sender_calls == 1
    assert "position_key" not in embedded.text
    assert "K_pos" not in embedded.text

    stego = base64.b64decode(embedded.json()["png_base64"], validate=True)
    monkeypatch.setattr(receiver_service, "derive_keys", count_receiver)
    recovered = client.post(
        "/api/extract",
        json={
            "stego": file_json("stego.png", stego),
            "passphrase": "correct horse battery staple",
            "mode": "randomized",
        },
    )
    assert recovered.status_code == 200, recovered.text
    assert receiver_calls == 1
    assert "position_key" not in recovered.text
    assert "K_pos" not in recovered.text


def test_body_limit_rejects_oversized_declared_length_before_reading_content() -> None:
    response = client.post(
        "/api/embed",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": str(24 * 1024 * 1024 + 1)},
    )
    assert response.status_code == 413
