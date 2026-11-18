package id.cipherstego.android.core.files

object PayloadCapacity {
    const val HEADER_BYTES = 32L
    const val GCM_TAG_BYTES = 16L

    fun totalRgbCapacityBits(width: Int, height: Int): Long {
        require(width > 0 && height > 0) { "Image dimensions must be positive." }
        return width.toLong() * height.toLong() * 3L
    }

    fun totalRgbCapacityBytes(width: Int, height: Int): Long =
        totalRgbCapacityBits(width, height) / 8L

    fun maxCiphertextBytes(width: Int, height: Int): Long =
        (totalRgbCapacityBytes(width, height) - HEADER_BYTES).coerceAtLeast(0L)

    fun estimatedCiphertextBytes(pdfBytes: Long): Long? =
        if (pdfBytes < 0L || pdfBytes > Long.MAX_VALUE - GCM_TAG_BYTES) null
        else pdfBytes + GCM_TAG_BYTES
}
