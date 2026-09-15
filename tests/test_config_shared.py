from config_shared import (
    construire_slug_wiki, construire_url_wiki_set, email_config_complete,
    PRIX_MOYEN_PAR_COLLECTION, charger_config_email,
)


def test_construire_slug_wiki_remplace_espaces_et_deux_points():
    assert construire_slug_wiki("10321", "Corvette") == "10321-Corvette"
    # Les ':' sont retirés (cassent les liens wiki) puis les espaces convertis en '-'.
    assert construire_slug_wiki("21351", "L'Étrange Noël: Disney") == "21351-L'Étrange-Noël-Disney"


def test_construire_url_wiki_set_pointe_vers_la_bonne_page():
    url = construire_url_wiki_set("10321", "Corvette")
    assert url == "https://github.com/Aktawind/lego-price-tracker/wiki/10321-Corvette"


def test_email_config_complete():
    assert email_config_complete({"api_key": "abc", "destinataire": "a@a.com"}) is True
    assert email_config_complete({"api_key": None, "destinataire": "a@a.com"}) is False
    assert email_config_complete({"api_key": "abc", "destinataire": None}) is False
    assert email_config_complete({}) is False


def test_prix_moyen_par_collection_valeurs_connues():
    # Le taux par défaut (sets sans collection connue) est de 10 centimes/pièce.
    assert PRIX_MOYEN_PAR_COLLECTION['default'] == 0.100
    assert PRIX_MOYEN_PAR_COLLECTION['LEGO® Icons'] == 0.0883
    assert PRIX_MOYEN_PAR_COLLECTION['LEGO® Education'] == 0.100


def test_charger_config_email_expediteur_par_defaut_si_absent(monkeypatch):
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    assert charger_config_email()["expediteur"] == "onboarding@resend.dev"


def test_charger_config_email_expediteur_par_defaut_si_vide(monkeypatch):
    # GitHub Actions règle la variable d'environnement même quand le secret
    # n'existe pas, mais avec une valeur vide plutôt qu'absente -- il ne faut
    # pas envoyer un email avec un expéditeur vide (Resend le rejette en 422).
    monkeypatch.setenv("RESEND_FROM_EMAIL", "")
    assert charger_config_email()["expediteur"] == "onboarding@resend.dev"


def test_charger_config_email_expediteur_personnalise(monkeypatch):
    monkeypatch.setenv("RESEND_FROM_EMAIL", "alertes@mondomaine.fr")
    assert charger_config_email()["expediteur"] == "alertes@mondomaine.fr"
