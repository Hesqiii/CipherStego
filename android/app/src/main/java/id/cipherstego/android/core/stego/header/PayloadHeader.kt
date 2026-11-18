package id.cipherstego.android.core.stego.header

class PayloadHeader private constructor(
    salt: ByteArray,
    nonce: ByteArray,
    val ciphertextLength: Long,
) {
    private val saltBytes = salt.copyOf()
    private val nonceBytes = nonce.copyOf()

    val salt: ByteArray
        get() = saltBytes.copyOf()

    val nonce: ByteArray
        get() = nonceBytes.copyOf()

    fun serialize(): ByteArray = ByteArray(HEADER_BYTES).also { output ->
        System.arraycopy(saltBytes, 0, output, 0, SALT_BYTES)
        System.arraycopy(nonceBytes, 0, output, SALT_BYTES, NONCE_BYTES)
        output[28] = (ciphertextLength ushr 24).toByte()
        output[29] = (ciphertextLength ushr 16).toByte()
        output[30] = (ciphertextLength ushr 8).toByte()
        output[31] = ciphertextLength.toByte()
    }

    companion object {
        const val HEADER_BYTES = 32
        const val SALT_BYTES = 16
        const val NONCE_BYTES = 12
        const val TAG_BYTES = 16
        const val MIN_CIPHERTEXT_BYTES = TAG_BYTES.toLong()
        const val MAX_CIPHERTEXT_BYTES = 0xFFFF_FFFFL

        fun create(salt: ByteArray, nonce: ByteArray, ciphertextLength: Long): PayloadHeader {
            require(salt.size == SALT_BYTES) { "Header salt must be 16 bytes." }
            require(nonce.size == NONCE_BYTES) { "Header nonce must be 12 bytes." }
            require(ciphertextLength in MIN_CIPHERTEXT_BYTES..MAX_CIPHERTEXT_BYTES) {
                "Ciphertext length must include the 16-byte GCM tag and fit unsigned 32-bit."
            }
            return PayloadHeader(salt, nonce, ciphertextLength)
        }

        fun parse(serialized: ByteArray): PayloadHeader {
            require(serialized.size == HEADER_BYTES) { "Header must be exactly 32 bytes." }
            val length = ((serialized[28].toLong() and 0xFF) shl 24) or
                ((serialized[29].toLong() and 0xFF) shl 16) or
                ((serialized[30].toLong() and 0xFF) shl 8) or
                (serialized[31].toLong() and 0xFF)
            return create(
                salt = serialized.copyOfRange(0, SALT_BYTES),
                nonce = serialized.copyOfRange(SALT_BYTES, SALT_BYTES + NONCE_BYTES),
                ciphertextLength = length,
            )
        }
    }
}
