import os
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
    }


@contextmanager
def yhteys():
    yht = mysql.connector.connect(**_asetukset())
    try:
        yield yht
        yht.commit()
    except Exception:
        yht.rollback()
        raise
    finally:
        yht.close()


def alusta_tietokanta():
    sql_polku = os.path.join(os.path.dirname(__file__), "alustus.sql")
    with open(sql_polku, encoding="utf-8") as f:
        lauseet = [l.strip() for l in f.read().split(";") if l.strip()]
    with yhteys() as yht:
        with yht.cursor() as kursori:
            for lause in lauseet:
                kursori.execute(lause)
