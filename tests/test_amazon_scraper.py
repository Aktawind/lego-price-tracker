from bs4 import BeautifulSoup

from scrapers import amazon_scraper


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def test_extraire_prix_via_a_offscreen():
    html = '<span class="a-price"><span class="a-offscreen">34,99€</span></span>'
    assert amazon_scraper._extraire_prix_depuis_soup(_soup(html)) == 34.99


def test_extraire_prix_via_a_price_whole_et_fraction():
    html = '''
    <span class="a-price">
        <span class="a-price-whole">34</span>
        <span class="a-price-fraction">99</span>
    </span>
    '''
    assert amazon_scraper._extraire_prix_depuis_soup(_soup(html)) == 34.99


def test_extraire_prix_priorise_a_offscreen_sur_le_reste():
    html = '''
    <span class="a-offscreen">129,00€</span>
    <span class="a-price-whole">1</span><span class="a-price-fraction">00</span>
    '''
    assert amazon_scraper._extraire_prix_depuis_soup(_soup(html)) == 129.00


def test_extraire_prix_retourne_none_si_rien_ne_correspond():
    assert amazon_scraper._extraire_prix_depuis_soup(_soup('<p>Indisponible</p>')) is None
