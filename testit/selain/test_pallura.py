"""Nukkuvan/kummituksen merkki pallurassa: pikkupallurassa (8–10 px) yksi keskitetty z,
isossa zzZ oikeassa yläkulmassa (#98)."""
import pytest

# Valkoisten (z-kirjaimen täyttö) pikselien painopiste suhteessa keskipisteeseen.
PAINOPISTE = """([koko, taso]) => {
  const c = luoPallura({profiili: {bitmappi: [], taustavari: '#000', etualavari: '#000'},
                        taso, nimimerkki: 'x'}, koko);
  const d = c.getContext('2d').getImageData(0, 0, koko, koko).data;
  let n = 0, sx = 0, sy = 0;
  for (let i = 0; i < d.length; i += 4) {
    if (d[i] > 200 && d[i + 1] > 200 && d[i + 2] > 200 && d[i + 3] > 200) {
      n++; sx += (i / 4) % koko; sy += Math.floor(i / 4 / koko);
    }
  }
  return n ? {n, dx: sx / n - koko / 2, dy: sy / n - koko / 2} : {n};
}"""


@pytest.mark.parametrize("koko", [8, 10])
def test_pikkupallurassa_yksi_keskitetty_z(kayttaja, koko):
    s = kayttaja("/korkeakoulut", "#korkeakoulut-rungot tr")
    p = s.evaluate(PAINOPISTE, [koko, "nukkuva"])
    assert p["n"] >= 4 and abs(p["dx"]) < 1.5 and abs(p["dy"]) < 1.5, p


def test_isossa_pallurassa_zzz_oikeassa_ylakulmassa(kayttaja):
    s = kayttaja("/korkeakoulut", "#korkeakoulut-rungot tr")
    p = s.evaluate(PAINOPISTE, [28, "nukkuva"])
    assert p["n"] > 0 and p["dx"] > 2 and p["dy"] < -2, p
