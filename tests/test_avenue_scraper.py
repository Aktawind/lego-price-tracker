from bs4 import BeautifulSoup

import avenue_scraper


def _soup_offre(alt_vendeur, prix="99.99", href="/go/px/1234"):
    html = f'''
    <div class="prodf-px" data-prix="{prix}">
        <div class="prodf-px-logo"><img alt="{alt_vendeur}"></div>
        <a href="{href}"></a>
    </div>
    '''
    return BeautifulSoup(html, 'html.parser')


def test_extraire_offres_reconnait_galaxus():
    soup = _soup_offre("Acheter LEGO Icons 10321 chez Galaxus")
    offres = avenue_scraper.extraire_offres_de_la_page(soup)
    assert len(offres) == 1
    assert offres[0]['site'] == "Galaxus"
    assert offres[0]['prix'] == 99.99


def test_extraire_offres_ignore_un_vendeur_non_suivi():
    soup = _soup_offre("Acheter LEGO Icons 10321 chez Rakuten")
    assert avenue_scraper.extraire_offres_de_la_page(soup) == []


def test_extraire_offres_construit_une_url_absolue():
    soup = _soup_offre("Acheter LEGO Icons 10321 chez Amazon", href="go/px/5678")
    offres = avenue_scraper.extraire_offres_de_la_page(soup)
    assert offres[0]['url'] == "https://www.avenuedelabrique.com/go/px/5678"
