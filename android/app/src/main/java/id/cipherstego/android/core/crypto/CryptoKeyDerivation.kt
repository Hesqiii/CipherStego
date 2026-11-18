package id.cipherstego.android.core.crypto

import java.nio.charset.StandardCharsets

/**
 * Proposal specifies distinct HKDF context labels but not their exact values or K_pos length.
 * These versioned labels and a 32-byte K_pos are explicit implementation parameters.
 */
object CryptoKeyDerivation {
    const val ENCRYPTION_CONTEXT_LABEL = "CipherStego/v1/encryption-key"
    const val POSITION_CONTEXT_LABEL = "CipherStego/v1/position-key"
    const val ENCRYPTION_KEY_BYTES = 32
    const val POSITION_KEY_BYTES = 32

    fun derive(masterKey: ByteArray, salt: ByteArray): DerivedKeys {
        require(masterKey.size == PasswordKeyDerivation.MASTER_KEY_BYTES) {
            "Master key must be 32 bytes."
        }
        require(salt.size == PasswordKeyDerivation.SALT_BYTES) { "Salt must be 16 bytes." }

        val pseudorandomKey = HkdfSha256.extract(masterKey, salt)
        var encryptionKey: ByteArray? = null
        var positionKey: ByteArray? = null
        try {
            encryptionKey = HkdfSha256.expand(
                pseudorandomKey,
                ENCRYPTION_CONTEXT_LABEL.toByteArray(StandardCharsets.UTF_8),
                ENCRYPTION_KEY_BYTES,
            )
            positionKey = HkdfSha256.expand(
                pseudorandomKey,
                POSITION_CONTEXT_LABEL.toByteArray(StandardCharsets.UTF_8),
                POSITION_KEY_BYTES,
            )
            return DerivedKeys(encryptionKey, positionKey)
        } finally {
            pseudorandomKey.fill(0)
            encryptionKey?.fill(0)
            positionKey?.fill(0)
        }
    }
}
