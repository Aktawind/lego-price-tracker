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

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Lecture de la configuration des sets
def charger_configuration_sets(fichier_config):
    # Lit le fichier de configuration Excel et le transforme en dictionnaire
    try:
        df_config = pd.read_excel(fichier_config, dtype=str)
        # Remplacer les valeurs 'NaN' (cellules vides) par des chaînes vides
        df_config.fillna('', inplace=True)
        
        sets_a_surveiller = {}
        for index, row in df_config.iterrows():
            set_id = row['ID_Set']
            
            # Si c'est la première fois qu'on voit ce set, on l'initialise
            if set_id not in sets_a_surveiller:
                sets_a_surveiller[set_id] = {
                    "nom": row['Nom_Set'],
                    "sites": {}
                }
            
            # On prépare les infos du site
            site_info = {
                "url": row['URL'],
                "type": row['Type']
            }
            # On ajoute le sélecteur seulement s'il n'est pas vide
            if row['Selecteur']:
                site_info['selecteur'] = row['Selecteur']
                
            # On ajoute le site à la liste du set
            sets_a_surveiller[set_id]['sites'][row['Site']] = site_info
            
        return sets_a_surveiller

    except FileNotFoundError:
        logging.error(f"Erreur: Le fichier de configuration '{fichier_config}' est introuvable.")
        return None
    except Exception as e:
        logging.error(f"Erreur lors de la lecture du fichier de configuration Excel: {e}")
        return None
    
SETS_A_SURVEILLER = charger_configuration_sets('config_sets.xlsx')
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

# Fonction pour récupérer le prix sur Amazon avec Selenium
def recuperer_prix_amazon_selenium(url, headers):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={headers['User-Agent']}")
    chrome_options.add_argument(f"accept-language={headers['Accept-Language']}")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(url)

        # 1. Gérer la page 'Continuer'
        try:
            # On cherche un élément <button> qui contient le texte 'Continuer les achats'
            continuer_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Continuer les achats']"))
            )
            #logging.info("Page intermédiaire 'Continuer' détectée. Clic...")
            continuer_button.click()
            # On attend que la nouvelle page se charge
            wait.until(EC.staleness_of(continuer_button)) 
        except Exception:
            logging.info("Pas de page intermédiaire 'Continuer' visible dans le temps imparti.")

        # 2. Gérer la bannière de cookies
        try:
            bouton_cookies = wait.until(
                EC.element_to_be_clickable((By.ID, "sp-cc-accept"))
            )
            #logging.info("Bannière de cookies trouvée. Clic sur 'Accepter'.")
            bouton_cookies.click()
            wait.until(EC.invisibility_of_element(bouton_cookies))
        except Exception:
            logging.info("Pas de bannière de cookies visible dans le temps imparti.")

        # 3. Attendre l'élément final du prix
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span.a-price-whole")))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
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
        logging.error(f"Erreur finale avec Selenium pour Amazon ({url}): {e}")
        driver.save_screenshot("amazon_debug_screenshot.png")
        return None
    finally:
        driver.quit()

# Fonction pour récupérer le prix sur un site standard
def recuperer_prix_standard(url, selecteur, headers):
    try:
        reponse = requests.get(url, headers=headers, verify=False)
        reponse.raise_for_status()
        soup = BeautifulSoup(reponse.content, 'html.parser')
        element_prix = soup.select_one(selecteur)
        if element_prix:
            prix_texte = element_prix.get_text()
            prix_nettoye = prix_texte.replace('\u202f', '').replace('\xa0', '').replace(' ', '').replace('€', '').replace(',', '.').strip()
            return float(prix_nettoye)
        return None
    except Exception as e:
        logging.error(f"Erreur en récupérant le prix pour {url}: {e}")
        return None

# Fonction pour envoyer un email d'alerte
def envoyer_email_alerte(nom_set, nouveau_prix, site, url):
    sujet = f"Alerte Baisse de Prix LEGO : {nom_set}"
    corps = f"Le prix du set LEGO '{nom_set}' a baissé sur {site} !\n\nNouveau prix : {nouveau_prix}€\n\nLien : {url}"
    msg = MIMEText(corps)
    msg['Subject'] = sujet
    msg['From'] = EMAIL_ADRESSE
    msg['To'] = EMAIL_DESTINATAIRE
    try:
        # On se connecte au serveur SMTP de Gmail sur le port 587
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            # On active le chiffrement TLS
            smtp_server.starttls()
            # On s'identifie
            smtp_server.login(EMAIL_ADRESSE, EMAIL_MOT_DE_PASSE)
            # On envoie l'email
            smtp_server.sendmail(EMAIL_ADRESSE, EMAIL_DESTINATAIRE, msg.as_string())
        logging.info(f"Email d'alerte envoyé pour {nom_set} !")
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi de l'email : {e}")

# Fonction principale pour vérifier les prix
def verifier_les_prix():
    #logging.info(f"\nLancement de la vérification des prix - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        df = pd.read_excel(FICHIER_EXCEL, dtype={'ID_Set': str})
    except FileNotFoundError:
        #logging.info("Fichier Excel non trouvé. Création d'un nouveau fichier.")
        df = pd.DataFrame({'Date': pd.Series(dtype='str'),'ID_Set': pd.Series(dtype='str'),'Nom_Set': pd.Series(dtype='str'),'Site': pd.Series(dtype='str'),'Prix': pd.Series(dtype='float')})
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9' # <-- LA LIGNE CLÉ !
    }
    lignes_a_ajouter = []
    # On crée un dictionnaire qui associe un type à une fonction
    SCRAPERS = {
        "amazon": recuperer_prix_amazon_selenium,
        "standard": recuperer_prix_standard
    }

    for set_id, set_info in SETS_A_SURVEILLER.items():
        nom_set = set_info['nom']
        for site, site_info in set_info['sites'].items():
            logging.info(f"Vérification de '{nom_set}' sur {site}...")

            scraper_type = site_info.get('type')
            scraper_function = SCRAPERS.get(scraper_type)

            prix_actuel = None
            if scraper_function:
                args = [site_info['url'], headers]
                if scraper_type == 'standard':
                    args.insert(1, site_info['selecteur']) 
                prix_actuel = scraper_function(*args)
            else:
                logging.error(f"  -> ERREUR: Type de scraper inconnu '{scraper_type}'")

            if prix_actuel is None:
                logging.warning(f"Prix non trouvé.")
                continue
            logging.info(f"Prix actuel : {prix_actuel}€")
            df_filtre = df[(df['ID_Set'] == str(set_id)) & (df['Site'] == site)]
            prix_precedent = df_filtre['Prix'].iloc[-1] if not df_filtre.empty else None
            if prix_precedent is None or abs(prix_actuel - prix_precedent) > 0.01:
                logging.info(f"  -> Changement de prix détecté (précédent : {prix_precedent}€). Enregistrement...")
                nouvelle_ligne = {'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'ID_Set': str(set_id), 'Nom_Set': nom_set, 'Site': site, 'Prix': prix_actuel}
                lignes_a_ajouter.append(nouvelle_ligne)
                if prix_precedent is not None and prix_actuel < prix_precedent:
                    logging.info("BAISSE DE PRIX ! Envoi de l'alerte...")
                    envoyer_email_alerte(nom_set, prix_actuel, site, site_info['url'])
            else:
                logging.info("Pas de changement de prix.")
            time.sleep(5)
    if lignes_a_ajouter:
        nouvelles_lignes_df = pd.DataFrame(lignes_a_ajouter)
        df = pd.concat([df, nouvelles_lignes_df], ignore_index=True)
        df.to_excel(FICHIER_EXCEL, index=False)
        logging.info("Modifications enregistrées dans le fichier Excel.")

# Ce bloc garantit que la fonction principale est appelée
# uniquement lorsque le script est exécuté directement.
if __name__ == "__main__":
    verifier_les_prix()