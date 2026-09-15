from config_shared import construire_slug_wiki, construire_url_wiki_set, email_config_complete


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
