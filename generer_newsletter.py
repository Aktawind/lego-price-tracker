# Fichier : generer_newsletter.py
# Newsletter hebdomadaire (envoyée tous les vendredis, voir .github/workflows/newsletter.yml)
# qui récapitule, pour tous les sets suivis, ceux qui sont actuellement en
# dessous de la barre "bonne affaire" ou "très bonne affaire" -- contrairement
# à l'alerte quotidienne (catch_lego_price.py), qui ne notifie que sur une
# VRAIE baisse par rapport au meilleur prix précédent, cette newsletter
# rappelle chaque semaine tous les sets qui restent une bonne affaire, même
# si leur prix n'a pas bougé depuis la dernière alerte.
import logging

import pandas as pd

import email_manager
import historique_db
from catch_lego_price import charger_configuration_sets_df, FICHIER_CONFIG_EXCEL
from config_shared import (
    PRIX_MOYEN_PAR_COLLECTION, SEUIL_BONNE_AFFAIRE, SEUIL_TRES_BONNE_AFFAIRE,
    construire_url_wiki_set, charger_config_email, email_config_complete,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


def _formater_duree(jours):
    """Convertit un nombre de jours en texte lisible ('3 jours', '2 semaines', '4 mois')."""
    if jours < 14:
        return f"{jours} jour{'s' if jours > 1 else ''}"
    if jours < 60:
        semaines = round(jours / 7)
        return f"{semaines} semaine{'s' if semaines > 1 else ''}"
    mois = round(jours / 30.4)
    return f"{mois} mois"


def _serie_prix_journaliers(df_historique_set):
    """Réduit l'historique d'un set à un point par jour (le prix le plus bas ce
    jour-là, tous sites confondus), trié par date -- sert de base pour détecter
    les baisses successives sans être perturbé par plusieurs sites scannés le
    même jour."""
    df = df_historique_set.copy()
    df['JourDate'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
    return df.groupby('JourDate')['Prix'].min().sort_index()


def _temps_depuis_baisse_precedente(serie_prix):
    """Retourne le nombre de jours entre les deux dernières baisses de prix
    enregistrées pour ce set (ou None s'il n'y a pas assez de baisses connues
    pour répondre : premier prix jamais enregistré, ou prix toujours stable)."""
    dates_baisse = [
        date for i, date in enumerate(serie_prix.index)
        if i > 0 and serie_prix.iloc[i] < serie_prix.iloc[i - 1]
    ]
    if len(dates_baisse) < 2:
        return None
    return (dates_baisse[-1] - dates_baisse[-2]).days


def _analyser_set_pour_newsletter(id_set, nom_set, image_url, nb_pieces, collection, marque, df_historique_set):
    """Calcule les infos d'un set pour la newsletter : prix actuel, % de
    réduction par rapport au prix Lego.com de référence, classement bonne/très
    bonne affaire, prix le plus bas jamais enregistré (et sa date), et depuis
    quand le prix n'avait pas baissé. Retourne None si le set n'est pas
    éligible.

    Le classement bonne/très bonne affaire réutilise le même calcul que le
    wiki et l'alerte quotidienne (prix/pièce moyen de la collection, voir
    PRIX_MOYEN_PAR_COLLECTION) plutôt que le prix Lego.com, pour rester
    cohérent avec ce qui est déjà affiché ailleurs -- seul le pourcentage de
    réduction affiché se base sur le prix Lego.com, comme demandé."""
    if df_historique_set.empty:
        return None

    # Comme pour l'alerte quotidienne (catch_lego_price.py) et le wiki, le
    # référentiel de prix moyen au pièce ne vaut que pour les gammes LEGO
    # officielles.
    if str(marque).strip().upper() != 'LEGO' or pd.isna(nb_pieces):
        return None

    prix_moyen = PRIX_MOYEN_PAR_COLLECTION.get(collection, PRIX_MOYEN_PAR_COLLECTION['default'])
    prix_juste = nb_pieces * prix_moyen

    dernier_prix_par_site = df_historique_set.sort_values('Date').groupby('Site').last()
    prix_actuel = dernier_prix_par_site['Prix'].min()

    if prix_actuel <= prix_juste * SEUIL_TRES_BONNE_AFFAIRE:
        categorie = "tres_bonne"
    elif prix_actuel <= prix_juste * SEUIL_BONNE_AFFAIRE:
        categorie = "bonne"
    else:
        return None

    if 'Lego' not in dernier_prix_par_site.index:
        return None  # Pas de prix Lego.com connu : impossible de calculer une réduction à afficher.
    prix_lego = dernier_prix_par_site.loc['Lego', 'Prix']
    if not prix_lego or prix_lego <= 0:
        return None

    pourcentage = round((1 - prix_actuel / prix_lego) * 100)

    prix_min = df_historique_set['Prix'].min()
    date_min = pd.to_datetime(df_historique_set.loc[df_historique_set['Prix'].idxmin(), 'Date'])

    serie = _serie_prix_journaliers(df_historique_set)
    jours_depuis_baisse = _temps_depuis_baisse_precedente(serie)

    return {
        'id_set': id_set,
        'nom_set': nom_set,
        'image_url': image_url,
        'categorie': categorie,
        'prix_actuel': prix_actuel,
        'pourcentage_reduction': pourcentage,
        'prix_min_historique': prix_min,
        'date_min_historique': date_min,
        'texte_depuis_baisse': _formater_duree(jours_depuis_baisse) if jours_depuis_baisse is not None else None,
        'url_wiki': construire_url_wiki_set(id_set, nom_set),
    }


def calculer_deals_newsletter(df_config, df_historique):
    """Parcourt tous les sets suivis et retourne (tres_bonnes_affaires, bonnes_affaires),
    deux listes de dicts triées par % de réduction décroissant."""
    tres_bonnes, bonnes = [], []
    for _, row in df_config.iterrows():
        id_set = row['ID_Set']
        nom_set = row.get('Nom_Set', id_set)
        image_url = row.get('Image_URL', '')
        nb_pieces = pd.to_numeric(row.get('nbPieces'), errors='coerce')
        collection_brute = row.get('Collection')
        collection = collection_brute if pd.notna(collection_brute) and str(collection_brute).strip() else None
        marque_brute = row.get('Marque')
        marque = marque_brute if pd.notna(marque_brute) and str(marque_brute).strip() else 'LEGO'
        df_historique_set = df_historique[df_historique['ID_Set'] == id_set]
        resultat = _analyser_set_pour_newsletter(
            id_set, nom_set, image_url, nb_pieces, collection, marque, df_historique_set
        )
        if resultat is None:
            continue
        (tres_bonnes if resultat['categorie'] == 'tres_bonne' else bonnes).append(resultat)

    tres_bonnes.sort(key=lambda d: d['pourcentage_reduction'], reverse=True)
    bonnes.sort(key=lambda d: d['pourcentage_reduction'], reverse=True)
    return tres_bonnes, bonnes


def generer_et_envoyer_newsletter():
    logging.info("Génération de la newsletter hebdomadaire des bonnes affaires...")
    df_config = charger_configuration_sets_df(FICHIER_CONFIG_EXCEL)
    if df_config is None:
        return
    df_historique = historique_db.charger_historique()

    tres_bonnes, bonnes = calculer_deals_newsletter(df_config, df_historique)

    if not tres_bonnes and not bonnes:
        logging.info("Aucune bonne affaire cette semaine, pas d'envoi de newsletter.")
        return

    email_config = charger_config_email()
    if not email_config_complete(email_config):
        logging.error("Variables d'environnement pour l'email non configurées (BREVO_API_KEY / BREVO_FROM_EMAIL / MAIL_DESTINATAIRE). Newsletter non envoyée.")
        return

    email_manager.envoyer_newsletter_hebdomadaire(tres_bonnes, bonnes, email_config)


if __name__ == "__main__":
    generer_et_envoyer_newsletter()
