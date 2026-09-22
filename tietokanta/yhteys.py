import os
import time
import threading
from contextlib import contextmanager
import mysql.connector
from mysql.connector import errors
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


def _idle_validointi_s() -> int:
    """Kynnys (s), jonka yli poolissa maannut yhteys validoidaan (ping+reconnect)
    ennen luovutusta. Hot-path (peräkkäiset kyselyt) alittaa kynnyksen → ei pingiä.
    (.env: DB_IDLE_VALIDOINTI_S; oletus 30 s.)"""
    return int(os.getenv("DB_IDLE_VALIDOINTI_S", "30"))


class _LaiskaPooli:
    """Luo yhteydet tarvittaessa kattoon (koko) asti ja käyttää palautetut
    uudelleen. Katon täyttyessä (rinnakkaisuuspiikki) antaa väliaikaisen yhteyden,
    joka suljetaan palautuksessa — ei tukita ruuhkaa eikä kasvateta poolia yli.

    Kestävyys MySQL:n uudelleenkäynnistykselle: (1) idle_validointi_s-kynnyksen yli
    maannut yhteys pingataan (reconnect) ennen luovutusta ja korvataan jos kuollut;
    (2) yhteystason virheen saanut yhteys suljetaan palautuksessa (rikki=True) eikä
    palaudu pooliin. Hot-pathilla (idle < kynnys) ei pingiä → ei ylimääräistä
    verkkomatkaa luokittelun tuhansiin kyselyihin."""

    def __init__(self, koko: int, asetukset: dict, idle_validointi_s: int = 30,
                 aika=time.monotonic):
        self._koko = koko
        self._asetukset = asetukset
        self._idle_validointi_s = idle_validointi_s
        self._aika = aika
        self._vapaat: list = []   # (yhteys, palautus_hetki), LIFO
        self._luotu = 0           # luotujen pooliyhteyksien määrä (vapaat + lainassa)
        self._lukko = threading.Lock()

    def _yhdista(self):
        return mysql.connector.connect(**self._asetukset)

    def _luo_pooliyhteys(self):
        """Uusi pooliyhteys; slotti (_luotu) vapautetaan jos kättely epäonnistuu."""
        try:
            return self._yhdista()
        except Exception:
            with self._lukko:
                self._luotu -= 1
            raise

    def hae(self):
        """Palauttaa (yhteys, pooloitu). pooloitu=False → väliaikainen yhteys, joka
        suljetaan palautuksessa (katto oli täynnä)."""
        with self._lukko:
            if self._vapaat:
                yht, hetki = self._vapaat.pop()
                tuore = (self._aika() - hetki) < self._idle_validointi_s
            else:
                yht = None
                luo_pooliin = self._luotu < self._koko
                if luo_pooliin:
                    self._luotu += 1
        # Kättely/ping lukon ULKOPUOLELLA — verkkoviive ei saa tukkia muita säikeitä.
        if yht is not None:
            if tuore:
                return yht, True          # hot-path: ei pingiä
            # Idle liian kauan → varmista elossa; kuollut korvataan tuoreella.
            try:
                yht.ping(reconnect=True, attempts=1, delay=0)
                return yht, True
            except Exception:
                try:
                    yht.close()
                except Exception:
                    pass
                return self._luo_pooliyhteys(), True   # slotti säilyi varattuna
        if luo_pooliin:
            return self._luo_pooliyhteys(), True
        return self._yhdista(), False

    def palauta(self, yht, pooloitu: bool, rikki: bool = False) -> None:
        if pooloitu and not rikki:
            with self._lukko:
                self._vapaat.append((yht, self._aika()))  # pooliin ilman ping-verkkomatkaa
            return
        try:
            yht.close()
        except Exception:
            pass
        if pooloitu:  # rikki pooliyhteys → vapauta slotti uudelleenluontia varten
            with self._lukko:
                self._luotu -= 1


def _hae_pooli() -> _LaiskaPooli:
    global _pooli
    if _pooli is None:
        with _pooli_lukko:
            if _pooli is None:
                _pooli = _LaiskaPooli(_pooli_koko(), _asetukset(), _idle_validointi_s())
    return _pooli


@contextmanager
def yhteys():
    pooli = _hae_pooli()
    yht, pooloitu = pooli.hae()
    rikki = False
    try:
        yield yht
        yht.commit()
    except (errors.OperationalError, errors.InterfaceError):
        # Yhteystason virhe (palvelin katkaisi, "Connection not available", ...) →
        # yhteys on rikki: ei rollbackia (kaatuisi) eikä paluuta pooliin.
        rikki = True
        raise
    except Exception:
        try:
            yht.rollback()
        except Exception:
            pass
        raise
    finally:
        pooli.palauta(yht, pooloitu, rikki=rikki)


def alusta_tietokanta():
    sql_polku = os.path.join(os.path.dirname(__file__), "alustus.sql")
    with open(sql_polku, encoding="utf-8") as f:
        lauseet = [l.strip() for l in f.read().split(";") if l.strip()]
    with yhteys() as yht:
        with yht.cursor() as kursori:
            for lause in lauseet:
                kursori.execute(lause)
