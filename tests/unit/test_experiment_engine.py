from backend.core.crypto.payload_crypto import encrypt_payload_with_keys
from backend.core.steganography.randomized_lsb import embed_randomized
from backend.core.steganography.sequential_lsb import embed_sequential
from backend.experiments.engine import _channel_bit_counts, _security_scenarios
from PIL import Image


def test_sequential_channel_slot_accounting_counts_header_and_ciphertext() -> None:
    counts = _channel_bit_counts("sequential", total_slots=1000, ciphertext_length=1, position_key=b"unused")

    assert counts == {"red": 88, "green": 88, "blue": 88}


def test_randomized_channel_slot_accounting_counts_header_and_actual_permuted_positions() -> None:
    counts = _channel_bit_counts("randomized", total_slots=1000, ciphertext_length=1, position_key=b"p" * 32)

    assert sum(counts.values()) == 264
    assert all(value > 0 for value in counts.values())


def test_s3_and_s4_reject_tampering_without_creating_pdf_for_both_methods(tmp_path) -> None:
    pdf = b"%PDF-1.7\nshort experiment test fixture\n%%EOF\n"
    passphrase = "test-only passphrase"
    encrypted, keys = encrypt_payload_with_keys(passphrase, pdf)
    cover_path = tmp_path / "cover.png"
    Image.new("RGB", (64, 64), (30, 80, 120)).save(cover_path, format="PNG")

    for mode in ("sequential", "randomized"):
        if mode == "sequential":
            stego = embed_sequential(cover_path, encrypted.header_bytes, encrypted.ciphertext)
        else:
            stego = embed_randomized(
                cover_path, encrypted.header_bytes, encrypted.ciphertext, keys.position_key
            )
        result = _security_scenarios(
            mode,
            stego,
            encrypted,
            keys,
            passphrase,
            "stego.png",
            tmp_path,
            f"P01_C1_{mode}",
        )

        all_checks = [result["wrong_passphrase"], *result["tampering"]]
        assert all(check["status"] == "rejected" for check in all_checks)
        assert all(check["pdf_created"] is False for check in all_checks)
        assert [check["failure_stage"] for check in result["tampering"]] == [
            "gcm_authentication",
            "gcm_authentication",
            "gcm_authentication",
            "gcm_authentication",
            "capacity_validation",
        ]
