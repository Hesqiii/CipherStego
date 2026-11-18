const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

let currentStego = null;
let currentPdf = null;
let currentEvaluation = null;
let sourcePdfHash = null;
let extractHeaderBytes = null;
let tamperedPng = null;
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

function headerFromCanvasPixels(imageData) {
  const { data, width, height } = imageData;
  const byteSamples = [];
  for (let pixel = 0; pixel < width * height && byteSamples.length < 256; pixel += 1) {
    const start = pixel * 4;
    byteSamples.push(data[start], data[start + 1], data[start + 2]);
  }
  if (byteSamples.length < 256) throw new Error("Citra terlalu kecil untuk memuat header 32 byte.");
  const bits = byteSamples.slice(0, 256).map((value) => value & 1);
  const bytes = new Uint8Array(32);
  for (let i = 0; i < bytes.length; i += 1) {
    let value = 0;
    for (let bit = 0; bit < 8; bit += 1) value = (value << 1) | bits[i * 8 + bit];
    bytes[i] = value;
  }
  return { bytes, bits };
}

async function headerFromImage(source) {
  const bitmap = await createImageBitmap(source);
  try {
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d", { willReadFrequently: true, colorSpace: "srgb" });
    if (!context) throw new Error("Canvas tidak tersedia untuk membaca visual header.");
    context.drawImage(bitmap, 0, 0);
    const rows = Math.ceil(86 / bitmap.width);
    const pixels = context.getImageData(0, 0, bitmap.width, Math.min(bitmap.height, rows));
    return { ...headerFromCanvasPixels(pixels), width: bitmap.width, height: bitmap.height };
  } finally {
    bitmap.close();
  }
}

function bytesToHex(bytes) {
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join(" ");
}

function addByteUnit(container, value, offset, changedValue = null) {
  const unit = document.createElement("div");
  unit.className = "byte-unit";
  const index = document.createElement("span");
  index.className = "byte-index";
  index.textContent = offset.toString(16).padStart(2, "0");
  index.setAttribute("aria-label", `Offset byte ${offset}`);
  unit.append(index);

  const bits = document.createElement("div");
  bits.className = "byte-bits";
  for (let shift = 7; shift >= 0; shift -= 1) {
    const bitValue = (value >> shift) & 1;
    const bit = document.createElement("span");
    bit.className = `bit${bitValue ? " is-one" : ""}`;
    const changed = changedValue !== null && (((value ^ changedValue) >> shift) & 1) === 1;
    if (changed) bit.classList.add("is-changed");
    bit.textContent = String(bitValue);
    bit.setAttribute("aria-label", `Byte ${offset}, bit ${shift}: ${bitValue}${changed ? ", berubah" : ""}`);
    bits.append(bit);
  }
  unit.append(bits);
  container.append(unit);
}

function renderByteField(bytes, changedBytes, id, start) {
  const view = $(id);
  view.replaceChildren();
  bytes.forEach((value, index) => addByteUnit(
    view,
    value,
    start + index,
    changedBytes ? changedBytes[start + index] : null,
  ));
}

function renderHeader(header, previous = null) {
  const bytes = header.bytes;
  const changedBytes = previous?.bytes || null;
  const fields = [
    { start: 0, length: 16, hex: "#salt-hex", bits: "#salt-bits" },
    { start: 16, length: 12, hex: "#nonce-hex", bits: "#nonce-bits" },
    { start: 28, length: 4, hex: "#length-hex", bits: "#length-bits" },
  ];
  for (const field of fields) {
    $(field.hex).textContent = bytesToHex(bytes.slice(field.start, field.start + field.length));
    renderByteField(bytes.slice(field.start, field.start + field.length), changedBytes, field.bits, field.start);
  }
  const length = new DataView(bytes.buffer, bytes.byteOffset + 28, 4).getUint32(0, false);
  $("#length-reading").textContent = `Panjang ciphertext dari header: ${length.toLocaleString("id-ID")} byte.`;
  $("#header-dimensions").textContent = `${header.width} × ${header.height} px`;
  $("#header-placeholder").hidden = true;
  $("#extract-header-fields").hidden = false;
}

function showHeaderReadError(message) {
  $("#header-placeholder").textContent = message;
  $("#header-placeholder").hidden = false;
  $("#extract-header-fields").hidden = true;
  $("#header-dimensions").textContent = "";
}

function setTraceState(stage, state, label) {
  const item = $(`[data-stage="${stage}"]`, $("#extract-trace"));
  item.dataset.state = state;
  $(".trace-state", item).textContent = label;
}

function resetTrace() {
  ["header", "derive", "positions", "bits", "tag"].forEach((stage) => setTraceState(stage, "", "Menunggu"));
  $("#trace-total").textContent = "";
  $("#extract-result").hidden = true;
  $("#recovered-hash").hidden = true;
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
  result.textContent = message;
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
  $("#recovered-hash").hidden = true;
  if (error.kind === "authentication" || error.code === "tag_invalid") {
    markAuthenticatedFlow(false, null);
    showResult("Tag GCM ditolak. Passphrase salah, mode berbeda, atau data berubah.", "error");
    setStatus($("#extract-status"), "Ekstrak dan verifikasi PDF ditolak oleh tag GCM.", "error");
    return;
  }

  if (error.kind === "server") {
    ["header", "derive", "positions", "bits", "tag"].forEach((stage) => setTraceState(stage, "", "Tanpa data"));
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
  setTraceState("header", "rejected", type === "format" ? "Format ditolak" : "Tidak terbaca");
  $("#trace-total").textContent = "Total waktu tidak tersedia";
  showResult(messages[type], "neutral");
  setStatus($("#extract-status"), messages[type], "");
}

async function readAndRenderSelectedHeader(file) {
  resetTrace();
  $("#extract-result").hidden = true;
  currentPdf = null;
  $("#tamper-download").hidden = true;
  tamperedPng = null;
  if (!file) {
    extractHeaderBytes = null;
    $("#extract-file-name").textContent = "Pilih citra stego untuk membaca headernya";
    $("#extract-file-detail").textContent = "PNG RGB 24-bit";
    showHeaderReadError("Pilih citra stego untuk membaca headernya");
    setStatus($("#extract-status"), "Pilih citra stego untuk membaca headernya.");
    return;
  }

  $("#extract-file-name").textContent = file.name;
  $("#extract-file-detail").textContent = `${formatBytes(file.size)}, PNG RGB 24-bit`;
  try {
    const header = await headerFromImage(file);
    extractHeaderBytes = header.bytes;
    renderHeader(header);
    setTraceState("header", "done", "Terbaca secara visual");
    setStatus($("#extract-status"), "Header terbaca secara visual. Isi tetap harus diverifikasi oleh server.");
  } catch (error) {
    extractHeaderBytes = null;
    showHeaderReadError(`Header visual tidak dapat dibaca. ${error.message}`);
    setStatus($("#extract-status"), `Baca header gagal. ${error.message}`);
  }
}

$("#extract-file").addEventListener("change", (event) => readAndRenderSelectedHeader(event.target.files[0]));

async function runExtract(payload, statusButton = null) {
  resetTrace();
  setTraceState("header", "done", "Terbaca");
  const button = statusButton || $("#extract-submit");
  setBusy(button, true, "Memverifikasi tag AES-GCM…");
  setStatus($("#extract-status"), "Ekstrak dan verifikasi PDF sedang berjalan.");
  try {
    const mode = $('[name="extract-mode"]:checked').value;
    const result = await postJSON("/api/extract", { stego: payload, passphrase: $("#extract-passphrase").value, mode });
    currentPdf = result;
    markAuthenticatedFlow(true, result.metadata.elapsed_ms);
    showResult("Tag AES-GCM valid. PDF berhasil dipulihkan.", "success");
    const recoveredHash = $("#recovered-hash");
    recoveredHash.replaceChildren();
    const label = document.createElement("span");
    label.textContent = sourcePdfHash ? "SHA-256 PDF pulih dibandingkan dengan hash sisipan terakhir pada sesi ini" : "SHA-256 PDF pulih sebagai fingerprint";
    const code = document.createElement("code");
    code.textContent = result.metadata.sha256;
    recoveredHash.append(label, code);
    if (sourcePdfHash) {
      const comparison = document.createElement("span");
      comparison.className = "hash-comparison";
      comparison.textContent = result.metadata.sha256 === sourcePdfHash ? "Cocok" : "Tidak cocok";
      recoveredHash.append(comparison);
    }
    recoveredHash.hidden = false;
    $("#download-pdf").hidden = false;
    setStatus($("#extract-status"), "Ekstrak dan verifikasi PDF berhasil.", "success");
  } catch (error) {
    showExtractError(error);
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
    tamperedPng = null;
    $("#tamper-download").hidden = true;
    const payload = await readFilePayload(file);
    const header = await headerFromImage(file);
    extractHeaderBytes = header.bytes;
    renderHeader(header);
    await runExtract({ name: payload.name, data: payload.data });
  } catch (error) {
    showExtractError(error);
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
  setBusy(button, true, "Mengubah bit salt dan menguji tag…");
  $("#tamper-download").hidden = true;
  try {
    const source = await readFilePayload(file);
    const changed = await postJSON("/api/tamper", { stego: { name: source.name, data: source.data } });
    tamperedPng = changed;
    const originalHeader = extractHeaderBytes ? { bytes: extractHeaderBytes } : await headerFromImage(file);
    const alteredHeader = await headerFromImage(new Blob([bytesFromBase64(changed.png_base64)], { type: "image/png" }));
    renderHeader(alteredHeader, originalHeader);
    $("#tamper-download").hidden = false;
    await runExtract({ name: changed.filename, data: changed.png_base64 }, button);
  } catch (error) {
    showExtractError(error);
    setStatus($("#extract-status"), `Simulasi tamper gagal. ${error.message}`);
  } finally {
    setBusy(button, false);
  }
});

$("#download-tampered").addEventListener("click", () => {
  if (tamperedPng) downloadBase64(tamperedPng.png_base64, tamperedPng.filename, "image/png");
});

$("#download-pdf").addEventListener("click", () => {
  if (currentPdf) downloadBase64(currentPdf.pdf_base64, currentPdf.filename, "application/pdf");
});

$("#extract-passphrase").addEventListener("input", () => {
  if ($( "#extract-result").dataset.kind === "error") resetTrace();
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
});

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
    $("#stego-preview").src = `data:image/png;base64,${result.png_base64}`;
    $("#embed-result-name").textContent = result.filename;
    const metadata = result.metadata;
    sourcePdfHash = metadata.source_sha256;
    const items = [
      ["Metode", mode === "randomized" ? "Key-Based Randomized LSB" : "Sequential LSB"],
      ["Resolusi", `${metadata.width} × ${metadata.height} px`],
      ["PDF sumber", formatBytes(metadata.source_bytes)],
      ["Ciphertext dan tag", formatBytes(metadata.ciphertext_bytes)],
      ["Kapasitas terpakai", `${formatNumber(metadata.capacity_used_percent, 2)}%`],
      ["Waktu proses", `${formatNumber(metadata.elapsed_ms, 2)} ms`],
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
    $("#embed-hash").textContent = `SHA-256 sumber  ${metadata.source_sha256}`;
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
