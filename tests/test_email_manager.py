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


def test_sujet_accorde_au_singulier_sans_record(monkeypatch):
    capture = {}
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda sujet, *a, **k: capture.setdefault('sujet', sujet) or True)
    email_manager.envoyer_email_recapitulatif([DEAL_TEST], {})
    assert capture['sujet'] == "Alerte Prix LEGO : 1 baisse de prix détectée !"


def test_sujet_accorde_au_pluriel_sans_record(monkeypatch):
    capture = {}
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda sujet, *a, **k: capture.setdefault('sujet', sujet) or True)
    email_manager.envoyer_email_recapitulatif([DEAL_TEST, DEAL_TEST], {})
    assert capture['sujet'] == "Alerte Prix LEGO : 2 baisses de prix détectées !"


def test_sujet_accorde_avec_record_absolu(monkeypatch):
    capture = {}
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda sujet, *a, **k: capture.setdefault('sujet', sujet) or True)
    deal_record = dict(DEAL_TEST, est_record_absolu=True)
    email_manager.envoyer_email_recapitulatif([deal_record, DEAL_TEST], {})
    assert capture['sujet'] == "🏆 1 prix jamais vu ! (2 baisses au total)"


def test_pas_d_emoji_brique_dans_le_corps_html(monkeypatch):
    captures = {}
    monkeypatch.setattr(
        email_manager.envoi_email, 'envoyer',
        lambda sujet, texte, html, *a, **k: captures.update(html=html) or True,
    )
    email_manager.envoyer_email_recapitulatif([DEAL_TEST], {})
    assert '🧱' not in captures['html']
    assert 'Baisses de prix détectées' in captures['html']
