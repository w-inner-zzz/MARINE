"""Build the public website into dist/ (standard library only).

    python scripts/build_site.py           build dist/
    python scripts/build_site.py --serve   build, then serve dist/ on http://localhost:8788
                                           with the same headers as the host (site/_headers)

Layout of the built site:
    /          landing page (site/index.html)
    /bridge/   bridge view (web-navigator/)
    /learn/    full teaching website (web/)

Only the website files are copied: the Python source, tests and docs stay out
of the public site. The scenario data in web*/data is pre-computed by
`python export_web.py` and committed, so the host does not need to run Python
code beyond this copy step.
"""

import argparse
import fnmatch
import functools
import http.server
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SITE = ROOT / "site"
SECTIONS = {"bridge": ROOT / "web-navigator", "learn": ROOT / "web"}
EXTRAS = {ROOT / "docs" / "diagnosis_flowchart.svg": "diagnosis_flowchart.svg"}

# Cloudflare Pages limits (https://developers.cloudflare.com/pages/platform/limits)
MAX_FILES = 20_000
MAX_FILE_BYTES = 25 * 1024 * 1024
IGNORE = shutil.ignore_patterns("__pycache__", "*.py", "*.pyc", ".DS_Store", "Thumbs.db")
LOCAL_REF = re.compile(r'(?:src|href)="(?!https?:|#|mailto:|data:)([^"]+)"')


def build(dist: pathlib.Path = DIST) -> None:
    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree(SITE, dist, ignore=IGNORE)
    for name, source in SECTIONS.items():
        shutil.copytree(source, dist / name, ignore=IGNORE)
    for source, name in EXTRAS.items():
        shutil.copy2(source, dist / name)
    check(dist)
    files = [p for p in dist.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    print(f"built {dist}: {len(files)} files, {size / 1e6:.1f} MB")


def check(dist: pathlib.Path) -> None:
    """Fail the build on anything the host would reject or that would 404."""
    problems = []
    files = [p for p in dist.rglob("*") if p.is_file()]
    if len(files) > MAX_FILES:
        problems.append(f"{len(files)} files (limit {MAX_FILES})")
    problems += [f"{p.relative_to(dist)} is over 25 MiB" for p in files
                 if p.stat().st_size > MAX_FILE_BYTES]
    for page in dist.rglob("*.html"):
        for ref in LOCAL_REF.findall(page.read_text(encoding="utf-8")):
            target = (page.parent / ref.split("#")[0].split("?")[0]).resolve()
            if ref.startswith("/"):
                target = (dist / ref.lstrip("/")).resolve()
                if ref.endswith("/"):
                    target = target / "index.html"
            elif ref.endswith("/"):
                target = target / "index.html"
            if dist.resolve() not in target.parents:
                problems.append(f"{page.relative_to(dist)}: {ref} points outside the site")
            elif not target.exists():
                problems.append(f"{page.relative_to(dist)}: {ref} is missing")
    if problems:
        raise SystemExit("build failed:\n  " + "\n  ".join(problems))


def parse_headers(text: str):
    """site/_headers -> [(url pattern, {name: value})], in the host's format."""
    rules, current = [], None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            current = (line.strip(), {})
            rules.append(current)
        elif current and ":" in line:
            name, value = line.strip().split(":", 1)
            current[1][name.strip()] = value.strip()
    return rules


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/ like the host: _headers applied, 404.html for missing pages."""
    rules = []

    def end_headers(self):
        path = self.path.split("?")[0]
        for pattern, headers in self.rules:
            if fnmatch.fnmatchcase(path, pattern):
                for name, value in headers.items():
                    self.send_header(name, value)
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        page = pathlib.Path(self.directory) / "404.html"
        if code != 404 or not page.exists():
            return super().send_error(code, message, explain)
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int) -> None:
    PreviewHandler.rules = parse_headers((DIST / "_headers").read_text(encoding="utf-8"))
    handler = functools.partial(PreviewHandler, directory=str(DIST))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"serving dist/ on http://localhost:{port}/  (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="serve dist/ after building")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    build()
    if args.serve:
        serve(args.port)
    sys.exit(0)
