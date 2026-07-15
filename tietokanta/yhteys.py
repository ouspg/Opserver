import os
import threading
from contextlib import contextmanager
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def _asetukset() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 21212)),
        "user": os.getenv("DB_USER", "kyber"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "opserverdb"),
        "charset": "utf8mb4",
        # Etäpalvelin (geopalvelin1, Tailscale) voi olla tavoittamattomissa →
        # ilman katkaisua connect roikkuu loputtomiin (näyttää "ei tulosta mitään").
        # Katkaisulla kutsu epäonnistuu selkeästi muutamassa sekunnissa.
        "connection_timeout": int(os.getenv("DB_YHTEYS_AIKAKATKAISU_S", "8")),
    }


# Laiska yhteyspooli: etäpalvelimella (geopalvelin1, Tailscale) jokainen TCP+auth-
# kättely maksaa satoja ms – sekunteja. mysql.connector.MySQLConnectionPool avaa
# KAIKKI pool_size-yhteydet heti rakennettaessa → ~24 s ennen ensimmäistäkään
# kyselyä (mitattu: 8 × ~2,7 s). Tämä pooli luo yhteydet vasta tarvittaessa: eka
# kysely maksaa yhden kättelyn, pooli kasvaa vain jos rinnakkaisuus sitä vaatii.
# Ei per-lainaus-ping()iä — se lisäisi verkkomatkan joka kyselyyn (luokittelun
# tuhannet kirjoitukset × Tailscale-RTT). Aktiivikäytössä yhteydet eivät ehdi
# vanhentua; harvinainen idle-katkennut yhteys → kysely virhe kerran (luokittelun
# passiluuppi yrittää erän uusiksi, UI-kysely toistetaan käsin).
_pooli = None
_pooli_lukko = threading.Lock()


def _pooli_koko() -> int:
    """Poolin koko (.env: DB_POOLI_KOKO). Oltava ≥ LLM_RINNAKKAISUUS + varaa UI:lle."""
    return int(os.getenv("DB_POOLI_KOKO", "8"))


class _LaiskaPooli:
    """Luo yhteydet tarvittaessa kattoon (koko) asti ja käyttää palautetut
    uudelleen. Katon täyttyessä (rinnakkaisuuspiikki) antaa väliaikaisen yhteyden,
    joka suljetaan palautuksessa — ei tukita ruuhkaa eikä kasvateta poolia yli."""

    def __init__(self, koko: int, asetukset: dict):
        self._koko = koko
        self._asetukset = asetukset
        self._vapaat: list = []   # käytettävissä olevat pooliyhteydet (LIFO)
        self._luotu = 0           # luotujen pooliyhteyksien määrä (vapaat + lainassa)
        self._lukko = threading.Lock()

    def _yhdista(self):
        return mysql.connector.connect(**self._asetukset)

    def hae(self):
        """Palauttaa (yhteys, pooloitu). pooloitu=False → väliaikainen yhteys, joka
        suljetaan palautuksessa (katto oli täynnä)."""
        with self._lukko:
            if self._vapaat:
                return self._vapaat.pop(), True
            luo_pooliin = self._luotu < self._koko
            if luo_pooliin:
                self._luotu += 1
        # Kättely lukon ULKOPUOLELLA — verkkoviive ei saa tukkia muita säikeitä.
        if luo_pooliin:
            try:
                return self._yhdista(), True
            except Exception:
                with self._lukko:
                    self._luotu -= 1  # vapauta slotti, ettei pooli jää vajaaksi
                raise
        return self._yhdista(), False

    def palauta(self, yht, pooloitu: bool) -> None:
        if pooloitu:
            with self._lukko:
                self._vapaat.append(yht)  # takaisin pooliin ilman ping-verkkomatkaa
        else:
            try:
                yht.close()
            except Exception:
                pass


def _hae_pooli() -> _LaiskaPooli:
    global _pooli
    if _pooli is None:
        with _pooli_lukko:
            if _pooli is None:
                _pooli = _LaiskaPooli(_pooli_koko(), _asetukset())
    return _pooli


@contextmanager
def yhteys():
    pooli = _hae_pooli()
    yht, pooloitu = pooli.hae()
    try:
        yield yht
        yht.commit()
    except Exception:
        try:
            yht.rollback()
        except Exception:
            pass
        raise
    finally:
        pooli.palauta(yht, pooloitu)


def alusta_tietokanta():
    sql_polku = os.path.join(os.path.dirname(__file__), "alustus.sql")
    with open(sql_polku, encoding="utf-8") as f:
        lauseet = [l.strip() for l in f.read().split(";") if l.strip()]
    with yhteys() as yht:
        with yht.cursor() as kursori:
            for lause in lauseet:
                kursori.execute(lause)
