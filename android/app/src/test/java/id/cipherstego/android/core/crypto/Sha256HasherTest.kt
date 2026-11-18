package id.cipherstego.android.core.crypto

import java.io.ByteArrayInputStream
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class Sha256HasherTest {
    @Test
    fun matchesKnownSha256VectorsAndHexEncoding() {
        assertEquals(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            Sha256Hasher.toHex(Sha256Hasher.hash(byteArrayOf())),
        )
        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            Sha256Hasher.toHex(Sha256Hasher.hash("abc".toByteArray(Charsets.US_ASCII))),
        )
    }

    @Test
    fun streamAndByteArrayHashAreConsistentAndInputSensitive() {
        val first = "CipherStego test PDF bytes".toByteArray()
        val second = first.copyOf().also { it[0] = (it[0].toInt() xor 1).toByte() }
        assertArrayEquals(Sha256Hasher.hash(first), Sha256Hasher.hash(ByteArrayInputStream(first)))
        assertFalse(Sha256Hasher.hash(first).contentEquals(Sha256Hasher.hash(second)))
    }
}
