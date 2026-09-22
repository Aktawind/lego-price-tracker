from datetime import datetime, timedelta

import pandas as pd

import generer_newsletter as newsletter


def _historique(lignes):
    """lignes: liste de (jours_ecoules, site, prix)."""
    return pd.DataFrame({
        'Date': [(datetime.now() - timedelta(days=j)).strftime('%Y-%m-%d %H:%M:%S') for j, _, _ in lignes],
        'ID_Set': ['10321'] * len(lignes),
        'Nom_Set': ['Corvette'] * len(lignes),
        'Site': [site for _, site, _ in lignes],
        'Prix': [prix for _, _, prix in lignes],
        'URL': [''] * len(lignes),
    })


def test_set_sans_prix_lego_connu_est_ignore():
    hist = _historique([(5, 'Idealo', 30.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', hist)
    assert resultat is None


def test_set_pas_assez_reduit_est_ignore():
    # 95€ vs prix Lego 100€ : 5% de réduction, sous la barre "bonne affaire" (20%).
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 95.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', hist)
    assert resultat is None


def test_set_bonne_affaire_est_categorise():
    # 79€ vs 100€ Lego : 21% de réduction -> "bonne affaire" (seuil 20%, pas 30%).
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 79.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', hist)
    assert resultat is not None
    assert resultat['categorie'] == 'bonne'
    assert resultat['pourcentage_reduction'] == 21


def test_set_tres_bonne_affaire_est_categorise():
    # 69€ vs 100€ Lego : 31% de réduction -> "très bonne affaire" (seuil 30%).
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 69.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', hist)
    assert resultat['categorie'] == 'tres_bonne'


def test_prix_min_historique_et_sa_date():
    hist = _historique([(60, 'Lego', 100.0), (40, 'Amazon', 45.0), (5, 'Amazon', 45.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', hist)
    assert resultat['prix_min_historique'] == 45.0


def test_temps_depuis_baisse_precedente_sans_assez_de_baisses():
    serie = pd.Series([50.0], index=[datetime.now().date()])
    assert newsletter._temps_depuis_baisse_precedente(serie) is None


def test_temps_depuis_baisse_precedente_calcule_lecart_entre_les_deux_dernieres_baisses():
    aujourdhui = datetime.now().date()
    serie = pd.Series(
        [100.0, 90.0, 90.0, 80.0],
        index=[aujourdhui - timedelta(days=j) for j in (30, 16, 8, 0)],
    )
    # Baisses : jour -16 (100->90) puis jour 0 (90->80) : écart de 16 jours.
    assert newsletter._temps_depuis_baisse_precedente(serie) == 16


def test_formater_duree():
    assert newsletter._formater_duree(1) == "1 jour"
    assert newsletter._formater_duree(5) == "5 jours"
    assert newsletter._formater_duree(14) == "2 semaines"
    assert newsletter._formater_duree(90) == "3 mois"


def test_calculer_deals_newsletter_trie_par_pourcentage_decroissant():
    df_config = pd.DataFrame({
        'ID_Set': ['A', 'B'],
        'Nom_Set': ['SetA', 'SetB'],
        'Image_URL': ['', ''],
    })
    hist_a = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 79.0)])  # 21%
    hist_a['ID_Set'] = 'A'
    hist_b = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 60.0)])  # 40%
    hist_b['ID_Set'] = 'B'
    df_historique = pd.concat([hist_a, hist_b], ignore_index=True)

    tres_bonnes, bonnes = newsletter.calculer_deals_newsletter(df_config, df_historique)
    assert [d['id_set'] for d in tres_bonnes] == ['B']
    assert [d['id_set'] for d in bonnes] == ['A']


def test_calculer_deals_newsletter_exclut_les_sets_sans_bonne_affaire():
    df_config = pd.DataFrame({
        'ID_Set': ['A'],
        'Nom_Set': ['SetA'],
        'Image_URL': [''],
    })
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 95.0)])
    hist['ID_Set'] = 'A'

    tres_bonnes, bonnes = newsletter.calculer_deals_newsletter(df_config, hist)
    assert tres_bonnes == []
    assert bonnes == []
