"""SIPs sidecar HTTP server.

Serves the static dashboard (drop-in replacement for `python -m http.server 5510`)
AND provides write endpoints so the Studies feature can persist screenshots /
numeric fields / notes to disk while you edit, without any cloud round-trip.

Layout on disk:
    D:/SIPs/dashboard/
    ├── index.html
    ├── data.json
    ├── dates.json
    ├── data/<DATE>.json           (committed to git)
    └── studies/                   (committed to git)
        ├── studies.json           (all study records, single file)
        └── images/
            └── <key>.<ext>        (screenshots, one file per IndexedDB key)

API:
    GET  /api/health
        -> 200 {"ok": true, "writable": true, "studiesCount": N, "imagesCount": M}

    POST /api/studies/save           body = full studies array as JSON
        -> 200 {"ok": true, "count": N}

    POST /api/studies/image          body = {"key": "img-...", "dataUrl": "data:image/png;base64,..."}
        -> 200 {"ok": true, "path": "studies/images/img-xxx.png"}

    DELETE /api/studies/image/<key>
        -> 200 {"ok": true}

    GET  /studies/studies.json       (just a normal static file)
    GET  /studies/images/<key>.<ext> (just a normal static file)

Run:
    py D:/SIPs/sidecar.py
    # serves on http://127.0.0.1:5510
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

HOST = '127.0.0.1'
PORT = int(os.environ.get('SIPS_SIDECAR_PORT') or 5510)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard')
STUDIES_DIR = os.path.join(ROOT, 'studies')
IMAGES_DIR = os.path.join(STUDIES_DIR, 'images')
STUDIES_JSON = os.path.join(STUDIES_DIR, 'studies.json')
IMAGES_INDEX = os.path.join(IMAGES_DIR, 'index.json')

os.makedirs(IMAGES_DIR, exist_ok=True)
if not os.path.exists(STUDIES_JSON):
    with open(STUDIES_JSON, 'w', encoding='utf-8') as fh:
        json.dump([], fh)


def _rebuild_image_index():
    """Scan images dir and write {key: 'key.ext'} mapping so static hosts can resolve image paths."""
    mapping = {}
    for name in os.listdir(IMAGES_DIR):
        if name in ('index.json', 'index.json.tmp') or name.startswith('.'):
            continue
        base, _, ext = name.rpartition('.')
        if base and ext:
            mapping[base] = name
    tmp = IMAGES_INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(mapping, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, IMAGES_INDEX)
    return mapping


# Build the index once on startup so the file always exists.
_rebuild_image_index()


def _safe_key(key: str) -> str:
    """Allow only the characters we generate ourselves; reject anything else."""
    if not re.fullmatch(r'[A-Za-z0-9_\-]{1,128}', key or ''):
        raise ValueError(f'invalid key: {key!r}')
    return key


def _find_image_for_key(key: str) -> str | None:
    key = _safe_key(key)
    for ext in ('png', 'jpg', 'jpeg', 'webp', 'gif'):
        path = os.path.join(IMAGES_DIR, f'{key}.{ext}')
        if os.path.exists(path):
            return path
    return None


class SidecarHandler(SimpleHTTPRequestHandler):
    # Serve files from ROOT
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # -- CORS / no-cache for the live editor; cache is fine for static assets --
    def end_headers(self):
        # Allow same-origin + the file:// case (if ever opened directly).
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        # Studies JSON shouldn't be cached; static assets are fine.
        if self.path.startswith('/api/') or self.path.startswith('/studies/'):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, fmt, *args):
        # Quiet down the per-request spam; keep errors only.
        if args and str(args[1])[:1] in ('4', '5'):
            sys.stderr.write('%s - - [%s] %s\n' % (self.client_address[0], self.log_date_time_string(), fmt % args))

    # -- preflight --
    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    # -- JSON helpers --
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict | list:
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length > 0 else b''
        return json.loads(raw.decode('utf-8')) if raw else {}

    # -- GET: health endpoint + everything else falls through to static --
    def do_GET(self):
        if self.path == '/api/health':
            try:
                with open(STUDIES_JSON, 'r', encoding='utf-8') as fh:
                    studies = json.load(fh)
                images = [f for f in os.listdir(IMAGES_DIR) if not f.startswith('.') and f not in ('index.json', 'index.json.tmp')]
                self._send_json(HTTPStatus.OK, {
                    'ok': True,
                    'writable': True,
                    'studiesCount': len(studies) if isinstance(studies, list) else 0,
                    'imagesCount': len(images),
                    'studiesPath': os.path.relpath(STUDIES_JSON, ROOT).replace('\\', '/'),
                })
            except Exception as e:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {'ok': False, 'error': str(e)})
            return
        return super().do_GET()

    # -- POST: save studies, save image --
    def do_POST(self):
        try:
            if self.path == '/api/studies/save':
                payload = self._read_json()
                if not isinstance(payload, list):
                    self._send_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': 'expected JSON array of studies'})
                    return
                # Atomic write: tmp then rename
                tmp = STUDIES_JSON + '.tmp'
                with open(tmp, 'w', encoding='utf-8') as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
                os.replace(tmp, STUDIES_JSON)
                self._send_json(HTTPStatus.OK, {'ok': True, 'count': len(payload)})
                return

            if self.path == '/api/studies/image':
                data = self._read_json()
                key = _safe_key(str(data.get('key', '')))
                data_url = str(data.get('dataUrl', ''))
                m = re.match(r'^data:image/([A-Za-z0-9.+-]+);base64,(.+)$', data_url, re.DOTALL)
                if not m:
                    self._send_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': 'dataUrl must be data:image/<type>;base64,...'})
                    return
                mime_ext = m.group(1).lower()
                # Normalize MIME → file extension
                ext = {'jpeg': 'jpg', 'svg+xml': 'svg'}.get(mime_ext, mime_ext)
                if ext not in ('png', 'jpg', 'webp', 'gif', 'svg'):
                    self._send_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': f'unsupported image type: {mime_ext}'})
                    return
                # If an existing image with a different extension exists for this key, remove it.
                existing = _find_image_for_key(key)
                if existing and not existing.endswith('.' + ext):
                    try:
                        os.remove(existing)
                    except OSError:
                        pass
                binary = base64.b64decode(m.group(2), validate=True)
                out_path = os.path.join(IMAGES_DIR, f'{key}.{ext}')
                tmp = out_path + '.tmp'
                with open(tmp, 'wb') as fh:
                    fh.write(binary)
                os.replace(tmp, out_path)
                rel = os.path.relpath(out_path, ROOT).replace('\\', '/')
                _rebuild_image_index()
                self._send_json(HTTPStatus.OK, {'ok': True, 'path': rel, 'bytes': len(binary)})
                return

            self._send_json(HTTPStatus.NOT_FOUND, {'ok': False, 'error': f'unknown POST: {self.path}'})
        except ValueError as e:
            self._send_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(e)})
        except Exception as e:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {'ok': False, 'error': str(e)})

    # -- DELETE: remove image --
    def do_DELETE(self):
        try:
            m = re.match(r'^/api/studies/image/([A-Za-z0-9_\-]{1,128})/?$', self.path)
            if not m:
                self._send_json(HTTPStatus.NOT_FOUND, {'ok': False, 'error': f'unknown DELETE: {self.path}'})
                return
            key = m.group(1)
            existing = _find_image_for_key(key)
            if existing:
                os.remove(existing)
                _rebuild_image_index()
                self._send_json(HTTPStatus.OK, {'ok': True, 'deleted': os.path.basename(existing)})
            else:
                # Idempotent: a delete of a missing key is still "ok"
                self._send_json(HTTPStatus.OK, {'ok': True, 'deleted': None})
        except Exception as e:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {'ok': False, 'error': str(e)})


def main():
    print(f'[sidecar] serving {ROOT} on http://{HOST}:{PORT}')
    print(f'[sidecar] studies file: {STUDIES_JSON}')
    print(f'[sidecar] images dir:   {IMAGES_DIR}')
    server = ThreadingHTTPServer((HOST, PORT), SidecarHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[sidecar] shutting down')
        server.server_close()


if __name__ == '__main__':
    main()
