"""HTTP Basic Auth -middleware (WEBUI_AUTH_* .env:ssä); onnistunut kirjautuminen muistetaan evästeellä."""
import base64
import hashlib
import hmac
import os
import secrets


_AUTH_EVASTE = "opserver_auth"


def _auth_token(kayttaja: str, salasana: str) -> str:
    """Auth-evästeen arvo: HMAC-SHA256 käyttäjästä salasana-avaimella. Väärentämätön
    ilman salasanaa; saadaan vain Basic-todennetun HTTP-vastauksen kautta."""
    return hmac.new(salasana.encode(), kayttaja.encode(), hashlib.sha256).hexdigest()


def _evasteesta(cookie_otsikko: str, nimi: str) -> str:
    for osa in cookie_otsikko.split(";"):
        avain, _, arvo = osa.strip().partition("=")
        if avain == nimi:
            return arvo
    return ""


class PerusAutentikointi:
    """HTTP Basic Auth -välikerros demojen suojaukseen (esim. Tailscale Funnel).

    Aktivoituu vain kun .env:ssä on sekä WEBUI_AUTH_KAYTTAJA että
    WEBUI_AUTH_SALASANA; tyhjänä = pois päältä (LAN-oletus muuttumaton). Suojaa
    sekä HTTP- että WebSocket-yhteydet. Tunnusvertailu on vakioaikainen
    (secrets.compare_digest). Turvallinen vain HTTPS:n yli (Funnel päättää TLS:n).

    Selain ei lähetä Authorization-otsikkoa WebSocket-kättelyssä, joten authatun
    HTTP-vastauksen yhteydessä asetetaan auth-eväste; selain lähettää sen WS-
    kättelyssä ja _kelpaa hyväksyy joko Basic-otsikon tai evästeen.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        kayttaja = os.environ.get("WEBUI_AUTH_KAYTTAJA", "")
        salasana = os.environ.get("WEBUI_AUTH_SALASANA", "")
        if not (kayttaja and salasana):
            await self.app(scope, receive, send)
            return
        if self._kelpaa(scope, kayttaja, salasana):
            if scope["type"] == "http":
                await self.app(scope, receive, self._evasteen_kanssa(send, kayttaja, salasana))
            else:
                await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
        else:
            await send({"type": "http.response.start", "status": 401, "headers": [
                (b"www-authenticate", b'Basic realm="Opserver"'),
                (b"content-type", b"text/plain; charset=utf-8"),
            ]})
            await send({"type": "http.response.body", "body": "Kirjautuminen vaaditaan.".encode()})

    @staticmethod
    def _evasteen_kanssa(send, kayttaja: str, salasana: str):
        """Kääre, joka lisää auth-evästeen HTTP-vastauksen alkuun."""
        evaste = (f"{_AUTH_EVASTE}={_auth_token(kayttaja, salasana)}"
                  "; Path=/; HttpOnly; SameSite=Strict").encode("latin-1")

        async def kaaritty(viesti):
            if viesti["type"] == "http.response.start":
                viesti = dict(viesti)
                viesti["headers"] = list(viesti.get("headers") or []) + [(b"set-cookie", evaste)]
            await send(viesti)

        return kaaritty

    @staticmethod
    def _kelpaa(scope, kayttaja: str, salasana: str) -> bool:
        otsikot = dict(scope.get("headers") or [])
        auth = otsikot.get(b"authorization", b"").decode("latin-1")
        if auth.startswith("Basic "):
            try:
                nimi, _, sala = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
                if (secrets.compare_digest(nimi, kayttaja)
                        and secrets.compare_digest(sala, salasana)):
                    return True
            except (ValueError, UnicodeDecodeError):
                pass
        # WebSocket-kättely: selain lähettää evästeen muttei Authorization-otsikkoa.
        token = _evasteesta(otsikot.get(b"cookie", b"").decode("latin-1"), _AUTH_EVASTE)
        if token:
            return secrets.compare_digest(token, _auth_token(kayttaja, salasana))
        return False
