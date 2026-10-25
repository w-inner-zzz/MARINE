"""The public website build (scripts/build_site.py) and basic accessibility of its pages."""

import importlib.util
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_site)

PAGES = [ROOT / "site" / "index.html", ROOT / "site" / "404.html",
         ROOT / "web-navigator" / "index.html", ROOT / "web" / "index.html"]


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    out = tmp_path_factory.mktemp("site") / "dist"
    build_site.build(out)
    return out


def test_build_layout(dist):
    for page in ("index.html", "404.html", "_headers", "bridge/index.html", "learn/index.html",
                 "diagnosis_flowchart.svg"):
        assert (dist / page).is_file(), page
    assert any((dist / "bridge" / "data").rglob("*.js"))
    assert any((dist / "learn" / "data").rglob("*.js"))


def test_build_publishes_no_source_code(dist):
    files = [p.relative_to(dist).as_posix() for p in dist.rglob("*") if p.is_file()]
    assert not [f for f in files if f.endswith((".py", ".pyc", ".env")) or "/." in "/" + f]


def test_build_fails_on_a_missing_asset(tmp_path):
    (tmp_path / "index.html").write_text('<img src="gone.png" alt="">', encoding="utf-8")
    with pytest.raises(SystemExit, match="gone.png is missing"):
        build_site.check(tmp_path)


def test_headers_file_parses():
    rules = dict(build_site.parse_headers((ROOT / "site" / "_headers").read_text(encoding="utf-8")))
    assert "Content-Security-Policy" in rules["/*"]
    assert "script-src 'self'" in rules["/*"]["Content-Security-Policy"]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_page_basics(page):
    html = page.read_text(encoding="utf-8")
    assert re.search(r'<html lang="en">', html)
    assert re.search(r"<title>[^<]+</title>", html)
    assert 'name="viewport"' in html
    assert '<main id="main"' in html
    for img in re.findall(r"<img\b[^>]*>", html):
        assert "alt=" in img, img
    assert "<script>" not in html, "inline scripts are blocked by the Content-Security-Policy"


@pytest.mark.parametrize("page", PAGES[:1] + PAGES[2:], ids=lambda p: p.relative_to(ROOT).as_posix())
def test_skip_link(page):
    assert 'class="skip-link" href="#main"' in page.read_text(encoding="utf-8")


@pytest.mark.parametrize("page", PAGES[2:], ids=lambda p: p.parent.name)
def test_charts_and_maps_have_text_alternatives(page):
    html = page.read_text(encoding="utf-8")
    charts = [div for div, classes in re.findall(r'(<div id="[^"]+" class="([^"]+)"[^>]*>)', html)
              if {"chart", "map", "acc-chart"} & set(classes.split())]
    assert len(charts) >= 3
    for div in charts:
        assert 'role="img"' in div and "aria-label=" in div, div
