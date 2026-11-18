package id.cipherstego.android.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val CipherBlue = Color(0xFF0A45A4)
private val CipherBackground = Color(0xFFF7F9FC)
private val CipherText = Color(0xFF191C1E)
private val CipherMuted = Color(0xFF434652)

private val CipherColorScheme = lightColorScheme(
    primary = CipherBlue,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD5DEFF),
    onPrimaryContainer = Color(0xFF001947),
    secondary = Color(0xFF555F6F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD6E0F3),
    onSecondaryContainer = Color(0xFF3D4757),
    background = CipherBackground,
    onBackground = CipherText,
    surface = Color.White,
    onSurface = CipherText,
    onSurfaceVariant = CipherMuted,
    outline = Color(0xFF737784),
)

@Composable
fun CipherStegoTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = CipherColorScheme,
        typography = Typography(),
        content = content,
    )
}
