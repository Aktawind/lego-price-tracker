# Fichier : avenue_scraper.py (Version Selenium)
import pandas as pd
import requests
from bs4 import BeautifulSoup
import logging
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from config_shared import MAP_VENDEURS

# --- CONFIGURATION ---
FICHIER_CONFIG_EXCEL = "config_sets.xlsx"
FICHIER_OUTPUT_JSON = "deals_du_jour.json"
URL_BASE_AVENUE = "https://www.avenuedelabrique.com/"


def scrape_set_on_avenue(driver, set_id):
    """
    Scrape Avenue de la Brique pour un set donné en simulant une recherche.
    Ne retourne que les offres des vendeurs présents dans MAP_VENDEURS.
    """
    wait = WebDriverWait(driver, 10)
    logging.info(f"Recherche du set {set_id} sur Avenue de la Brique...")
    offres_trouvees = []
    try:
        # 1. Aller sur la page d'accueil
        driver.get(URL_BASE_AVENUE)
        
        # 2. Gérer les cookies s'il y en a
        try:
            # Le bouton a un ID "cookie_tout_accepter"
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.ID, "cookie_tout_accepter")))
            bouton_cookies.click()
            logging.info("  -> Bannière de cookies acceptée.")
        except Exception:
            logging.info("  -> Pas de bannière de cookies visible.")

        # 3. Trouver le champ de recherche, taper l'ID et appuyer sur Entrée
        champ_recherche = wait.until(EC.visibility_of_element_located((By.ID, "RechercheRecherche")))
        champ_recherche.clear()
        champ_recherche.send_keys(set_id)
        champ_recherche.send_keys(Keys.RETURN)
        logging.info(f"  -> Recherche lancée pour '{set_id}'.")

        # 4. Attendre que la page de résultats (ou la page produit) se charge
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.prodf-comp-px")))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        offres_html = soup.find_all('div', class_='prodf-px')
        
        for offre in offres_html:
            logo_img = offre.select_one('.prodf-px-logo img')
            lien_tag = offre.find('a')
            prix_brut = offre.get('data-prix')
            
            if not all([logo_img, logo_img.has_attr('alt'), lien_tag, lien_tag.has_attr('href'), prix_brut]):
                continue
            
            alt_text = logo_img['alt'].lower()
            
            vendeur_assigne = None
            for vendeur_keyword, nom_site in MAP_VENDEURS.items():
                # On cherche une correspondance exacte de "chez [nom du vendeur]"
                if vendeur_keyword in alt_text:
                    vendeur_assigne = nom_site
                    break # On a trouvé le vendeur, on arrête de chercher
            
            if vendeur_assigne:
                # Si on a trouvé un vendeur de notre liste, on enregistre l'offre
                url_relative = lien_tag['href']
                url_absolue = f"{URL_BASE_AVENUE}{url_relative.lstrip('/')}"
                
                offres_trouvees.append({
                    "site": vendeur_assigne,
                    "url": url_absolue,
                    "prix": float(prix_brut)
                })
                logging.info(f"  -> Offre trouvée et assignée à : {vendeur_assigne}")
            else:
                logging.info(f"  -> Vendeur non suivi ignoré (alt: '{logo_img['alt']}')")

        return offres_trouvees
    except Exception as e:
        logging.error(f"Erreur scraping Avenue pour {set_id}: {e}")
        return []

def main():
    """Script principal pour scraper Avenue de la Brique."""
    logging.info("Lancement du scraper d'Avenue de la Brique...")
    try:
        df_config = pd.read_excel(FICHIER_CONFIG_EXCEL, dtype=str)
    except FileNotFoundError:
        logging.error(f"'{FICHIER_CONFIG_EXCEL}' introuvable. Arrêt.")
        return

    # --- Configuration du driver Selenium (une seule fois pour tout le script) ---
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    
    deals_par_set = {}
    for set_id in df_config['ID_Set']:
        offres = scrape_set_on_avenue(driver, set_id)
        if offres:
            deals_par_set[set_id] = offres
        time.sleep(3) # Pause de politesse entre chaque recherche de set

    deals_finaux = {}
    logging.info("Nettoyage des offres pour ne garder que la meilleure par site...")
    for set_id, offres in deals_par_set.items():
        meilleures_offres_par_site = {}
        for offre in offres:
            site = offre['site']
            prix = offre['prix']
            
            # Si on n'a pas encore vu ce site, ou si ce prix est meilleur, on le garde
            if site not in meilleures_offres_par_site or prix < meilleures_offres_par_site[site]['prix']:
                meilleures_offres_par_site[site] = offre
        
        # On convertit le dictionnaire de meilleures offres en une simple liste
        if meilleures_offres_par_site:
            deals_finaux[set_id] = list(meilleures_offres_par_site.values())
    
    driver.quit() # On ferme le navigateur à la fin
    
    with open(FICHIER_OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(deals_par_set, f, ensure_ascii=False, indent=4)
        
    logging.info(f"Scraping d'Avenue de la Brique terminé. Résultats dans '{FICHIER_OUTPUT_JSON}'.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()