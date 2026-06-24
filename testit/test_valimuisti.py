"""Testit TTL-välimuistille."""
from tietokanta.valimuisti import ttl_valimuisti


def test_valimuistittaa_saman_argumentin():
    kutsut = []

    @ttl_valimuisti(60, kello=lambda: 1000.0)
    def f(x):
        kutsut.append(x)
        return x * 2

    assert f(5) == 10
    assert f(5) == 10
    assert kutsut == [5]  # laskettu vain kerran


def test_eri_argumentit_lasketaan_erikseen():
    kutsut = []

    @ttl_valimuisti(60, kello=lambda: 1000.0)
    def f(x):
        kutsut.append(x)
        return x

    f(1); f(2); f(1)
    assert kutsut == [1, 2]


def test_vanhenee_ttl_jalkeen():
    kutsut = []
    nyt = [1000.0]

    @ttl_valimuisti(60, kello=lambda: nyt[0])
    def f(x):
        kutsut.append(x)
        return x

    f(1)
    nyt[0] = 1059.0   # alle TTL:n → yhä välimuistissa
    f(1)
    nyt[0] = 1061.0   # yli TTL:n → lasketaan uudelleen
    f(1)
    assert kutsut == [1, 1]


def test_tyhjenna_pakottaa_uudelleenlaskennan():
    kutsut = []

    @ttl_valimuisti(60, kello=lambda: 1000.0)
    def f(x):
        kutsut.append(x)
        return x

    f(1)
    f.tyhjenna()
    f(1)
    assert kutsut == [1, 1]


def test_kwargs_avaimina():
    kutsut = []

    @ttl_valimuisti(60, kello=lambda: 1000.0)
    def f(a, b=0):
        kutsut.append((a, b))
        return a + b

    assert f(1, b=2) == 3
    assert f(1, b=2) == 3
    assert f(1, b=3) == 4
    assert kutsut == [(1, 2), (1, 3)]
