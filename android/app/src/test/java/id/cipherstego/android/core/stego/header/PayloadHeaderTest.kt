package id.cipherstego.android.core.stego.header

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class PayloadHeaderTest {
    @Test
    fun serializesAndParsesTheExactThirtyTwoByteLayout() {
        val salt = ByteArray(16) { it.toByte() }
        val nonce = ByteArray(12) { (it + 16).toByte() }
        val header = PayloadHeader.create(salt, nonce, 0x01020304L)

        val serialized = header.serialize()
        assertEquals(32, serialized.size)
        assertArrayEquals(salt, serialized.copyOfRange(0, 16))
        assertArrayEquals(nonce, serialized.copyOfRange(16, 28))
        assertArrayEquals(byteArrayOf(1, 2, 3, 4), serialized.copyOfRange(28, 32))

        val parsed = PayloadHeader.parse(serialized)
        assertArrayEquals(serialized, parsed.serialize())
        assertEquals(0x01020304L, parsed.ciphertextLength)
    }

    @Test
    fun supportsUnsignedLengthBoundaryAndRejectsInvalidLengths() {
        val header = PayloadHeader.create(ByteArray(16), ByteArray(12), PayloadHeader.MAX_CIPHERTEXT_BYTES)
        assertEquals(PayloadHeader.MAX_CIPHERTEXT_BYTES, PayloadHeader.parse(header.serialize()).ciphertextLength)
        assertThrows(IllegalArgumentException::class.java) {
            PayloadHeader.create(ByteArray(16), ByteArray(12), PayloadHeader.MIN_CIPHERTEXT_BYTES - 1)
        }
        assertThrows(IllegalArgumentException::class.java) {
            PayloadHeader.create(ByteArray(16), ByteArray(12), PayloadHeader.MAX_CIPHERTEXT_BYTES + 1)
        }
    }

    @Test
    fun rejectsWrongHeaderSaltNonceAndSerializedSizes() {
        assertThrows(IllegalArgumentException::class.java) {
            PayloadHeader.create(ByteArray(15), ByteArray(12), 16)
        }
        assertThrows(IllegalArgumentException::class.java) {
            PayloadHeader.create(ByteArray(16), ByteArray(11), 16)
        }
        assertThrows(IllegalArgumentException::class.java) {
            PayloadHeader.parse(ByteArray(31))
        }
        val tooShortCiphertext = ByteArray(32).also { it[31] = 15 }
        assertThrows(IllegalArgumentException::class.java) {
            PayloadHeader.parse(tooShortCiphertext)
        }
    }
}
