"""LLM-asetusten pysyvä muutos .env-tiedostoon (ja ajossa olevaan ympäristöön)."""
import os

_ENV_POLKU = os.path.join(os.path.dirname(__file__), "..", ".env")


def paivita_env(avain: str, arvo: str, polku: str = _ENV_POLKU) -> None:
    """Asettaa avain=arvo .env-tiedostoon: korvaa rivin tai lisää sen loppuun."""
    rivit = []
    if os.path.exists(polku):
        with open(polku, encoding="utf-8") as f:
            rivit = f.readlines()

    korvattu = False
    for i, rivi in enumerate(rivit):
        if rivi.lstrip().startswith(f"{avain}=") or rivi.lstrip().startswith(f"{avain} ="):
            rivit[i] = f"{avain}={arvo}\n"
            korvattu = True
            break
    if not korvattu:
        if rivit and not rivit[-1].endswith("\n"):
            rivit[-1] += "\n"
        rivit.append(f"{avain}={arvo}\n")

    with open(polku, "w", encoding="utf-8") as f:
        f.writelines(rivit)


def aseta_malli(malli: str) -> None:
    """Vaihtaa LLM_MODEL:n pysyvästi .env:iin ja päivittää ajossa olevan ympäristön."""
    paivita_env("LLM_MODEL", malli, _ENV_POLKU)
    os.environ["LLM_MODEL"] = malli
