const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

let currentStego = null;
let currentPdf = null;
let currentEvaluation = null;
let planeInput = null;

function setStatus(element, message, kind = "") {
  element.textContent = message;
  if (kind) element.dataset.kind = kind;
  else delete element.dataset.kind;
}

function setBusy(button, busy, busyLabel) {
  if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent.trim();
  button.disabled = busy;
  button.textContent = busy ? busyLabel : button.dataset.idleLabel;
}

function bytesFromBase64(value) {
  const binary = atob(value);
  const result = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) result[i] = binary.charCodeAt(i);
  return result;
}

function downloadBytes(bytes, filename, type) {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1200);
}

function downloadBase64(value, filename, type) {
  downloadBytes(bytesFromBase64(value), filename, type);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} byte`;
  return `${(bytes / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} KiB`;
}

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString("id-ID", { maximumFractionDigits: digits });
}

async function readFilePayload(file) {
  if (!file) throw new Error("Pilih berkas terlebih dahulu.");
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return { name: file.name, data: btoa(binary), buffer };
}

async function postJSON(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error || "Permintaan lokal gagal.");
    error.kind = body.kind || "server";
    error.code = body.code || "";
    error.status = response.status;
    throw error;
  }
  return body;
}

function showView(name) {
  $$(".view").forEach((section) => {
    const active = section.id === `view-${name}`;
    section.hidden = !active;
    section.classList.toggle("active", active);
  });
  $$(".nav-link").forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  window.scrollTo(0, 0);
}

$$('[data-view]').forEach((control) => control.addEventListener("click", (event) => {
  event.preventDefault();
  showView(control.dataset.view);
}));

$$('[data-password-toggle]').forEach((button) => button.addEventListener("click", () => {
  const input = document.getElementById(button.dataset.passwordToggle);
  const visible = input.type === "password";
  input.type = visible ? "text" : "password";
  button.setAttribute("aria-label", visible ? "Sembunyikan passphrase" : "Tampilkan passphrase");
  button.setAttribute("aria-pressed", String(visible));
}));

function setTraceState(stage, state, label) {
  const item = $(`[data-stage="${stage}"]`, $("#extract-trace"));
  item.dataset.state = state;
  const mark = $(".trace-mark", item);
  mark.textContent = state === "done" ? "✓" : state === "rejected" ? "×" : state === "pending" ? "○" : "—";
  $(".trace-state", item).setAttribute("aria-label", label || "Belum dijalankan");
  $(".trace-state", item).textContent = label;
}

function resetTrace() {
  ["header", "derive", "positions", "bits", "tag"].forEach((stage) => setTraceState(stage, "pending", ""));
  $("#trace-total").textContent = "";
  $("#extract-result").hidden = true;
  $("#recovered-details").hidden = true;
  $("#download-pdf").hidden = true;
}

function markAuthenticatedFlow(success, elapsed) {
  ["header", "derive", "positions", "bits"].forEach((stage) => setTraceState(stage, "done", "Dicapai"));
  setTraceState("tag", success ? "done" : "rejected", success ? "Valid" : "Ditolak");
  $("#trace-total").textContent = elapsed === null || elapsed === undefined
    ? "Total waktu tidak tersedia"
    : `Total ${formatNumber(elapsed, 2)} ms`;
}

function showResult(message, kind) {
  const result = $("#extract-result");
  $("#extract-result-message").textContent = message;
  result.dataset.kind = kind;
  result.hidden = false;
}

function classifyInputError(error) {
  if (error.code === "header_invalid" || /header|field panjang/i.test(error.message)) return "header";
  if (error.code === "capacity_exceeded" || /kapasitas|melewati batas/i.test(error.message)) return "capacity";
  if (error.code === "unsupported_format" || /PNG RGB|berkas penampung harus berupa PNG|tanda tangan PDF|tidak dapat dibaca/i.test(error.message)) return "format";
  return "input";
}

function showExtractError(error) {
  $("#recovered-details").hidden = true;
  if (error.kind === "authentication" || error.code === "tag_invalid") {
    markAuthenticatedFlow(false, null);
    showResult("Tag GCM ditolak. Passphrase salah, mode salah, atau data berubah. Tidak ada PDF yang dihasilkan.", "error");
    setStatus($("#extract-status"), "Ekstrak dan verifikasi PDF ditolak oleh tag GCM.", "error");
    return;
  }

  if (error.kind === "server") {
    ["header", "derive", "positions", "bits", "tag"].forEach((stage) => setTraceState(stage, "unreached", "Tidak dilaporkan"));
    $("#trace-total").textContent = "Total waktu tidak tersedia";
    showResult(error.message, "neutral");
    setStatus($("#extract-status"), error.message, "");
    return;
  }

  const type = classifyInputError(error);
  const messages = {
    capacity: `Kapasitas tidak cukup. ${error.message}`,
    format: `Format berkas tidak didukung. ${error.message}`,
    header: `Header tidak valid. ${error.message}`,
    input: error.message,
  };
  ["header", "derive", "positions", "bits", "tag"].forEach((stage) => setTraceState(stage, "unreached", "Tidak dicapai"));
  $("#trace-total").textContent = "Total waktu tidak tersedia";
  showResult(messages[type], "neutral");
  setStatus($("#extract-status"), messages[type], "");
}

function updateSelectedFile(file) {
  resetTrace();
  $("#extract-result").hidden = true;
  currentPdf = null;
  $("#extract-file-name").textContent = file ? file.name : "Pilih citra stego";
  setStatus($("#extract-status"), file ? "Passphrase diperlukan untuk menjalankan verifikasi." : "Pilih citra stego, lalu masukkan passphrase.");
}

function syncExtractActions() {
  const hasFile = Boolean($("#extract-file").files[0]);
  $("#extract-submit").disabled = !(hasFile && $("#extract-passphrase").value.length > 0);
  $("#tamper-test").disabled = !hasFile;
}

$("#extract-file").addEventListener("change", (event) => {
  syncExtractActions();
  updateSelectedFile(event.target.files[0]);
});
$("#extract-passphrase").addEventListener("input", syncExtractActions);

async function runExtract(payload, statusButton = null) {
  resetTrace();
  const button = statusButton || $("#extract-submit");
  setBusy(button, true, "Memverifikasi tag AES-GCM…");
  setStatus($("#extract-status"), "Ekstrak dan verifikasi PDF sedang berjalan.");
  try {
    const mode = $('[name="extract-mode"]:checked').value;
    const result = await postJSON("/api/extract", { stego: payload, passphrase: $("#extract-passphrase").value, mode });
    currentPdf = result;
    markAuthenticatedFlow(true, result.metadata.elapsed_ms);
    showResult("Tag AES-GCM valid. PDF berhasil dipulihkan.", "success");
    $("#recovered-hash").textContent = result.metadata.sha256;
    $("#recovered-size").textContent = formatBytes(result.metadata.pdf_bytes);
    $("#recovered-details").hidden = false;
    $("#download-pdf").hidden = false;
    setStatus($("#extract-status"), "Ekstrak dan verifikasi PDF berhasil.", "success");
  } catch (error) {
    if (error.kind) showExtractError(error);
    else {
      showResult(`Pemrosesan gagal. ${error.message}`, "neutral");
      setStatus($("#extract-status"), `Pemrosesan gagal. ${error.message}`);
    }
  } finally {
    setBusy(button, false);
  }
}

$("#extract-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("#extract-file").files[0];
  if (!file) {
    $("#extract-file").reportValidity();
    return;
  }
  try {
    const payload = await readFilePayload(file);
    await runExtract({ name: payload.name, data: payload.data });
  } catch (error) {
    showResult(`Berkas tidak dapat dibaca. ${error.message}`, "neutral");
    setStatus($("#extract-status"), `Berkas tidak dapat dibaca. ${error.message}`);
  }
});

$("#tamper-test").addEventListener("click", async (event) => {
  const file = $("#extract-file").files[0];
  if (!file || !$("#extract-passphrase").value) {
    if (!file) $("#extract-file").reportValidity();
    else $("#extract-passphrase").reportValidity();
    return;
  }
  const button = event.currentTarget;
  setBusy(button, true, "Mengubah data dan menguji tag…");
  resetTrace();
  try {
    const source = await readFilePayload(file);
    const changed = await postJSON("/api/tamper", { stego: { name: source.name, data: source.data } });
    await runExtract({ name: changed.filename, data: changed.png_base64 }, button);
  } catch (error) {
    if (error.kind) showExtractError(error);
    else {
      showResult(`Uji perubahan gagal. ${error.message}`, "neutral");
      setStatus($("#extract-status"), `Uji perubahan gagal. ${error.message}`);
    }
  } finally {
    setBusy(button, false);
  }
});

$("#download-pdf").addEventListener("click", () => {
  if (currentPdf) downloadBase64(currentPdf.pdf_base64, currentPdf.filename, "application/pdf");
});

$("#extract-passphrase").addEventListener("input", () => {
  if ($("#extract-result").dataset.kind === "error") resetTrace();
});

function row(label, sequential, randomized, note = "") {
  const tr = document.createElement("tr");
  [label, sequential, randomized, note].forEach((value) => {
    const td = document.createElement("td");
    td.textContent = String(value);
    tr.append(td);
  });
  return tr;
}

function rsSummary(value) {
  return `${value.regular_positive}/${value.singular_positive} | ${value.regular_negative}/${value.singular_negative}`;
}

function renderEvaluation(data) {
  const sequential = data.results.find((item) => item.method === "sequential");
  const randomized = data.results.find((item) => item.method === "randomized");
  const table = $("#evaluation-table");
  table.replaceChildren();
  const rows = [
    row("Waktu proses", `${formatNumber(sequential.elapsed_ms, 2)} ms`, `${formatNumber(randomized.elapsed_ms, 2)} ms`, "Satu pengujian per metode"),
    row("MSE", formatNumber(sequential.mse, 8), formatNumber(randomized.mse, 8), "Lebih kecil berarti perubahan rata-rata lebih kecil"),
    row("PSNR", sequential.psnr_db === null ? "∞" : `${formatNumber(sequential.psnr_db)} dB`, randomized.psnr_db === null ? "∞" : `${formatNumber(randomized.psnr_db)} dB`, "Lebih besar biasanya berarti distorsi lebih rendah"),
    row("SSIM", formatNumber(sequential.ssim, 6), formatNumber(randomized.ssim, 6), "Nilai mendekati 1 berarti struktur lebih mirip"),
    row("Chi-square", `${sequential.chi_square.statistic} (p=${sequential.chi_square.p_value.toPrecision(3)})`, `${randomized.chi_square.statistic} (p=${randomized.chi_square.p_value.toPrecision(3)})`, "Uji pasangan histogram eksploratif"),
    row("RS Analysis", rsSummary(sequential.rs), rsSummary(randomized.rs), "R/S positif lalu negatif; bukan estimasi payload"),
    row("SHA-256 cocok", sequential.recovery_matches ? "Ya" : "Tidak", randomized.recovery_matches ? "Ya" : "Tidak", "Hash pemulihan dibandingkan dengan sumber"),
    row("Kanal berubah", sequential.changed_channels, randomized.changed_channels, "Jumlah kanal RGB yang berubah"),
  ];
  rows.forEach((tr) => table.append(tr));

  $("#metric-mse").textContent = `${formatNumber(sequential.mse, 6)} / ${formatNumber(randomized.mse, 6)}`;
  $("#metric-psnr").textContent = `${sequential.psnr_db === null ? "∞" : formatNumber(sequential.psnr_db)} / ${randomized.psnr_db === null ? "∞" : formatNumber(randomized.psnr_db)} dB`;
  $("#metric-ssim").textContent = `${formatNumber(sequential.ssim, 5)} / ${formatNumber(randomized.ssim, 5)}`;
  $("#evaluation-subtitle").textContent = `${data.source_name}, ${formatBytes(data.source_bytes)}, ${data.width} × ${data.height} px, ciphertext ${formatBytes(data.payload_ciphertext_bytes)}`;
  $("#evaluation-note").textContent = data.note;
  $("#evaluation-results").hidden = false;
}

async function imageDataFromBlob(blob) {
  const bitmap = await createImageBitmap(blob);
  try {
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d", { willReadFrequently: true, colorSpace: "srgb" });
    if (!context) throw new Error("Canvas tidak tersedia untuk visualisasi LSB.");
    context.drawImage(bitmap, 0, 0);
    return { pixels: context.getImageData(0, 0, bitmap.width, bitmap.height), width: bitmap.width, height: bitmap.height };
  } finally {
    bitmap.close();
  }
}

function paintLsbPlane(canvas, original, changed = null) {
  const { width, height, pixels } = original;
  const output = canvas.getContext("2d").createImageData(width, height);
  const source = pixels.data;
  const comparison = changed?.pixels.data;
  const target = output.data;
  for (let offset = 0; offset < source.length; offset += 4) {
    const differs = comparison !== undefined && (
      source[offset] !== comparison[offset]
      || source[offset + 1] !== comparison[offset + 1]
      || source[offset + 2] !== comparison[offset + 2]
    );
    if (differs) {
      target[offset] = 192;
      target[offset + 1] = 38;
      target[offset + 2] = 101;
    } else {
      target[offset] = (source[offset] & 1) * 255;
      target[offset + 1] = (source[offset + 1] & 1) * 255;
      target[offset + 2] = (source[offset + 2] & 1) * 255;
    }
    target[offset + 3] = 255;
  }
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").putImageData(output, 0, 0);
}

async function renderLsbPlanes() {
  const section = $("#plane-section");
  section.hidden = false;
  if (!planeInput) {
    $("#plane-status").textContent = "Pilih PDF dan cover PNG untuk membuat bidang LSB.";
    return;
  }

  let source;
  try {
    source = await imageDataFromBlob(new Blob([planeInput.cover.buffer], { type: "image/png" }));
  } catch (error) {
    $("#plane-status").textContent = `Bidang LSB tidak dapat dibuat. ${error.message}`;
    return;
  }
  if (source.width * source.height > 1_500_000) {
    $("#plane-status").textContent = "Visualisasi dilewati untuk cover di atas 1,5 juta piksel. Tabel evaluasi tetap berasal dari server.";
    return;
  }

  $("#plane-status").textContent = "Membuat dua keluaran penyisipan untuk perbandingan visual.";
  try {
    const common = {
      pdf: { name: planeInput.pdf.name, data: planeInput.pdf.data },
      cover: { name: planeInput.cover.name, data: planeInput.cover.data },
      passphrase: planeInput.passphrase,
    };
    const [sequentialResult, randomizedResult] = await Promise.all([
      postJSON("/api/embed", { ...common, mode: "sequential" }),
      postJSON("/api/embed", { ...common, mode: "randomized" }),
    ]);
    const [sequential, randomized] = await Promise.all([
      imageDataFromBlob(new Blob([bytesFromBase64(sequentialResult.png_base64)], { type: "image/png" })),
      imageDataFromBlob(new Blob([bytesFromBase64(randomizedResult.png_base64)], { type: "image/png" })),
    ]);
    paintLsbPlane($("#plane-original"), source);
    paintLsbPlane($("#plane-sequential"), sequential, source);
    paintLsbPlane($("#plane-randomized"), randomized, source);
    $("#plane-status").textContent = `${source.width} × ${source.height} px. Magenta menandai kanal RGB yang berubah.`;
  } catch (error) {
    $("#plane-status").textContent = `Visualisasi LSB gagal. ${error.message}`;
  }
}

$("#evaluate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#evaluate-submit");
  setBusy(button, true, "Mengevaluasi dua metode…");
  $("#evaluation-results").hidden = true;
  setStatus($("#evaluate-status"), "Evaluasi lokal sedang berjalan.");
  try {
    const pdf = await readFilePayload($("#evaluate-pdf").files[0]);
    const cover = await readFilePayload($("#evaluate-cover").files[0]);
    const passphrase = $("#evaluate-passphrase").value;
    if (passphrase.length < 12) throw new Error("Gunakan passphrase minimal 12 karakter.");
    const payload = {
      pdf: { name: pdf.name, data: pdf.data },
      cover: { name: cover.name, data: cover.data },
      passphrase,
    };
    currentEvaluation = await postJSON("/api/evaluate", payload);
    renderEvaluation(currentEvaluation);
    planeInput = { ...payload, pdf, cover };
    setStatus($("#evaluate-status"), "Evaluasi selesai. Visualisasi LSB mengikuti di bawah tabel.", "success");
    await renderLsbPlanes();
  } catch (error) {
    setStatus($("#evaluate-status"), error.message, "");
  } finally {
    setBusy(button, false);
  }
});

$("#download-csv").addEventListener("click", () => {
  if (!currentEvaluation) return;
  const sequential = currentEvaluation.results.find((item) => item.method === "sequential");
  const randomized = currentEvaluation.results.find((item) => item.method === "randomized");
  const rows = [
    ["Metrik", "Sequential LSB", "Key-Based Randomized LSB"],
    ["Waktu proses ms", sequential.elapsed_ms, randomized.elapsed_ms],
    ["MSE", sequential.mse, randomized.mse],
    ["PSNR dB", sequential.psnr_db, randomized.psnr_db],
    ["SSIM", sequential.ssim, randomized.ssim],
    ["Chi-square statistik", sequential.chi_square.statistic, randomized.chi_square.statistic],
    ["Chi-square p-value", sequential.chi_square.p_value, randomized.chi_square.p_value],
    ["RS positif dan negatif", rsSummary(sequential.rs), rsSummary(randomized.rs)],
    ["SHA-256 cocok", sequential.recovery_matches, randomized.recovery_matches],
    ["Kanal berubah", sequential.changed_channels, randomized.changed_channels],
  ];
  const csv = rows.map((values) => values.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
  downloadBytes(new TextEncoder().encode(`\uFEFF${csv}`), "cipherstego-evaluasi.csv", "text/csv;charset=utf-8");
});

function updateFileLabel(input, nameTarget, detailTarget = null) {
  input.addEventListener("change", () => {
    const file = input.files[0];
    $(nameTarget).textContent = file ? file.name : "Pilih berkas";
    if (detailTarget) $(detailTarget).textContent = file ? formatBytes(file.size) : "";
  });
}

updateFileLabel($("#evaluate-pdf"), "#evaluate-pdf-name");
updateFileLabel($("#evaluate-cover"), "#evaluate-cover-name");

function syncEvaluationAction() {
  const complete = $("#evaluate-pdf").files[0]
    && $("#evaluate-cover").files[0]
    && $("#evaluate-passphrase").value.length >= 12;
  $("#evaluate-submit").disabled = !complete;
}

$("#evaluate-pdf").addEventListener("change", syncEvaluationAction);
$("#evaluate-cover").addEventListener("change", syncEvaluationAction);
$("#evaluate-passphrase").addEventListener("input", syncEvaluationAction);

let selectedCoverBitmap = null;
let selectedPdfBytes = 0;
let maxPdfCapacity = 0;

function updateCapacity() {
  const fill = $("#embed-capacity-fill");
  const percent = maxPdfCapacity ? Math.min(100, selectedPdfBytes / maxPdfCapacity * 100) : 0;
  fill.style.width = `${percent}%`;
  $("#embed-capacity-value").textContent = maxPdfCapacity && selectedPdfBytes
    ? `${formatBytes(selectedPdfBytes)} / ${formatBytes(maxPdfCapacity)}`
    : "—";
}

$("#embed-pdf").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  selectedPdfBytes = file ? file.size : 0;
  $("#embed-pdf-name").textContent = file ? file.name : "Pilih dokumen PDF";
  $("#embed-pdf-detail").textContent = file ? `${formatBytes(file.size)}, PDF, maksimal 600 KiB` : "PDF, maksimal 600 KiB";
  updateCapacity();
  syncEmbedAction();
});

$("#embed-cover").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (selectedCoverBitmap) selectedCoverBitmap.close();
  selectedCoverBitmap = null;
  maxPdfCapacity = 0;
  $("#embed-cover-name").textContent = file ? file.name : "Pilih PNG RGB";
  $("#embed-cover-preview-wrap").hidden = true;
  if (!file) {
    $("#embed-capacity-help").textContent = "Kapasitas dihitung setelah citra dipilih.";
    updateCapacity();
    syncEmbedAction();
    return;
  }
  try {
    selectedCoverBitmap = await createImageBitmap(file);
    const { width, height } = selectedCoverBitmap;
    maxPdfCapacity = Math.max(0, Math.floor((width * height * 3 - 256) / 8) - 16);
    const preview = $("#embed-cover-preview");
    preview.src = URL.createObjectURL(file);
    preview.onload = () => URL.revokeObjectURL(preview.src);
    $("#embed-cover-dimensions").textContent = `${width} × ${height} px`;
    $("#embed-cover-preview-wrap").hidden = false;
    $("#embed-capacity-help").textContent = `Kapasitas payload PDF maksimum ${formatBytes(maxPdfCapacity)} setelah header dan tag GCM.`;
  } catch {
    $("#embed-capacity-help").textContent = "Citra tidak dapat dibaca. Pilih PNG RGB 24-bit yang valid.";
  }
  updateCapacity();
  syncEmbedAction();
});

function syncEmbedAction() {
  const complete = $("#embed-pdf").files[0]
    && $("#embed-cover").files[0]
    && $("#embed-passphrase").value.length >= 12;
  $("#embed-submit").disabled = !complete;
}

$("#embed-passphrase").addEventListener("input", syncEmbedAction);

$("#embed-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#embed-submit");
  setBusy(button, true, "Mengenkripsi dan menyisipkan…");
  $("#embed-result").hidden = true;
  $("#embed-placeholder").hidden = false;
  setStatus($("#embed-status"), "Enkripsi dan penyisipan lokal sedang berjalan.");
  try {
    const pdf = await readFilePayload($("#embed-pdf").files[0]);
    const cover = await readFilePayload($("#embed-cover").files[0]);
    const passphrase = $("#embed-passphrase").value;
    if (passphrase.length < 12) throw new Error("Gunakan passphrase minimal 12 karakter.");
    const mode = $('[name="embed-mode"]:checked').value;
    const result = await postJSON("/api/embed", {
      pdf: { name: pdf.name, data: pdf.data },
      cover: { name: cover.name, data: cover.data },
      passphrase,
      mode,
    });
    currentStego = result;
    const metadata = result.metadata;
    const items = [
      ["SHA-256 sumber", metadata.source_sha256],
      ["Ukuran PDF", formatBytes(metadata.source_bytes)],
      ["Kapasitas terpakai", `${formatNumber(metadata.capacity_used_percent, 2)}%`],
      ["Waktu", `${formatNumber(metadata.elapsed_ms, 2)} ms`],
    ];
    const list = $("#embed-metadata");
    list.replaceChildren();
    items.forEach(([term, value]) => {
      const dt = document.createElement("dt");
      dt.textContent = term;
      const dd = document.createElement("dd");
      dd.textContent = value;
      list.append(dt, dd);
    });
    $("#embed-placeholder").hidden = true;
    $("#embed-result").hidden = false;
    setStatus($("#embed-status"), "Enkripsi dan penyisipan berhasil.", "success");
  } catch (error) {
    setStatus($("#embed-status"), error.message, "");
  } finally {
    setBusy(button, false);
  }
});

$("#download-stego").addEventListener("click", () => {
  if (currentStego) downloadBase64(currentStego.png_base64, currentStego.filename, "image/png");
});

resetTrace();
syncExtractActions();
syncEvaluationAction();
syncEmbedAction();
