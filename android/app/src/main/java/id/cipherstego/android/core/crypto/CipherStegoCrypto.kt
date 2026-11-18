package id.cipherstego.android.core.crypto

import id.cipherstego.android.core.stego.header.PayloadHeader
import java.security.GeneralSecurityException
import java.security.SecureRandom
import javax.crypto.AEADBadTagException
import javax.crypto.BadPaddingException

/**
 * High-level local crypto operations. Each call consumes and clears its passphrase CharArray.
 */
object CipherStegoCrypto {
    private val secureRandom = SecureRandom()

    fun encrypt(passphrase: CharArray, plaintext: ByteArray): CryptoResult<EncryptedPayload> {
        var masterKey: ByteArray? = null
        var derivedKeys: DerivedKeys? = null
        var encryptionKey: ByteArray? = null
        var aad: ByteArray? = null

        try {
            if (passphrase.isEmpty()) return CryptoResult.Failure(CryptoFailure.InvalidInput)

            val salt = PasswordKeyDerivation.generateSalt()
            val nonce = ByteArray(AesGcmEngine.NONCE_BYTES).also(secureRandom::nextBytes)
            masterKey = PasswordKeyDerivation.deriveMasterKey(passphrase, salt)
            derivedKeys = CryptoKeyDerivation.derive(masterKey, salt)

            val keyBytes = derivedKeys.encryptionKey
            encryptionKey = keyBytes
            val header = PayloadHeader.create(
                salt = salt,
                nonce = nonce,
                ciphertextLength = plaintext.size.toLong() + AesGcmEngine.TAG_BYTES,
            )
            val associatedData = header.serialize()
            aad = associatedData
            val ciphertext = AesGcmEngine.encrypt(plaintext, keyBytes, nonce, associatedData)
            return CryptoResult.Success(EncryptedPayload(header, ciphertext))
        } catch (_: IllegalArgumentException) {
            return CryptoResult.Failure(CryptoFailure.InvalidInput)
        } catch (_: GeneralSecurityException) {
            return CryptoResult.Failure(CryptoFailure.ProviderUnavailable)
        } finally {
            passphrase.fill('\u0000')
            masterKey?.fill(0)
            encryptionKey?.fill(0)
            aad?.fill(0)
            derivedKeys?.close()
        }
    }

    fun decrypt(passphrase: CharArray, payload: EncryptedPayload): CryptoResult<ByteArray> {
        var masterKey: ByteArray? = null
        var derivedKeys: DerivedKeys? = null
        var encryptionKey: ByteArray? = null
        var ciphertext: ByteArray? = null
        var nonce: ByteArray? = null
        var salt: ByteArray? = null
        var aad: ByteArray? = null

        try {
            if (passphrase.isEmpty()) return CryptoResult.Failure(CryptoFailure.InvalidInput)

            val payloadSalt = payload.header.salt
            val payloadNonce = payload.header.nonce
            val associatedData = payload.header.serialize()
            val ciphertextBytes = payload.ciphertextCopy()
            salt = payloadSalt
            nonce = payloadNonce
            aad = associatedData
            ciphertext = ciphertextBytes

            masterKey = PasswordKeyDerivation.deriveMasterKey(passphrase, payloadSalt)
            derivedKeys = CryptoKeyDerivation.derive(masterKey, payloadSalt)
            val keyBytes = derivedKeys.encryptionKey
            encryptionKey = keyBytes
            val plaintext = AesGcmEngine.decrypt(ciphertextBytes, keyBytes, payloadNonce, associatedData)
            return CryptoResult.Success(plaintext)
        } catch (_: AEADBadTagException) {
            return CryptoResult.Failure(CryptoFailure.AuthenticationFailed)
        } catch (_: BadPaddingException) {
            return CryptoResult.Failure(CryptoFailure.AuthenticationFailed)
        } catch (_: IllegalArgumentException) {
            return CryptoResult.Failure(CryptoFailure.InvalidInput)
        } catch (_: GeneralSecurityException) {
            return CryptoResult.Failure(CryptoFailure.ProviderUnavailable)
        } finally {
            passphrase.fill('\u0000')
            masterKey?.fill(0)
            encryptionKey?.fill(0)
            ciphertext?.fill(0)
            nonce?.fill(0)
            salt?.fill(0)
            aad?.fill(0)
            derivedKeys?.close()
        }
    }
}
