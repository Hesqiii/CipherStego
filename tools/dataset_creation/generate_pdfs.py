from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "experiment_data" / "dataset" / "pdf"
DEFAULT_REPORT = PROJECT_ROOT / "experiment_data" / "reports" / "pdf_generation_report.json"
SEED = 20261118


@dataclass(frozen=True)
class PdfSpec:
    sample_id: str
    target_kib: int
    pages: int
    title: str
    characteristic: str
    kind: str


SPECS = (
    PdfSpec("P01", 10, 1, "Surat pengantar simulasi", "Surat satu halaman", "letter"),
    PdfSpec("P02", 25, 3, "Catatan pengamatan ruang simulasi", "Dokumen teks 2-3 halaman", "text"),
    PdfSpec("P03", 50, 12, "Laporan pencatatan berkelompok", "Laporan dengan tabel", "tables"),
    PdfSpec("P04", 100, 5, "Makalah pola pengukuran sintetis", "Makalah dengan grafik vektor", "vector"),
    PdfSpec("P05", 150, 5, "Ringkasan pengamatan dengan ilustrasi", "Dokumen dengan bitmap kecil", "bitmap"),
    PdfSpec("P06", 200, 6, "Modul latihan membaca data", "Modul/diktat bergambar", "module"),
    PdfSpec("P07", 300, 7, "Laporan ringkas beberapa seri", "Laporan dengan grafik dan tabel", "dense_vector"),
    PdfSpec("P08", 400, 4, "Lembar arsip simulasi", "Dokumen pindai beresolusi rendah", "scan"),
    PdfSpec("P09", 500, 6, "Catatan teks dan foto sintetis", "Dokumen teks dan foto", "photo"),
    PdfSpec("P10", 600, 6, "Arsip lembar pengamatan", "Dokumen pindai beberapa halaman", "scan"),
)

WORDS = (
    "pengamatan", "simulasi", "contoh", "wilayah", "pola", "catatan", "sampel",
    "perubahan", "nilai", "periode", "kelompok", "hasil", "ringkasan", "sistem",
    "tahap", "ukur", "warna", "bidang", "rekap", "model", "proses", "pencatatan",
)
SENTENCE_FRAGMENTS = (
    "Catatan ini merangkum pengamatan sintetis pada ruang simulasi.",
    "Nilai disusun untuk latihan membaca pola dan tidak mewakili pengukuran nyata.",
    "Setiap kelompok contoh memakai rentang yang sama agar perbandingan mudah diikuti.",
    "Perbedaan antarperiode menunjukkan variasi yang dibuat khusus untuk dokumen ini.",
    "Angka pada tabel dan gambar merupakan data rekaan yang dapat dibuat ulang dari seed.",
    "Tidak ada nama orang, nomor identitas, alamat, ataupun organisasi nyata dalam berkas.",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fictional_paragraph(rng: random.Random, index: int) -> str:
    base = SENTENCE_FRAGMENTS[index % len(SENTENCE_FRAGMENTS)]
    details = " ".join(rng.choice(WORDS) for _ in range(8))
    return f"{base} Rangkaian istilah contoh: {details}."


def _draw_paragraph(pdf: canvas.Canvas, text: str, x: float, top: float, width: float,
                    font_size: float = 9.2) -> float:
    style = ParagraphStyle(
        "synthetic", fontName="Helvetica", fontSize=font_size, leading=font_size * 1.42,
        textColor=colors.HexColor("#263548"), spaceAfter=0,
    )
    para = Paragraph(text, style)
    _, height = para.wrap(width, 500)
    para.drawOn(pdf, x, top - height)
    return top - height - 8


def _header(pdf: canvas.Canvas, spec: PdfSpec, page: int) -> None:
    width, height = A4
    pdf.setFillColor(colors.HexColor("#15324b"))
    pdf.rect(0, height - 63, width, 63, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(42, height - 37, spec.title)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(42, height - 52, f"Data sintetis | {spec.sample_id} | halaman {page} dari {spec.pages}")
    pdf.setFillColor(colors.HexColor("#536477"))
    pdf.setFont("Helvetica", 7)
    pdf.drawString(42, 25, "Berkas fiktif untuk pengujian teknis; bukan dokumen atau pengukuran nyata.")
    pdf.drawRightString(width - 42, 25, f"{page}/{spec.pages}")


def _draw_table(pdf: canvas.Canvas, rng: random.Random, x: float, top: float,
                rows: int, cols: int = 4, row_h: float = 11) -> float:
    width = A4[0] - 84
    col_w = width / cols
    pdf.setFillColor(colors.HexColor("#e7eef4"))
    pdf.rect(x, top - row_h, width, row_h, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#91a2b2"))
    pdf.setLineWidth(0.35)
    for r in range(rows + 1):
        y = top - r * row_h
        pdf.line(x, y, x + width, y)
    for c in range(cols + 1):
        xx = x + c * col_w
        pdf.line(xx, top, xx, top - rows * row_h)
    pdf.setFont("Helvetica-Bold", 6.4)
    headings = ("Periode", "Kelompok", "Nilai contoh", "Catatan")
    for c in range(cols):
        pdf.setFillColor(colors.HexColor("#173a58"))
        pdf.drawString(x + c * col_w + 3, top - row_h + 3, headings[c])
    for r in range(1, rows):
        if r % 2 == 0:
            pdf.setFillColor(colors.HexColor("#f5f8fa"))
            pdf.rect(x, top - (r + 1) * row_h, width, row_h, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#263548"))
        pdf.setFont("Helvetica", 5.8)
        values = (f"T{r:03d}", f"G{rng.randrange(1, 9):02d}",
                  f"{rng.uniform(1, 99):.2f}", rng.choice(("rentang A", "rentang B", "simulasi")))
        for c, value in enumerate(values):
            pdf.drawString(x + c * col_w + 3, top - (r + 1) * row_h + 3, value)
    return top - rows * row_h - 12


def _draw_vector_chart(pdf: canvas.Canvas, rng: random.Random, x: float, top: float,
                       width: float, height: float, points: int, label: str) -> None:
    bottom = top - height
    pdf.setFillColor(colors.HexColor("#f8fafc"))
    pdf.roundRect(x, bottom, width, height, 5, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#c7d2dc"))
    pdf.setLineWidth(0.35)
    for i in range(4):
        y = bottom + 20 + i * (height - 40) / 4
        pdf.line(x + 28, y, x + width - 8, y)
    pdf.setFillColor(colors.HexColor("#30465c"))
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(x + 7, top - 12, label)
    plot_left, plot_right = x + 29, x + width - 9
    plot_bottom, plot_top = bottom + 18, top - 18
    pdf.setStrokeColor(colors.HexColor("#137c8b"))
    pdf.setLineWidth(0.42)
    path = pdf.beginPath()
    for i in range(points):
        px = plot_left + (plot_right - plot_left) * i / max(1, points - 1)
        py = plot_bottom + (plot_top - plot_bottom) * (0.5 + 0.26 * __import__("math").sin(i * 0.031)
                                                        + rng.uniform(-0.18, 0.18))
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    pdf.drawPath(path, stroke=1, fill=0)


def _image_bytes(rng: random.Random, size: tuple[int, int], mode: str) -> bytes:
    width, height = size
    image = Image.new("RGB", size, "#eaf0ef")
    draw = ImageDraw.Draw(image)
    if mode == "photo":
        for y in range(height):
            shade = int(95 + 75 * y / height)
            draw.line((0, y, width, y), fill=(shade // 2, shade, min(220, shade + 35)))
        for i in range(28):
            x = rng.randrange(width)
            y = rng.randrange(height // 2, height)
            radius = rng.randrange(8, max(9, min(width, height) // 5))
            color = (rng.randrange(25, 100), rng.randrange(75, 145), rng.randrange(35, 95))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        for _ in range(width * height // 6):
            x, y = rng.randrange(width), rng.randrange(height)
            p = image.getpixel((x, y))
            delta = rng.randrange(-18, 19)
            image.putpixel((x, y), tuple(max(0, min(255, channel + delta)) for channel in p))
    else:
        draw.rectangle((0, 0, width - 1, height - 1), fill="#f2f6f4")
        for i in range(12):
            x0, y0 = rng.randrange(width), rng.randrange(height)
            x1, y1 = rng.randrange(width), rng.randrange(height)
            color = (rng.randrange(35, 180), rng.randrange(65, 190), rng.randrange(80, 210))
            draw.line((x0, y0, x1, y1), fill=color, width=rng.randrange(1, 4))
        for i in range(4):
            x, y = rng.randrange(width), rng.randrange(height)
            r = rng.randrange(5, max(6, min(width, height) // 8))
            draw.ellipse((x-r, y-r, x+r, y+r), outline="#315b73", width=2)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=84, optimize=False, progressive=False)
    return buffer.getvalue()


def _scan_bytes(rng: random.Random, page: int, spec: PdfSpec) -> bytes:
    # A deliberately low-resolution (110 dpi) rendered page with subtle scanner grain.
    size = (850, 1202)
    grain = bytes(max(0, min(255, int(round(rng.gauss(248, 0.15))))) for _ in range(size[0] * size[1]))
    image = Image.frombytes("L", size, grain).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_path = Path(r"C:\Windows\Fonts\arial.ttf")
    font = ImageFont.truetype(str(font_path), 17) if font_path.exists() else ImageFont.load_default()
    draw.text((60, 52), spec.title, fill="#233243", font=font)
    draw.text((60, 83), f"Lembar simulasi {page:02d} | salinan sintetis", fill="#4b5661", font=font)
    draw.line((60, 118, 790, 118), fill="#87929d", width=2)
    y = 150
    for i in range(4):
        text = _fictional_paragraph(rng, page * 31 + i)
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=font) > 720:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        for line in lines:
            draw.text((62, y), line, fill="#38424a", font=font)
            y += 22
        y += 28
        if i == 2:
            draw.line((75, y, 760, y), fill="#adb4ba", width=1)
            y += 14
    for row in range(6):
        y0 = 930 + row * 27
        draw.line((65, y0, 780, y0), fill="#8d979f", width=1)
    for col in range(5):
        x = 65 + col * 178
        draw.line((x, 930, x, 1085), fill="#8d979f", width=1)
    draw.text((60, 1120), "Sumber: data contoh yang dibuat untuk dokumen ini.", fill="#515b63", font=font)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=74, optimize=False, progressive=False)
    return output.getvalue()


def _draw_regular_page(pdf: canvas.Canvas, spec: PdfSpec, page: int, rng: random.Random,
                       image_cache: dict[str, bytes]) -> None:
    width, height = A4
    _header(pdf, spec, page)
    top = height - 88
    pdf.setFillColor(colors.HexColor("#203c56"))
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(42, top, f"Bagian {page}: ringkasan data rekaan")
    top -= 18
    paragraph_count = 2 if spec.kind == "letter" else 4
    if spec.kind == "text":
        paragraph_count = 19
    for i in range(paragraph_count):
        top = _draw_paragraph(pdf, _fictional_paragraph(rng, page * 17 + i),
                              42, top, width - 84, 7.2 if spec.kind == "text" else 9.0)
    if spec.kind == "letter":
        pdf.setFont("Helvetica", 9)
        pdf.drawString(42, max(90, top - 10), "Hormat kami,")
        pdf.drawString(42, max(65, top - 25), "Unit Simulasi")
        # A small, visibly rendered geometric seal, not a real mark or logo.
        pdf.setStrokeColor(colors.HexColor("#557f96"))
        pdf.setLineWidth(0.7)
        for radius in range(4, 42, 3):
            pdf.circle(width - 83, 126, radius, stroke=1, fill=0)
        pdf.setFont("Helvetica-Bold", 6)
        pdf.drawCentredString(width - 83, 124, "CONTOH")
        stamp = _image_bytes(rng, (280, 210), "photo")
        pdf.drawImage(ImageReader(io.BytesIO(stamp)), 72, 104, width=100, height=75, preserveAspectRatio=True)
        pdf.setFont("Helvetica-Oblique", 6)
        pdf.drawString(72, 96, "Ilustrasi sintetis")
    elif spec.kind == "text":
        _draw_vector_chart(pdf, rng, 42, 292, 250, 72, 520, "Ringkasan pola sintetis")
    elif spec.kind == "tables":
        rows = 30
        _draw_table(pdf, rng, 42, top - 4, rows, row_h=9)
        _draw_table(pdf, rng, 42, top - rows * 9 - 20, rows, row_h=9)
    elif spec.kind in {"vector", "dense_vector"}:
        charts = 2 if spec.kind == "vector" else 3
        count = 900 if spec.kind == "vector" else 1300
        chart_h = 82 if charts == 3 else 112
        for chart in range(charts):
            _draw_vector_chart(pdf, rng, 42, top - chart * (chart_h + 12),
                               width - 84, chart_h, count, f"Grafik vektor {page}.{chart+1}")
    elif spec.kind in {"bitmap", "module", "photo"}:
        if spec.kind == "bitmap":
            key, size, mode, x, y, w, h = f"small-{page}", (430, 300), "diagram", 66, 280, 225, 157
            if page % 2 == 0:
                key = "small-shared"
        elif spec.kind == "module":
            key, size, mode, x, y, w, h = f"module-{page}", (600, 420), "diagram", 80, 220, 435, 305
        else:
            key, size, mode, x, y, w, h = f"photo-{page}", (780, 520), "photo", 50, 210, 495, 330
        if key not in image_cache:
            image_cache[key] = _image_bytes(rng, size, mode)
        pdf.drawImage(ImageReader(io.BytesIO(image_cache[key])), x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")
        if spec.kind == "bitmap":
            second_key = f"small-detail-{page}"
            image_cache[second_key] = _image_bytes(rng, (300, 210), "diagram")
            pdf.drawImage(ImageReader(io.BytesIO(image_cache[second_key])), 318, 280, width=190, height=133, preserveAspectRatio=True, mask="auto")
        pdf.setFillColor(colors.HexColor("#536477"))
        pdf.setFont("Helvetica-Oblique", 7)
        pdf.drawString(x, y - 12, f"Ilustrasi sintetis {page}; tidak berasal dari foto atau dokumen nyata.")
        if spec.kind in {"module", "photo"}:
            _draw_table(pdf, rng, 42, 190, 9, row_h=11)
    pdf.showPage()


def _draw_paragraph(pdf: canvas.Canvas, text: str, x: float, top: float,
                    width: float, font_size: float = 9) -> float:
    return _draw_paragraph_impl(pdf, text, x, top, width, font_size)


def _draw_paragraph_impl(pdf: canvas.Canvas, text: str, x: float, top: float,
                         width: float, font_size: float) -> float:
    style = ParagraphStyle(
        "synthetic-body", fontName="Helvetica", fontSize=font_size,
        leading=font_size * 1.45, textColor=colors.HexColor("#263548"),
    )
    para = Paragraph(text, style)
    _, height = para.wrap(width, 500)
    para.drawOn(pdf, x, top - height)
    return top - height - 8


def _draw_scan_page(pdf: canvas.Canvas, spec: PdfSpec, page: int, rng: random.Random, asset_dir: Path) -> None:
    jpeg = _scan_bytes(rng, page, spec)
    image_path = asset_dir / f"{spec.sample_id}-scan-{page:02d}.jpg"
    image_path.write_bytes(jpeg)
    pdf.drawImage(str(image_path), 0, 0, width=A4[0], height=A4[1], preserveAspectRatio=False)
    pdf.showPage()


def _build_pdf(path: Path, spec: PdfSpec, seed: int) -> None:
    rng = random.Random(seed + int(spec.sample_id[1:]))
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1, invariant=1)
    pdf.setTitle(f"{spec.sample_id} - Dokumen sintetis")
    pdf.setAuthor("Data sintetis")
    pdf.setSubject("Konten fiktif untuk pengujian lokal")
    pdf.setCreator("CipherStego synthetic dataset generator")
    cache: dict[str, bytes] = {}
    for page in range(1, spec.pages + 1):
        if spec.kind == "scan":
            _draw_scan_page(pdf, spec, page, rng, path.parent)
        else:
            _draw_regular_page(pdf, spec, page, rng, cache)
    pdf.save()


def validate_pdf(path: Path, expected_pages: int) -> dict[str, object]:
    data = path.read_bytes()
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
        raise ValueError(f"Struktur dasar PDF tidak valid: {path.name}")
    reader = PdfReader(str(path), strict=True)
    if reader.is_encrypted:
        raise ValueError(f"PDF tidak boleh terenkripsi: {path.name}")
    pages = len(reader.pages)
    if pages != expected_pages:
        raise ValueError(f"Jumlah halaman {pages}, seharusnya {expected_pages}: {path.name}")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip() and path.stem not in {"P08", "P10"}:
        raise ValueError(f"Tidak ditemukan teks yang dapat diekstrak: {path.name}")
    return {
        "status": "valid",
        "signature": "valid",
        "eof_marker": "valid",
        "page_count": pages,
        "text_extractable": bool(text.strip()),
    }


def generate_dataset(output_dir: Path, report_path: Path, *, force: bool = False,
                     seed: int = SEED) -> dict[str, object]:
    output_dir = output_dir.resolve()
    report_path = report_path.resolve()
    targets = [output_dir / f"{spec.sample_id}.pdf" for spec in SPECS]
    collisions = [path for path in [*targets, report_path] if path.exists()]
    if collisions and not force:
        names = ", ".join(str(path) for path in collisions)
        raise FileExistsError(f"Output sudah ada; tidak ditimpa. Gunakan --force secara sadar: {names}")

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=".cipherstego-pdf-", dir=output_dir) as scratch:
        scratch_dir = Path(scratch)
        for spec in SPECS:
            final_path = output_dir / f"{spec.sample_id}.pdf"
            staged_path = scratch_dir / final_path.name
            _build_pdf(staged_path, spec, seed)
            validation = validate_pdf(staged_path, spec.pages)
            size = staged_path.stat().st_size
            staged_path.replace(final_path)
            rows.append({
                "sample_id": spec.sample_id,
                "filename": final_path.name,
                "target_kib": spec.target_kib,
                "size_bytes": size,
                "size_kib": round(size / 1024, 3),
                "difference_bytes": size - spec.target_kib * 1024,
                "page_count": spec.pages,
                "characteristic": spec.characteristic,
                "sha256": _sha256(final_path),
                "validation": validation,
                "privacy_review": "manual_review_required",
            })
    report: dict[str, object] = {
        "report_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "generator": "tools/dataset_creation/generate_pdfs.py",
        "outputs": rows,
        "privacy_review": {
            "status": "manual_review_required",
            "note": "Generator tidak menyatakan tinjauan privasi lulus; setiap PDF perlu diperiksa manusia.",
        },
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if force:
        report_path.write_text(serialized, encoding="utf-8")
    else:
        with report_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Buat dataset PDF sintetis P01-P10 secara deterministik.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true", help="Izinkan menimpa PDF dan laporan yang dituju.")
    args = parser.parse_args(argv)
    try:
        report = generate_dataset(args.output_dir, args.report, force=args.force, seed=args.seed)
    except (FileExistsError, OSError, ValueError) as exc:
        parser.error(str(exc))
    for row in report["outputs"]:
        print(f"{row['sample_id']} {row['size_bytes']} B ({row['size_kib']} KiB), "
              f"{row['page_count']} halaman, SHA-256 {row['sha256']}, valid")
    print(f"Laporan dibuat: {args.report}")
    print("Tinjauan privasi: wajib diperiksa manual untuk semua PDF.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





















