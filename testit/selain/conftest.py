"""Selaintestit (headless Chromium, playwright) oikeaa WebUI:ta ja MySQL:ää vasten.

Ajetaan vain `./testit/selaintesti.sh`:lla (asettaa OPSERVER_SELAIN=1) — tavallinen
pytest-ajo ohittaa nämä, koska ne vaativat MySQL:n ja selaimen.

Jokainen ajo luo oman kannan (selain_<pid>) MySQL-palvelimelle SELAIN_DB_*, ajaa
alustus.sql:n + esitäyttämättömät migraatiot, täyttää siemen.py:n datalla, käynnistää
uvicornin vapaaseen porttiin ja pudottaa kannan lopuksi → ajot eivät sotke toisiaan
ja kirjoittavat testit alkavat aina samasta tilasta."""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

if not os.environ.get("OPSERVER_SELAIN"):
    collect_ignore_glob = ["test_*.py"]

JUURI = Path(__file__).resolve().parents[2]
SLUG = "esr_kyber"


def _db_asetukset():
    return dict(host=os.environ.get("SELAIN_DB_HOST", "127.0.0.1"),
                port=int(os.environ.get("SELAIN_DB_PORT", "21414")),
                user=os.environ.get("SELAIN_DB_USER", "root"),
                password=os.environ.get("SELAIN_DB_PASSWORD", "selain"))


def _aja_sql(kursori, sql):
    for _ in kursori.execute(sql, multi=True):
        pass


def _aja_migraatio(kursori, sql):
    """Lause kerrallaan kuten `asenna`: alustus.sql sisältää jo osan migraatioista, joten
    duplikaattiluokan virheet = jo sovellettu; muut virheet kaatavat."""
    import mysql.connector
    for lause in re.split(r";\s*\n", re.sub(r"(?m)^--.*$", "", sql)):
        if not lause.strip():
            continue
        try:
            _aja_sql(kursori, lause)
        except mysql.connector.Error as e:
            if not re.search(r"Duplicate column|Duplicate key name|Duplicate entry|already exists|Can.t DROP", str(e)):
                raise


@pytest.fixture(scope="session")
def kanta():
    """Oma kanta tälle ajolle; nimi palautetaan, pudotetaan lopuksi."""
    import mysql.connector
    from testit.selain import siemen
    nimi = f"selain_{os.getpid()}"
    yht = mysql.connector.connect(**_db_asetukset(), autocommit=True)
    kursori = yht.cursor()
    kursori.execute(f"DROP DATABASE IF EXISTS {nimi}")
    kursori.execute(f"CREATE DATABASE {nimi}")
    kursori.execute(f"USE {nimi}")
    _aja_sql(kursori, (JUURI / "tietokanta/alustus.sql").read_text())
    esitaytetyt = set(re.findall(r"migraatio_\d+\.sql", (JUURI / "tietokanta/alustus_migraatiot.sql").read_text()))
    for tiedosto in sorted((JUURI / "tietokanta").glob("migraatio_*.sql")):
        if tiedosto.name not in esitaytetyt:
            _aja_migraatio(kursori, tiedosto.read_text())
    siemen.tayta(kursori)
    try:
        yield nimi
    finally:
        kursori.execute(f"DROP DATABASE IF EXISTS {nimi}")
        yht.close()


@pytest.fixture(scope="session")
def pohja(kanta):
    """Käynnissä olevan WebUI:n osoite (ilman Basic Authia)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        portti = s.getsockname()[1]
    db = _db_asetukset()
    ymparisto = {**os.environ, "DB_HOST": db["host"], "DB_PORT": str(db["port"]), "DB_USER": db["user"],
                 "DB_PASSWORD": db["password"], "DB_NAME": kanta,
                 "WEBUI_AUTH_KAYTTAJA": "", "WEBUI_AUTH_SALASANA": ""}
    loki = open(Path(os.environ.get("TMPDIR", "/tmp")) / f"selain_uvicorn_{portti}.log", "w")
    prosessi = subprocess.Popen([sys.executable, "-m", "uvicorn", "webui.palvelin:sovellus", "--port", str(portti)],
                                cwd=JUURI, env=ymparisto, stdout=loki, stderr=subprocess.STDOUT)
    osoite = f"http://127.0.0.1:{portti}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(osoite + "/api/korkeakoulut", timeout=2)
                break
            except OSError:
                if prosessi.poll() is not None:
                    pytest.fail(f"uvicorn kaatui, ks. {loki.name}")
                time.sleep(0.2)
        else:
            pytest.fail(f"uvicorn ei vastannut, ks. {loki.name}")
        yield osoite
    finally:
        prosessi.terminate()
        prosessi.wait(10)
        loki.close()


@pytest.fixture(scope="session")
def selain():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def kayttaja(selain, pohja):
    """Tehdas: kayttaja(polku, odota=None, leveys=1280, korkeus=800) → uusi sivu omassa
    browser contextissaan (= eri käyttäjä: oma eväste, localStorage ja profiili).
    Sivun JS-virheet kaatavat testin lopuksi."""
    kontekstit, virheet = [], []

    def uusi(polku, odota=None, leveys=1280, korkeus=800):
        k = selain.new_context(viewport={"width": leveys, "height": korkeus})
        kontekstit.append(k)
        sivu = k.new_page()
        sivu.on("pageerror", lambda e: virheet.append(str(e)))
        sivu.goto(pohja + polku)
        if odota:
            sivu.wait_for_selector(odota, timeout=30000)
        return sivu

    yield uusi
    for k in kontekstit:
        k.close()
    assert not virheet, f"JS-virheet sivulla: {virheet}"
