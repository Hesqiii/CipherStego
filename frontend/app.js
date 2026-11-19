const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const MAX_PDF_BYTES = 600 * 1024;
const MAX_PNG_BYTES = 16 * 1024 * 1024;
const MAX_IMAGE_PIXELS = 8_000_000;
const MIN_PASSPHRASE_LENGTH = 12;
const PNG_SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10];
const previewUrls = new Map();
const resultUrls = new Map();
const selectedFiles = new Map();

let apiReady = false;
let currentView = "embed";
let embedController = null;
let extractController = null;
let evaluationController = null;

function setSummary(target, title, detail, kind = "") {
  target.replaceChildren();
  const heading = document.createElement("strong");
  const description = document.createElement("span");
  heading.textContent = title;
  description.textContent = detail;
  target.append(heading, description);
  target.dataset.kind = kind;
  target.hidden = false;
}

function clearSummary(target) {
  target.replaceChildren();
  target.hidden = true;
  delete target.dataset.kind;
}

function setStatus(target, message, kind = "") {
  target.textContent = message;
  if (kind) target.dataset.kind = kind;
  else delete target.dataset.kind;
}

function revokeUrl(collection, key) {
  const url = collection.get(key);
  if (url) URL.revokeObjectURL(url);
  collection.delete(key);
}

function clearPreview(frame, image) {
  revokeUrl(previewUrls, image.id);
  image.removeAttribute("src");
  frame.hidden = true;
}

function showPreview(file, frame, image, caption) {
  clearPreview(frame, image);
  const url = URL.createObjectURL(file);
  previewUrls.set(image.id, url);
  image.src = url;
  caption.textContent = `${file.name} · ${formatBytes(file.size)}`;
  frame.hidden = false;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} byte`;
  return `${(bytes / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} KiB`;
}

function formatMilliseconds(value) {
  return `${Number(value).toLocaleString("id-ID", { maximumFractionDigits: 3 })} ms`;
}

function readResponseError(response, body) {
  if (typeof body?.detail === "string") return body.detail;
  if (typeof body?.error === "string") return body.error;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => item.msg || "Permintaan tidak valid.").join(" ");
  }
  return `Permintaan gagal dengan HTTP ${response.status}.`;
}

async function postJson(path, payload, signal) {
  let response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Backend lokal tidak dapat dihubungi. Pastikan run.bat masih berjalan.");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(readResponseError(response, body));
  return body;
}

async function checkLocalApi() {
  const status = $("#backend-status");
  const container = $(".topbar-status");
  apiReady = false;
  updateActionControls();
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || body.status !== "ok") throw new Error("Health check gagal.");
    apiReady = body.processing === "sender_receiver_available";
    if (!apiReady) throw new Error("Endpoint sender/receiver belum tersedia.");
    container.dataset.state = "ready";
    status.textContent = "API lokal aktif · kedua metode siap";
  } catch {
    apiReady = false;
    container.dataset.state = "unavailable";
    status.textContent = "Backend lokal tidak terjangkau";
  }
  updateActionControls();
}

async function isPdf(file) {
  if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
    return { ok: false, message: "Pilih berkas dengan ekstensi .pdf." };
  }
  if (file.size > MAX_PDF_BYTES) {
    return { ok: false, message: `Ukuran ${formatBytes(file.size)} melebihi batas 600 KiB.` };
  }
  if (file.size < 5) return { ok: false, message: "Berkas terlalu kecil untuk menjadi PDF yang valid." };
  const signature = new TextDecoder().decode(await file.slice(0, 5).arrayBuffer());
  if (signature !== "%PDF-") return { ok: false, message: "Signature PDF tidak ditemukan pada awal file." };
  return { ok: true, message: `${formatBytes(file.size)} · signature PDF terdeteksi di browser.` };
}

async function inspectPng(file) {
  if (!file || !file.name.toLowerCase().endsWith(".png")) {
    throw new Error("Pilih berkas dengan ekstensi .png.");
  }
  if (file.size > MAX_PNG_BYTES) {
    throw new Error("Ukuran PNG melebihi batas pemrosesan lokal 16 MiB.");
  }
  const bytes = new Uint8Array(await file.slice(0, 29).arrayBuffer());
  const signatureMatches = PNG_SIGNATURE.every((value, index) => bytes[index] === value);
  if (bytes.length !== 29 || !signatureMatches) throw new Error("Signature PNG tidak valid.");

  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const ihdrLength = view.getUint32(8, false);
  const ihdrName = String.fromCharCode(...bytes.slice(12, 16));
  const width = view.getUint32(16, false);
  const height = view.getUint32(20, false);
  const bitDepth = bytes[24];
  const colorType = bytes[25];
  if (ihdrLength !== 13 || ihdrName !== "IHDR" || width < 1 || height < 1) {
    throw new Error("Header PNG tidak valid.");
  }
  if (width * height > MAX_IMAGE_PIXELS) {
    throw new Error("Dimensi PNG melebihi batas pemrosesan lokal 8 megapiksel.");
  }
  if (bitDepth !== 8 || colorType !== 2) {
    throw new Error("Citra harus PNG truecolor RGB 8-bit tanpa alpha atau palette.");
  }

  let chunkOffset = 8;
  while (chunkOffset + 8 <= file.size) {
    const chunkHeader = new Uint8Array(await file.slice(chunkOffset, chunkOffset + 8).arrayBuffer());
    if (chunkHeader.length !== 8) throw new Error("Struktur chunk PNG tidak lengkap.");
    const chunkLength = new DataView(chunkHeader.buffer, chunkHeader.byteOffset, 4).getUint32(0, false);
    const chunkName = String.fromCharCode(...chunkHeader.subarray(4, 8));
    if (chunkOffset + chunkLength + 12 > file.size) throw new Error("Struktur chunk PNG tidak lengkap.");
    if (chunkName === "tRNS") throw new Error("PNG dengan transparency chunk tidak didukung; pilih RGB tanpa transparansi.");
    chunkOffset += chunkLength + 12;
    if (chunkName === "IDAT" || chunkName === "IEND") break;
  }

  const bitmap = await createImageBitmap(file);
  try {
    if (bitmap.width !== width || bitmap.height !== height) {
      throw new Error("Dimensi gambar berbeda dari informasi header PNG.");
    }
  } finally {
    bitmap.close();
  }
  return { width, height };
}

function capacityFor(width, height) {
  const slots = width * height * 3;
  const ciphertextBytes = Math.floor(slots / 8) - 32;
  const pdfBytes = Math.max(0, ciphertextBytes - 16);
  return { slots, ciphertextBytes: Math.max(0, ciphertextBytes), pdfBytes };
}

function updateCapacity() {
  const readout = $("#capacity-readout");
  const cover = selectedFiles.get("embed-cover");
  if (!cover?.ok) {
    readout.hidden = true;
    return;
  }

  const { slots, ciphertextBytes, pdfBytes } = capacityFor(cover.width, cover.height);
  const effectivePdfLimit = Math.min(MAX_PDF_BYTES, pdfBytes);
  const pdf = selectedFiles.get("embed-pdf");
  const selectedPdfBytes = pdf?.ok ? pdf.file.size : 0;
  const usedBytes = Math.min(effectivePdfLimit, selectedPdfBytes);
  const percentage = effectivePdfLimit > 0 ? Math.min(100, (usedBytes / effectivePdfLimit) * 100) : 0;

  $("#capacity-value").textContent = `${formatBytes(effectivePdfLimit)} maksimum`;
  $("#capacity-bar").style.width = `${percentage}%`;
  $("#capacity-detail").textContent = pdf?.ok
    ? `PDF ${formatBytes(selectedPdfBytes)} · ${formatBytes(ciphertextBytes)} tersedia untuk ciphertext dan tag · ${slots.toLocaleString("id-ID")} slot RGB.`
    : `Memperhitungkan header 32 byte dan tag GCM 16 byte · ${slots.toLocaleString("id-ID")} slot RGB. Batas PDF demo tetap 600 KiB.`;
  readout.hidden = false;
}

function updateActionControls({ refreshMessages = true } = {}) {
  const pdf = selectedFiles.get("embed-pdf");
  const cover = selectedFiles.get("embed-cover");
  const stego = selectedFiles.get("extract-stego");
  const embedPass = $("#embed-pass").value;
  const extractPass = $("#extract-pass").value;
  const mode = $("[name='embed-mode']:checked")?.value;
  const extractMode = $("[name='extract-mode']:checked")?.value;
  const coverPdfLimit = cover?.ok
    ? Math.min(MAX_PDF_BYTES, capacityFor(cover.width, cover.height).pdfBytes)
    : 0;

  $("#embed-submit").disabled = !(
    apiReady && pdf?.ok && cover?.ok && ["sequential", "randomized"].includes(mode)
    && pdf.file.size <= coverPdfLimit
    && embedPass.length >= MIN_PASSPHRASE_LENGTH
    && !embedController
  );
  $("#extract-submit").disabled = !(
    apiReady && stego?.ok && ["sequential", "randomized"].includes(extractMode)
    && extractPass.length >= MIN_PASSPHRASE_LENGTH
    && !extractController
  );

  const evaluationPdf = selectedFiles.get("evaluate-pdf");
  const evaluationCover = selectedFiles.get("evaluate-cover");
  const evaluationMode = $("[name='evaluate-mode']:checked")?.value;
  const evaluationCapacity = evaluationCover?.ok
    ? Math.min(MAX_PDF_BYTES, capacityFor(evaluationCover.width, evaluationCover.height).pdfBytes)
    : 0;
  const evaluationReady = apiReady && evaluationPdf?.ok && evaluationCover?.ok
    && evaluationPdf.file.size <= evaluationCapacity
    && ["sequential", "randomized"].includes(evaluationMode)
    && $("#evaluate-pass").value.length >= MIN_PASSPHRASE_LENGTH
    && !evaluationController;
  $("#evaluate-submit").disabled = !evaluationReady;

  if (refreshMessages && !embedController) {
    if (!apiReady) setStatus($("#embed-status"), "Menunggu backend lokal siap. Jalankan run.bat.");
    else if (!pdf?.ok || !cover?.ok) setStatus($("#embed-status"), "Pilih PDF dan PNG RGB yang valid.");
    else if (pdf.file.size > coverPdfLimit) setStatus($("#embed-status"), "PDF melebihi kapasitas PNG. Pilih PNG dengan kapasitas lebih besar.", "error");
    else if (embedPass.length < MIN_PASSPHRASE_LENGTH) setStatus($("#embed-status"), "Passphrase minimal 12 karakter.");
    else setStatus($("#embed-status"), "Siap mengenkripsi dan menyisipkan payload.");
  }
  if (refreshMessages && !extractController) {
    if (!apiReady) setStatus($("#extract-status"), "Menunggu backend lokal siap. Jalankan run.bat.");
    else if (!stego?.ok) setStatus($("#extract-status"), "Pilih stego-PNG RGB yang valid.");
    else if (extractPass.length < MIN_PASSPHRASE_LENGTH) setStatus($("#extract-status"), "Passphrase minimal 12 karakter.");
    else setStatus($("#extract-status"), "Siap mengekstrak dan memverifikasi payload.");
  }
  if (refreshMessages && !evaluationController) {
    if (!apiReady) setStatus($("#evaluate-status"), "Menunggu backend lokal siap. Jalankan run.bat.");
    else if (!evaluationPdf?.ok || !evaluationCover?.ok) setStatus($("#evaluate-status"), "Pilih PDF dan PNG RGB yang valid.");
    else if (evaluationPdf.file.size > evaluationCapacity) setStatus($("#evaluate-status"), "PDF melebihi kapasitas cover PNG.", "error");
    else if ($("#evaluate-pass").value.length < MIN_PASSPHRASE_LENGTH) setStatus($("#evaluate-status"), "Passphrase minimal 12 karakter.");
    else setStatus($("#evaluate-status"), "Siap menjalankan satu pengukuran evaluasi.");
  }
}

function syncMethodDetails() {
  const embedMode = $(`[name='embed-mode']:checked`)?.value || "sequential";
  const extractMode = $(`[name='extract-mode']:checked`)?.value || "sequential";
  const label = (mode) => mode === "randomized" ? "Key-Based Randomized LSB" : "Sequential LSB";
  $("#embed-method-stamp").textContent = label(embedMode);
  $("#extract-method-stamp").textContent = label(extractMode);
  $("#embed-kpos-note").hidden = embedMode !== "randomized";
  $("#extract-kpos-note").hidden = extractMode !== "randomized";
  $("#embed-process-sequence").textContent = embedMode === "randomized"
    ? "Salt → PBKDF2 → HKDF → AES-GCM → header sequential → ciphertext pada posisi acak berbasis K_pos"
    : "Salt → PBKDF2 → HKDF → AES-GCM → header + ciphertext → Sequential LSB";
}

function clearSenderResult() {
  if (embedController) embedController.abort();
  embedController = null;
  const button = $("#embed-submit");
  button.textContent = "Enkripsi dan sisipkan";
  button.removeAttribute("aria-busy");
  revokeUrl(resultUrls, "embed");
  $("#stego-result-preview").removeAttribute("src");
  $("#stego-result-caption").textContent = "";
  $("#stego-download").removeAttribute("href");
  $("#stego-download").removeAttribute("download");
  ["#embed-result-method", "#embed-result-dimensions", "#embed-result-payload", "#embed-result-capacity", "#embed-result-time", "#embed-result-hash"].forEach((selector) => {
    $(selector).textContent = "";
  });
  $("#embed-result").hidden = true;
  $("#embed-empty").hidden = false;
  setStatus($("#embed-result-status"), "");
  updateActionControls();
}

function clearReceiverResult() {
  if (extractController) extractController.abort();
  extractController = null;
  const button = $("#extract-submit");
  button.textContent = "Ekstrak dan verifikasi";
  button.removeAttribute("aria-busy");
  revokeUrl(resultUrls, "extract");
  $("#pdf-download").removeAttribute("href");
  $("#pdf-download").removeAttribute("download");
  ["#extract-result-method", "#extract-result-auth", "#extract-result-size", "#extract-result-time", "#extract-result-hash"].forEach((selector) => {
    $(selector).textContent = "";
  });
  $("#extract-result").hidden = true;
  $("#extract-empty").hidden = false;
  setStatus($("#extract-result-status"), "");
  updateActionControls();
}

function resetPasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  input.type = "password";
  const button = $(`[data-toggle-password='${inputId}']`);
  button.textContent = "Tampilkan";
  button.setAttribute("aria-pressed", "false");
}

function handlePdfChange(inputId, summaryId) {
  const input = document.getElementById(inputId);
  const summary = document.getElementById(summaryId);
  const file = input.files?.[0];
  clearSenderResult();
  selectedFiles.delete(inputId);
  updateActionControls();
  if (!file) {
    clearSummary(summary);
    updateCapacity();
    updateActionControls();
    return;
  }

  void isPdf(file).then((result) => {
    if (input.files?.[0] !== file) return;
    selectedFiles.set(inputId, { file, ok: result.ok });
    setSummary(summary, result.ok ? file.name : `${file.name} · tidak dapat digunakan`, result.message, result.ok ? "success" : "error");
    updateCapacity();
    updateActionControls();
  }).catch(() => {
    if (input.files?.[0] !== file) return;
    setSummary(summary, "Berkas tidak dapat diperiksa", "Pilih PDF yang dapat dibaca.", "error");
    updateActionControls();
  });
}

async function handlePngChange(inputId, summaryId, frameId, previewId, captionId) {
  const input = document.getElementById(inputId);
  const summary = document.getElementById(summaryId);
  const frame = document.getElementById(frameId);
  const preview = document.getElementById(previewId);
  const caption = document.getElementById(captionId);
  const file = input.files?.[0];
  if (inputId === "embed-cover") clearSenderResult();
  else clearReceiverResult();
  clearPreview(frame, preview);
  selectedFiles.delete(inputId);
  updateCapacity();
  updateActionControls();
  if (!file) {
    clearSummary(summary);
    updateCapacity();
    updateActionControls();
    return;
  }

  try {
    const dimensions = await inspectPng(file);
    if (input.files?.[0] !== file) return;
    selectedFiles.set(inputId, { file, ok: true, ...dimensions });
    setSummary(summary, file.name, `${dimensions.width} × ${dimensions.height} px · ${formatBytes(file.size)} · PNG RGB 8-bit. Backend akan mengulang validasi.`, "success");
    showPreview(file, frame, preview, caption);
  } catch (error) {
    if (input.files?.[0] !== file) return;
    setSummary(summary, `${file.name} · tidak dapat digunakan`, error.message, "error");
  }
  updateCapacity();
  updateActionControls();
}

function attachDropZone(zone) {
  const input = document.getElementById(zone.dataset.for);
  zone.addEventListener("dragover", (event) => {
    event.preventDefault();
    zone.classList.add("drag-active");
  });
  zone.addEventListener("dragleave", (event) => {
    if (!zone.contains(event.relatedTarget)) zone.classList.remove("drag-active");
  });
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("drag-active");
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function fileToBase64(file) {
  return file.arrayBuffer().then((buffer) => {
    const bytes = new Uint8Array(buffer);
    const parts = [];
    const chunkSize = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      parts.push(String.fromCharCode(...bytes.subarray(offset, offset + chunkSize)));
    }
    return btoa(parts.join(""));
  });
}

function base64ToBlob(encoded, mimeType) {
  if (typeof encoded !== "string" || !encoded.length) throw new Error("Backend mengembalikan file kosong.");
  const chunks = [];
  const chunkLength = 32_768;
  for (let offset = 0; offset < encoded.length; offset += chunkLength) {
    const binary = atob(encoded.slice(offset, offset + chunkLength));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    chunks.push(bytes);
  }
  return new Blob(chunks, { type: mimeType });
}

function requireResponseFields(body, fields) {
  if (!body || fields.some((field) => body[field] === undefined || body[field] === null)) {
    throw new Error("Format respons backend tidak sesuai kontrak API.");
  }
}

async function submitEmbed() {
  if ($("#embed-submit").disabled) return;
  clearSenderResult();
  const pdf = selectedFiles.get("embed-pdf").file;
  const cover = selectedFiles.get("embed-cover").file;
  const passphrase = $("#embed-pass").value;
  const mode = $("[name='embed-mode']:checked").value;
  const controller = new AbortController();
  embedController = controller;
  const button = $("#embed-submit");
  button.disabled = true;
  button.textContent = "Mengenkripsi dan menyisipkan…";
  button.setAttribute("aria-busy", "true");
  setStatus($("#embed-status"), mode === "randomized"
    ? "Mengirim file ke backend lokal. Pembentukan permutasi posisi dapat memerlukan waktu lebih lama."
    : "Mengirim file ke backend lokal dan memproses Sequential LSB.");

  try {
    const [pdfBase64, coverBase64] = await Promise.all([fileToBase64(pdf), fileToBase64(cover)]);
    const body = await postJson("/api/embed", {
      pdf: { name: pdf.name, data: pdfBase64 },
      cover: { name: cover.name, data: coverBase64 },
      passphrase,
      mode,
    }, controller.signal);
    requireResponseFields(body, ["filename", "png_base64", "metadata"]);
    requireResponseFields(body.metadata, [
      "mode", "width", "height", "source_bytes", "ciphertext_bytes",
      "capacity_used_percent", "elapsed_ms", "source_sha256",
    ]);
    if (embedController !== controller) return;
    if (body.metadata.mode !== mode) throw new Error("Metode pada respons berbeda dari metode yang dipilih.");

    const blob = base64ToBlob(body.png_base64, "image/png");
    const url = URL.createObjectURL(blob);
    resultUrls.set("embed", url);
    const preview = $("#stego-result-preview");
    preview.src = url;
    $("#stego-result-caption").textContent = `${body.filename} · ${formatBytes(blob.size)}`;
    $("#embed-result-method").textContent = mode === "randomized" ? "Key-Based Randomized LSB" : "Sequential LSB";
    $("#embed-result-dimensions").textContent = `${body.metadata.width} × ${body.metadata.height} px`;
    $("#embed-result-payload").textContent = `${formatBytes(body.metadata.source_bytes)} PDF · ${formatBytes(body.metadata.ciphertext_bytes)} ciphertext + tag`;
    $("#embed-result-capacity").textContent = `${Number(body.metadata.capacity_used_percent).toLocaleString("id-ID", { maximumFractionDigits: 4 })}%`;
    $("#embed-result-time").textContent = formatMilliseconds(body.metadata.elapsed_ms);
    $("#embed-result-hash").textContent = body.metadata.source_sha256;
    const download = $("#stego-download");
    download.href = url;
    download.download = body.filename;
    $("#embed-empty").hidden = true;
    $("#embed-result").hidden = false;
    setStatus($("#embed-result-status"), "Payload berhasil dienkripsi dan disisipkan.", "success");
    setStatus($("#embed-status"), "Selesai. Stego-PNG siap diunduh.", "success");
  } catch (error) {
    if (error.name !== "AbortError" && embedController === controller) {
      setStatus($("#embed-status"), error.message || "Pengamanan gagal.", "error");
    }
  } finally {
    if (embedController === controller) {
      embedController = null;
      button.removeAttribute("aria-busy");
      button.textContent = "Enkripsi dan sisipkan";
      updateActionControls({ refreshMessages: false });
    }
  }
}

async function submitExtract() {
  if ($("#extract-submit").disabled) return;
  clearReceiverResult();
  const stego = selectedFiles.get("extract-stego").file;
  const passphrase = $("#extract-pass").value;
  const mode = $("[name='extract-mode']:checked").value;
  const controller = new AbortController();
  extractController = controller;
  const button = $("#extract-submit");
  button.disabled = true;
  button.textContent = "Mengekstrak dan memverifikasi…";
  button.setAttribute("aria-busy", "true");
  setStatus($("#extract-status"), mode === "randomized"
    ? "Mengekstrak header, menyusun ulang permutasi, lalu memverifikasi autentikasi GCM."
    : "Menunggu ekstraksi dan autentikasi GCM dari backend lokal.");

  try {
    const stegoBase64 = await fileToBase64(stego);
    const body = await postJson("/api/extract", {
      stego: { name: stego.name, data: stegoBase64 },
      passphrase,
      mode,
    }, controller.signal);
    requireResponseFields(body, ["filename", "pdf_base64", "authenticated", "metadata"]);
    requireResponseFields(body.metadata, ["mode", "pdf_bytes", "elapsed_ms", "sha256"]);
    if (body.authenticated !== true) throw new Error("Backend tidak mengonfirmasi autentikasi payload.");
    if (body.metadata.mode !== mode) throw new Error("Metode pada respons berbeda dari metode yang dipilih.");
    if (extractController !== controller) return;

    const blob = base64ToBlob(body.pdf_base64, "application/pdf");
    const url = URL.createObjectURL(blob);
    resultUrls.set("extract", url);
    $("#extract-result-method").textContent = mode === "randomized" ? "Key-Based Randomized LSB" : "Sequential LSB";
    $("#extract-result-auth").textContent = "Berhasil · tag AES-GCM valid";
    $("#extract-result-size").textContent = formatBytes(body.metadata.pdf_bytes);
    $("#extract-result-time").textContent = formatMilliseconds(body.metadata.elapsed_ms);
    $("#extract-result-hash").textContent = body.metadata.sha256;
    const download = $("#pdf-download");
    download.href = url;
    download.download = body.filename;
    $("#extract-empty").hidden = true;
    $("#extract-result").hidden = false;
    setStatus($("#extract-result-status"), "Autentikasi berhasil. PDF pulih tersedia untuk diunduh.", "success");
    setStatus($("#extract-status"), "Tag valid. PDF hanya diberikan setelah autentikasi GCM berhasil.", "success");
  } catch (error) {
    if (error.name !== "AbortError" && extractController === controller) {
      setStatus($("#extract-status"), error.message || "Ekstraksi gagal.", "error");
    }
  } finally {
    if (extractController === controller) {
      extractController = null;
      button.removeAttribute("aria-busy");
      button.textContent = "Ekstrak dan verifikasi";
      updateActionControls({ refreshMessages: false });
    }
  }
}

function clearEvaluationResult() {
  if (evaluationController) evaluationController.abort();
  evaluationController = null;
  const button = $("#evaluate-submit");
  button.textContent = "Jalankan evaluasi";
  button.removeAttribute("aria-busy");
  $("#evaluate-result").hidden = true;
  $("#evaluate-empty").hidden = false;
  $("#evaluation-metrics").replaceChildren();
  $("#evaluation-timings").replaceChildren();
  $("#evaluation-steganalysis").replaceChildren();
  setStatus($("#evaluate-result-status p"), "");
  updateActionControls();
}

function formatMetric(metric) {
  let value = "Tidak tersedia";
  if (metric.status === "infinite") value = "∞";
  else if (metric.value !== null && Number.isFinite(metric.value)) {
    value = Number(metric.value).toLocaleString("id-ID", { maximumFractionDigits: 8 });
  }
  return `${value}${metric.unit ? ` ${metric.unit}` : ""}`;
}

function appendTableRow(tbody, values) {
  const row = document.createElement("tr");
  for (const [index, value] of values.entries()) {
    const cell = document.createElement(index === 0 ? "th" : "td");
    if (index === 0) cell.scope = "row";
    cell.textContent = String(value);
    row.append(cell);
  }
  tbody.append(row);
}

function renderEvaluation(body) {
  requireResponseFields(body, ["mode", "width", "height", "source_bytes", "source_sha256", "recovered_sha256", "recovery_matches", "metrics", "timings", "chi_square", "rs_analysis"]);
  requireResponseFields(body.metrics, ["mse", "psnr", "ssim"]);
  requireResponseFields(body.timings, ["evaluation_total_ms", "embedding_total_ms", "extraction_total_ms"]);
  const label = body.mode === "randomized" ? "Key-Based Randomized LSB" : "Sequential LSB";
  $("#evaluate-method-stamp").lastChild.textContent = label;
  $("#evaluation-method-size").textContent = `${label} · ${body.width} × ${body.height} px · ${formatBytes(body.source_bytes)}`;
  $("#evaluation-recovery").textContent = body.recovery_matches ? "Berhasil · byte sama" : "Gagal · hash berbeda";
  $("#evaluation-hash").textContent = `Sumber: ${body.source_sha256} · Pulih: ${body.recovered_sha256}`;
  const status = $("#evaluate-result-status");
  status.dataset.kind = body.recovery_matches ? "success" : "error";
  status.querySelector(".status-pip").className = `status-pip${body.recovery_matches ? "" : " pending-pip"}`;
  status.querySelector("p").textContent = body.recovery_matches
    ? "PDF berhasil dipulihkan identik; metrik dan analisis berasal dari pemrosesan backend ini."
    : "PDF pulih tidak cocok dengan sumber. Jangan gunakan hasil ini sebagai bukti keberhasilan.";

  const metricRows = $("#evaluation-metrics");
  metricRows.replaceChildren();
  for (const [key, labelText] of [["mse", "MSE"], ["psnr", "PSNR"], ["ssim", "SSIM"]]) {
    const metric = body.metrics[key];
    const reason = metric.reason || body.unavailable_metrics?.[key] || "";
    appendTableRow(metricRows, [labelText, formatMetric(metric), [metric.status, reason].filter(Boolean).join(" · ") || "finite"]);
  }
  const timingRows = $("#evaluation-timings");
  timingRows.replaceChildren();
  const timingLabels = [
    ["evaluation_total_ms", "Total evaluasi"], ["embedding_total_ms", "Embedding total"],
    ["embedding_permutation_ms", "Pembentukan permutasi (embedding)"], ["embedding_lsb_ms", "Penyisipan LSB"],
    ["extraction_total_ms", "Extraction total"], ["extraction_permutation_ms", "Pembentukan permutasi (extraction)"],
    ["extraction_lsb_ms", "Pembacaan LSB"],
  ];
  for (const [key, labelText] of timingLabels) {
    const value = body.timings[key];
    appendTableRow(timingRows, [labelText, value === null || value === undefined ? "Tidak dilaporkan oleh backend" : `${Number(value).toLocaleString("id-ID", { maximumFractionDigits: 3 })} ms`]);
  }
  renderSteganalysis(body);
  $("#evaluate-empty").hidden = true;
  $("#evaluate-result").hidden = false;
}

function renderSteganalysis(body) {
  const target = $("#evaluation-steganalysis");
  target.replaceChildren();
  const chi = body.chi_square;
  const rs = body.rs_analysis;
  if (chi?.stego) {
    const section = document.createElement("section");
    section.className = "analysis-card";
    const title = document.createElement("h4");
    title.textContent = "Chi-square cover dan stego";
    for (const [label, result] of [["Cover", chi.cover], ["Stego", chi.stego]]) {
      if (!result) continue;
      const summary = document.createElement("p");
      const indicator = result.possible_embedding_indicator === null
        ? "tidak dapat ditentukan"
        : result.possible_embedding_indicator ? "terindikasi" : "tidak terindikasi";
      summary.textContent = `${label}: status ${result.status}; indikator kemungkinan penyisipan ${indicator}; ${result.family_size} uji, α = ${result.alpha}.`;
      section.append(summary);
    }
    const interpretation = document.createElement("p");
    interpretation.textContent = chi.stego.interpretation || chi.stego.reason || "Backend tidak memberi interpretasi tambahan.";
    section.prepend(title);
    section.append(interpretation);
    target.append(section);
  }
  if (rs) {
    const section = document.createElement("section");
    section.className = "analysis-card";
    const title = document.createElement("h4");
    title.textContent = "RS analysis";
    const estimate = document.createElement("p");
    const bits = rs.estimated_total_bits === null ? "tidak tersedia" : `${Number(rs.estimated_total_bits).toLocaleString("id-ID", { maximumFractionDigits: 2 })} bit`;
    const error = rs.absolute_error_bits === null ? "tidak tersedia" : `${Number(rs.absolute_error_bits).toLocaleString("id-ID", { maximumFractionDigits: 2 })} bit`;
    estimate.textContent = `Status: ${rs.status}. Perkiraan: ${bits}; galat absolut: ${error}; bit yang disisipkan: ${Number(rs.actual_embedded_bits).toLocaleString("id-ID")}.`;
    const limitation = document.createElement("p");
    limitation.textContent = rs.limitation || "Keterbatasan tidak dilaporkan.";
    section.append(title, estimate, limitation);
    const channels = document.createElement("ul");
    for (const [channel, result] of Object.entries(rs.channels || {})) {
      const item = document.createElement("li");
      const estimateText = result.corrected_estimated_bits === null ? "estimasi tidak tersedia" : `${Number(result.corrected_estimated_bits).toLocaleString("id-ID", { maximumFractionDigits: 2 })} bit`;
      item.textContent = `${channel}: ${result.status} · ${estimateText}${result.reason ? ` · ${result.reason}` : ""}`;
      channels.append(item);
    }
    section.append(channels);
    target.append(section);
  }
  for (const [metric, reason] of Object.entries(body.unavailable_metrics || {})) {
    const note = document.createElement("p");
    note.className = "status";
    note.textContent = `${metric}: tidak tersedia · ${reason}`;
    target.append(note);
  }
}

async function handleEvaluationFile(inputId, summaryId, isImage = false) {
  const input = document.getElementById(inputId);
  const summary = document.getElementById(summaryId);
  const file = input.files?.[0];
  clearEvaluationResult();
  selectedFiles.delete(inputId);
  if (inputId === "evaluate-cover") clearPreview($("#evaluate-cover-frame"), $("#evaluate-cover-preview"));
  if (!file) {
    clearSummary(summary);
    updateActionControls();
    return;
  }
  try {
    if (isImage) {
      const dimensions = await inspectPng(file);
      if (input.files?.[0] !== file) return;
      selectedFiles.set(inputId, { file, ok: true, ...dimensions });
      setSummary(summary, file.name, `${dimensions.width} × ${dimensions.height} px · ${formatBytes(file.size)} · PNG RGB 8-bit.`, "success");
      showPreview(file, $("#evaluate-cover-frame"), $("#evaluate-cover-preview"), $("#evaluate-cover-caption"));
    } else {
      const result = await isPdf(file);
      if (input.files?.[0] !== file) return;
      selectedFiles.set(inputId, { file, ok: result.ok });
      setSummary(summary, result.ok ? file.name : `${file.name} · tidak dapat digunakan`, result.message, result.ok ? "success" : "error");
    }
  } catch (error) {
    if (input.files?.[0] !== file) return;
    setSummary(summary, `${file.name} · tidak dapat digunakan`, error.message || "Berkas tidak dapat diperiksa.", "error");
  }
  updateActionControls();
}

async function submitEvaluation() {
  if ($("#evaluate-submit").disabled) return;
  clearEvaluationResult();
  const pdf = selectedFiles.get("evaluate-pdf").file;
  const cover = selectedFiles.get("evaluate-cover").file;
  const passphrase = $("#evaluate-pass").value;
  const mode = $("[name='evaluate-mode']:checked").value;
  const controller = new AbortController();
  evaluationController = controller;
  const button = $("#evaluate-submit");
  button.disabled = true;
  button.textContent = "Mengukur sampel…";
  button.setAttribute("aria-busy", "true");
  setStatus($("#evaluate-status"), mode === "randomized"
    ? "Backend lokal menyisipkan payload, mengekstrak ulang, lalu menghitung metrik. Randomized LSB dapat memerlukan waktu lebih lama."
    : "Backend lokal menyisipkan payload, mengekstrak ulang, lalu menghitung metrik.");
  try {
    const [pdfBase64, coverBase64] = await Promise.all([fileToBase64(pdf), fileToBase64(cover)]);
    const body = await postJson("/api/evaluate", {
      pdf: { name: pdf.name, data: pdfBase64 },
      cover: { name: cover.name, data: coverBase64 },
      passphrase,
      mode,
    }, controller.signal);
    if (evaluationController !== controller) return;
    if (body.mode !== mode) throw new Error("Metode pada respons berbeda dari metode yang dipilih.");
    renderEvaluation(body);
    setStatus($("#evaluate-status"), "Pengukuran satu sampel selesai.", "success");
  } catch (error) {
    if (error.name !== "AbortError" && evaluationController === controller) {
      setStatus($("#evaluate-status"), error.message || "Evaluasi gagal.", "error");
    }
  } finally {
    if (evaluationController === controller) {
      evaluationController = null;
      button.removeAttribute("aria-busy");
      button.textContent = "Jalankan evaluasi";
      updateActionControls({ refreshMessages: false });
    }
  }
}

function showView(name) {
  if (name === currentView) return;
  if (currentView === "embed") {
    clearSenderResult();
    $("#embed-pass").value = "";
    resetPasswordVisibility("embed-pass");
  } else if (currentView === "extract") {
    clearReceiverResult();
    $("#extract-pass").value = "";
    resetPasswordVisibility("extract-pass");
  } else if (currentView === "evaluate") {
    clearEvaluationResult();
    $("#evaluate-pass").value = "";
    resetPasswordVisibility("evaluate-pass");
  }
  currentView = name;
  $$(".view").forEach((view) => {
    const active = view.id === `view-${name}`;
    view.hidden = !active;
    view.classList.toggle("active", active);
  });
  $$(".nav-link").forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  window.scrollTo(0, 0);
  document.getElementById(`${name}-title`)?.focus({ preventScroll: true });
  updateActionControls();
}

$("#brand-home").addEventListener("click", () => showView("embed"));
$(".nav-link[data-view='embed']").addEventListener("click", () => showView("embed"));
$(".nav-link[data-view='extract']").addEventListener("click", () => showView("extract"));
$(".nav-link[data-view='evaluate']").addEventListener("click", () => showView("evaluate"));
$$('[data-drop-zone]').forEach(attachDropZone);

$("#embed-pdf").addEventListener("change", () => handlePdfChange("embed-pdf", "embed-pdf-summary"));
$("#embed-cover").addEventListener("change", () => handlePngChange("embed-cover", "embed-cover-summary", "cover-preview-frame", "cover-preview", "cover-preview-caption"));
$("#extract-stego").addEventListener("change", () => handlePngChange("extract-stego", "extract-stego-summary", "stego-preview-frame", "stego-preview", "stego-preview-caption"));
$("#evaluate-pdf").addEventListener("change", () => void handleEvaluationFile("evaluate-pdf", "evaluate-pdf-summary"));
$("#evaluate-cover").addEventListener("change", () => void handleEvaluationFile("evaluate-cover", "evaluate-cover-summary", true));
$("#embed-submit").addEventListener("click", submitEmbed);
$("#extract-submit").addEventListener("click", submitExtract);
$("#evaluate-submit").addEventListener("click", submitEvaluation);

$$('[data-toggle-password]').forEach((button) => button.addEventListener("click", () => {
  const input = document.getElementById(button.dataset.togglePassword);
  const visible = input.type === "password";
  input.type = visible ? "text" : "password";
  button.textContent = visible ? "Sembunyikan" : "Tampilkan";
  button.setAttribute("aria-pressed", String(visible));
}));

$$('[name="embed-mode"]').forEach((input) => input.addEventListener("change", () => {
  clearSenderResult();
  $$("[name='embed-mode']").forEach((radio) => radio.closest(".method-option").classList.toggle("selected", radio.checked));
  syncMethodDetails();
  updateActionControls();
}));
$$('[name="extract-mode"]').forEach((input) => input.addEventListener("change", () => {
  clearReceiverResult();
  $$("[name='extract-mode']").forEach((radio) => radio.closest(".method-option").classList.toggle("selected", radio.checked));
  syncMethodDetails();
  updateActionControls();
}));
$$('[name="evaluate-mode"]').forEach((input) => input.addEventListener("change", () => {
  clearEvaluationResult();
  $$('[name="evaluate-mode"]').forEach((radio) => radio.closest(".method-option").classList.toggle("selected", radio.checked));
  const label = input.value === "randomized" ? "Key-Based Randomized LSB" : "Sequential LSB";
  $("#evaluate-method-stamp").lastChild.textContent = label;
  updateActionControls();
}));
$("#embed-pass").addEventListener("input", () => {
  clearSenderResult();
  updateActionControls();
});
$("#extract-pass").addEventListener("input", () => {
  clearReceiverResult();
  updateActionControls();
});
$("#evaluate-pass").addEventListener("input", () => {
  clearEvaluationResult();
  updateActionControls();
});

window.addEventListener("pagehide", () => {
  for (const url of [...previewUrls.values(), ...resultUrls.values()]) URL.revokeObjectURL(url);
  previewUrls.clear();
  resultUrls.clear();
  $("#embed-pass").value = "";
  $("#extract-pass").value = "";
  $("#evaluate-pass").value = "";
});

updateActionControls();
checkLocalApi();
