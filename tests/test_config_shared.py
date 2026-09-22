from config_shared import (
    construire_slug_wiki, construire_url_wiki_set, email_config_complete,
    PRIX_MOYEN_PAR_COLLECTION, charger_config_email, accord_pluriel,
    MAP_VENDEURS, driver_est_vivant, executer_avec_retries,
    sauvegarder_diagnostic_scraping,
)


def test_construire_slug_wiki_remplace_espaces_et_deux_points():
    assert construire_slug_wiki("10321", "Corvette") == "10321-Corvette"
    # Les ':' sont retirés (cassent les liens wiki) puis les espaces convertis en '-'.
    assert construire_slug_wiki("21351", "L'Étrange Noël: Disney") == "21351-L'Étrange-Noël-Disney"


def test_construire_url_wiki_set_pointe_vers_la_bonne_page():
    url = construire_url_wiki_set("10321", "Corvette")
    assert url == "https://github.com/Aktawind/lego-price-tracker/wiki/10321-Corvette"


def test_email_config_complete():
    assert email_config_complete({"api_key": "abc", "expediteur": "x@x.com", "destinataire": "a@a.com"}) is True
    assert email_config_complete({"api_key": None, "expediteur": "x@x.com", "destinataire": "a@a.com"}) is False
    assert email_config_complete({"api_key": "abc", "expediteur": None, "destinataire": "a@a.com"}) is False
    assert email_config_complete({"api_key": "abc", "expediteur": "x@x.com", "destinataire": None}) is False
    assert email_config_complete({}) is False


def test_prix_moyen_par_collection_valeurs_connues():
    # Le taux par défaut (sets sans collection connue) est de 10 centimes/pièce.
    assert PRIX_MOYEN_PAR_COLLECTION['default'] == 0.100
    assert PRIX_MOYEN_PAR_COLLECTION['LEGO® Icons'] == 0.0883
    assert PRIX_MOYEN_PAR_COLLECTION['LEGO® Education'] == 0.100


def test_charger_config_email_expediteur_absent_si_pas_configure(monkeypatch):
    # Contrairement à Resend, Brevo n'a pas d'expéditeur "bac à sable" par défaut :
    # sans BREVO_FROM_EMAIL, l'expéditeur doit rester vide (pas de valeur inventée).
    monkeypatch.delenv("BREVO_FROM_EMAIL", raising=False)
    assert charger_config_email()["expediteur"] is None


def test_charger_config_email_expediteur_vide_traite_comme_absent(monkeypatch):
    # Même piège que pour Resend : GitHub Actions règle la variable même quand
    # le secret n'existe pas côté repo, mais avec une valeur vide.
    monkeypatch.setenv("BREVO_FROM_EMAIL", "")
    assert charger_config_email()["expediteur"] is None


def test_charger_config_email_expediteur_personnalise(monkeypatch):
    monkeypatch.setenv("BREVO_FROM_EMAIL", "alertes@mondomaine.fr")
    assert charger_config_email()["expediteur"] == "alertes@mondomaine.fr"


def test_accord_pluriel():
    assert accord_pluriel(0) == ''  # "0 baisse détectée", pas "0 baisses détectées"
    assert accord_pluriel(1) == ''
    assert accord_pluriel(2) == 's'
    assert accord_pluriel(8) == 's'


def test_map_vendeurs_suit_galaxus():
    assert MAP_VENDEURS["chez galaxus"] == "Galaxus"


class FakeDriver:
    def __init__(self, vivant=True):
        self._vivant = vivant

    @property
    def current_url(self):
        if not self._vivant:
            raise Exception("session invalide")
        return "https://example.com"


def test_driver_est_vivant():
    assert driver_est_vivant(FakeDriver(vivant=True)) is True
    assert driver_est_vivant(FakeDriver(vivant=False)) is False


def test_executer_avec_retries_reussit_du_premier_coup():
    appels = []
    succes, erreur = executer_avec_retries(lambda: appels.append(1), max_essais=3, pause_secondes=0)
    assert succes is True
    assert erreur is None
    assert len(appels) == 1


def test_executer_avec_retries_reussit_apres_un_echec():
    appels = []

    def action():
        appels.append(1)
        if len(appels) < 2:
            raise ValueError("aléa transitoire")

    succes, erreur = executer_avec_retries(action, max_essais=3, pause_secondes=0)
    assert succes is True
    assert erreur is None
    assert len(appels) == 2


def test_executer_avec_retries_abandonne_apres_max_essais():
    def action():
        raise ValueError("toujours cassé")

    succes, erreur = executer_avec_retries(action, max_essais=2, pause_secondes=0)
    assert succes is False
    assert isinstance(erreur, ValueError)


def test_executer_avec_retries_appelle_on_echec_entre_les_tentatives():
    appels_echec = []

    def action():
        raise ValueError("boom")

    executer_avec_retries(
        action, max_essais=3, pause_secondes=0,
        on_echec=lambda e, tentative: appels_echec.append(tentative),
    )
    # on_echec n'est appelé qu'entre deux tentatives, jamais après la dernière.
    assert appels_echec == [1, 2]


class FakeDriverAvecScreenshot:
    def __init__(self):
        self.captures = []

    def save_screenshot(self, chemin):
        self.captures.append(chemin)


def test_sauvegarder_diagnostic_scraping_nomme_par_domaine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sauvegarder_diagnostic_scraping("<html>contenu</html>", "https://www.lego.com/fr-fr/product/72151", prefixe="debug_lego_metadata")

    fichiers = list(tmp_path.glob("debug_lego_metadata_www_lego_com_*.html"))
    assert len(fichiers) == 1
    assert fichiers[0].read_text(encoding="utf-8") == "<html>contenu</html>"


def test_sauvegarder_diagnostic_scraping_capture_ecran_si_driver_fourni(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    driver = FakeDriverAvecScreenshot()
    sauvegarder_diagnostic_scraping("<html></html>", "https://example.com/page", driver=driver)

    assert len(driver.captures) == 1
    assert driver.captures[0].startswith("debug_example_com_")
    assert driver.captures[0].endswith(".png")


def test_sauvegarder_diagnostic_scraping_sans_driver_necrit_pas_de_png(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sauvegarder_diagnostic_scraping("<html></html>", "https://example.com/page")

    assert list(tmp_path.glob("*.png")) == []
    assert list(tmp_path.glob("*.html"))
