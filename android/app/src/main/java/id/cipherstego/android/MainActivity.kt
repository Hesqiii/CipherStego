package id.cipherstego.android

import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.cipherstego.android.core.files.PayloadCapacity
import id.cipherstego.android.core.files.PdfSelection
import id.cipherstego.android.core.files.PngSelection
import id.cipherstego.android.feature.workflow.CipherStegoUiState
import id.cipherstego.android.feature.workflow.CipherStegoViewModel
import id.cipherstego.android.feature.workflow.EmbeddingMethod
import id.cipherstego.android.feature.workflow.FileTask
import id.cipherstego.android.ui.theme.CipherStegoTheme
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { CipherStegoTheme { CipherStegoApp() } }
    }
}

private enum class Destination(val label: String, val title: String) {
    Protect("Kirim", "Embed & Encrypt"),
    Recover("Terima", "Extract & Decrypt"),
    Evaluate("Evaluasi", "Evaluation & Benchmark"),
}

@Composable
private fun CipherStegoApp(viewModel: CipherStegoViewModel = viewModel()) {
    var selectedIndex by rememberSaveable { mutableIntStateOf(0) }
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val pdfPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) {
        it?.let { uri -> keepReadPermission(context, uri); viewModel.selectPdf(uri) }
    }
    val senderImagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) {
        it?.let { uri -> keepReadPermission(context, uri); viewModel.selectSenderImage(uri) }
    }
    val receiverImagePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) {
        it?.let { uri -> keepReadPermission(context, uri); viewModel.selectReceiverImage(uri) }
    }
    val futurePdfSaver = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/pdf"),
    ) { uri -> if (uri != null) viewModel.clearMessage() }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                Destination.entries.forEachIndexed { index, item ->
                    val icon = when (item) {
                        Destination.Protect -> Icons.Outlined.Lock
                        Destination.Recover -> Icons.Outlined.LockOpen
                        Destination.Evaluate -> Icons.Outlined.BarChart
                    }
                    NavigationBarItem(
                        selected = selectedIndex == index,
                        onClick = {
                            viewModel.onDestinationChanged(selectedIndex)
                            selectedIndex = index
                        },
                        icon = { Icon(icon, contentDescription = null) },
                        label = { Text(item.label) },
                    )
                }
            }
        },
    ) { insets ->
        Column(
            modifier = Modifier.fillMaxSize().padding(insets).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Column(
                modifier = Modifier.fillMaxWidth().widthIn(max = 720.dp).align(Alignment.CenterHorizontally)
                    .padding(horizontal = 20.dp, vertical = 24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                val destination = Destination.entries[selectedIndex]
                Text("CIPHERSTEGO", style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                Text(destination.title, style = MaterialTheme.typography.headlineMedium)
                Text(
                    when (destination) {
                        Destination.Protect -> "Pilih dokumen dan citra penutup untuk menyiapkan proses."
                        Destination.Recover -> "Pilih citra stego untuk menyiapkan pemulihan dokumen."
                        Destination.Evaluate -> "Hasil eksperimen akan tersedia setelah mesin benchmark dibuat."
                    },
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                state.message?.let { StatusMessage(it, state.messageIsError) }

                when (destination) {
                    Destination.Protect -> SenderScreen(
                        state,
                        onSelectPdf = { pdfPicker.launch(arrayOf("application/pdf")) },
                        onSelectImage = { senderImagePicker.launch(arrayOf("image/png")) },
                        onMethod = viewModel::setEmbeddingMethod,
                        onPassphrase = viewModel::setSenderPassphrase,
                        onAction = viewModel::reportUnavailable,
                    )
                    Destination.Recover -> ReceiverScreen(
                        state,
                        onSelectImage = { receiverImagePicker.launch(arrayOf("image/png")) },
                        onMethod = viewModel::setReceiverMethod,
                        onPassphrase = viewModel::setReceiverPassphrase,
                        onAction = viewModel::reportUnavailable,
                        onChooseOutput = { futurePdfSaver.launch("recovered.pdf") },
                    )
                    Destination.Evaluate -> EvaluationScreen()
                }

                state.activeTask?.let {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        Text(
                            if (it == FileTask.Pdf) "Memeriksa PDF…" else "Memeriksa PNG…",
                            Modifier.padding(start = 10.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SenderScreen(
    state: CipherStegoUiState,
    onSelectPdf: () -> Unit,
    onSelectImage: () -> Unit,
    onMethod: (EmbeddingMethod) -> Unit,
    onPassphrase: (String) -> Unit,
    onAction: () -> Unit,
) {
    SectionCard("Dokumen PDF", Icons.Outlined.PictureAsPdf) {
        Text("Pilih dokumen sumber. Metadata dan signature dibaca melalui Android Storage Access Framework.")
        OutlinedButton(onClick = onSelectPdf, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.PictureAsPdf, null); Text("Pilih file PDF", Modifier.padding(start = 8.dp))
        }
        state.pdf?.let { PdfDetails(it) } ?: EmptyHint("Belum ada PDF dipilih.")
    }
    SectionCard("Citra penutup", Icons.Outlined.Image) {
        Text("Diperlukan PNG truecolor RGB 24-bit (8-bit per kanal).")
        OutlinedButton(onClick = onSelectImage, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.Image, null); Text("Pilih citra PNG", Modifier.padding(start = 8.dp))
        }
        state.senderImage?.let { PngDetails(it) }
            ?: EmptyHint("Pratinjau, dimensi, dan validasi PNG akan tampil setelah memilih file.")
    }
    state.senderImage?.takeIf { it.isSupportedRgb24 }?.let { CapacityCard(it, state.pdf) }
    SectionCard("Metode penyisipan", Icons.Outlined.Lock) { MethodSelector(state.selectedMethod, onMethod) }
    SectionCard("Passphrase", Icons.Outlined.Lock) {
        PassphraseField(state.senderPassphrase, onPassphrase)
        Text("Hanya disimpan sementara di memori dan dibersihkan saat berpindah bagian.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    Button(onClick = onAction, enabled = false, modifier = Modifier.fillMaxWidth().height(52.dp)) {
        Text("Encrypt & Embed")
    }
    EmptyHint("Belum tersedia pada milestone ini. Tidak ada enkripsi atau file output yang dibuat.")
}

@Composable
private fun ReceiverScreen(
    state: CipherStegoUiState,
    onSelectImage: () -> Unit,
    onMethod: (EmbeddingMethod) -> Unit,
    onPassphrase: (String) -> Unit,
    onAction: () -> Unit,
    onChooseOutput: () -> Unit,
) {
    SectionCard("Citra stego", Icons.Outlined.Image) {
        Text("Pilih PNG untuk pemeriksaan awal.")
        OutlinedButton(onClick = onSelectImage, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.Image, null); Text("Pilih citra PNG", Modifier.padding(start = 8.dp))
        }
        state.receiverImage?.let { PngDetails(it) } ?: EmptyHint("Belum ada citra stego dipilih.")
    }
    SectionCard("Validasi header", Icons.Outlined.LockOpen) {
        Text("Belum diperiksa. Validasi header 32-byte tersedia bersama mesin ekstraksi.")
        Text("Status: belum tersedia", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    SectionCard("Metode penyisipan", Icons.Outlined.LockOpen) { MethodSelector(state.receiverMethod, onMethod) }
    SectionCard("Passphrase", Icons.Outlined.Lock) {
        PassphraseField(state.receiverPassphrase, onPassphrase)
        Text("Hanya berada di memori dan dibersihkan saat berpindah bagian.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    Button(onClick = onAction, enabled = false, modifier = Modifier.fillMaxWidth().height(52.dp)) {
        Text("Extract & Decrypt")
    }
    EmptyHint("Ekstraksi dan dekripsi belum tersedia pada milestone ini.")
    SectionCard("Output PDF", Icons.Outlined.PictureAsPdf) {
        EmptyHint("Belum ada dokumen hasil. File baru dapat disimpan setelah ekstraksi tersedia.")
        OutlinedButton(onClick = onChooseOutput, enabled = false, modifier = Modifier.fillMaxWidth()) {
            Text("Pilih lokasi simpan (CreateDocument)")
        }
        Text("Nama bawaan: recovered.pdf. Jika nama itu sudah dipakai, pilih nama unik pada dialog simpan.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun EvaluationScreen() {
    Text("Hasil eksperimen tampil setelah benchmark diimplementasikan. Tidak ada nilai simulasi.",
        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    SectionCard("Metrik eksperimen", Icons.Outlined.BarChart) {
        listOf("MSE", "PSNR", "SSIM", "Waktu embedding", "Waktu extraction",
            "Analisis chi-square", "Analisis RS").forEachIndexed { i, metric ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(metric, style = MaterialTheme.typography.bodyLarge)
                Text("Belum tersedia", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (i != 6) HorizontalDivider()
        }
    }
    SectionCard("Perbandingan metode", Icons.Outlined.BarChart) {
        Text("Sequential LSB dan Key-Based Randomized LSB")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ComparisonColumn("Sequential LSB", Modifier.weight(1f))
            ComparisonColumn("Key-Based Randomized LSB", Modifier.weight(1f))
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, null, tint = MaterialTheme.colorScheme.primary)
                Text(title, Modifier.padding(start = 10.dp), style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold)
            }
            content()
        }
    }
}

@Composable
private fun PdfDetails(pdf: PdfSelection) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(pdf.metadata.displayName, style = MaterialTheme.typography.titleSmall)
        Text("Ukuran: ${pdf.metadata.sizeBytes?.let(::formatBytes) ?: "Tidak diketahui"}")
        Text("Jenis: PDF (application/pdf)")
        Text("Validasi: signature PDF terdeteksi", color = MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun PngDetails(image: PngSelection) {
    image.preview?.let {
        Image(it.asImageBitmap(), "Pratinjau ${image.metadata.displayName}",
            Modifier.fillMaxWidth().heightIn(max = 280.dp).background(
                MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(14.dp)),
            contentScale = androidx.compose.ui.layout.ContentScale.Fit)
    }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(image.metadata.displayName, style = MaterialTheme.typography.titleSmall)
        Text("Ukuran: ${image.metadata.sizeBytes?.let(::formatBytes) ?: "Tidak diketahui"}")
        Text("Dimensi: ${image.width} × ${image.height} px")
        Text("Format: PNG, bit depth ${image.bitDepth}, color type ${image.colorType}")
        Text(image.validationMessage,
            color = if (image.isSupportedRgb24) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
    }
}

@Composable
private fun CapacityCard(image: PngSelection, pdf: PdfSelection?) {
    SectionCard("Kapasitas payload", Icons.Outlined.BarChart) {
        CapacityRow("Total kapasitas RGB", "${formatBytes(image.totalRgbCapacityBytes)} (${image.totalRgbCapacityBits} bit)")
        CapacityRow("Header yang dicadangkan", "32 byte")
        CapacityRow("Kapasitas ciphertext maksimum", formatBytes(image.ciphertextCapacityBytes))
        HorizontalDivider()
        val size = pdf?.metadata?.sizeBytes
        when {
            pdf == null -> EmptyHint("Pilih PDF untuk memperkirakan penggunaan kapasitas.")
            !image.isSupportedRgb24 -> Text("Pilih PNG RGB 24-bit yang valid untuk menghitung payload.")
            size == null -> Text("Ukuran PDF tidak disediakan penyedia; estimasi belum tersedia.")
            else -> {
                val required = PayloadCapacity.estimatedCiphertextBytes(size)
                if (required == null) {
                    Text("Ukuran PDF terlalu besar untuk estimasi aman.")
                    return@SectionCard
                }
                val fits = required <= image.ciphertextCapacityBytes
                val percent = if (image.ciphertextCapacityBytes > 0L)
                    required.toDouble() / image.ciphertextCapacityBytes * 100.0 else 0.0
                Text("Estimasi ciphertext: ${formatBytes(required)} (PDF + tag GCM 16 byte)")
                Text(if (fits) "Estimasi penggunaan: ${formatPercent(percent)}% — muat"
                    else "Estimasi ciphertext melebihi kapasitas citra.",
                    color = if (fits) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.Medium)
            }
        }
        Text("Mengikuti 8 × (32 + L) ≤ W × H × 3. Total RGB mencakup seluruh bit LSB; kapasitas payload mengurangi header 32 byte.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun CapacityRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun MethodSelector(selected: EmbeddingMethod, onSelected: (EmbeddingMethod) -> Unit) {
    EmbeddingMethod.entries.forEach { method ->
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected == method, onClick = { onSelected(method) })
            Text(method.label, Modifier.padding(start = 4.dp), style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
private fun PassphraseField(value: String, onValueChange: (String) -> Unit) {
    var visible by remember { mutableStateOf(false) }
    OutlinedTextField(
        value, onValueChange, modifier = Modifier.fillMaxWidth(), label = { Text("Passphrase") }, singleLine = true,
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        trailingIcon = {
            IconButton(onClick = { visible = !visible }) {
                Icon(if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                    contentDescription = if (visible) "Sembunyikan passphrase" else "Tampilkan passphrase")
            }
        },
    )
}

@Composable
private fun StatusMessage(message: String, error: Boolean) {
    val color = if (error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
    Surface(color = color.copy(alpha = 0.08f), contentColor = color, shape = RoundedCornerShape(14.dp),
        modifier = Modifier.fillMaxWidth()) {
        Text(message, Modifier.padding(14.dp), style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun EmptyHint(text: String) {
    Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
}

@Composable
private fun ComparisonColumn(title: String, modifier: Modifier) {
    Column(modifier.background(MaterialTheme.colorScheme.background, RoundedCornerShape(14.dp)).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        listOf("MSE", "PSNR", "SSIM", "Chi-square", "RS").forEach {
            Text("$it: —", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun keepReadPermission(context: Context, uri: Uri) {
    try {
        context.contentResolver.takePersistableUriPermission(uri, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
    } catch (_: SecurityException) {
        // Some document providers issue a temporary read grant only.
    }
}

private fun formatPercent(value: Double): String = String.format(Locale.US, "%.1f", value)

private fun formatBytes(bytes: Long): String {
    if (bytes < 1024L) return "$bytes B"
    val units = listOf("KiB", "MiB", "GiB", "TiB")
    var value = bytes.toDouble()
    var index = -1
    do { value /= 1024.0; index++ } while (value >= 1024.0 && index < units.lastIndex)
    return String.format(Locale.getDefault(), "%.1f %s", value, units[index])
}
