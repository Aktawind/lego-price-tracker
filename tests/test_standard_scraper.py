from bs4 import BeautifulSoup

from scrapers import standard_scraper


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def test_json_ld_price_simple_offer():
    html = '''<script type="application/ld+json">
    {"@type": "Product", "offers": {"@type": "Offer", "price": "209.99"}}
    </script>'''
    assert standard_scraper._extraire_prix_json_ld(_soup(html)) == 209.99


def test_json_ld_price_aggregate_offer_low_price():
    html = '''<script type="application/ld+json">
    {"@type": "Product", "offers": {"@type": "AggregateOffer", "lowPrice": "49.99", "highPrice": "59.99"}}
    </script>'''
    assert standard_scraper._extraire_prix_json_ld(_soup(html)) == 49.99


def test_json_ld_price_list_of_objects():
    html = '''<script type="application/ld+json">
    [{"@type": "BreadcrumbList"}, {"@type": "Product", "offers": {"price": "99.0"}}]
    </script>'''
    assert standard_scraper._extraire_prix_json_ld(_soup(html)) == 99.0


def test_json_ld_price_absent_retourne_none():
    assert standard_scraper._extraire_prix_json_ld(_soup('<title>Page</title>')) is None


def test_json_ld_invalide_ne_fait_pas_planter():
    html = '<script type="application/ld+json">{pas du json valide}</script>'
    assert standard_scraper._extraire_prix_json_ld(_soup(html)) is None


class FausseReponse:
    def __init__(self, content):
        self.content = content.encode('utf-8')

    def raise_for_status(self):
        pass


def test_scrape_utilise_le_selecteur_css_en_priorite(monkeypatch):
    html = '''
    <html><body>
        <div class="prix">129,99€</div>
        <script type="application/ld+json">{"offers": {"price": "999.99"}}</script>
    </body></html>
    '''
    monkeypatch.setattr(standard_scraper.requests, 'get', lambda *a, **k: FausseReponse(html))
    prix = standard_scraper.scrape('https://example.com', '.prix', headers={})
    assert prix == 129.99


def test_scrape_retombe_sur_json_ld_si_selecteur_absent(monkeypatch):
    html = '''
    <html><body>
        <div class="autre-chose">rien à voir</div>
        <script type="application/ld+json">{"offers": {"price": "209.99"}}</script>
    </body></html>
    '''
    monkeypatch.setattr(standard_scraper.requests, 'get', lambda *a, **k: FausseReponse(html))
    prix = standard_scraper.scrape('https://www.lego.com/fr-fr/product/10321', '[data-test="product-price"]', headers={})
    assert prix == 209.99


def test_scrape_selecteur_prefixe_ignore_le_suffixe_de_hash_css(monkeypatch):
    # Idealo (et d'autres sites basés sur des CSS modules) génère un suffixe
    # de hash qui change à chaque déploiement (ex: sr-detailedPriceInfo__price_sYVmx) :
    # le sélecteur utilisé en config doit matcher un préfixe stable, insensible
    # à ce suffixe. Basé sur une page réelle capturée via le diagnostic.
    html = '''
    <div class="sr-detailedPriceInfo_ypbTl"><div class="sr-detailedPriceInfo__price_sYVmx">
    <span></span>139,99 €<span class="sr-detailedPriceInfo__vatIncluded_aJ2yj">TVA incluse</span>
    </div></div>
    '''
    monkeypatch.setattr(standard_scraper.requests, 'get', lambda *a, **k: FausseReponse(html))
    prix = standard_scraper.scrape(
        'https://www.idealo.fr/cat/6992/jeux-de-construction.html?q=x',
        'div[class^="sr-detailedPriceInfo__price_"]', headers={},
    )
    assert prix == 139.99


def test_scrape_retourne_none_si_rien_ne_marche(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # scrape() écrit un fichier de diagnostic dans le cwd
    html = '<html><body><p>Aucun prix ici</p></body></html>'
    monkeypatch.setattr(standard_scraper.requests, 'get', lambda *a, **k: FausseReponse(html))
    prix = standard_scraper.scrape('https://example.com', '.prix', headers={})
    assert prix is None


def test_scrape_log_distingue_json_ld_absent_de_json_ld_sans_prix(monkeypatch, caplog, tmp_path):
    monkeypatch.chdir(tmp_path)  # scrape() écrit un fichier de diagnostic dans le cwd
    # Diagnostic utile pour un futur échec sans accès direct au site : on veut
    # pouvoir distinguer "page bloquée / pas de JSON-LD" de "JSON-LD présent
    # mais sans champ prix exploitable" (ex: rupture de stock).
    monkeypatch.setattr(standard_scraper.requests, 'get',
                         lambda *a, **k: FausseReponse('<html><body><p>Aucun prix ici</p></body></html>'))
    with caplog.at_level('WARNING'):
        standard_scraper.scrape('https://example.com', '.prix', headers={})
    assert "Aucune donnée JSON-LD trouvée" in caplog.text

    caplog.clear()
    html_sans_prix = '<script type="application/ld+json">{"offers": {"availability": "OutOfStock"}}</script>'
    monkeypatch.setattr(standard_scraper.requests, 'get', lambda *a, **k: FausseReponse(html_sans_prix))
    with caplog.at_level('WARNING'):
        standard_scraper.scrape('https://example.com', '.prix', headers={})
    assert "présentes" in caplog.text or "présent" in caplog.text


def test_scrape_sauvegarde_un_diagnostic_nomme_par_domaine_en_cas_echec(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    html = '<html><body><p>Aucun prix ici</p></body></html>'
    monkeypatch.setattr(standard_scraper.requests, 'get', lambda *a, **k: FausseReponse(html))
    standard_scraper.scrape('https://www.idealo.fr/prix/12345.html', '.prix', headers={})

    fichiers = list(tmp_path.glob('debug_www_idealo_fr_*.html'))
    assert len(fichiers) == 1
    assert 'Aucun prix ici' in fichiers[0].read_text(encoding='utf-8')
