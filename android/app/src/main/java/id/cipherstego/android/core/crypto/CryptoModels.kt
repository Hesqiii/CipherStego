package id.cipherstego.android.core.crypto

import id.cipherstego.android.core.stego.header.PayloadHeader
import java.io.Closeable

/**
 * Holds the two independent HKDF outputs for one operation.
 *
 * Call close() when finished. JVM/provider copies cannot be reliably zeroized.
 */
class DerivedKeys internal constructor(
    encryptionKey: ByteArray,
    positionKey: ByteArray,
) : Closeable {
    private val encryptionBytes = encryptionKey.copyOf()
    private val positionBytes = positionKey.copyOf()
    @Volatile private var closed = false

    val encryptionKey: ByteArray
        get() {
            check(!closed) { "Derived keys have been cleared." }
            return encryptionBytes.copyOf()
        }

    val positionKey: ByteArray
        get() {
            check(!closed) { "Derived keys have been cleared." }
            return positionBytes.copyOf()
        }

    @Synchronized
    override fun close() {
        if (!closed) {
            encryptionBytes.fill(0)
            positionBytes.fill(0)
            closed = true
        }
    }
}

/** Ciphertext includes its 16-byte GCM tag; the serialized header is the AAD. */
class EncryptedPayload(
    val header: PayloadHeader,
    ciphertext: ByteArray,
) {
    private val ciphertextBytes = ciphertext.copyOf()

    init {
        require(ciphertextBytes.size.toLong() == header.ciphertextLength) {
            "Ciphertext length does not match the header."
        }
    }

    val ciphertext: ByteArray
        get() = ciphertextBytes.copyOf()

    internal fun ciphertextCopy(): ByteArray = ciphertextBytes.copyOf()
}
