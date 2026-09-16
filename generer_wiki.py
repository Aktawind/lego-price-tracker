import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import git
from datetime import datetime, timedelta
import re
import logging
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from config_shared import PRIX_MOYEN_PAR_COLLECTION, SEUIL_BONNE_AFFAIRE, SEUIL_TRES_BONNE_AFFAIRE, construire_slug_wiki
import historique_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- CONFIGURATION ---
FICHIER_CONFIG = "config_sets.xlsx"
WIKI_REPO_URL = os.getenv("WIKI_URL", "https://github.com/Aktawind/lego-price-tracker.wiki.git")
WIKI_LOCAL_PATH = "lego_wiki"

# --- Nettoyage du dossier wiki ---
def nettoyer_dossier_wiki(chemin_dossier):
    """Supprime tous les fichiers .md et les images de graphiques existants."""
    logging.info(f"Nettoyage du dossier du wiki : {chemin_dossier}")
    # Nettoyer les fichiers .md à la racine
    for fichier in os.listdir(chemin_dossier):
        if fichier.endswith(".md"):
            os.remove(os.path.join(chemin_dossier, fichier))
    
    # Nettoyer les graphiques dans le dossier images
    dossier_images = os.path.join(chemin_dossier, "images")
    if os.path.exists(dossier_images):
        for fichier in os.listdir(dossier_images):
            if fichier.startswith("graph_") and fichier.endswith(".png"):
                os.remove(os.path.join(dossier_images, fichier))

# --- Préparation du chemin local pour le dépôt wiki ---
def preparer_repo_wiki():
    """Clone le repo du wiki s'il n'existe pas, ou le met à jour."""
    if os.path.exists(WIKI_LOCAL_PATH):
        logging.info("Mise à jour du dépôt wiki local...")
        repo = git.Repo(WIKI_LOCAL_PATH)
        repo.remotes.origin.pull()
    else:
        logging.info("Clonage du dépôt wiki...")
        git.Repo.clone_from(WIKI_REPO_URL, WIKI_LOCAL_PATH)
    
    # Créer le dossier pour les images s'il n'existe pas
    os.makedirs(os.path.join(WIKI_LOCAL_PATH, "images"), exist_ok=True)

# --- GÉNÉRATION DES GRAPHIQUES ---
def generer_graphique(df_set_history, id_set):
    """Génère et sauvegarde un graphique d'évolution des prix pour un set."""
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(10, 6))

    # Utiliser Seaborn pour un joli graphique
    sns.lineplot(data=df_set_history, x='Date', y='Prix', hue='Site', marker='o', ax=ax)

    # On laisse matplotlib choisir intelligemment le nombre de graduations :
    # avec plus d'un an d'historique quotidien, afficher une graduation par
    # jour rendait l'axe illisible (un mur de dates superposées).
    locator = AutoDateLocator(minticks=4, maxticks=10)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))

    ax.set_title(f"Évolution du prix pour le set {id_set}", fontsize=16)
    ax.set_ylabel("Prix (€)")
    ax.set_xlabel("")
    plt.tight_layout()
    
    chemin_image = os.path.join(WIKI_LOCAL_PATH, "images", f"graph_{id_set}.png")
    plt.savefig(chemin_image, dpi=150)
    plt.close(fig) # Fermer la figure pour libérer la mémoire
    logging.info(f"Graphique généré : {chemin_image}")
    return f"images/graph_{id_set}.png"

# --- GÉNÉRATION DES PAGES WIKI ---
# REMPLACEZ VOTRE FONCTION generer_pages_wiki PAR CELLE-CI

# Dans generer_wiki.py

def generer_pages_wiki(df_config):
    logging.info("Début de la génération des pages du Wiki...")
    
    df_prix = historique_db.charger_historique()
    if df_prix.empty:
        logging.error("Aucun historique de prix trouvé en base. Génération du wiki annulée.")
        return
    df_prix['Date'] = pd.to_datetime(df_prix['Date']).dt.normalize()

    preparer_repo_wiki()
    nettoyer_dossier_wiki(WIKI_LOCAL_PATH)

    home_content = ["# Suivi des Prix LEGO", "Mis à jour le : " + datetime.now().strftime('%d/%m/%Y à %H:%M') + "\n",
                    "| Image | Set | Meilleur Prix Actuel |", "|:---:|:---|:---|"]
    
    for index, config_set in df_config.iterrows():
        id_set = config_set['ID_Set']
        nom_set = config_set['Nom_Set']
        image_url = config_set.get('Image_URL', '')
        nb_pieces = pd.to_numeric(config_set.get('nbPieces'), errors='coerce')
        collection_brute = config_set.get('Collection')
        collection = collection_brute if pd.notna(collection_brute) and str(collection_brute).strip() else None
        marque = config_set.get('Marque')
        marque = marque if pd.notna(marque) and str(marque).strip() else 'LEGO'
        prix_alerte = pd.to_numeric(config_set.get('Prix_Alerte'), errors='coerce')

        # On prend TOUT l'historique pour ce set, sans filtrer les sites
        df_set_history = df_prix[df_prix['ID_Set'] == id_set].copy()
        
        if df_set_history.empty:
            logging.warning(f"Aucun historique de prix trouvé pour le set {id_set}. Il sera ignoré pour le wiki.")
            continue

        dernier_scan = df_set_history.sort_values('Date').groupby('Site').last().reset_index()
        dernier_scan_trie = dernier_scan.sort_values('Prix', ascending=True)

        meilleur_prix_actuel = dernier_scan_trie['Prix'].min()
        site_meilleur_prix = dernier_scan_trie.iloc[0]['Site']

        # Calculs pour l'analyse de prix. Le référentiel PRIX_MOYEN_PAR_COLLECTION
        # ne concerne que les gammes LEGO officielles : pour les autres marques
        # (Lumibricks, etc.) on n'a pas de "prix juste" fiable, donc on saute ce calcul.
        est_lego = marque.strip().upper() == 'LEGO'
        prix_moyen_collection = PRIX_MOYEN_PAR_COLLECTION.get(collection, PRIX_MOYEN_PAR_COLLECTION['default']) if est_lego else None
        prix_juste = nb_pieces * prix_moyen_collection if (est_lego and pd.notna(nb_pieces) and prix_moyen_collection) else None
        seuil_bonne = prix_juste * SEUIL_BONNE_AFFAIRE if prix_juste else None
        seuil_tres_bonne = prix_juste * SEUIL_TRES_BONNE_AFFAIRE if prix_juste else None

        lien_wiki = construire_slug_wiki(id_set, nom_set)
        nom_fichier_page = f"{lien_wiki}.md"

        # --- Page d'accueil ---
        indicateur_deal = ""
        if seuil_tres_bonne and meilleur_prix_actuel <= seuil_tres_bonne:
            indicateur_deal = "🔥🔥"
        elif seuil_bonne and meilleur_prix_actuel <= seuil_bonne:
            indicateur_deal = "✅✅"

        image_md = f"[<img src='{image_url}' width='100'>]({lien_wiki})" if image_url else ""
        set_md = f"**[{nom_set}]({lien_wiki})**<br>*{id_set}*"
        prix_md = f"**{meilleur_prix_actuel:.2f}€** {indicateur_deal}<br>*sur {site_meilleur_prix}*"
        home_content.append(f"| {image_md} | {set_md} | {prix_md} |")

        # --- Pages de détail ---
        page_detail_content = [f"# {nom_set} ({id_set})"]
        if image_url: page_detail_content.append(f"<img src='{image_url}' alt='Image de {nom_set}' width='400'>\n")

        prix_plus_bas_jamais_vu = df_set_history['Prix'].min()
        date_limite_6_mois = datetime.now() - timedelta(days=182)
        historique_6_mois = df_set_history[df_set_history['Date'] >= date_limite_6_mois]
        prix_plus_bas_6_mois = historique_6_mois['Prix'].min() if not historique_6_mois.empty else prix_plus_bas_jamais_vu

        page_detail_content.append("## Analyse du Prix")
        if not est_lego:
            page_detail_content.append(f"- **Marque :** {marque}")
        page_detail_content.append(f"- **Collection :** {collection if collection else 'Non catégorisée'}")
        if pd.notna(nb_pieces):
            page_detail_content.append(f"- **Nombre de pièces :** {int(nb_pieces)}")
        if prix_juste:
            page_detail_content.append(f"- **Prix juste estimé :** {prix_juste:.2f}€ ({prix_moyen_collection:.3f}€/pièce)")
            page_detail_content.append(f"- **Seuil Bonne Affaire :** < {seuil_bonne:.2f}€")
            page_detail_content.append(f"- **Seuil TRÈS Bonne Affaire :** < {seuil_tres_bonne:.2f}€")
        if pd.notna(prix_alerte):
            page_detail_content.append(f"- **Seuil d'alerte configuré :** < {prix_alerte:.2f}€")
        page_detail_content.append(f"- **Prix le plus bas des 6 derniers mois :** {prix_plus_bas_6_mois:.2f}€")
        page_detail_content.append(f"- **Prix le plus bas jamais enregistré :** {prix_plus_bas_jamais_vu:.2f}€\n")

        page_detail_content.append("## Prix Actuels par Site")
        page_detail_content.append("| Site | Prix Actuel | Prix par Pièce | Analyse |")
        page_detail_content.append("|:---|:---:|:---:|:---:|")

        # On boucle sur le tableau trié des prix trouvés
        for _, row in dernier_scan_trie.iterrows():
            prix = row['Prix']
            site = row['Site']
            
            # === LOGIQUE DE LIENS CONDITIONNELS ===
            colonne_url_config = f"URL_{site.replace('.', '_')}"
            url_manuelle = config_set.get(colonne_url_config)

            if pd.notna(url_manuelle) and url_manuelle:
                site_md = f"[{site}]({url_manuelle})"
            else:
                site_md = site
            # ======================================
            
            analyse_emoji = "-"
            if prix_juste:
                ppp_actuel = prix / nb_pieces
                if ppp_actuel <= prix_moyen_collection * SEUIL_TRES_BONNE_AFFAIRE: analyse_emoji = "TRÈS Bonne Affaire 🔥🔥"
                elif ppp_actuel <= prix_moyen_collection * SEUIL_BONNE_AFFAIRE: analyse_emoji = "Bonne Affaire ✅✅"
                elif ppp_actuel <= prix_moyen_collection: analyse_emoji = "Prix Juste ✅"
                else: analyse_emoji = "Élevé ❌"
                page_detail_content.append(f"| {site_md} | **{prix:.2f}€** | {ppp_actuel:.3f}€ | {analyse_emoji} |")
            else:
                page_detail_content.append(f"| {site_md} | **{prix:.2f}€** | - | {analyse_emoji} |")

        chemin_graphique = generer_graphique(df_set_history, id_set)
        page_detail_content.append("\n## Évolution des prix")
        page_detail_content.append(f"<img src='./{chemin_graphique}' alt='Graphique des prix' width='900'>\n")
        
        with open(os.path.join(WIKI_LOCAL_PATH, nom_fichier_page), 'w', encoding='utf-8') as f:
            f.write("\n".join(page_detail_content))
        logging.info(f"Page de détail générée : {nom_fichier_page}")

    with open(os.path.join(WIKI_LOCAL_PATH, "Home.md"), 'w', encoding='utf-8') as f:
        f.write("\n".join(home_content))
    logging.info("Page d'accueil 'Home.md' générée.")

# --- PUSH DES CHANGEMENTS VERS LE WIKI ---
def pousser_changements_wiki():
    try:
        repo = git.Repo(WIKI_LOCAL_PATH)
        if not repo.is_dirty(untracked_files=True):
            logging.info("Aucun changement à pousser sur le wiki.")
            return

        logging.info("Détection de changements. Configuration de Git et push vers le wiki...")
        
        # Configuration de l'utilisateur Git DANS le script
        repo.config_writer().set_value("user", "name", os.getenv("GIT_USER", "Bot")).release()
        repo.config_writer().set_value("user", "email", os.getenv("GIT_EMAIL", "bot@example.com")).release()
        
        repo.git.add(A=True)
        repo.index.commit(f"Mise à jour automatique des prix - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        # On s'assure que l'URL distante est la bonne (celle avec le token)
        origin = repo.remote(name='origin')
        origin.set_url(WIKI_REPO_URL)
        
        origin.push()
        logging.info("Wiki mis à jour avec succès !")
    except Exception as e:
        logging.error(f"Erreur lors du push vers le wiki : {e}")

# --- POINT D'ENTRÉE DU SCRIPT ---
if __name__ == "__main__":
    df_config = pd.read_excel(FICHIER_CONFIG, dtype={'ID_Set': str})
    if not df_config.empty:
        generer_pages_wiki(df_config) # On passe df_config en argument
        pousser_changements_wiki()