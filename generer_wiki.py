import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import git
from datetime import datetime
import re

# --- CONFIGURATION ---
FICHIER_PRIX = "prix_lego.xlsx"
FICHIER_CONFIG = "config_sets.xlsx"
WIKI_REPO_URL = os.getenv("WIKI_URL", "https://github.com/lego-price-tracker.wiki.git")
WIKI_LOCAL_PATH = "lego_wiki"

def preparer_repo_wiki():
    """Clone le repo du wiki s'il n'existe pas, ou le met à jour."""
    if os.path.exists(WIKI_LOCAL_PATH):
        print("Mise à jour du dépôt wiki local...")
        repo = git.Repo(WIKI_LOCAL_PATH)
        repo.remotes.origin.pull()
    else:
        print("Clonage du dépôt wiki...")
        git.Repo.clone_from(WIKI_REPO_URL, WIKI_LOCAL_PATH)
    
    # Créer le dossier pour les images s'il n'existe pas
    os.makedirs(os.path.join(WIKI_LOCAL_PATH, "images"), exist_ok=True)

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
    print(f"Graphique généré : {chemin_image}")
    return f"images/graph_{id_set}.png"

def generer_pages_wiki():
    print("Début de la génération des pages du Wiki...")
    
    try:
        df_prix = pd.read_excel(FICHIER_PRIX, dtype={'ID_Set': str})
        df_config = pd.read_excel(FICHIER_CONFIG, dtype={'ID_Set': str})
        df_prix['Date'] = pd.to_datetime(df_prix['Date'])
    except FileNotFoundError as e:
        print(f"Erreur: Fichier manquant - {e}")
        return

    preparer_repo_wiki()

    home_content = ["# Suivi des Prix LEGO\n\n", "Mis à jour le : " + datetime.now().strftime('%d/%m/%Y à %H:%M') + "\n"]
    
    # On boucle directement sur chaque ligne de la configuration
    for index, config_set in df_config.iterrows():
        id_set = config_set['ID_Set']
        nom_set = config_set['Nom_Set']
        image_url = config_set.get('Image_URL', '') # Utiliser .get pour éviter une erreur si la colonne manque

        df_set_history = df_prix[df_prix['ID_Set'] == id_set].copy()
        
        if df_set_history.empty:
            print(f"Aucun historique de prix pour le set {id_set} ({nom_set}). Il sera ignoré.")
            continue

        dernier_scan = df_set_history.sort_values('Date').groupby('Site').last().reset_index()
        meilleur_prix_actuel = dernier_scan['Prix'].min()
        site_meilleur_prix = dernier_scan[dernier_scan['Prix'] == meilleur_prix_actuel]['Site'].iloc[0]

        # On garde uniquement les lettres, chiffres, et tirets.
        nom_set_nettoye = re.sub(r'[^a-zA-Z0-9]', '-', nom_set)
        # On remplace les tirets multiples par un seul
        nom_set_nettoye = re.sub(r'-+', '-', nom_set_nettoye)
        
        nom_fichier_page = f"{id_set}-{nom_set_nettoye}.md"
        # ==================================
        
        home_content.append(f"## [{nom_set}]({nom_fichier_page.replace(' ', '%20')})")
        home_content.append(f"**Meilleur prix actuel : {meilleur_prix_actuel:.2f}€** sur *{site_meilleur_prix}*")
        if image_url:
            home_content.append(f"[<img src='{image_url}' width='200' alt='Image de {nom_set}'>]({nom_fichier_page.replace(' ', '%20')})\n")

        chemin_graphique_relatif = generer_graphique(df_set_history, id_set)
        
        page_detail_content = [f"# {nom_set} ({id_set})\n"]
        if image_url:
            page_detail_content.append(f"![Image de {nom_set}]({image_url})\n")
        page_detail_content.append("## Évolution des prix\n")
        page_detail_content.append(f"![Graphique d'évolution des prix](./{chemin_graphique_relatif})\n")
        
        with open(os.path.join(WIKI_LOCAL_PATH, nom_fichier_page), 'w', encoding='utf-8') as f:
            f.write("\n".join(page_detail_content))
        print(f"Page de détail générée : {nom_fichier_page}")

    with open(os.path.join(WIKI_LOCAL_PATH, "Home.md"), 'w', encoding='utf-8') as f:
        f.write("\n".join(home_content))
    print("Page d'accueil 'Home.md' générée.")

def pousser_changements_wiki():
    try:
        repo = git.Repo(WIKI_LOCAL_PATH)
        if not repo.is_dirty(untracked_files=True):
            print("Aucun changement à pousser sur le wiki.")
            return

        print("Détection de changements. Configuration de Git et push vers le wiki...")
        
        # Configuration de l'utilisateur Git DANS le script
        repo.config_writer().set_value("user", "name", os.getenv("GIT_USER", "Bot")).release()
        repo.config_writer().set_value("user", "email", os.getenv("GIT_EMAIL", "bot@example.com")).release()
        
        repo.git.add(A=True)
        repo.index.commit(f"Mise à jour automatique des prix - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        # On s'assure que l'URL distante est la bonne (celle avec le token)
        origin = repo.remote(name='origin')
        origin.set_url(WIKI_REPO_URL)
        
        origin.push()
        print("Wiki mis à jour avec succès !")
    except Exception as e:
        print(f"Erreur lors du push vers le wiki : {e}")

if __name__ == "__main__":
    generer_pages_wiki()
    pousser_changements_wiki()