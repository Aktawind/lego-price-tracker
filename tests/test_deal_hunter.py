import deal_hunter


DEAL_TEST = {"marchand": "Amazon", "titre": "Promo test", "details": "Détails", "url": "https://example.com"}


def test_envoyer_email_alerte_deals_retourne_true_si_envoi_ok(monkeypatch):
    monkeypatch.setattr(deal_hunter.envoi_email, 'envoyer', lambda *a, **k: True)
    assert deal_hunter.envoyer_email_alerte_deals([DEAL_TEST], {}) is True


def test_envoyer_email_alerte_deals_retourne_false_si_envoi_echoue(monkeypatch):
    monkeypatch.setattr(deal_hunter.envoi_email, 'envoyer', lambda *a, **k: False)
    assert deal_hunter.envoyer_email_alerte_deals([DEAL_TEST], {}) is False


def test_sujet_accorde_au_singulier_pour_une_seule_promo(monkeypatch):
    capture = {}
    monkeypatch.setattr(deal_hunter.envoi_email, 'envoyer', lambda sujet, *a, **k: capture.setdefault('sujet', sujet) or True)
    deal_hunter.envoyer_email_alerte_deals([DEAL_TEST], {})
    assert capture['sujet'] == "🔥 Alerte Bons Plans LEGO : 1 nouvelle promotion trouvée !"


def test_sujet_accorde_au_pluriel_pour_plusieurs_promos(monkeypatch):
    capture = {}
    monkeypatch.setattr(deal_hunter.envoi_email, 'envoyer', lambda sujet, *a, **k: capture.setdefault('sujet', sujet) or True)
    deal_hunter.envoyer_email_alerte_deals([DEAL_TEST, DEAL_TEST], {})
    assert capture['sujet'] == "🔥 Alerte Bons Plans LEGO : 2 nouvelles promotions trouvées !"


def test_resoudre_url_avenue_garde_une_url_absolue_telle_quelle():
    # Bug observé en conditions réelles : préfixer une URL déjà absolue donnait
    # "avenuedelabrique.comhttps://..." (page introuvable).
    url = "https://www.avenuedelabrique.com/go/bp/951_19/09/2026"
    assert deal_hunter.resoudre_url_avenue(url) == url


def test_resoudre_url_avenue_prefixe_un_chemin_relatif():
    assert deal_hunter.resoudre_url_avenue("/promotions-et-bons-plans-lego/xyz") == \
        "https://www.avenuedelabrique.com/promotions-et-bons-plans-lego/xyz"
