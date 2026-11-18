"""Shared cryptographic parameters for the proposal format."""

PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
MASTER_KEY_BYTES = 32
AES_KEY_BYTES = 32
NONCE_BYTES = 12
GCM_TAG_BYTES = 16
HEADER_BYTES = 32
UINT32_MAX = (1 << 32) - 1
HKDF_SHA256_MAX_BYTES = 255 * 32
HKDF_KEY_BYTES = 32
HKDF_ENCRYPTION_INFO = b"cipherstego/v1/encryption"
HKDF_POSITION_INFO = b"cipherstego/v1/position"
