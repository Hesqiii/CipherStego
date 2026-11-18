package id.cipherstego.android.core.files

import android.content.ContentResolver
import android.database.Cursor
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.CRC32
import kotlin.math.max

data class DocumentMetadata(
    val uri: Uri,
    val displayName: String,
    val sizeBytes: Long?,
    val mimeType: String?,
)

data class PdfSelection(
    val metadata: DocumentMetadata,
)

data class PngSelection(
    val metadata: DocumentMetadata,
    val width: Int,
    val height: Int,
    val bitDepth: Int,
    val colorType: Int,
    val isSupportedRgb24: Boolean,
    val validationMessage: String,
    val preview: Bitmap?,
) {
    val totalRgbCapacityBits: Long
        get() = PayloadCapacity.totalRgbCapacityBits(width, height)

    val totalRgbCapacityBytes: Long
        get() = PayloadCapacity.totalRgbCapacityBytes(width, height)

    val ciphertextCapacityBytes: Long
        get() = PayloadCapacity.maxCiphertextBytes(width, height)


}

sealed interface InspectionResult<out T> {
    data class Valid<T>(val value: T) : InspectionResult<T>
    data class Invalid(val message: String) : InspectionResult<Nothing>
}

class DocumentInspector(private val resolver: ContentResolver) {
    suspend fun inspectPdf(uri: Uri): InspectionResult<PdfSelection> = withContext(Dispatchers.IO) {
        try {
            val metadata = readMetadata(uri)
            if (metadata.sizeBytes == 0L) {
                return@withContext InspectionResult.Invalid("File PDF kosong.")
            }
            val signature = resolver.openInputStream(uri)?.use { readPrefix(it, PDF_SIGNATURE.size) }
                ?: return@withContext InspectionResult.Invalid("File tidak dapat dibuka.")
            if (signature.isEmpty()) {
                return@withContext InspectionResult.Invalid("File PDF kosong.")
            }
            if (!signature.contentEquals(PDF_SIGNATURE)) {
                return@withContext InspectionResult.Invalid("Isi file bukan PDF yang valid.")
            }
            InspectionResult.Valid(PdfSelection(metadata))
        } catch (error: Exception) {
            InspectionResult.Invalid(error.messageForUser("Tidak dapat membaca file PDF."))
        }
    }

    suspend fun inspectPng(uri: Uri): InspectionResult<PngSelection> = withContext(Dispatchers.IO) {
        try {
            val metadata = readMetadata(uri)
            if (metadata.sizeBytes == 0L) {
                return@withContext InspectionResult.Invalid("File PNG kosong.")
            }

            val ihdr = resolver.openInputStream(uri)?.use(::readPngIhdr)
                ?: return@withContext InspectionResult.Invalid("File tidak dapat dibuka.")
            val (width, height, bitDepth, colorType) = ihdr
            if (width <= 0 || height <= 0 || width.toLong() * height.toLong() > Int.MAX_VALUE) {
                return@withContext InspectionResult.Invalid("Dimensi gambar tidak valid atau terlalu besar.")
            }

            val supported = bitDepth == 8 && colorType == 2
            val preview = if (supported) decodePreview(uri, width, height) else null
            val message = when {
                !supported -> "Tidak didukung: proposal memerlukan PNG RGB 24-bit (8-bit, truecolor RGB)."
                preview == null -> "IHDR valid, tetapi pratinjau tidak dapat didekode dengan aman."
                else -> "Valid: PNG RGB 24-bit."
            }
            InspectionResult.Valid(
                PngSelection(
                    metadata = metadata,
                    width = width,
                    height = height,
                    bitDepth = bitDepth,
                    colorType = colorType,
                    isSupportedRgb24 = supported && preview != null,
                    validationMessage = message,
                    preview = preview,
                ),
            )
        } catch (error: Exception) {
            InspectionResult.Invalid(error.messageForUser("Tidak dapat membaca file PNG."))
        }
    }

    private fun readMetadata(uri: Uri): DocumentMetadata {
        var name: String? = null
        var size: Long? = null
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)
            ?.use { cursor: Cursor ->
                if (cursor.moveToFirst()) {
                    val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (nameIndex >= 0) name = cursor.getString(nameIndex)
                    if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) size = cursor.getLong(sizeIndex).takeIf { it >= 0L }
                }
            }
        return DocumentMetadata(
            uri = uri,
            displayName = name?.takeIf { it.isNotBlank() } ?: (uri.lastPathSegment ?: "Dokumen"),
            sizeBytes = size,
            mimeType = resolver.getType(uri),
        )
    }

    private fun readPrefix(stream: InputStream, size: Int): ByteArray {
        val result = ByteArray(size)
        var offset = 0
        while (offset < size) {
            val count = stream.read(result, offset, size - offset)
            if (count < 0) break
            offset += count
        }
        return result.copyOf(offset)
    }

    private fun readPngIhdr(stream: InputStream): PngHeader? {
        val bytes = ByteArray(33)
        var offset = 0
        while (offset < bytes.size) {
            val count = stream.read(bytes, offset, bytes.size - offset)
            if (count < 0) return null
            offset += count
        }
        if (!bytes.copyOfRange(0, 8).contentEquals(PNG_SIGNATURE)) return null

        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN)
        buffer.position(8)
        if (buffer.int != 13) return null
        if (buffer.get().toInt() != 'I'.code ||
            buffer.get().toInt() != 'H'.code ||
            buffer.get().toInt() != 'D'.code ||
            buffer.get().toInt() != 'R'.code
        ) return null

        val width = buffer.int
        val height = buffer.int
        val bitDepth = buffer.get().toInt() and 0xFF
        val colorType = buffer.get().toInt() and 0xFF
        val compression = buffer.get().toInt() and 0xFF
        val filter = buffer.get().toInt() and 0xFF
        val interlace = buffer.get().toInt() and 0xFF
        val expectedCrc = buffer.int.toLong() and 0xFFFF_FFFFL
        val crc = CRC32().apply { update(bytes, 12, 17) }.value
        if (crc != expectedCrc || compression != 0 || filter != 0 || interlace !in 0..1) return null
        val validDepth = when (colorType) {
            0 -> bitDepth in setOf(1, 2, 4, 8, 16)
            2 -> bitDepth in setOf(8, 16)
            3 -> bitDepth in setOf(1, 2, 4, 8)
            4, 6 -> bitDepth in setOf(8, 16)
            else -> false
        }
        if (!validDepth) return null
        return PngHeader(width, height, bitDepth, colorType)
    }

    private fun decodePreview(uri: Uri, width: Int, height: Int): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null

        var sample = 1
        while (max(bounds.outWidth / sample, bounds.outHeight / sample) > MAX_PREVIEW_EDGE) {
            sample *= 2
        }
        val options = BitmapFactory.Options().apply {
            inJustDecodeBounds = false
            inSampleSize = sample
            inPreferredConfig = Bitmap.Config.ARGB_8888
        }
        return try {
            resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
                ?.takeIf { it.width > 0 && it.height > 0 && width > 0 && height > 0 }
        } catch (_: OutOfMemoryError) {
            null
        }
    }

    private fun Exception.messageForUser(fallback: String): String =
        message?.takeIf { it.isNotBlank() } ?: fallback

    private data class PngHeader(
        val width: Int,
        val height: Int,
        val bitDepth: Int,
        val colorType: Int,
    )

    private companion object {
        const val MAX_PREVIEW_EDGE = 1024
        val PDF_SIGNATURE = "%PDF-".toByteArray(Charsets.US_ASCII)
        val PNG_SIGNATURE = byteArrayOf(
            0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        )
    }
}
