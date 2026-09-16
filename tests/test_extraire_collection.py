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


def test_plan_a_ignores_generic_category():
    # "category": "LEGO" est une valeur générique observée en pratique sur lego.com,
    # pas le nom d'une gamme -- ne doit jamais finir en config.
    html = '''<script type="application/ld+json">
    {"@type": "Product", "category": "LEGO"}
    </script>'''
    collection, methode = extraire_collection(_soup(html))
    assert methode is None
    assert collection == "N/A"


def test_plan_a_ignore_lego_avec_symbole_trademark():
    # Observé en conditions réelles : lego.com renvoie littéralement "LEGO®"
    # (avec le symbole ®) plutôt que "LEGO" tout court -- doit être filtré pareil,
    # tout en gardant intacts les vrais thèmes qui utilisent ce symbole (LEGO® Icons).
    html = '''<script type="application/ld+json">
    {"@type": "Product", "category": "LEGO®"}
    </script>'''
    collection, methode = extraire_collection(_soup(html))
    assert methode is None
    assert collection == "N/A"


def test_plan_a_garde_un_vrai_theme_avec_symbole_trademark():
    html = '''<script type="application/ld+json">
    {"@type": "Product", "category": "LEGO® Icons"}
    </script>'''
    collection, methode = extraire_collection(_soup(html))
    assert collection == "LEGO® Icons"
    assert methode == "json-ld:category"


def test_plan_a_breadcrumb_sans_theme_est_ignore():
    # Fil d'Ariane à 3 niveaux seulement (Accueil > LEGO > Set) : pas de vrai thème dedans.
    html = '''<script type="application/ld+json">
    {"@type": "BreadcrumbList", "itemListElement": [
        {"name": "Accueil"}, {"name": "LEGO"}, {"name": "Corvette"}
    ]}
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
