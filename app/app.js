const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

let currentStego = null;
let currentPdf = null;
let currentEvaluation = null;

function setStatus(element, message, kind = "") {
  element.textContent = message;
  element.dataset.kind = kind;
}

function setBusy(button, busy, label) {
  if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent.trim();
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
  button.textContent = busy ? label : button.dataset.idleLabel;
}

function readBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Berkas tidak dapat dibaca."));
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.slice(result.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
}

async function filePayload(file) {
  if (!file) throw new Error("Pilih berkas terlebih dahulu.");
  return { name: file.name, data: await readBase64(file) };
}

async function postJSON(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || "Pemrosesan lokal gagal.");
  return result;
}

function fromBase64(value) {
  const raw = atob(value);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

function downloadBytes(bytes, name, mime) {
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function downloadBase64(value, name, mime) {
  downloadBytes(fromBase64(value), name, mime);
}

async function copyText(value, status) {
  try {
    await navigator.clipboard.writeText(value);
    setStatus(status, "Disalin ke clipboard.", "success");
  } catch {
    setStatus(status, "Clipboard tidak tersedia. Salin nilai dari tampilan hasil.", "error");
  }
}

function renderDefinitionList(target, pairs) {
  target.replaceChildren();
  for (const [label, value, className] of pairs) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    if (className) dd.className = className;
    target.append(dt, dd);
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} byte`;
  return `${(bytes / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 })} KiB`;
}

function modeLabel(mode) {
  return mode === "randomized" ? "Key-Based Randomized LSB" : "Sequential LSB";
}

function clearEmbedResult() {
  currentStego = null;
  $("#embed-output").hidden = true;
  $("#embed-empty").hidden = false;
}

function clearExtractResult() {
  currentPdf = null;
  $("#extract-output").hidden = true;
  $("#extract-empty").hidden = false;
}

function showView(name) {
  $$(".view").forEach((view) => {
    const active = view.id === `view-${name}`;
    view.hidden = !active;
    view.classList.toggle("active", active);
  });
  $$(".sidebar-link").forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
}

$$(".sidebar-link").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));

$$('[data-toggle-password]').forEach((button) => button.addEventListener("click", () => {
  const input = document.getElementById(button.dataset.togglePassword);
  const visible = input.type === "password";
  input.type = visible ? "text" : "password";
  button.setAttribute("aria-pressed", String(visible));
  button.setAttribute("aria-label", visible ? "Sembunyikan passphrase" : "Tampilkan passphrase");
}));

$("#embed-pdf").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("#embed-pdf-name").textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "Belum ada berkas";
  clearEmbedResult();
});

$("#embed-cover").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  $("#embed-cover-name").textContent = file ? file.name : "Pilih PNG RGB 24-bit";
  clearEmbedResult();
  if (!file) return;
  try {
    const bitmap = await createImageBitmap(file);
    const totalSlots = bitmap.width * bitmap.height * 3;
    const usableBytes = Math.floor((totalSlots - 256) / 8);
    const pdfLimit = Math.max(0, usableBytes - 16);
    $("#capacity-help").textContent = `${bitmap.width} × ${bitmap.height} px · sekitar ${formatBytes(pdfLimit)} payload PDF maksimum setelah header dan tag GCM. Server tetap memeriksa format RGB.`;
    bitmap.close();
  } catch {
    $("#capacity-help").textContent = "Citra belum dapat dibaca. Pilih PNG RGB 24-bit yang valid.";
  }
});

$("#embed-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearEmbedResult();
  const button = $("#embed-submit");
  const status = $("#embed-status");
  const mode = $('[name="embed-mode"]:checked').value;
  setBusy(button, true, mode === "randomized" ? "Menyusun posisi dan memproses…" : "Mengenkripsi dan menyisipkan…");
  setStatus(status, "PDF dan PNG diproses di server lokal. Tidak ada berkas yang disimpan oleh server.", "working");
  try {
    const pdf = await filePayload($("#embed-pdf").files[0]);
    const cover = await filePayload($("#embed-cover").files[0]);
    const passphrase = $("#embed-pass").value;
    if (passphrase.length < 12) throw new Error("Gunakan passphrase minimal 12 karakter.");
    const result = await postJSON("/api/embed", { pdf, cover, passphrase, mode });
    currentStego = result;
    $("#stego-preview").src = `data:image/png;base64,${result.png_base64}`;
    $("#embed-metadata").replaceChildren();
    renderDefinitionList($("#embed-metadata"), [
      ["Nama keluaran", result.filename],
      ["Metode", modeLabel(result.metadata.mode)],
      ["Resolusi", `${result.metadata.width} × ${result.metadata.height} px`],
      ["PDF sumber", formatBytes(result.metadata.source_bytes)],
      ["Ciphertext + tag", formatBytes(result.metadata.ciphertext_bytes)],
      ["Kapasitas terpakai", `${result.metadata.capacity_used_percent}%`],
      ["Waktu proses", `${result.metadata.elapsed_ms} ms`],
      ["SHA-256 sumber", result.metadata.source_sha256, "hash"],
    ]);
    $("#embed-fingerprint-note").textContent = result.metadata.note;
    $("#embed-empty").hidden = true;
    $("#embed-output").hidden = false;
    setStatus(status, "Penyisipan selesai. Unduh stego-PNG untuk diuji pada layar ekstraksi.", "success");
  } catch (error) {
    setStatus(status, error.message, "error");
  } finally {
    setBusy(button, false);
  }
});

$("#download-stego").addEventListener("click", () => {
  if (currentStego) downloadBase64(currentStego.png_base64, currentStego.filename, "image/png");
});

$("#copy-embed-metadata").addEventListener("click", () => {
  if (currentStego) copyText(JSON.stringify(currentStego.metadata, null, 2), $("#embed-status"));
});

$("#extract-stego").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("#extract-stego-name").textContent = file ? `${file.name} · ${formatBytes(file.size)}` : "Belum ada berkas";
  clearExtractResult();
});

$("#generate-tamper").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const status = $("#extract-status");
  try {
    const stego = await filePayload($("#extract-stego").files[0]);
    setBusy(button, true, "Membuat salinan uji…");
    const result = await postJSON("/api/tamper", { stego });
    downloadBase64(result.png_base64, result.filename, "image/png");
    setStatus(status, "Salinan dengan satu bit header berubah diunduh. Pilih salinan itu untuk melihat tag AES-GCM menolak pemulihan.", "success");
  } catch (error) {
    setStatus(status, error.message, "error");
  } finally {
    setBusy(button, false);
  }
});

$("#extract-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearExtractResult();
  const button = $("#extract-submit");
  const status = $("#extract-status");
  setBusy(button, true, "Menurunkan kunci dan memverifikasi tag…");
  setStatus(status, "PDF belum ditulis; menunggu hasil autentikasi AES-GCM.", "working");
  try {
    const stego = await filePayload($("#extract-stego").files[0]);
    const passphrase = $("#extract-pass").value;
    const mode = $('[name="extract-mode"]:checked').value;
    const result = await postJSON("/api/extract", { stego, passphrase, mode });
    currentPdf = result;
    renderDefinitionList($("#extract-metadata"), [
      ["Status tag AES-GCM", "Valid"],
      ["Metode", modeLabel(result.metadata.mode)],
      ["Resolusi citra", `${result.metadata.width} × ${result.metadata.height} px`],
      ["Ukuran PDF pulih", formatBytes(result.metadata.pdf_bytes)],
      ["Waktu proses", `${result.metadata.elapsed_ms} ms`],
      ["SHA-256 PDF pulih", result.metadata.sha256, "hash"],
    ]);
    $("#extract-empty").hidden = true;
    $("#extract-output").hidden = false;
    setStatus(status, "Tag cocok dan PDF siap diunduh.", "success");
  } catch (error) {
    setStatus(status, error.message, "error");
  } finally {
    setBusy(button, false);
  }
});

$("#download-pdf").addEventListener("click", () => {
  if (currentPdf) downloadBase64(currentPdf.pdf_base64, currentPdf.filename, "application/pdf");
});

$("#copy-extract-hash").addEventListener("click", () => {
  if (currentPdf) copyText(currentPdf.metadata.sha256, $("#extract-status"));
});

function addMetricRow(body, label, sequential, randomized, note = "") {
  const row = document.createElement("tr");
  for (const value of [label, sequential, randomized, note]) {
    const cell = document.createElement("td");
    cell.textContent = String(value);
    row.append(cell);
  }
  body.append(row);
}

function renderEvaluation(data) {
  const seq = data.results.find((item) => item.method === "sequential");
  const rnd = data.results.find((item) => item.method === "randomized");
  const body = $("#evaluation-table");
  body.replaceChildren();
  addMetricRow(body, "Pemulihan SHA-256", seq.recovery_matches ? "Cocok" : "Gagal", rnd.recovery_matches ? "Cocok" : "Gagal", "Hash diuji di luar stego-header");
  addMetricRow(body, "MSE", seq.mse, rnd.mse, "Lebih kecil berarti perubahan rata-rata lebih kecil");
  addMetricRow(body, "PSNR", seq.psnr_db === null ? "∞" : `${seq.psnr_db} dB`, rnd.psnr_db === null ? "∞" : `${rnd.psnr_db} dB`, "Lebih besar biasanya berarti distorsi lebih rendah");
  addMetricRow(body, "SSIM", seq.ssim, rnd.ssim, "Nilai mendekati 1 berarti struktur lebih mirip");
  addMetricRow(body, "Kanal berubah", seq.changed_channels, rnd.changed_channels, "Termasuk perubahan header dan payload");
  addMetricRow(body, "Chi-square histogram", `${seq.chi_square.statistic} · p=${seq.chi_square.p_value.toPrecision(3)}`, `${rnd.chi_square.statistic} · p=${rnd.chi_square.p_value.toPrecision(3)}`, "Uji pasangan histogram eksploratif");
  addMetricRow(body, "RS regular/singular + mask", `${seq.rs.regular_positive}/${seq.rs.singular_positive} · ${seq.rs.regular_negative}/${seq.rs.singular_negative}`, `${rnd.rs.regular_positive}/${rnd.rs.singular_positive} · ${rnd.rs.regular_negative}/${rnd.rs.singular_negative}`, "Hitungan dasar; bukan estimasi payload");
  addMetricRow(body, "Waktu satu proses", `${seq.elapsed_ms} ms`, `${rnd.elapsed_ms} ms`, "Satu ulangan untuk demonstrasi ini");
  $("#evaluation-subtitle").textContent = `${data.source_name} · ${formatBytes(data.source_bytes)} · ${data.width} × ${data.height} px · ciphertext ${formatBytes(data.payload_ciphertext_bytes)}`;
  $("#evaluation-note").textContent = data.note;
  $("#evaluation-results").hidden = false;
}

$("#evaluate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#evaluation-results").hidden = true;
  const button = $("#evaluate-submit");
  const status = $("#evaluate-status");
  setBusy(button, true, "Menguji dua metode…");
  setStatus(status, "Ciphertext yang sama dipakai pada kedua metode. Permutasi acak dapat memerlukan waktu pada citra besar.", "working");
  try {
    const pdf = await filePayload($("#eval-pdf").files[0]);
    const cover = await filePayload($("#eval-cover").files[0]);
    const passphrase = $("#eval-pass").value;
    if (passphrase.length < 12) throw new Error("Gunakan passphrase uji minimal 12 karakter.");
    currentEvaluation = await postJSON("/api/evaluate", { pdf, cover, passphrase });
    renderEvaluation(currentEvaluation);
    setStatus(status, "Perbandingan selesai untuk satu pasangan berkas.", "success");
  } catch (error) {
    setStatus(status, error.message, "error");
  } finally {
    setBusy(button, false);
  }
});

$("#download-csv").addEventListener("click", () => {
  if (!currentEvaluation) return;
  const rows = [["Metrik", "Sequential LSB", "Randomized LSB"]];
  const seq = currentEvaluation.results.find((item) => item.method === "sequential");
  const rnd = currentEvaluation.results.find((item) => item.method === "randomized");
  rows.push(["Pemulihan SHA-256", seq.recovery_matches, rnd.recovery_matches]);
  for (const key of ["mse", "psnr_db", "ssim", "changed_channels", "elapsed_ms"]) rows.push([key, seq[key], rnd[key]]);
  rows.push(["Chi-square statistic", seq.chi_square.statistic, rnd.chi_square.statistic]);
  rows.push(["Chi-square p-value", seq.chi_square.p_value, rnd.chi_square.p_value]);
  rows.push(["RS counts Rm/Sm/R-m/S-m", `${seq.rs.regular_positive}/${seq.rs.singular_positive}/${seq.rs.regular_negative}/${seq.rs.singular_negative}`, `${rnd.rs.regular_positive}/${rnd.rs.singular_positive}/${rnd.rs.regular_negative}/${rnd.rs.singular_negative}`]);
  const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\r\n");
  downloadBytes(new TextEncoder().encode(`\uFEFF${csv}`), "cipherstego-evaluasi.csv", "text/csv;charset=utf-8");
});
