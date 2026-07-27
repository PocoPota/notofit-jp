"""和欧調整ツールのローカルサーバ（docs/tuner.md）。

    .venv/bin/python -m notofit.server

ブラウザは表示のみを担当し、フォント生成は本番ビルドと同じ notofit.build を通す。
調整画面で見たものと配布物が食い違わないようにするため。
"""
from __future__ import annotations

import json
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from .build import (ROOT, CACHE, TuningConfig, WeightConfig, build_weight,
                    prepare_base, _subset, _key, NOTO)

PORT = 8765
TUNER = ROOT / 'tuner'
CONFIG_PATH = ROOT / 'config' / 'tuning.json'
_lock = threading.Lock()


def default_config() -> TuningConfig:
    return TuningConfig(
        weights=[WeightConfig(400, 400, 400, 1.0, 0), WeightConfig(700, 700, 700, 1.0, 0)],
        paltFraction=0.0,
    )


def load_config() -> TuningConfig:
    if CONFIG_PATH.exists():
        return TuningConfig.load(CONFIG_PATH)
    cfg = default_config()
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.save(CONFIG_PATH)
    return cfg


def reference_font(wght: int, text: str) -> bytes:
    """比較用の素の Noto Sans JP。置き換え互換性を目視で確かめるために使う。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f'ref-noto-{wght}-{_key(text)}.woff2'
    if not dest.exists():
        sub = CACHE / f'noto-sub-{_key(text)}.ttf'
        if not sub.exists():
            _subset(NOTO, text, sub)
        font = instancer.instantiateVariableFont(TTFont(sub), {'wght': wght},
                                                 updateFontNames=False)
        font.flavor = 'woff2'
        font.save(dest)
        font.close()
    return dest.read_bytes()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body=b'', ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), 'application/json')

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            if url.path in ('/', '/index.html'):
                return self._send(200, (TUNER / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if url.path == '/api/config':
                return self._json(json.loads(CONFIG_PATH.read_text()))
            if url.path == '/api/preview':
                return self._send(200, self._preview(q), 'font/woff2')
            if url.path == '/api/reference':
                weight = int(q.get('weight', ['400'])[0])
                return self._send(200, reference_font(weight, q.get('text', [''])[0]), 'font/woff2')
            self._send(404, b'not found', 'text/plain')
        except Exception as exc:  # noqa: BLE001 — 画面にそのまま出す
            import traceback
            traceback.print_exc()
            self._json({'error': str(exc)}, 500)

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        payload = json.loads(self.rfile.read(length) or b'{}')
        if url.path == '/api/config':
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
            return self._json({'saved': str(CONFIG_PATH)})
        self._send(404, b'not found', 'text/plain')

    def _preview(self, q) -> bytes:
        """クエリの設計値でプレビュー用フォントを生成する。"""
        weight = int(q.get('weight', ['400'])[0])
        text = q.get('text', [''])[0]
        cfg = TuningConfig(
            weights=[WeightConfig(
                weight=weight,
                jaWght=int(q.get('jaWght', [str(weight)])[0]),
                latinWght=float(q.get('latinWght', [str(weight)])[0]),
                scale=float(q.get('scale', ['1.0'])[0]),
                baselineOffset=int(q.get('baselineOffset', ['0'])[0]),
            )],
            paltFraction=float(q.get('palt', ['0'])[0]),
        )
        with _lock, tempfile.TemporaryDirectory() as tmp:
            path = build_weight(cfg, weight, Path(tmp), text=text, woff2=True)
            return path.read_bytes()


def main():
    load_config()
    url = f'http://127.0.0.1:{PORT}/'
    print(f'和欧調整ツール: {url}\n設定: {CONFIG_PATH}\n終了: Ctrl-C')
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n終了')


if __name__ == '__main__':
    main()
