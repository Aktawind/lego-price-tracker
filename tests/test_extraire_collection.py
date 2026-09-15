from bs4 import BeautifulSoup

from config_generator import extraire_collection


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def test_plan_a_json_ld_category():
    html = '''<script type="application/ld+json">
    {"@type": "Product", "name": "Corvette", "category": "Icons"}
    </script>'''
    collection, methode = extraire_collection(_soup(html))
    assert collection == "Icons"
    assert methode == "json-ld:category"


def test_plan_a_json_ld_breadcrumb():
    html = '''<script type="application/ld+json">
    {"@type": "BreadcrumbList", "itemListElement": [
        {"name": "Accueil"}, {"name": "Technic"}, {"name": "Megacar Koenigsegg"}
    ]}
    </script>'''
    collection, methode = extraire_collection(_soup(html))
    assert collection == "Technic"
    assert methode == "json-ld:breadcrumb"


def test_plan_a_ignores_lego_brand():
    # Le champ "brand" vaut presque toujours "LEGO" lui-même : pas une collection utile.
    html = '''<script type="application/ld+json">
    {"@type": "Product", "brand": {"name": "LEGO"}}
    </script>'''
    collection, methode = extraire_collection(_soup(html))
    assert methode is None
    assert collection == "N/A"


def test_plan_b_lien_theme():
    html = '<a href="/fr-fr/themes/star-wars">Star Wars</a>'
    collection, methode = extraire_collection(_soup(html))
    assert collection == "Star Wars"
    assert methode == "lien-theme"


def test_plan_c_css_brandlink_legacy():
    html = '<a class="BrandLink-abc123"><img alt="Technic Logo"></a>'
    collection, methode = extraire_collection(_soup(html))
    assert collection == "Technic"
    assert methode == "css-brandlink"


def test_rien_ne_marche():
    collection, methode = extraire_collection(_soup('<title>Page</title>'))
    assert collection == "N/A"
    assert methode is None


def test_json_ld_invalide_ne_fait_pas_planter():
    html = '<script type="application/ld+json">{ceci n\'est pas du json}</script>'
    collection, methode = extraire_collection(_soup(html))
    assert collection == "N/A"
    assert methode is None
