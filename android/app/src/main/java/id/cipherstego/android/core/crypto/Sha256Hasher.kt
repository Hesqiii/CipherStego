package id.cipherstego.android.core.crypto

import java.io.InputStream
import java.security.MessageDigest

object Sha256Hasher {
    const val DIGEST_BYTES = 32
    private const val BUFFER_BYTES = 8 * 1024
    private const val HEX = "0123456789abcdef"

    fun hash(content: ByteArray): ByteArray =
        MessageDigest.getInstance("SHA-256").digest(content)

    /** Hashes a stream incrementally and leaves ownership/closing to the caller. */
    fun hash(input: InputStream): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(BUFFER_BYTES)
        try {
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                if (count > 0) digest.update(buffer, 0, count)
            }
            return digest.digest()
        } finally {
            buffer.fill(0)
        }
    }

    fun toHex(digest: ByteArray): String {
        require(digest.size == DIGEST_BYTES) { "SHA-256 digest must be 32 bytes." }
        val chars = CharArray(digest.size * 2)
        digest.forEachIndexed { index, byte ->
            val value = byte.toInt() and 0xFF
            chars[index * 2] = HEX[value ushr 4]
            chars[index * 2 + 1] = HEX[value and 0x0F]
        }
        return String(chars)
    }
}
