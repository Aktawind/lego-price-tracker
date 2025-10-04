import pandas as pd
import os
import re
from bs4 import BeautifulSoup
import logging
import glob

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


FICHIER_CONFIG_EXCEL = "config_sets.xlsx"
FICHIER_LISTE_SETS = "sets_a_analyser.txt"

# Dictionnaire pour mapper les domaines aux noms de colonnes dans l'Excel
DOMAIN_TO_COLUMN_MAP = {
    "avenuedelabrique.com": "URL_AvenueDeLaBrique",
    "amazon.fr": "URL_Amazon",
    "amzn.eu": "URL_Amazon",
    "lego.com": "URL_Lego",
    "auchan.fr": "URL_Auchan",
    "carrefour.fr": "URL_Carrefour",
    "e.leclerc": "URL_Leclerc",
    "brickmo.com": "URL_Brickmo"
    # Ajoutez d'autres domaines au besoin
}
def get_lego_metadata(set_id):
    """Scrape Lego.com pour récupérer les métadonnées d'un set en utilisant Selenium."""
    logging.info(f"Récupération des métadonnées pour le set {set_id} sur Lego.com (via Selenium)...")
    url = f"https://www.lego.com/fr-fr/product/{set_id}"
    
    # On utilise une configuration Selenium
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-test="product-overview-name"]')))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # --- NOM ET IMAGE ---
        nom_set_elem = soup.find('h1', {'data-test': 'product-overview-name'})
        nom_set = nom_set_elem.text.strip() if nom_set_elem else "Nom non trouvé"
        
        image_url = ""
        image_elem = soup.select_one('[data-test="mediagallery-image-0"] source')
        if image_elem and image_elem.has_attr('srcset'):
            image_url = image_elem['srcset'].split(',')[0].split(' ')[0]
        if not image_url:
            meta_image = soup.find('meta', property='og:image')
            if meta_image: image_url = meta_image['content']

        # === NOMBRE DE PIÈCES ===
        nb_pieces = "N/A"
        # Plan A : Données d'accessibilité (le plus fiable)
        try:
            pieces_p = soup.find(lambda tag: tag.name == 'p' and 'visually-hidden' in tag.get('class', []) and 'nombre de pièces' in tag.get_text(strip=True).lower())
            if pieces_p:
                match = re.search(r'\d+', pieces_p.get_text())
                if match:
                    nb_pieces = match.group(0)
        except Exception:
            pass # On continue silencieusement si ça échoue

        # Plan B : Attribut data-test (si le Plan A a échoué)
        if nb_pieces == "N/A":
            logging.info("  -> Plan A pour les pièces (visually-hidden) a échoué, tentative du Plan B (data-test)...")
            # On cherche l'un des data-test connus
            pieces_elem = soup.select_one('[data-test="pieces-value"]')
            if pieces_elem:
                # On prend le texte de l'élément, qui devrait être le nombre
                nb_pieces = pieces_elem.text.strip()
        
        # Message final si tout a échoué
        if nb_pieces == "N/A":
            logging.warning(f"Impossible de trouver le nombre de pièces pour {set_id} avec toutes les méthodes.")
            
        # --- COLLECTION ---
        collection = "N/A"
        collection_elem = soup.select_one('a[class*="BrandLink"] img')
        if collection_elem and collection_elem.has_attr('alt'):
            collection = collection_elem['alt'].strip().replace('Logo', '').strip()
        
        logging.info(f"Métadonnées récupérées : Nom='{nom_set}', Pièces='{nb_pieces}', Collection='{collection}'")
        return { "nom": nom_set, "image_url": image_url, "nb_pieces": nb_pieces, "collection": collection, "url_lego": url }
        
    except Exception as e:
        logging.error(f"Erreur majeure lors de la récupération des métadonnées pour {set_id} : {e}")
        return None
    finally:
        driver.quit()

def process_set_file(file_path):
    """Traite un fichier .txt pour ajouter/mettre à jour un set dans la configuration."""
    set_id = os.path.splitext(os.path.basename(file_path))[0]
    logging.info(f"--- Traitement du fichier pour le nouveau set ID: {set_id} ---")

    # Lire les URL depuis le fichier
    with open(file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    # Scraper les métadonnées depuis Lego.com
    metadata = get_lego_metadata(set_id)
    if not metadata:
        logging.error(f"Arrêt du traitement pour {set_id} car les métadonnées n'ont pas pu être récupérées.")
        return

    # Préparer la nouvelle ligne pour l'Excel
    nouvelle_ligne = {
        "ID_Set": set_id,
        "Nom_Set": metadata['nom'],
        "nbPieces": metadata['nb_pieces'],
        "Collection": metadata['collection'],
        "Image_URL": metadata['image_url'],
    }
    
    # Ajouter l'URL de Lego.com à la liste
    urls.append(metadata['url_lego'])

    # Identifier et classer les URL
    for url in urls:
        url_trouvee = False
        for domain, column_name in DOMAIN_TO_COLUMN_MAP.items():
            if domain in url:
                nouvelle_ligne[column_name] = url
                url_trouvee = True
                break
        if not url_trouvee:
            logging.warning(f"Domaine non reconnu pour l'URL : {url}")
    
    return nouvelle_ligne

def main():
    logging.info("Lancement du générateur de configuration...")
    config_changed = False

    # --- ÉTAPE 1 : CHARGER L'ÉTAT ACTUEL ET L'ÉTAT DÉSIRÉ ---
    try:
        df_config = pd.read_excel(FICHIER_CONFIG_EXCEL, dtype=str)
    except FileNotFoundError:
        df_config = pd.DataFrame(columns=["ID_Set"])

    try:
        with open(FICHIER_LISTE_SETS, 'r', encoding='utf-8') as f:
            ids_desires = {line.strip() for line in f if line.strip().isdigit()}
    except FileNotFoundError:
        logging.warning(f"'{FICHIER_LISTE_SETS}' non trouvé. Aucune synchronisation de liste ne sera effectuée.")
        ids_desires = set(df_config['ID_Set'].tolist()) # On considère que la liste actuelle est la bonne

    ids_actuels = set(df_config['ID_Set'].tolist())

    # --- ÉTAPE 2 : SYNCHRONISATION (AJOUTS ET SUPPRESSIONS DE LA LISTE) ---
    
    # Sets à supprimer
    ids_a_supprimer = ids_actuels - ids_desires
    if ids_a_supprimer:
        logging.info(f"Suppression des sets non présents dans la liste : {ids_a_supprimer}")
        df_config = df_config[~df_config['ID_Set'].isin(ids_a_supprimer)]
        config_changed = True
        # Nettoyer l'historique
        try:
            df_historique = pd.read_excel(FICHIER_HISTORIQUE, dtype=str)
            df_historique_nettoye = df_historique[~df_historique['ID_Set'].isin(ids_a_supprimer)]
            df_historique_nettoye.to_excel(FICHIER_HISTORIQUE, index=False)
            logging.info(f"Historique des prix nettoyé pour les sets supprimés.")
        except FileNotFoundError: pass

    # Sets à ajouter
    ids_a_ajouter = ids_desires - ids_actuels
    if ids_a_ajouter:
        logging.info(f"Ajout de nouveaux sets depuis la liste : {ids_a_ajouter}")
        nouvelles_lignes = []
        for set_id in ids_a_ajouter:
            metadata = get_lego_metadata(set_id)
            if metadata:
                nouvelle_ligne = {
                    "ID_Set": set_id, "Nom_Set": metadata['nom'], "nbPieces": metadata['nb_pieces'],
                    "Collection": metadata['collection'], "Image_URL": metadata['image_url'],
                    "URL_Lego": metadata['url_lego']
                }
                nouvelles_lignes.append(nouvelle_ligne)
        
        if nouvelles_lignes:
            nouvelles_lignes_df = pd.DataFrame(nouvelles_lignes)
            df_config = pd.concat([df_config, nouvelles_lignes_df], ignore_index=True)
            config_changed = True

    # --- ÉTAPE 3 : GESTION DES FICHIERS DE COMMANDE INDIVIDUELS (EN PRIORITÉ) ---
    fichiers_commandes = [f for f in os.listdir() if not f.startswith('.') and os.path.splitext(os.path.basename(f))[0].isdigit()]
    
    for file_path in fichiers_commandes:
        set_id = os.path.splitext(os.path.basename(file_path))[0]
        with open(file_path, 'r', encoding='utf-8') as f:
            lignes = f.readlines()
        
        contenu_simple = "".join(lignes).strip().lower()

        if contenu_simple == 'delete':
            # La commande 'delete' via fichier individuel a la priorité
            if set_id in df_config['ID_Set'].values:
                df_config = df_config[df_config['ID_Set'] != set_id]
                logging.info(f"Set {set_id} supprimé via fichier de commande.")
                config_changed = True

                try:
                    df_historique = pd.read_excel("prix_lego.xlsx", dtype=str)
                    df_historique_nettoye = df_historique[df_historique['ID_Set'] != set_id]
                    df_historique_nettoye.to_excel("prix_lego.xlsx", index=False)
                    logging.info(f"Historique des prix pour le set {set_id} nettoyé.")
                except FileNotFoundError:
                    pass
            else:
                logging.warning(f"Le set {set_id} à supprimer n'a pas été trouvé.")
        else:
            # Traitement des URL dans le fichier
            urls = [line.strip(' :\t\n\r') for line in lignes if line.strip()]
            if not urls: continue # Si le fichier est vide, on l'ignore
            
            if set_id in df_config['ID_Set'].values:
                logging.info(f"Fusion des URL du fichier {file_path} pour le set {set_id}...")
                index_a_modifier = df_config.index[df_config['ID_Set'] == set_id].item()
                for url in urls:
                    for domain, column in DOMAIN_TO_COLUMN_MAP.items():
                        if domain in url:
                            df_config.loc[index_a_modifier, column] = url
                            break
                config_changed = True
            else:
                logging.warning(f"Le fichier {file_path} concerne un set ({set_id}) qui n'est pas dans la liste. Ajoutez-le à sets_a_analyser.txt d'abord.")

        # Correction du bug : On supprime le fichier après l'avoir traité
        os.remove(file_path)
        logging.info(f"Fichier de commande '{file_path}' traité et supprimé.")

    # --- ÉTAPE 4 : SAUVEGARDE FINALE ---
    if config_changed:
        # On trie le DataFrame par ID de set pour un fichier propre
        df_config = df_config.sort_values('ID_Set').reset_index(drop=True)
        df_config.to_excel(FICHIER_CONFIG_EXCEL, index=False)
        logging.info(f"Fichier '{FICHIER_CONFIG_EXCEL}' mis à jour.")
    else:
        logging.info("Aucun changement de configuration nécessaire.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()