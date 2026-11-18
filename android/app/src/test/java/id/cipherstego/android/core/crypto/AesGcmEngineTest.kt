package id.cipherstego.android.core.crypto

import id.cipherstego.android.core.stego.header.PayloadHeader
import javax.crypto.AEADBadTagException
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertThrows
import org.junit.Test

class AesGcmEngineTest {
    @Test
    fun rawEngineRoundTripsAndAuthenticatesHeaderAsAad() {
        val key = ByteArray(32) { it.toByte() }
        val nonce = ByteArray(12) { (it + 20).toByte() }
        val salt = ByteArray(16) { (it + 40).toByte() }
        val plaintext = "header-bound payload".toByteArray()
        val header = PayloadHeader.create(salt, nonce, plaintext.size.toLong() + 16)
        val aad = header.serialize()
        val ciphertext = AesGcmEngine.encrypt(plaintext, key, nonce, aad)

        assertEquals(plaintext.size + 16, ciphertext.size)
        assertArrayEquals(plaintext, AesGcmEngine.decrypt(ciphertext, key, nonce, aad))

        val modifiedAad = aad.copyOf().also { it[0] = (it[0].toInt() xor 1).toByte() }
        assertThrows(AEADBadTagException::class.java) {
            AesGcmEngine.decrypt(ciphertext, key, nonce, modifiedAad)
        }
        key.fill(0)
    }

    @Test
    fun rejectsInvalidNonceAndTampering() {
        val key = ByteArray(32) { 7 }
        val nonce = ByteArray(12) { 9 }
        val aad = byteArrayOf(1, 2, 3)
        val ciphertext = AesGcmEngine.encrypt(byteArrayOf(4, 5, 6), key, nonce, aad)

        assertThrows(IllegalArgumentException::class.java) {
            AesGcmEngine.encrypt(byteArrayOf(1), key, ByteArray(11), aad)
        }
        val modifiedCiphertext = ciphertext.copyOf().also { it[0] = (it[0].toInt() xor 1).toByte() }
        val modifiedTag = ciphertext.copyOf().also {
            val last = it.lastIndex
            it[last] = (it[last].toInt() xor 1).toByte()
        }
        assertThrows(AEADBadTagException::class.java) {
            AesGcmEngine.decrypt(modifiedCiphertext, key, nonce, aad)
        }
        assertThrows(AEADBadTagException::class.java) {
            AesGcmEngine.decrypt(modifiedTag, key, nonce, aad)
        }
    }

    @Test
    fun serviceOnlyReturnsPlaintextAfterGcmAuthentication() {
        val original = ByteArray(3072) { (it * 31).toByte() }
        val encryptionPassphrase = "correct horse battery staple".toCharArray()
        val encrypted = CipherStegoCrypto.encrypt(encryptionPassphrase, original)
        assertTrue(encrypted is CryptoResult.Success)
        assertTrue(encryptionPassphrase.all { it == '\u0000' })

        val payload = (encrypted as CryptoResult.Success).value
        assertEquals(original.size + 16L, payload.header.ciphertextLength)

        val decrypted = CipherStegoCrypto.decrypt("correct horse battery staple".toCharArray(), payload)
        assertTrue(decrypted is CryptoResult.Success)
        assertArrayEquals(original, (decrypted as CryptoResult.Success).value)

        val wrongPassword = CipherStegoCrypto.decrypt("wrong passphrase".toCharArray(), payload)
        assertTrue(wrongPassword is CryptoResult.Failure)
        assertEquals(CryptoFailure.AuthenticationFailed, (wrongPassword as CryptoResult.Failure).reason)

        val damaged = payload.ciphertext.also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }
        val damagedPayload = EncryptedPayload(payload.header, damaged)
        val damagedResult = CipherStegoCrypto.decrypt("correct horse battery staple".toCharArray(), damagedPayload)
        assertTrue(damagedResult is CryptoResult.Failure)
        assertEquals(CryptoFailure.AuthenticationFailed, (damagedResult as CryptoResult.Failure).reason)
    }
}
