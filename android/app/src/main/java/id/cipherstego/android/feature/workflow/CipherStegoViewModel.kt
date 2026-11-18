package id.cipherstego.android.feature.workflow

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import id.cipherstego.android.core.files.DocumentInspector
import id.cipherstego.android.core.files.InspectionResult
import id.cipherstego.android.core.files.PdfSelection
import id.cipherstego.android.core.files.PngSelection
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class EmbeddingMethod(val label: String) {
    Sequential("Sequential LSB"),
    Randomized("Key-Based Randomized LSB"),
}

enum class FileTask {
    Pdf,
    SenderImage,
    ReceiverImage,
}

data class CipherStegoUiState(
    val pdf: PdfSelection? = null,
    val senderImage: PngSelection? = null,
    val receiverImage: PngSelection? = null,
    val selectedMethod: EmbeddingMethod = EmbeddingMethod.Sequential,
    val receiverMethod: EmbeddingMethod = EmbeddingMethod.Sequential,
    val senderPassphrase: String = "",
    val receiverPassphrase: String = "",
    val activeTask: FileTask? = null,
    val message: String? = null,
    val messageIsError: Boolean = false,
)

class CipherStegoViewModel(application: Application) : AndroidViewModel(application) {
    private val inspector = DocumentInspector(application.contentResolver)
    private val _uiState = MutableStateFlow(CipherStegoUiState())
    val uiState = _uiState.asStateFlow()

    fun selectPdf(uri: Uri) = inspect(FileTask.Pdf) {
        when (val result = inspector.inspectPdf(uri)) {
            is InspectionResult.Valid -> _uiState.update {
                it.copy(pdf = result.value, message = null, messageIsError = false)
            }
            is InspectionResult.Invalid -> _uiState.update {
                it.copy(pdf = null, message = result.message, messageIsError = true)
            }
        }
    }

    fun selectSenderImage(uri: Uri) = inspect(FileTask.SenderImage) {
        when (val result = inspector.inspectPng(uri)) {
            is InspectionResult.Valid -> _uiState.update {
                it.copy(senderImage = result.value, message = result.value.validationMessage,
                    messageIsError = !result.value.isSupportedRgb24)
            }
            is InspectionResult.Invalid -> _uiState.update {
                it.copy(senderImage = null, message = result.message, messageIsError = true)
            }
        }
    }

    fun selectReceiverImage(uri: Uri) = inspect(FileTask.ReceiverImage) {
        when (val result = inspector.inspectPng(uri)) {
            is InspectionResult.Valid -> _uiState.update {
                it.copy(receiverImage = result.value, message = result.value.validationMessage,
                    messageIsError = !result.value.isSupportedRgb24)
            }
            is InspectionResult.Invalid -> _uiState.update {
                it.copy(receiverImage = null, message = result.message, messageIsError = true)
            }
        }
    }

    fun setEmbeddingMethod(method: EmbeddingMethod) {
        _uiState.update { it.copy(selectedMethod = method) }
    }

    fun setReceiverMethod(method: EmbeddingMethod) {
        _uiState.update { it.copy(receiverMethod = method) }
    }

    fun setSenderPassphrase(value: String) {
        _uiState.update { it.copy(senderPassphrase = value) }
    }

    fun setReceiverPassphrase(value: String) {
        _uiState.update { it.copy(receiverPassphrase = value) }
    }

    fun onDestinationChanged(previous: Int) {
        _uiState.update {
            it.copy(
                senderPassphrase = if (previous == 0) "" else it.senderPassphrase,
                receiverPassphrase = if (previous == 1) "" else it.receiverPassphrase,
                message = null,
                messageIsError = false,
            )
        }
    }

    fun reportUnavailable() {
        _uiState.update {
            it.copy(
                senderPassphrase = "",
                receiverPassphrase = "",
                message = "Pemrosesan belum tersedia pada milestone ini.",
                messageIsError = false,
            )
        }
    }

    fun clearMessage() {
        _uiState.update { it.copy(message = null, messageIsError = false) }
    }

    private fun inspect(task: FileTask, block: suspend () -> Unit) {
        viewModelScope.launch {
            _uiState.update { it.copy(activeTask = task, message = null, messageIsError = false) }
            try {
                block()
            } finally {
                _uiState.update { if (it.activeTask == task) it.copy(activeTask = null) else it }
            }
        }
    }
}
