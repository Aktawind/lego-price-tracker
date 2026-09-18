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
from selenium.common.exceptions import TimeoutException
from config_shared import MAP_VENDEURS, driver_est_vivant, executer_avec_retries
from config_generator import marque_est_lego

# --- CONFIGURATION ---
FICHIER_CONFIG_EXCEL = "config_sets.xlsx"
FICHIER_OUTPUT_JSON = "deals_du_jour.json"
URL_BASE_AVENUE = "https://www.avenuedelabrique.com/"

def extraire_offres_de_la_page(soup):
    """
    Fonction unique qui prend une page parsée (soup) et en extrait les offres.
    C'est notre "extracteur" de base.
    """
    offres_trouvees = []
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
            if vendeur_keyword in alt_text:
                vendeur_assigne = nom_site
                break
        
        if vendeur_assigne:
            url_relative = lien_tag['href']
            url_absolue = f"{URL_BASE_AVENUE}{url_relative.lstrip('/')}"
            
            offres_trouvees.append({
                "site": vendeur_assigne,
                "url": url_absolue,
                "prix": float(prix_brut)
            })
        else:
            logging.info(f"  -> Vendeur non suivi ignoré (alt: '{logo_img['alt']}')")
    
    return offres_trouvees

def _creer_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    # --disable-dev-shm-usage : /dev/shm est minuscule (souvent 64 Mo) dans les
    # conteneurs CI comme les runners GitHub Actions, et Chrome s'en sert
    # beaucoup pour le rendu. Sans cette option, le processus de rendu peut
    # planter sans message exploitable (juste une pile d'adresses brutes,
    # exactement ce qu'on observait sur certains sets) dès qu'une page un peu
    # lourde (beaucoup d'offres/images) est chargée. catch_lego_price.py
    # l'utilise déjà pour la même raison.
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)


def main():
    """Script principal pour scraper Avenue de la Brique."""
    logging.info("Lancement du scraper d'Avenue de la Brique...")
    try:
        df_config = pd.read_excel(FICHIER_CONFIG_EXCEL, dtype=str).fillna('')
    except FileNotFoundError:
        logging.error(f"'{FICHIER_CONFIG_EXCEL}' introuvable. Arrêt.")
        return

    driver = _creer_driver()
    wait = WebDriverWait(driver, 10)

    deals_par_set = {}
    for index, row in df_config.iterrows():
        set_id = row['ID_Set']
        url_avenue_specifique = row.get('URL_AvenueDeLaBrique')

        # Avenue de la Brique est un comparateur de prix spécifiquement LEGO :
        # une recherche pour un set d'une autre marque (ex: LUMI-LUNA/Lumibricks)
        # ne trouvera jamais de résultat. Avant, ça produisait un échec garanti
        # (timeout) à chaque run, en plus de gaspiller du temps pour rien.
        if not marque_est_lego(row.get('Marque')) and not url_avenue_specifique:
            logging.info(f"Set {set_id} ignoré (marque non-LEGO, non répertorié sur Avenue de la Brique).")
            continue

        def _tenter_un_set():
            nonlocal driver, wait
            if not driver_est_vivant(driver):
                logging.warning(f"Session Selenium invalide détectée pour le set {set_id}, redémarrage du driver...")
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = _creer_driver()
                wait = WebDriverWait(driver, 10)

            if url_avenue_specifique:
                logging.info(f"Utilisation de l'URL directe pour le set {set_id}...")
                driver.get(url_avenue_specifique)
            else:
                logging.info(f"Recherche automatique pour le set {set_id}...")
                driver.get(URL_BASE_AVENUE)
                try:
                    wait.until(EC.element_to_be_clickable((By.ID, "cookie_tout_accepter"))).click()
                except Exception: pass

                champ_recherche = wait.until(EC.visibility_of_element_located((By.ID, "RechercheRecherche")))
                champ_recherche.clear()
                champ_recherche.send_keys(set_id)
                champ_recherche.send_keys(Keys.RETURN)

            # Attente commune pour les deux cas. Un timeout ici signifie le plus
            # souvent que la recherche n'a simplement donné aucun résultat (page
            # différente, set introuvable ce jour-là) : ce n'est pas une erreur à
            # proprement parler, donc pas la peine de retenter ni de logger une
            # pile d'appels illisible pour ça.
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.prodf-comp-px")))
            except TimeoutException:
                logging.info(f"Aucune offre trouvée pour le set {set_id} sur Avenue de la Brique.")
                return

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # On appelle notre extracteur unique
            offres = extraire_offres_de_la_page(soup)
            if offres:
                deals_par_set[set_id] = offres

        # Un aléa ponctuel (popup, page lente, session qui plante) sur un set ne
        # doit pas faire perdre sa mise à jour de prix du jour : on retente une
        # fois avant d'abandonner (et on redémarre le driver s'il a planté).
        succes, erreur = executer_avec_retries(
            _tenter_un_set, max_essais=2, pause_secondes=3,
            on_echec=lambda e, tentative: logging.warning(
                f"Tentative {tentative} échouée pour le set {set_id}, nouvel essai... ({type(e).__name__}: {e})"
            ),
        )
        if not succes:
            logging.error(f"Erreur lors du traitement du set {set_id} sur Avenue de la Brique : {type(erreur).__name__}: {erreur}")

        time.sleep(3)

    try:
        driver.quit()
    except Exception:
        pass

    # Le dédoublonnage reste le même
    deals_finaux = {}
    logging.info("Nettoyage des offres pour ne garder que la meilleure par site...")
    for set_id, offres in deals_par_set.items():
        meilleures_offres_par_site = {}
        for offre in offres:
            site = offre['site']
            prix = offre['prix']
            if site not in meilleures_offres_par_site or prix < meilleures_offres_par_site[site]['prix']:
                meilleures_offres_par_site[site] = offre
        if meilleures_offres_par_site:
            deals_finaux[set_id] = list(meilleures_offres_par_site.values())
    
    with open(FICHIER_OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(deals_finaux, f, ensure_ascii=False, indent=4)
        
    logging.info(f"Scraping d'Avenue de la Brique terminé. Résultats dans '{FICHIER_OUTPUT_JSON}'.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()