import deal_hunter


DEAL_TEST = {"marchand": "Amazon", "titre": "Promo test", "details": "Détails", "url": "https://example.com"}


def test_envoyer_email_alerte_deals_retourne_true_si_envoi_ok(monkeypatch):
    monkeypatch.setattr(deal_hunter.envoi_email, 'envoyer', lambda *a, **k: True)
    assert deal_hunter.envoyer_email_alerte_deals([DEAL_TEST], {}) is True


def test_envoyer_email_alerte_deals_retourne_false_si_envoi_echoue(monkeypatch):
    monkeypatch.setattr(deal_hunter.envoi_email, 'envoyer', lambda *a, **k: False)
    assert deal_hunter.envoyer_email_alerte_deals([DEAL_TEST], {}) is False
