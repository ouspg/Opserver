import os
import threading
from contextlib import contextmanager
import mysql.connector
from mysql.connector import pooling, errors
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


# Yhteyspooli: etäpalvelimella (geopalvelin1, Tailscale) jokainen TCP+auth-
# kättely maksaa satoja millisekunteja, ja poolaamaton yhteys/kutsu teki sivuista
# tuskaisia. Pooli maksaa kättelyn ~kerran ja lainaa yhteyden uudelleen.
# pool_reset_session=False: käyttö on tilaton (ei sessiomuuttujia/temp-tauluja) ja
# yhteydenmanageri commit/rollbackaa aina ennen palautusta → nollausta ei tarvita
# (säästää yhden verkkomatkan palautuksessa).
_pooli = None
_pooli_lukko = threading.Lock()


def _pooli_koko() -> int:
    """Poolin koko (.env: DB_POOLI_KOKO). Oltava ≥ LLM_RINNAKKAISUUS + varaa UI:lle."""
    return int(os.getenv("DB_POOLI_KOKO", "8"))


def _hae_pooli():
    global _pooli
    if _pooli is None:
        with _pooli_lukko:
            if _pooli is None:
                _pooli = pooling.MySQLConnectionPool(
                    pool_name="opserver",
                    pool_size=_pooli_koko(),
                    pool_reset_session=False,
                    **_asetukset(),
                )
    return _pooli


@contextmanager
def yhteys():
    try:
        yht = _hae_pooli().get_connection()
    except errors.PoolError:
        # Pooli täynnä (esim. rinnakkaisuus > poolin koko) → tuore yhteys kuten
        # ennen. Ei kaadu ruuhkaan; hidas mutta toimii.
        yht = mysql.connector.connect(**_asetukset())
    # ponytail: ei per-lainaus-ping()iä — se lisäisi verkkomatkan joka kyselyyn
    # (luokittelun tuhannet kirjoitukset × Tailscale-RTT). Aktiivikäytössä yhteydet
    # eivät ehdi vanhentua; harvinainen idle-katkennut yhteys → kysely virhe kerran
    # (luokittelun passiluuppi yrittää erän uusiksi, UI-kysely toistetaan käsin).
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
        yht.close()  # pooliyhteys palautuu pooliin; tuore sulkeutuu


def alusta_tietokanta():
    sql_polku = os.path.join(os.path.dirname(__file__), "alustus.sql")
    with open(sql_polku, encoding="utf-8") as f:
        lauseet = [l.strip() for l in f.read().split(";") if l.strip()]
    with yhteys() as yht:
        with yht.cursor() as kursori:
            for lause in lauseet:
                kursori.execute(lause)
