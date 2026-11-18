package id.cipherstego.android.core.files

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PayloadCapacityTest {
    @Test
    fun calculatesCapacityForKnownRgbDimensions() {
        assertEquals(30_000L, PayloadCapacity.totalRgbCapacityBits(100, 100))
        assertEquals(3_750L, PayloadCapacity.totalRgbCapacityBytes(100, 100))
        assertEquals(3_718L, PayloadCapacity.maxCiphertextBytes(100, 100))
    }

    @Test
    fun includesGcmTagInEstimatedCiphertextSize() {
        assertEquals(116L, PayloadCapacity.estimatedCiphertextBytes(100L))
        assertNull(PayloadCapacity.estimatedCiphertextBytes(-1L))
        assertNull(PayloadCapacity.estimatedCiphertextBytes(Long.MAX_VALUE))
    }
}
