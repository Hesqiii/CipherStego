package id.cipherstego.android.core.crypto

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Test

class HkdfSha256Test {
    @Test
    fun matchesRfc5869Sha256TestCase1() {
        val ikm = ByteArray(22) { 0x0B.toByte() }
        val salt = "000102030405060708090a0b0c".hexBytes()
        val info = "f0f1f2f3f4f5f6f7f8f9".hexBytes()

        val prk = HkdfSha256.extract(ikm, salt)
        assertArrayEquals(
            "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5".hexBytes(),
            prk,
        )
        assertArrayEquals(
            ("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf" +
                "34007208d5b887185865").hexBytes(),
            HkdfSha256.expand(prk, info, 42),
        )
        prk.fill(0)
    }

    @Test
    fun contextLabelsDeriveIndependentRepeatableKeys() {
        val master = ByteArray(32) { (it * 3).toByte() }
        val salt = ByteArray(16) { (it + 8).toByte() }
        val first = CryptoKeyDerivation.derive(master, salt)
        val second = CryptoKeyDerivation.derive(master, salt)
        try {
            assertEquals(32, first.encryptionKey.size)
            assertEquals(32, first.positionKey.size)
            assertArrayEquals(first.encryptionKey, second.encryptionKey)
            assertArrayEquals(first.positionKey, second.positionKey)
            assertFalse(first.encryptionKey.contentEquals(first.positionKey))
        } finally {
            first.close()
            second.close()
            master.fill(0)
        }
    }

    @Test
    fun rejectsOutputBeyondRfcLimit() {
        assertThrows(IllegalArgumentException::class.java) {
            HkdfSha256.expand(ByteArray(32), byteArrayOf(), HkdfSha256.MAX_OUTPUT_BYTES + 1)
        }
    }

    private fun String.hexBytes(): ByteArray =
        chunked(2).map { it.toInt(16).toByte() }.toByteArray()
}
