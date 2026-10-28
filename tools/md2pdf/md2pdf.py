# -*- coding: utf-8 -*-
"""Markdown -> styled HTML -> PDF via headless Chrome (Chrome DevTools Protocol)."""
import base64
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import markdown
import websocket

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = r"""
@page { size: A4; margin: 20mm 17mm 17mm 17mm; }

* { box-sizing: border-box; }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Source Han Sans SC",
               "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif;
  font-size: 10.5pt;
  line-height: 1.8;
  color: #1f2328;
  margin: 0;
  text-align: justify;
  text-justify: inter-ideograph;
  -webkit-font-smoothing: antialiased;
}

/* ---------- Title block ---------- */
h1 {
  font-size: 22pt;
  line-height: 1.45;
  font-weight: 700;
  text-align: center;
  color: #10243e;
  margin: 18mm 0 6mm;
  padding: 0 6mm 6mm;
  border-bottom: 2.5px solid #2f6fb5;
  letter-spacing: .5px;
}

h1 + blockquote {
  margin: 0 0 10mm;
  padding: 5mm 6mm;
  background: #f4f7fb;
  border-left: 4px solid #2f6fb5;
  border-radius: 0 4px 4px 0;
  text-align: center;
  color: #4a5568;
  font-size: 9.5pt;
}

h1 + blockquote p { margin: 0; }

/* ---------- Headings ---------- */
h2 {
  font-size: 15pt;
  font-weight: 700;
  color: #14395f;
  margin: 11mm 0 4mm;
  padding: 0 0 2.2mm 4mm;
  border-left: 5px solid #2f6fb5;
  line-height: 1.4;
  page-break-after: avoid;
  break-after: avoid;
}

h3 {
  font-size: 12pt;
  font-weight: 700;
  color: #22558c;
  margin: 6mm 0 2.5mm;
  line-height: 1.5;
  page-break-after: avoid;
  break-after: avoid;
}

h4 { font-size: 11pt; font-weight: 700; color: #2f6fb5; margin: 4mm 0 2mm; }

/* ---------- Body ---------- */
p { margin: 0 0 3mm; orphans: 2; widows: 2; }

strong { color: #0d3b66; font-weight: 700; }

em { color: #3d4550; }

ul, ol { margin: 0 0 3.5mm; padding-left: 7mm; }
li { margin-bottom: 1.4mm; }
li > ul, li > ol { margin-top: 1.4mm; }

hr {
  border: 0;
  border-top: 1px solid #d8dee6;
  margin: 6mm 0;
}

/* ---------- Blockquote ---------- */
blockquote {
  margin: 3mm 0 4mm;
  padding: 3mm 5mm;
  background: #f7f9fc;
  border-left: 4px solid #b8c6d8;
  border-radius: 0 4px 4px 0;
  color: #4a5568;
  font-size: 10pt;
}
blockquote p:last-child { margin-bottom: 0; }

/* ---------- Code ---------- */
code {
  font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
  font-size: 9.3pt;
  background: #f0f3f7;
  border: 1px solid #e0e6ee;
  border-radius: 3px;
  padding: 0.6pt 3pt;
  color: #b03060;
  word-break: break-all;
}

pre {
  background: #f6f8fa;
  border: 1px solid #e1e6ed;
  border-radius: 5px;
  padding: 3mm 4mm;
  overflow: hidden;
  page-break-inside: avoid;
}
pre code { background: none; border: 0; padding: 0; color: #24292f; font-size: 9pt; line-height: 1.6; }

/* ---------- Tables ---------- */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 3mm 0 5mm;
  font-size: 9.3pt;
  line-height: 1.6;
  page-break-inside: auto;
}

thead { display: table-header-group; }
tr { page-break-inside: avoid; break-inside: avoid; }

th, td {
  border: 1px solid #ccd6e0;
  padding: 2.1mm 2.6mm;
  vertical-align: top;
  text-align: left;
}

th {
  background: #eaf0f7;
  color: #14395f;
  font-weight: 700;
  border-bottom: 1.5px solid #b9c9dc;
  white-space: nowrap;
}

tbody tr:nth-child(even) td { background: #fafbfd; }

td strong { color: #0d3b66; }

/* ---------- misc ---------- */
a { color: #2f6fb5; text-decoration: none; }

ul li strong { color: #0d3b66; }
"""


def build_html(md_text: str) -> str:
    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
        output_format="html5",
    )
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<title>需求文档-简版</title>\n<style>' + CSS + "</style>\n</head>\n<body>\n"
        + body
        + "\n</body>\n</html>"
    )


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    found = shutil.which("chrome") or shutil.which("msedge")
    if found:
        return found
    raise SystemExit("ERROR: no Chrome/Edge binary found")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_for_devtools(port: int, timeout: float = 40.0) -> str:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=2
            ) as r:
                return json.loads(r.read().decode())["Browser"]
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.4)
    raise SystemExit(f"ERROR: devtools never came up ({last})")


def main() -> None:
    md_path = pathlib.Path(sys.argv[1]).resolve()
    out_path = pathlib.Path(sys.argv[2]).resolve()

    md_text = md_path.read_text(encoding="utf-8")
    html = build_html(md_text)

    tmpdir = tempfile.mkdtemp(prefix="md2pdf_")
    profile = os.path.join(tmpdir, "profile")
    html_file = os.path.join(tmpdir, "doc.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    chrome = find_chrome()
    port = free_port()
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-extensions",
            "--hide-scrollbars",
            "--font-render-hinting=none",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        browser = wait_for_devtools(port)
        print(f"browser: {browser}")

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10) as r:
            targets = json.loads(r.read().decode())
        page_ws = next(
            t["webSocketDebuggerUrl"] for t in targets if t.get("type") == "page"
        )

        ws = websocket.create_connection(page_ws, timeout=90)
        counter = [0]

        def send(method, params=None, wait=True):
            counter[0] += 1
            msg_id = counter[0]
            ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            if not wait:
                return None
            while True:
                resp = json.loads(ws.recv())
                if resp.get("id") == msg_id:
                    if "error" in resp:
                        raise RuntimeError(f"{method} -> {resp['error']}")
                    return resp.get("result", {})

        send("Page.enable")
        send("Runtime.enable")
        send(
            "Page.navigate",
            {"url": pathlib.Path(html_file).as_uri()},
        )
        time.sleep(2.5)  # let fonts/layout settle
        send(
            "Runtime.evaluate",
            {"expression": "document.fonts.ready.then(()=>1)", "awaitPromise": True},
        )
        time.sleep(0.6)

        footer = (
            "<div style='font-family:Microsoft YaHei,sans-serif;font-size:8pt;"
            "color:#7a8794;width:100%;text-align:center;padding-top:3mm;"
            "border-top:.5px solid #d8dee6;'>"
            "<span class='pageNumber'></span> / <span class='totalPages'></span>"
            "</div>"
        )
        header = (
            "<div style='font-family:Microsoft YaHei,sans-serif;font-size:8pt;"
            "color:#8a95a1;width:100%;text-align:right;padding-bottom:2mm;'>"
            "具身智能机器人场景交付智能体 · 立项说明（简版）</div>"
        )

        result = send(
            "Page.printToPDF",
            {
                "landscape": False,
                "printBackground": True,
                "preferCSSPageSize": True,
                "displayHeaderFooter": True,
                "headerTemplate": header,
                "footerTemplate": footer,
                "marginTop": 0.6,
                "marginBottom": 0.6,
                "marginLeft": 0.6,
                "marginRight": 0.6,
            },
        )
        data = base64.b64decode(result["data"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # write via temp + replace, retrying through sync-software file locks
        tmp_out = out_path.with_suffix(out_path.suffix + ".tmp")
        last_err = None
        for attempt in range(6):
            try:
                tmp_out.write_bytes(data)
                os.replace(tmp_out, out_path)
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        if last_err is not None:
            raise last_err
        print(f"OK  {out_path}  ({len(data)/1024:.1f} KB)")
        ws.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
