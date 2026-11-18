package id.cipherstego.android.core.crypto

import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

internal object AesGcmEngine {
    const val KEY_BYTES = 32
    const val NONCE_BYTES = 12
    const val TAG_BYTES = 16
    const val TAG_BITS = TAG_BYTES * 8

    fun encrypt(
        plaintext: ByteArray,
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
    ): ByteArray {
        validate(key, nonce)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(TAG_BITS, nonce))
        cipher.updateAAD(associatedData)
        return cipher.doFinal(plaintext).also {
            check(it.size.toLong() == plaintext.size.toLong() + TAG_BYTES) {
                "Provider returned an unexpected GCM output length."
            }
        }
    }

    fun decrypt(
        ciphertextAndTag: ByteArray,
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
    ): ByteArray {
        validate(key, nonce)
        require(ciphertextAndTag.size >= TAG_BYTES) { "GCM ciphertext must include a 16-byte tag." }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(TAG_BITS, nonce))
        cipher.updateAAD(associatedData)
        return cipher.doFinal(ciphertextAndTag)
    }

    private fun validate(key: ByteArray, nonce: ByteArray) {
        require(key.size == KEY_BYTES) { "AES-256 key must be 32 bytes." }
        require(nonce.size == NONCE_BYTES) { "GCM nonce must be 12 bytes." }
    }
}
