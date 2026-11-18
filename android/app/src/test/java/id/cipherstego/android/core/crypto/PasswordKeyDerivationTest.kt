package id.cipherstego.android.core.crypto

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Test

class PasswordKeyDerivationTest {
    @Test
    fun matchesPublishedPbkdf2HmacSha256Vector() {
        val actual = PasswordKeyDerivation.deriveWithIterations(
            passphrase = "password".toCharArray(),
            salt = "salt".toByteArray(Charsets.US_ASCII),
            iterations = 1,
        )
        assertArrayEquals(
            "120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b".hexBytes(),
            actual,
        )
    }

    @Test
    fun productionDerivationIs32BytesDeterministicAndSaltDependent() {
        val saltA = ByteArray(16) { it.toByte() }
        val saltB = ByteArray(16) { (it + 1).toByte() }
        val first = PasswordKeyDerivation.deriveMasterKey("passphrase".toCharArray(), saltA)
        val repeated = PasswordKeyDerivation.deriveMasterKey("passphrase".toCharArray(), saltA)
        val otherSalt = PasswordKeyDerivation.deriveMasterKey("passphrase".toCharArray(), saltB)

        assertEquals(32, first.size)
        assertArrayEquals(first, repeated)
        assertFalse(first.contentEquals(otherSalt))
        first.fill(0)
        repeated.fill(0)
        otherSalt.fill(0)
    }

    @Test
    fun validatesEmptyPassphraseAndSaltSize() {
        assertThrows(IllegalArgumentException::class.java) {
            PasswordKeyDerivation.deriveMasterKey(charArrayOf(), ByteArray(16))
        }
        assertThrows(IllegalArgumentException::class.java) {
            PasswordKeyDerivation.deriveMasterKey("x".toCharArray(), ByteArray(15))
        }
    }

    private fun String.hexBytes(): ByteArray =
        chunked(2).map { it.toInt(16).toByte() }.toByteArray()
}
