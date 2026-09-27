from bs4 import BeautifulSoup

from config_generator import _extraire_produit_json_ld


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def test_extrait_nom_et_image():
    html = '''<script type="application/ld+json">
    {"@type": "Product", "name": "Corvette", "image": "https://example.com/corvette.jpg"}
    </script>'''
    resultat = _extraire_produit_json_ld(_soup(html))
    assert resultat['name'] == "Corvette"
    assert resultat['image'] == "https://example.com/corvette.jpg"


def test_image_en_liste_prend_le_premier_element():
    html = '''<script type="application/ld+json">
    {"@type": "Product", "name": "Corvette", "image": ["https://example.com/a.jpg", "https://example.com/b.jpg"]}
    </script>'''
    resultat = _extraire_produit_json_ld(_soup(html))
    assert resultat['image'] == "https://example.com/a.jpg"


def test_nb_pieces_via_additional_property():
    html = '''<script type="application/ld+json">
    {"@type": "Product", "name": "Corvette", "additionalProperty": [
        {"name": "Nombre de pièces", "value": "1471"}
    ]}
    </script>'''
    resultat = _extraire_produit_json_ld(_soup(html))
    assert resultat['nb_pieces'] == "1471"


def test_ignore_les_objets_qui_ne_sont_pas_des_produits():
    html = '''<script type="application/ld+json">
    {"@type": "BreadcrumbList", "itemListElement": [{"name": "Accueil"}]}
    </script>'''
    resultat = _extraire_produit_json_ld(_soup(html))
    assert resultat == {}


def test_json_invalide_ne_leve_pas_dexception():
    html = '<script type="application/ld+json">{ceci n est pas du json}</script>'
    assert _extraire_produit_json_ld(_soup(html)) == {}


def test_page_sans_json_ld():
    assert _extraire_produit_json_ld(_soup('<title>Page</title>')) == {}
