from datetime import datetime, timedelta

import pandas as pd

from catch_lego_price import analyser_record_prix


def _historique(prix_par_age_jours):
    """Construit un DataFrame d'historique avec un prix par ancienneté (en jours)."""
    return pd.DataFrame({
        'Date': [(datetime.now() - timedelta(days=jours)).strftime('%Y-%m-%d %H:%M:%S') for jours, _ in prix_par_age_jours],
        'Prix': [prix for _, prix in prix_par_age_jours],
    })


def test_historique_vide_ne_donne_pas_de_record():
    message, absolu, recent = analyser_record_prix(pd.DataFrame(columns=['Date', 'Prix']), 42)
    assert message is None
    assert absolu is False
    assert recent is False


def test_nouveau_prix_plus_bas_que_tout_l_historique_est_record_absolu():
    hist = _historique([(400, 60), (300, 55), (200, 50), (100, 45), (10, 40)])
    message, absolu, recent = analyser_record_prix(hist, 39)
    assert absolu is True
    assert recent is True
    assert message is not None
    assert "jamais" in message.lower()


def test_prix_plus_bas_que_les_6_mois_mais_pas_du_tout_temps():
    # Un prix plus bas existe il y a plus de 6 mois (400j), donc pas un record absolu,
    # mais c'est quand même le plus bas des 6 derniers mois.
    hist = _historique([(400, 30), (100, 45), (10, 40)])
    message, absolu, recent = analyser_record_prix(hist, 38)
    assert absolu is False
    assert recent is True
    assert message is not None
    assert "6 derniers mois" in message


def test_prix_pas_interessant_n_est_pas_un_record():
    hist = _historique([(100, 45), (10, 40)])
    message, absolu, recent = analyser_record_prix(hist, 42)
    assert absolu is False
    assert recent is False
    assert message is None


def test_egalite_avec_le_minimum_compte_comme_record():
    # Exactement le même prix que le minimum historique doit aussi déclencher l'alerte
    # (le tracker notifie déjà sur "prix < précédent", donc ce cas se produit surtout
    # quand le minimum historique remonte à plus longtemps que le dernier prix connu).
    hist = _historique([(200, 40)])
    message, absolu, recent = analyser_record_prix(hist, 40)
    assert absolu is True
    assert recent is True
