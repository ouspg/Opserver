"""WebUI-testit: Opserver-infomodaali (webui/reitit_info.py, webui/staattinen/info.js)."""
import shutil
import subprocess
from pathlib import Path
import pytest
from webui import reitit_info
from testit.webui_apu import _auth_pois  # noqa: F401 — autouse-fixture
from testit.webui_apu import asiakas


def test_info_palauttaa_infosivun_ja_kuvaan_kaannetyn_version(monkeypatch):
    # ./asenna antaa version Docker-kuvaan (kontissa ei ole .git-hakemistoa).
    monkeypatch.setenv("OPSERVER_VERSIO", "abc1234 2026-09-29")
    reitit_info._versio.cache_clear()
    data = asiakas.get("/api/info").json()
    assert data["teksti"] == Path("Opserver.md").read_text(encoding="utf-8")
    assert data["versio"] == "abc1234" and data["paiva"] == "2026-09-29"


def test_versio_tyokopiosta_ja_tuntematon_ilman_gitia(monkeypatch):
    # Kehityksessä (uvicorn .venv:llä) versio luetaan työkopion gitistä; jos sekään
    # ei onnistu, näytetään "tuntematon" eikä reitti kaadu.
    monkeypatch.delenv("OPSERVER_VERSIO", raising=False)
    reitit_info._versio.cache_clear()
    versio, paiva = reitit_info._versio()
    tyokopio = subprocess.run(["git", "log", "-1", "--format=%h %cs"], capture_output=True, text=True).stdout.split()
    assert [versio, paiva] == tyokopio
    def ei_gitia(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(reitit_info.subprocess, "run", ei_gitia)
    reitit_info._versio.cache_clear()
    assert reitit_info._versio() == ("tuntematon", "")
    reitit_info._versio.cache_clear()


@pytest.mark.skipif(shutil.which("node") is None, reason="node puuttuu")
def test_infosivun_markdown_renderoityy_ja_html_escapoidaan():
    # info.js:n markdownHtml ajetaan Nodella: perusmuotoilut toimivat, eikä
    # infosivun HTML tai javascript:-linkki suoritu (teksti escapoidaan ensin).
    ohjelma = """
    global.escapeHtml = (a) => String(a ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    global.document = { getElementById: () => ({ addEventListener() {}, classList: {} }) };
    global.window = {}; global.kytkeSulkeminen = () => {};
    eval(require("fs").readFileSync("webui/staattinen/info.js", "utf8"));
    process.stdout.write(window.markdownHtml(require("fs").readFileSync(0, "utf8")));
    """
    md = ("# Otsikko\nKappale **lihava** ja *kursiivi*\njatkuu.\n\n- a\n- b\n  jatko\n1. yksi\n\n"
          "<img src=x onerror=alert(1)> [x](javascript:alert(1)) [ok](https://e.fi/?a=1&b=2)\n---")
    tulos = subprocess.run(["node", "-e", ohjelma], input=md, capture_output=True, text=True, check=True).stdout
    assert tulos.split("\n") == [
        "<h1>Otsikko</h1>",
        "<p>Kappale <strong>lihava</strong> ja <em>kursiivi</em> jatkuu.</p>",
        "<ul>", "<li>a</li>", "<li>b jatko</li>", "</ul>", "<ol>", "<li>yksi</li>", "</ol>",
        '<p>&lt;img src=x onerror=alert(1)&gt; [x](javascript:alert(1)) '
        '<a href="https://e.fi/?a=1&amp;b=2" target="_blank" rel="noopener">ok</a></p>',
        "<hr>",
    ]
