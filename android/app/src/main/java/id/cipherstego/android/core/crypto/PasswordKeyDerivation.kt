package id.cipherstego.android.core.crypto

import java.security.SecureRandom
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

object PasswordKeyDerivation {
    const val ITERATIONS = 600_000
    const val SALT_BYTES = 16
    const val MASTER_KEY_BYTES = 32

    private val secureRandom = SecureRandom()

    fun generateSalt(): ByteArray = ByteArray(SALT_BYTES).also(secureRandom::nextBytes)

    /**
     * PBKDF2WithHmacSHA256 uses the Android provider's UTF-8 password conversion.
     * The passphrase is not normalized or otherwise transformed.
     */
    fun deriveMasterKey(passphrase: CharArray, salt: ByteArray): ByteArray {
        require(passphrase.isNotEmpty()) { "Passphrase must not be empty." }
        require(salt.size == SALT_BYTES) { "Salt must be 16 bytes." }
        return deriveWithIterations(passphrase, salt, ITERATIONS)
    }

    internal fun deriveWithIterations(
        passphrase: CharArray,
        salt: ByteArray,
        iterations: Int,
    ): ByteArray {
        require(passphrase.isNotEmpty()) { "Passphrase must not be empty." }
        require(salt.isNotEmpty()) { "Salt must not be empty." }
        require(iterations > 0) { "Iteration count must be positive." }

        val passwordCopy = passphrase.copyOf()
        val keySpec = PBEKeySpec(passwordCopy, salt.copyOf(), iterations, MASTER_KEY_BYTES * 8)
        return try {
            val encoded = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
                .generateSecret(keySpec)
                .encoded ?: throw IllegalStateException("Provider returned no encoded key.")
            check(encoded.size == MASTER_KEY_BYTES) { "Provider returned an unexpected key length." }
            encoded
        } finally {
            passwordCopy.fill('\u0000')
            keySpec.clearPassword()
        }
    }

}
