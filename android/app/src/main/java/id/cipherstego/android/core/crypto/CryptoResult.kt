package id.cipherstego.android.core.crypto

sealed interface CryptoResult<out T> {
    data class Success<T>(val value: T) : CryptoResult<T>
    data class Failure(val reason: CryptoFailure) : CryptoResult<Nothing>
}

sealed interface CryptoFailure {
    data object InvalidInput : CryptoFailure
    data object AuthenticationFailed : CryptoFailure
    data object ProviderUnavailable : CryptoFailure
}
