import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import smtplib
from email.mime.text import MIMEText
import urllib3
import os
import time
import logging
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

'''
    "KingJouet": { 
        "type": "standard_selenium", 
        "selecteur": ".prix" 
    }

    "Fnac": {
        "type": "standard_selenium", 
        "selecteur": ".f-faPriceBox__price.userPrice" 
    },
'''

CONFIG_SITES = {   
    "Leclerc": {
        "type": "standard",
        "selecteur": ".egToM .visually-hidden"
    }
}

def regrouper_taches_par_site(sets_a_surveiller):
    taches_par_site = {}
    for set_id, set_info in sets_a_surveiller.items():
        nom_set = set_info['nom']
        for site, site_details in set_info['sites'].items():
            if site not in taches_par_site:
                taches_par_site[site] = []
            
            tache = site_details.copy()
            tache['id_set'] = set_id
            tache['nom_set'] = nom_set
            taches_par_site[site].append(tache)
    return taches_par_site

# Lecture de la configuration des sets
def charger_configuration_sets(fichier_config, config_sites):
    """Lit le fichier de configuration Excel au format "large" et le transforme en dictionnaire."""
    try:
        df_config = pd.read_excel(fichier_config, dtype=str)
        df_config.fillna('', inplace=True)
        
        sets_a_surveiller = {}
        for index, row in df_config.iterrows():
            set_id = row['ID_Set']
            
            sets_a_surveiller[set_id] = {
                "nom": row['Nom_Set'],
                "sites": {}
            }
            
            for site_nom, site_config in config_sites.items():
                colonne_url = f"URL_{site_nom}"
                
                if colonne_url in row and row[colonne_url]:
                    site_info = site_config.copy()
                    site_info['url'] = row[colonne_url]
                    
                    # Le nom du site sera "Amazon", "Lego", "Cdiscount"...
                    sets_a_surveiller[set_id]['sites'][site_nom] = site_info
                    
        return sets_a_surveiller

    except FileNotFoundError:
        logging.error(f"Erreur: Le fichier de configuration '{fichier_config}' est introuvable.")
        return None
    except KeyError as e:
        logging.error(f"Erreur de configuration: Colonne manquante dans '{fichier_config}': {e}")
        return None
    except Exception as e:
        logging.error(f"Erreur lors de la lecture du fichier de configuration Excel: {e}")
        return None
    
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
SETS_A_SURVEILLER = charger_configuration_sets('config_sets.xlsx', CONFIG_SITES)
FICHIER_EXCEL = "prix_lego.xlsx"
EMAIL_ADRESSE = os.getenv('GMAIL_ADDRESS')
EMAIL_MOT_DE_PASSE = os.getenv('GMAIL_APP_PASSWORD')
EMAIL_DESTINATAIRE = os.getenv('MAIL_DESTINATAIRE')

# Vérification que la configuration des sets a été chargée correctement
if not SETS_A_SURVEILLER:
    exit()

# Vérification que les secrets sont bien chargés
if not all([EMAIL_ADRESSE, EMAIL_MOT_DE_PASSE, EMAIL_DESTINATAIRE]):
    logging.error("Erreur: Les secrets pour l'email (GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MAIL_DESTINATAIRE) ne sont pas configurés.")
    exit()

def obtenir_localisation_ip():
    """Interroge un service externe pour connaître la localisation de l'IP actuelle."""
    try:
        #logging.info("Récupération de la localisation de l'IP...")
        reponse = requests.get("https://ipinfo.io/json", timeout=5)
        reponse.raise_for_status()
        data = reponse.json()
        pays = data.get('country', 'N/A')
        #logging.info(f"Localisation détectée : Pays={pays}")
        return pays
    except Exception as e:
        logging.error(f"Impossible de récupérer la localisation de l'IP: {e}")
        return None
    
def creer_driver_selenium(scraper_type="standard"):
    """Crée et retourne une instance configurée du driver Chrome."""
    logging.info(f"Création d'un driver Selenium (type: {scraper_type})")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Options de camouflage les plus importantes
    chrome_options.add_argument("--disable-gpu") # Crucial dans les environnements sans GPU (comme GitHub Actions)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") # Masque le fait que le navigateur est contrôlé par un automate
    
    # Options expérimentales pour paraître plus humain
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)

    if scraper_type == "standard_selenium":
        stealth(driver, languages=["fr-FR", "fr"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
                
    return driver

def scrape_amazon_avec_driver(driver, url):
    """
    Prend un driver Selenium déjà ouvert et scrape une seule page produit Amazon.
    Gère la localisation, les popups 'Continuer' et les cookies.
    """
    wait = WebDriverWait(driver, 10)
    
    try:
        # On navigue vers l'URL du produit
        driver.get(url)

        # Gérer la page bloquante "Continuer" si elle apparaît
        try:
            continuer_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Continuer les achats']"))
            )
            #logging.info("Page 'Continuer' détectée. Clic...")
            continuer_button.click()
            # Attendre que la page produit soit chargée après le clic
            wait.until(EC.presence_of_element_located((By.ID, "dp-container")))
            #logging.info("Page produit chargée après le clic sur 'Continuer'.")
        except Exception:
            #logging.info("Pas de page 'Continuer' visible.")
            pass

        # ÉTAPE 3 : FORCER LA LOCALISATION SI NÉCESSAIRE
        pays_actuel = obtenir_localisation_ip()
        if pays_actuel and pays_actuel != 'FR':
            logging.info(f"IP non-française ({pays_actuel}) détectée. Forçage de la localisation...")
            try:
                bouton_localisation = wait.until(
                    EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link"))
                )
                bouton_localisation.click()
                
                champ_postal = wait.until(EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput")))
                champ_postal.send_keys("38540")
                
                bouton_actualiser = driver.find_element(By.CSS_SELECTOR, '[data-action="GLUXPostalUpdateAction"] input')
                bouton_actualiser.click()

                # Attendre que la popup se ferme et que la page se mette à jour
                wait.until(EC.staleness_of(bouton_actualiser))
                #logging.info("Localisation française forcée avec succès.")
            except Exception as e:
                logging.error(f"La procédure de forçage de localisation a échoué : {e}")
        else:
            #logging.info("IP française, pas de forçage de localisation.")
            pass

        # ÉTAPE 4 : GÉRER LA BANNIÈRE DE COOKIES
        try:
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.ID, "sp-cc-accept")))
            #logging.info("Bannière de cookies trouvée. Clic...")
            bouton_cookies.click()
        except Exception:
            #logging.info("Pas de bannière de cookies visible.")
            pass

        # ÉTAPE 5 : EXTRAIRE LE PRIX
        wait.until(EC.visibility_of_element_located((By.ID, "corePrice_feature_div")))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Plan A : Chercher le prix dans la balise la plus fiable (a-offscreen)
        element_prix = soup.select_one("span.a-offscreen")
        if element_prix:
            prix_texte_brut = element_prix.get_text()
            match = re.search(r'(\d+[.,]\d{1,2})', prix_texte_brut)
            if match:
                return float(match.group(1).replace(',', '.'))
        
        # Plan B : Si la première méthode échoue (prix éclaté)
        partie_entiere_elem = soup.select_one("span.a-price-whole")
        partie_fraction_elem = soup.select_one("span.a-price-fraction")
        if partie_entiere_elem and partie_fraction_elem:
            partie_entiere_texte = partie_entiere_elem.get_text()
            partie_fraction_texte = partie_fraction_elem.get_text(strip=True)
            partie_entiere_propre = "".join(filter(str.isdigit, partie_entiere_texte))
            prix_complet_str = f"{partie_entiere_propre}.{partie_fraction_texte}"
            return float(prix_complet_str)
            
        return None

    except Exception as e:
        logging.error(f"Erreur lors du scraping de l'URL Amazon {url}: {e}")
        driver.save_screenshot(f"error_amazon_{int(time.time())}.png")
        return None
    
def scrape_standard_stealth_avec_driver(driver, url, selecteur):
    """
    Prend un driver Selenium Stealth déjà ouvert et scrape une page standard
    qui nécessite le mode furtif ET une gestion de cookies (ex: Fnac).
    """
    logging.info(f"  -> Scraping (Stealth) de {url}")
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(url)
        
        # === LE SUPER GESTIONNAIRE DE COOKIES (identique à celui de Carrefour) ===
        try:
            # On cherche tous les boutons possibles en une seule fois
            xpath_cookies = (
                "//button[contains(text(), 'Tout accepter')]"
                " | //button[contains(text(), 'Accepter & Fermer')]"
                " | //button[contains(text(), 'accepter et fermer')]"
                " | //a[contains(text(), 'Continuer sans accepter')]"
                " | //button[contains(text(), 'Continuer sans accepter')]"
                " | //button[@id='onetrust-accept-btn-handler']"
            )
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_cookies)))
            logging.info(f"  -> Bannière de cookies trouvée. Clic sur '{bouton_cookies.text}'...")
            bouton_cookies.click()
            wait.until(EC.invisibility_of_element(bouton_cookies))
        except Exception:
            logging.info("  -> Pas de bannière de cookies gérée visible.")
        # ====================================================================

        # Attendre que le prix soit visible
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selecteur)))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        element_prix = soup.select_one(selecteur)
        
        if element_prix:
            # Votre logique de nettoyage de prix est correcte
            prix_texte_brut = element_prix.get_text()
            prix_texte_uniforme = prix_texte_brut.replace(',', '.')
            match = re.search(r'\d+\.\d+', prix_texte_uniforme)
            if match:
                return float(match.group(0))
            else:
                match_entier = re.search(r'\d+', prix_texte_uniforme)
                if match_entier:
                    return float(match_entier.group(0))
        return None
        
    except Exception as e:
        logging.error(f"Erreur lors du scraping (Stealth) de {url}: {e}")
        driver.save_screenshot(f"error_stealth_{int(time.time())}.png")
        return None
    
# Vérifiez que cette fonction existe aussi dans votre code

def scrape_eclate_avec_driver(driver, url, euros, centimes, timeout=10):
    """
    Prend un driver Selenium déjà ouvert et scrape un prix éclaté (ex: Carrefour).
    Gère la bannière de cookies avant de chercher le prix.
    """
    logging.info(f"  -> Scraping (prix éclaté) de {url}")
    wait = WebDriverWait(driver, timeout)
    
    try:
        driver.get(url)
        
        try:
            xpath_cookies = (
                "//button[contains(text(), 'Tout accepter')]"
                " | //button[contains(text(), 'Accepter & Fermer')]"
                " | //button[contains(text(), 'accepter et fermer')]"
                " | //a[contains(text(), 'Continuer sans accepter')]"  # <-- AJOUT POUR CARREFOUR (souvent un lien <a>)
                " | //button[contains(text(), 'Continuer sans accepter')]" # <-- Ou parfois un bouton <button>
                " | //button[@id='onetrust-accept-btn-handler']"
            )
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_cookies)))
            logging.info(f"  -> Bannière de cookies trouvée. Clic sur '{bouton_cookies.text}'...")
            bouton_cookies.click()
            wait.until(EC.invisibility_of_element(bouton_cookies))
        except Exception:
            logging.info("  -> Pas de bannière de cookies gérée visible.")
        
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, euros)))
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, centimes)))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        partie_entiere_elem = soup.select_one(euros)
        partie_fraction_elem = soup.select_one(centimes)
        
        if partie_entiere_elem and partie_fraction_elem:
            partie_entiere = partie_entiere_elem.get_text(strip=True).replace(',', '').replace('.', '')
            partie_fraction = partie_fraction_elem.get_text(strip=True).replace(',', '').replace('.', '')
            
            prix_complet_str = f"{partie_entiere}.{partie_fraction}"
            return float(prix_complet_str)
        return None

    except Exception as e:
        logging.error(f"Erreur lors du scraping (prix éclaté) de {url}: {e}")
        driver.save_screenshot(f"error_eclate_{int(time.time())}.png")
        return None

def recuperer_prix_standard(url, headers, selecteur):
    try:
        reponse = requests.get(url, headers=headers, verify=False)
        reponse.raise_for_status()
        soup = BeautifulSoup(reponse.content, 'html.parser')
        
        # 1. On utilise le sélecteur pour trouver la "boîte" qui contient le prix.
        element_prix = soup.select_one(selecteur)
        
        if not element_prix:
            logging.warning(f"Sélecteur '{selecteur}' non trouvé sur la page {url}")
            return None
            
        # 2. On prend UNIQUEMENT le texte de cette boîte.
        prix_texte_brut = element_prix.get_text()
        #logging.info(f"Texte brut trouvé avec le sélecteur '{selecteur}': '{prix_texte_brut.strip()}'")

        # 3. On applique notre regex chirurgicale sur ce petit bout de texte.
        match = re.search(r'\b(\d+[.,]\d{1,2})\b', prix_texte_brut)
        if match:
            prix_str = match.group(1).replace(',', '.')
            return float(prix_str)
            
        match_entier = re.search(r'(\d+)\s*€', prix_texte_brut)
        if match_entier:
            return float(match_entier.group(1))

        logging.warning(f"Aucun motif de prix trouvé dans le texte '{prix_texte_brut.strip()}'")
        return None
        
    except Exception as e:
        logging.error(f"Erreur en récupérant le prix pour {url}: {e}")
        return None
    
# Fonction pour envoyer un email d'alerte
def envoyer_email_recapitulatif(baisses_de_prix):
    """Prend une liste de baisses de prix et envoie un seul email de résumé."""
    
    nombre_baisses = len(baisses_de_prix)
    sujet = f"Alerte Prix LEGO : {nombre_baisses} baisse(s) de prix détectée(s) !"
    
    details_baisses = []
    for deal in baisses_de_prix:
        # On construit la ligne "Bonne Affaire" uniquement si c'est le cas
        message_bonne_affaire = ""
        if deal.get('bonne_affaire', False): # .get() pour éviter une erreur si la clé manque
            message_bonne_affaire = "\n   >> C'est une bonne affaire ! 🟢"
            
        detail_str = (
            f" {deal['nom_set']}\n"
            f"   Site: {deal['site']}\n"
            f"   Ancien Prix: {deal['prix_precedent']}€\n"
            f"   NOUVEAU PRIX: {deal['nouveau_prix']}€\n" # On met en avant le nouveau prix
            f"{message_bonne_affaire}\n" # On insère notre message ici
            f"   Lien: {deal['url']}"
        )
        details_baisses.append(detail_str)
    
    corps = "Bonjour,\n\nVoici les baisses de prix détectées aujourd'hui :\n\n" + "\n\n--------------------\n\n".join(details_baisses)
    
    # La partie envoi reste la même
    msg = MIMEText(corps)
    msg['Subject'] = sujet
    msg['From'] = EMAIL_ADRESSE
    msg['To'] = EMAIL_DESTINATAIRE
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(EMAIL_ADRESSE, EMAIL_MOT_DE_PASSE)
            smtp_server.sendmail(EMAIL_ADRESSE, EMAIL_DESTINATAIRE, msg.as_string())
        logging.info(f"Email récapitulatif de {nombre_baisses} baisse(s) envoyé !")
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi de l'email récapitulatif : {e}")

def verifier_les_prix():
    logging.info("Lancement de la vérification des prix")
    try:
        df_historique = pd.read_excel(FICHIER_EXCEL, dtype={'ID_Set': str})
    except FileNotFoundError:
        logging.info("Fichier Excel d'historique non trouvé. Création d'un nouveau.")
        df_historique = pd.DataFrame({'Date': pd.Series(dtype='str'),'ID_Set': pd.Series(dtype='str'),'Nom_Set': pd.Series(dtype='str'),'Site': pd.Series(dtype='str'),'Prix': pd.Series(dtype='float')})
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9'
    }
    
    lignes_a_ajouter = []
    baisses_de_prix_a_notifier = []

    taches_par_site = regrouper_taches_par_site(SETS_A_SURVEILLER)

    SCRAPERS_INTERNES = {
        "amazon_selenium": scrape_amazon_avec_driver,
        "standard_selenium": scrape_standard_stealth_avec_driver,
        "eclate_selenium": scrape_eclate_avec_driver,
        "standard": recuperer_prix_standard
    }

    # On charge la configuration une seule fois au début
    try:
        df_config = pd.read_excel('config_sets.xlsx', dtype=str)
    except FileNotFoundError:
        logging.error("Fichier de configuration 'config_sets.xlsx' introuvable. Arrêt.")
        return

    for site, taches in taches_par_site.items():
        logging.info(f"--- Début du traitement pour le site : {site} ---")
        
        # On remplace '.' par '_' pour matcher les clés du dictionnaire (ex: Lego.com -> Lego_com)
        site_key = site.replace('.', '_')
        site_config = CONFIG_SITES.get(site_key)
        
        if not site_config:
            logging.error(f"Configuration manquante pour le site {site}")
            continue
        
        scraper_type = site_config['type']
        scraper_function = SCRAPERS_INTERNES.get(scraper_type)

        if not scraper_function:
            logging.error(f"Aucune fonction de scraping trouvée pour le type '{scraper_type}'")
            continue

        driver = None
        # On ne démarre un navigateur que si c'est un type Selenium
        if "selenium" in scraper_type:
            try:
                driver = creer_driver_selenium(scraper_type)

                if scraper_type == "standard_selenium":
                    stealth(driver, languages=["fr-FR", "fr"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
                
                # Logique de localisation pour Amazon, faite une seule fois par session
                if scraper_type == "amazon_selenium":
                    pays_actuel = obtenir_localisation_ip()
                    if pays_actuel and pays_actuel != 'FR':
                        # ... (copiez-collez ici votre bloc complet de forçage de localisation)
                        logging.info(f"IP non-française ({pays_actuel}) détectée. Forçage de la localisation...")
                        driver.get("https://www.amazon.fr/")
                        # ... (clics sur le bouton, code postal, etc.)
            except Exception as e:
                logging.error(f"Impossible de démarrer Selenium pour {site}: {e}")
                if driver: driver.quit()
                continue

        for tache in taches:
            logging.info(f"Vérification de '{tache['nom_set']}'...")
            prix_actuel = None
            
            try:
                kwargs = {}
                if "selenium" in scraper_type:
                    kwargs['driver'] = driver
                    kwargs['url'] = tache['url']
                else: 
                    kwargs['url'] = tache['url']
                    kwargs['headers'] = headers

                if scraper_type in ['standard', 'standard_selenium']:
                    kwargs['selecteur'] = tache['selecteur']
                elif scraper_type == 'eclate_selenium':
                    kwargs.update(tache['selecteur'])

                prix_actuel = scraper_function(**kwargs)

            except Exception as e:
                logging.error(f"Erreur inattendue lors du scraping de {tache['url']}: {e}")

            if prix_actuel is None:
                logging.warning("Prix non trouvé.")
                continue
            
            logging.info(f"Prix actuel : {prix_actuel}€")
            df_filtre = df_historique[(df_historique['ID_Set'] == tache['id_set']) & (df_historique['Site'] == site)]
            prix_precedent = df_filtre['Prix'].iloc[-1] if not df_filtre.empty else None
            
            if prix_precedent is None or abs(prix_actuel - prix_precedent) > 0.01:
                logging.info(f"Changement de prix détecté (précédent : {prix_precedent}€). Enregistrement...")
                nouvelle_ligne = {'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'ID_Set': tache['id_set'], 'Nom_Set': tache['nom_set'], 'Site': site, 'Prix': prix_actuel}
                lignes_a_ajouter.append(nouvelle_ligne)
                
                if prix_precedent is not None and prix_actuel < prix_precedent:
                    logging.info("BAISSE DE PRIX ! Ajout à la liste de notification.")
                    
                    is_bonne_affaire = False
                    try:
                        # On récupère les infos de configuration pour ce set
                        config_set_row = df_config.loc[df_config['ID_Set'] == tache['id_set']].iloc[0]
                        nb_pieces = pd.to_numeric(config_set_row.get('nbPieces'), errors='coerce')
                        collection = config_set_row.get('Collection', 'default')
                        
                        if pd.notna(nb_pieces):
                            prix_moyen = PRIX_MOYEN_PAR_COLLECTION.get(collection, PRIX_MOYEN_PAR_COLLECTION['default'])
                            prix_juste = nb_pieces * prix_moyen
                            seuil = prix_juste * SEUIL_BONNE_AFFAIRE
                            if prix_actuel <= seuil:
                                is_bonne_affaire = True
                    except IndexError:
                        logging.warning(f"Impossible de trouver les infos de config pour le set {tache['id_set']} pour l'analyse de 'bonne affaire'.")

                    baisses_de_prix_a_notifier.append({
                        'nom_set': tache['nom_set'],
                        'nouveau_prix': prix_actuel,
                        'prix_precedent': prix_precedent,
                        'site': site,
                        'url': tache['url'],
                        'bonne_affaire': is_bonne_affaire
                    })
            else:
                logging.info("Pas de changement de prix.")
            time.sleep(5)
        
        if driver:
            logging.info(f"Fermeture de la session Selenium pour {site}")
            driver.quit()

    if baisses_de_prix_a_notifier:
        envoyer_email_recapitulatif(baisses_de_prix_a_notifier)
    if lignes_a_ajouter:
        df_a_ajouter = pd.DataFrame(lignes_a_ajouter)
        df_historique = pd.concat([df_historique, df_a_ajouter], ignore_index=True)
        df_historique['ID_Set'] = df_historique['ID_Set'].astype(str)
        df_historique['Prix'] = df_historique['Prix'].astype(float)
        df_historique.to_excel(FICHIER_EXCEL, index=False)
        logging.info(f"{len(lignes_a_ajouter)} modifications enregistrées dans le fichier Excel.")

# Ce bloc garantit que la fonction principale est appelée
# uniquement lorsque le script est exécuté directement.
if __name__ == "__main__":
    #obtenir_localisation_ip()
    verifier_les_prix()