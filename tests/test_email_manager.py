import email_manager


DEAL_TEST = {
    'id_set': '10321', 'nom_set': 'Corvette', 'nouveau_prix': 179.99,
    'prix_precedent': 219.99, 'site': 'Amazon', 'url': 'https://www.amazon.fr/',
    'image_url': '', 'analyse_affaire': 'standard', 'nb_pieces': 1210,
    'contexte_record': None, 'est_record_absolu': False, 'est_record_6_mois': False,
    'url_wiki': 'https://github.com/Aktawind/lego-price-tracker/wiki/10321-Corvette',
}


def test_envoyer_email_recapitulatif_retourne_true_si_envoi_ok(monkeypatch):
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda *a, **k: True)
    assert email_manager.envoyer_email_recapitulatif([DEAL_TEST], {}) is True


def test_envoyer_email_recapitulatif_retourne_false_si_envoi_echoue(monkeypatch):
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda *a, **k: False)
    assert email_manager.envoyer_email_recapitulatif([DEAL_TEST], {}) is False
