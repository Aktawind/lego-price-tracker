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


# Avec nb_pieces=1000 et une collection non répertoriée (prix moyen "default" à
# 0.100€/pièce, voir PRIX_MOYEN_PAR_COLLECTION), le "prix juste" est de 100€ :
# seuil "bonne affaire" à 80€, seuil "très bonne affaire" à 70€.


def test_set_sans_nb_pieces_est_ignore():
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 65.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', None, None, 'LEGO', hist)
    assert resultat is None


def test_set_marque_non_lego_est_ignore():
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 65.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', 1000, None, 'Lumibricks', hist)
    assert resultat is None


def test_classement_se_base_sur_le_prix_juste_pas_sur_le_prix_lego():
    # Prix Lego élevé (150€) : par rapport à lui, 85€ ressemble à une bonne
    # réduction (43%). Mais le "prix juste" (prix/pièce) n'est que de 100€, et
    # 85€ est au-dessus du seuil "bonne affaire" (80€) de ce prix juste : ce
    # n'est donc PAS une bonne affaire, même si ça y ressemble par rapport à
    # Lego. C'est ce classement (identique au wiki et à l'alerte quotidienne)
    # qui doit primer.
    hist = _historique([(5, 'Lego', 150.0), (5, 'Amazon', 85.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', 1000, None, 'LEGO', hist)
    assert resultat is None


def test_set_sans_prix_lego_connu_est_ignore_meme_si_prix_juste_qualifie():
    hist = _historique([(5, 'Idealo', 65.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', 1000, None, 'LEGO', hist)
    assert resultat is None


def test_set_bonne_affaire_est_categorise():
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 79.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', 1000, None, 'LEGO', hist)
    assert resultat is not None
    assert resultat['categorie'] == 'bonne'
    assert resultat['pourcentage_reduction'] == 21


def test_set_tres_bonne_affaire_est_categorise():
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 65.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', 1000, None, 'LEGO', hist)
    assert resultat['categorie'] == 'tres_bonne'
    assert resultat['pourcentage_reduction'] == 35


def test_prix_moyen_de_la_collection_est_pris_en_compte():
    # Technic : 0.1211€/pièce (voir PRIX_MOYEN_PAR_COLLECTION), donc prix juste
    # = 1000 * 0.1211 = 121.1€, seuil bonne affaire = 96.88€.
    hist = _historique([(5, 'Lego', 130.0), (5, 'Amazon', 95.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', 1000, 'Technic', 'LEGO', hist)
    assert resultat is not None
    assert resultat['categorie'] == 'bonne'


def test_prix_min_historique_et_sa_date():
    hist = _historique([(60, 'Lego', 100.0), (40, 'Amazon', 45.0), (5, 'Amazon', 45.0)])
    resultat = newsletter._analyser_set_pour_newsletter('10321', 'Corvette', '', 1000, None, 'LEGO', hist)
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
        'nbPieces': [1000, 1000],
        'Collection': [None, None],
        'Marque': ['LEGO', 'LEGO'],
    })
    hist_a = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 79.0)])  # bonne, 21%
    hist_a['ID_Set'] = 'A'
    hist_b = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 60.0)])  # tres_bonne, 40%
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
        'nbPieces': [1000],
        'Collection': [None],
        'Marque': ['LEGO'],
    })
    hist = _historique([(5, 'Lego', 100.0), (5, 'Amazon', 95.0)])
    hist['ID_Set'] = 'A'

    tres_bonnes, bonnes = newsletter.calculer_deals_newsletter(df_config, hist)
    assert tres_bonnes == []
    assert bonnes == []
