from datetime import datetime

import email_manager


DEAL_NEWSLETTER_TEST = {
    'id_set': '10321', 'nom_set': 'Corvette', 'image_url': '',
    'categorie': 'bonne', 'prix_actuel': 79.0, 'pourcentage_reduction': 21,
    'prix_min_historique': 75.0, 'date_min_historique': datetime(2026, 8, 1),
    'texte_depuis_baisse': '2 semaines',
    'url_wiki': 'https://github.com/Aktawind/lego-price-tracker/wiki/10321-Corvette',
}


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


def test_envoyer_newsletter_hebdomadaire_retourne_true_si_envoi_ok(monkeypatch):
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda *a, **k: True)
    assert email_manager.envoyer_newsletter_hebdomadaire([DEAL_NEWSLETTER_TEST], [], {}) is True


def test_envoyer_newsletter_hebdomadaire_retourne_false_si_envoi_echoue(monkeypatch):
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda *a, **k: False)
    assert email_manager.envoyer_newsletter_hebdomadaire([DEAL_NEWSLETTER_TEST], [], {}) is False


def test_newsletter_sujet_compte_les_deux_categories(monkeypatch):
    capture = {}
    monkeypatch.setattr(email_manager.envoi_email, 'envoyer', lambda sujet, *a, **k: capture.setdefault('sujet', sujet) or True)
    email_manager.envoyer_newsletter_hebdomadaire([DEAL_NEWSLETTER_TEST], [DEAL_NEWSLETTER_TEST, DEAL_NEWSLETTER_TEST], {})
    assert capture['sujet'] == "Newsletter LEGO : 3 bonnes affaires cette semaine"


def test_newsletter_html_contient_les_deux_sections(monkeypatch):
    captures = {}
    monkeypatch.setattr(
        email_manager.envoi_email, 'envoyer',
        lambda sujet, texte, html, *a, **k: captures.update(html=html) or True,
    )
    email_manager.envoyer_newsletter_hebdomadaire([DEAL_NEWSLETTER_TEST], [DEAL_NEWSLETTER_TEST], {})
    assert 'Très bonnes affaires' in captures['html']
    assert 'Bonnes affaires' in captures['html']
    assert 'Corvette' in captures['html']


def test_newsletter_omet_une_section_vide(monkeypatch):
    captures = {}
    monkeypatch.setattr(
        email_manager.envoi_email, 'envoyer',
        lambda sujet, texte, html, *a, **k: captures.update(html=html) or True,
    )
    email_manager.envoyer_newsletter_hebdomadaire([], [DEAL_NEWSLETTER_TEST], {})
    assert 'Très bonnes affaires' not in captures['html']
    assert 'Bonnes affaires' in captures['html']


def test_newsletter_affiche_le_texte_depuis_la_derniere_baisse(monkeypatch):
    captures = {}
    monkeypatch.setattr(
        email_manager.envoi_email, 'envoyer',
        lambda sujet, texte, html, *a, **k: captures.update(texte=texte) or True,
    )
    email_manager.envoyer_newsletter_hebdomadaire([DEAL_NEWSLETTER_TEST], [], {})
    assert "Il n'avait pas baissé de prix depuis 2 semaines." in captures['texte']
