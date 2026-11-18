package id.cipherstego.android.core.crypto

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object HkdfSha256 {
    const val HASH_LENGTH_BYTES = 32
    const val MAX_OUTPUT_BYTES = 255 * HASH_LENGTH_BYTES

    /** RFC 5869 extract step. An empty salt is treated as 32 zero bytes. */
    fun extract(inputKeyMaterial: ByteArray, salt: ByteArray = ByteArray(0)): ByteArray {
        val actualSalt = if (salt.isEmpty()) ByteArray(HASH_LENGTH_BYTES) else salt
        return hmacSha256(actualSalt, inputKeyMaterial)
    }

    /** RFC 5869 expand step. */
    fun expand(pseudorandomKey: ByteArray, info: ByteArray, outputLength: Int): ByteArray {
        require(pseudorandomKey.isNotEmpty()) { "Pseudorandom key must not be empty." }
        require(outputLength in 1..MAX_OUTPUT_BYTES) { "HKDF output length is out of range." }

        val mac = newMac(pseudorandomKey)
        val output = ByteArray(outputLength)
        var previousBlock = ByteArray(0)
        var outputOffset = 0
        var counter = 1

        try {
            while (outputOffset < outputLength) {
                mac.reset()
                if (previousBlock.isNotEmpty()) mac.update(previousBlock)
                mac.update(info)
                mac.update(counter.toByte())
                val nextBlock = mac.doFinal()
                previousBlock.fill(0)
                previousBlock = nextBlock

                val count = minOf(nextBlock.size, outputLength - outputOffset)
                System.arraycopy(nextBlock, 0, output, outputOffset, count)
                outputOffset += count
                counter++
            }
            return output
        } finally {
            previousBlock.fill(0)
        }
    }

    fun derive(
        inputKeyMaterial: ByteArray,
        salt: ByteArray,
        info: ByteArray,
        outputLength: Int,
    ): ByteArray {
        val pseudorandomKey = extract(inputKeyMaterial, salt)
        return try {
            expand(pseudorandomKey, info, outputLength)
        } finally {
            pseudorandomKey.fill(0)
        }
    }

    private fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray =
        newMac(key).doFinal(data)

    private fun newMac(key: ByteArray): Mac =
        Mac.getInstance("HmacSHA256").apply {
            init(SecretKeySpec(key, "HmacSHA256"))
        }
}
