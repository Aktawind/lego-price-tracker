import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import git
from datetime import datetime
import re
import logging
import urllib.parse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Dictionnaire de connaissance des prix moyens par pièce
PRIX_MOYEN_PAR_COLLECTION = {
    "Star Wars"  : 0.130,
    "Technic"    : 0.117,
    "Disney"     : 0.108,
    "Super Mario": 0.101,
    "Ideas"      : 0.096,
    "Icons"      : 0.092,
    "Botanicals" : 0.085,
    "default"    : 0.100
}

SEUIL_BONNE_AFFAIRE = 0.85 # 15% de réduction par rapport au prix moyen

# --- CONFIGURATION ---
FICHIER_PRIX = "prix_lego.xlsx"
FICHIER_CONFIG = "config_sets.xlsx"
WIKI_REPO_URL = os.getenv("WIKI_URL", "https://github.com/Aktawind/lego-price-tracker.wiki.git")
WIKI_LOCAL_PATH = "lego_wiki"

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

    ax.set_title(f"Évolution du prix pour le set {id_set}", fontsize=16)
    ax.set_ylabel("Prix (€)")
    ax.set_xlabel("Date")
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    chemin_image = os.path.join(WIKI_LOCAL_PATH, "images", f"graph_{id_set}.png")
    plt.savefig(chemin_image)
    plt.close(fig) # Fermer la figure pour libérer la mémoire
    logging.info(f"Graphique généré : {chemin_image}")
    return f"images/graph_{id_set}.png"

# --- GÉNÉRATION DES PAGES WIKI ---
def generer_pages_wiki():
    logging.info("Début de la génération des pages du Wiki...")
    
    try:
        df_prix = pd.read_excel(FICHIER_PRIX, dtype={'ID_Set': str})
        df_config = pd.read_excel(FICHIER_CONFIG, dtype={'ID_Set': str})
        df_prix['Date'] = pd.to_datetime(df_prix['Date'])
    except FileNotFoundError as e:
        logging.error(f"Erreur: Fichier manquant - {e}")
        return

    preparer_repo_wiki()

    home_content = ["# Suivi des Prix LEGO", "Mis à jour le : " + datetime.now().strftime('%d/%m/%Y à %H:%M') + "\n",
                    "| Image | Set | Meilleur Prix Actuel |", "|:---:|:---|:---|"]
    
    for index, config_set in df_config.iterrows():
        id_set = config_set['ID_Set']
        nom_set = config_set['Nom_Set']
        image_url = config_set.get('Image_URL', '')
        nb_pieces = pd.to_numeric(config_set.get('nbPieces'), errors='coerce')
        collection = config_set.get('Collection', 'default')

        df_set_history = df_prix[df_prix['ID_Set'] == id_set].copy()
        
        if df_set_history.empty:
            logging.warning(f"Aucun historique de prix pour {id_set}. Ignoré.")
            continue

        dernier_scan = df_set_history.sort_values('Date').groupby('Site').last().reset_index()
        meilleur_prix_actuel = dernier_scan['Prix'].min()
        site_meilleur_prix = dernier_scan[dernier_scan['Prix'] == meilleur_prix_actuel]['Site'].iloc[0]

        # --- Calculs pour l'analyse de prix ---
        prix_moyen_collection = PRIX_MOYEN_PAR_COLLECTION.get(collection, PRIX_MOYEN_PAR_COLLECTION['default'])
        prix_juste = nb_pieces * prix_moyen_collection if pd.notna(nb_pieces) else None
        seuil_bonne_affaire = prix_juste * SEUIL_BONNE_AFFAIRE if prix_juste else None
        
        # --- Génération des noms de page et liens ---
        nom_set_nettoye = re.sub(r'[^a-zA-Z0-9]', '-', nom_set).strip('-')
        nom_fichier_page = f"{id_set}-{nom_set_nettoye}.md"
        lien_wiki = nom_fichier_page[:-3] # On enlève le .md pour le lien

        # --- Page d'accueil ---
        indicateur_deal = "🟢" if seuil_bonne_affaire and meilleur_prix_actuel <= seuil_bonne_affaire else ""
        image_md = f"[<img src='{image_url}' width='100'>]({lien_wiki})" if image_url else ""
        set_md = f"**[{nom_set}]({lien_wiki})**<br>*{id_set}*"
        prix_md = f"**{meilleur_prix_actuel:.2f}€** {indicateur_deal}<br>*sur {site_meilleur_prix}*"
        home_content.append(f"| {image_md} | {set_md} | {prix_md} |")

        # --- Pages de détail ---
        chemin_graphique = generer_graphique(df_set_history, id_set)
        page_detail_content = [f"# {nom_set} ({id_set})"]
        if image_url: page_detail_content.append(f"<img src='{image_url}' alt='Image de {nom_set}' width='400'>\n")
        
        # Section d'analyse
        if prix_juste:
            prix_plus_bas_jamais_vu = df_set_history['Prix'].min()
            page_detail_content.append("## Analyse du Prix")
            page_detail_content.append(f"- **Collection :** {collection} ({prix_moyen_collection:.3f}€/pièce)")
            page_detail_content.append(f"- **Prix 'juste' estimé :** {prix_juste:.2f}€")
            page_detail_content.append(f"- **Seuil 'Bonne Affaire' :** Un prix inférieur à **{seuil_bonne_affaire:.2f}€** est considéré comme un bon deal.")
            page_detail_content.append(f"- **Prix le plus bas enregistré :** {prix_plus_bas_jamais_vu:.2f}€\n")

        page_detail_content.append("## Prix Actuels par Site")
        page_detail_content.append("| Site | Prix Actuel | Prix par Pièce | Analyse |")
        page_detail_content.append("|:---|:---:|:---:|:---:|")

        for _, row in dernier_scan.iterrows():
            prix = row['Prix']
            site = row['Site']
            analyse_html = ""
            if prix_juste:
                ppp_actuel = prix / nb_pieces
                if ppp_actuel <= prix_moyen_collection:
                    analyse_html = f"<strong><span style='color:green;'>Excellent !</span></strong>"
                else:
                    analyse_html = f"<strong><span style='color:red;'>Élevé</span></strong>"
                page_detail_content.append(f"| {site} | **{prix:.2f}€** | {ppp_actuel:.3f}€ | {analyse_html} |")
            else:
                 page_detail_content.append(f"| {site} | **{prix:.2f}€** | - | - |")
        
        page_detail_content.append("\n## Évolution des prix")
        page_detail_content.append(f"<img src='./{chemin_graphique}' alt='Graphique des prix' width='700'>\n")
        
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
    generer_pages_wiki()
    pousser_changements_wiki()