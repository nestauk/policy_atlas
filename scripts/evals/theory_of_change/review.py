"""A local website to browse the candidate longlist and record keep / reserve / drop decisions.

What it shows, per candidate: the facts from ``candidates/longlist.csv``, the figure
images, the original document, and (once extracted) the theory as transcribed in
``cases/<id>/case.json`` or ``case.draft.json``. A decision made on the page is written to
``candidates/decisions.csv`` and the longlist is rebuilt (``candidates/merge.py``), so the
file stays the record.

Run from the repo root, then open http://127.0.0.1:8765:

    python3 scripts/evals/theory_of_change/review.py

Only this machine can reach it. Uses the Python standard library only.
"""

import csv
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
CAND = HERE / "candidates"
sys.path.insert(0, str(CAND))
import merge  # noqa: E402

DECISIONS = ("keep", "reserve", "drop", "duplicate")
PORT = 8765


def data() -> dict:
    rows = list(csv.DictReader((CAND / "longlist.csv").open()))
    cases = {}
    for r in rows:
        d = HERE / "cases" / r["id"]
        for name in ("case.json", "case.draft.json"):
            if (d / name).exists():
                cases[r["id"]] = {"file": name, **json.loads((d / name).read_text())}
                break
        if (d / "source.json").exists():
            cases.setdefault(r["id"], {})["source"] = json.loads((d / "source.json").read_text())
        if (d / "brief.json").exists():
            cases.setdefault(r["id"], {})["short_brief"] = json.loads((d / "brief.json").read_text())
    return {"rows": rows, "cases": cases}


def decide(case_id: str, decision: str, reason: str) -> None:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    path = CAND / "decisions.csv"
    rows = [r for r in csv.DictReader(path.open()) if r["id"] != case_id]
    rows.append({"id": case_id, "decision": decision, "reason": reason.strip() or "(owner, no reason given)"})
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "decision", "reason"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["id"]))  # sorted, so git diffs stay small
    merge.main()


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str, status: int = 200, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server's name
        if self.path in ("/", "/index.html"):
            return self._send((HERE / "review.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/data":
            return self._send(json.dumps(data()).encode(), "application/json")
        if self.path.startswith("/file/"):
            path = (HERE / unquote(self.path[6:])).resolve()
            if not path.is_relative_to(HERE) or not path.is_file():
                return self._send(b"not found", "text/plain", 404)
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            # Downloaded web pages are untrusted: show them with scripts switched off.
            extra = {"Content-Security-Policy": "sandbox"} if "html" in ctype or "xml" in ctype else {}
            return self._send(path.read_bytes(), ctype, headers=extra)
        self._send(b"not found", "text/plain", 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/decision":
            return self._send(b"not found", "text/plain", 404)
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            decide(body["id"], body["decision"], body.get("reason", ""))
        except (ValueError, KeyError, SystemExit) as e:
            return self._send(str(e).encode(), "text/plain", 400)
        self._send(b'{"ok": true}', "application/json")

    def log_message(self, *args: object) -> None:  # keep the terminal quiet
        pass


if __name__ == "__main__":
    print(f"Longlist review: http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
