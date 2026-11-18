"""Loopback-only static app server and JSON API for CipherStego."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from crypto_engine import AuthenticationError, InputError, embed, evaluate, extract, safe_name, tamper_header

ROOT = Path(__file__).resolve().parent
MAX_BODY = 36 * 1024 * 1024


def decode_file(value: dict, field: str) -> tuple[bytes, str]:
    if not isinstance(value, dict) or not isinstance(value.get("data"), str):
        raise InputError(f"Pilih berkas {field} terlebih dahulu.")
    try:
        raw = base64.b64decode(value["data"], validate=True)
    except Exception as exc:
        raise InputError(f"Isi berkas {field} tidak valid.") from exc
    return raw, str(value.get("name") or field)


class Handler(BaseHTTPRequestHandler):
    server_version = "CipherStegoLocal/1.0"

    def log_message(self, _format: str, *_args) -> None:
        # Never log request bodies, filenames, or passphrases.
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        route = unquote(urlsplit(self.path).path)
        if route == "/":
            route = "/index.html"
        target = (ROOT / route.lstrip("/")).resolve()
        if target != ROOT and ROOT not in target.parents:
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        if not target.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        content_type = mime + ("; charset=utf-8" if mime.startswith(("text/", "application/javascript")) else "")
        self._send(200, target.read_bytes(), content_type)

    def do_POST(self) -> None:
        origin = self.headers.get("Origin")
        if origin:
            parsed_origin = urlsplit(origin)
            host = parsed_origin.hostname or ""
            try:
                origin_port = parsed_origin.port
            except ValueError:
                origin_port = None
            if host not in {"127.0.0.1", "localhost"} or origin_port != self.server.server_address[1]:
                self._json(403, {"error": "Permintaan hanya diterima dari aplikasi lokal."})
                return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                raise InputError("Ukuran permintaan tidak valid atau terlalu besar.")
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(request, dict):
                raise InputError("Format permintaan tidak valid.")
            passphrase = request.get("passphrase", "")
            route = urlsplit(self.path).path

            if route == "/api/embed":
                pdf, name = decode_file(request.get("pdf"), "PDF")
                cover, _cover_name = decode_file(request.get("cover"), "PNG")
                result = embed(pdf, cover, passphrase, request.get("mode", "randomized"), name)
                self._json(200, {
                    "png_base64": base64.b64encode(result["png"]).decode("ascii"),
                    "filename": Path(safe_name(name, "dokumen.pdf")).stem + "_stego.png",
                    "metadata": result["metadata"],
                })
                return

            if route == "/api/extract":
                stego, _name = decode_file(request.get("stego"), "stego-PNG")
                result = extract(stego, passphrase, request.get("mode", "randomized"))
                self._json(200, {
                    "pdf_base64": base64.b64encode(result["pdf"]).decode("ascii"),
                    "filename": "dokumen_pulih.pdf",
                    "metadata": result["metadata"],
                })
                return

            if route == "/api/tamper":
                stego, name = decode_file(request.get("stego"), "stego-PNG")
                altered = tamper_header(stego)
                stem = Path(safe_name(name, "stego.png")).stem
                self._json(200, {
                    "png_base64": base64.b64encode(altered).decode("ascii"),
                    "filename": f"{stem}_header_berubah.png",
                })
                return

            if route == "/api/evaluate":
                pdf, name = decode_file(request.get("pdf"), "PDF")
                cover, _cover_name = decode_file(request.get("cover"), "PNG")
                self._json(200, evaluate(pdf, cover, passphrase, name))
                return

            self._json(404, {"error": "Rute tidak ditemukan."})
        except AuthenticationError as exc:
            self._json(400, {"error": str(exc), "kind": "authentication"})
        except InputError as exc:
            self._json(400, {"error": str(exc), "kind": "input"})
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._json(400, {"error": str(exc) or "Permintaan tidak dapat dibaca.", "kind": "input"})
        except Exception:
            self._json(500, {"error": "Pemrosesan lokal gagal. Periksa berkas dan coba lagi.", "kind": "server"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Jalankan demo lokal CipherStego")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"CipherStego berjalan di http://127.0.0.1:{args.port}")
    print("Pemrosesan berkas berlangsung di perangkat ini; tekan Ctrl+C untuk berhenti.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
