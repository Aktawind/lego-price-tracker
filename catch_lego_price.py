import pandas as pd
from datetime import datetime
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib3
import os
import logging
import requests
from config_shared import PRIX_MOYEN_PAR_COLLECTION, SEUIL_BONNE_AFFAIRE, SEUIL_TRES_BONNE_AFFAIRE

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# On importe notre nouvelle boîte à outils de scrapers
import scrapers

# --- CONFIGURATION GLOBALE ---

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Le "cerveau" qui sait quel type de scraper utiliser pour chaque site.
# La clé (ex: "Amazon") doit correspondre au nom du site dans l'en-tête de colonne de l'Excel.
CONFIG_SITES = {   
    "Amazon": { "type": "amazon", "use_selenium": True },
    "Lego": { "type": "standard", "selecteur": '[data-test="product-price"]', "use_selenium": False },
    "Auchan": { "type": "standard", "selecteur": ".product-price", "use_selenium": False },
    "Leclerc": { "type": "standard", "selecteur": ".egToM .visually-hidden", "use_selenium": False },
    "Carrefour": { 
        "type": "carrefour", 
        "selecteur": { "euros": ".product-price__content.c-text--size-m", "centimes": ".product-price__content.c-text--size-s" },
        "use_selenium": True 
    },
    "Brickmo": { "type": "brickmo", "use_selenium": True },
}

# Fichiers
FICHIER_EXCEL = "prix_lego.xlsx"
FICHIER_CONFIG_EXCEL = 'config_sets.xlsx'

# Identifiants Email (lus depuis les secrets GitHub ou un fichier .env local)
EMAIL_ADRESSE = os.getenv('GMAIL_ADDRESS')
EMAIL_MOT_DE_PASSE = os.getenv('GMAIL_APP_PASSWORD')
EMAIL_DESTINATAIRE = os.getenv('MAIL_DESTINATAIRE')

# --- FONCTIONS UTILITAIRES ---

def charger_configuration_sets(fichier_config):
    """Lit le fichier de configuration Excel au format 'large'."""
    try:
        df = pd.read_excel(fichier_config, dtype=str)
        df.fillna('', inplace=True)
        return df
    except FileNotFoundError:
        logging.error(f"Fichier de configuration '{fichier_config}' introuvable.")
        return None
    except Exception as e:
        logging.error(f"Erreur lors de la lecture de '{fichier_config}': {e}")
        return None

def regrouper_taches_par_site(df_config):
    """Transforme le DataFrame de configuration en un dictionnaire de tâches groupées par site."""
    taches_par_site = {}
    for index, row in df_config.iterrows():
        set_id = row['ID_Set']
        nom_set = row['Nom_Set']
        for site_nom, site_config in CONFIG_SITES.items():
            colonne_url = f"URL_{site_nom}"
            if colonne_url in row and row[colonne_url]:
                if site_nom not in taches_par_site:
                    taches_par_site[site_nom] = []
                
                tache = site_config.copy()
                tache['url'] = row[colonne_url]
                tache['id_set'] = set_id
                tache['nom_set'] = nom_set
                taches_par_site[site_nom].append(tache)
    return taches_par_site

def creer_driver_selenium(scraper_type="standard"):
    """Crée et retourne une instance configurée du driver Chrome."""
    logging.info(f"Création d'un driver Selenium (type: {scraper_type})")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)

    if scraper_type == "fnac": # Si vous réactivez la Fnac
        stealth(driver, languages=["fr-FR", "fr"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
                
    return driver
    
# Fonction pour envoyer un email d'alerte
def envoyer_email_recapitulatif(baisses_de_prix):
    """
    Prend une liste de baisses de prix et envoie un seul email de résumé
    """
    
    nombre_baisses = len(baisses_de_prix)
    sujet = f"Alerte Prix LEGO : {nombre_baisses} baisse(s) de prix détectée(s) !"
    
    # On crée un email 'alternative' pour avoir une version texte et une version HTML
    msg = MIMEMultipart('alternative')
    msg['Subject'] = sujet
    msg['From'] = EMAIL_ADRESSE
    msg['To'] = EMAIL_DESTINATAIRE

    # On prépare les deux versions du corps de l'email
    text_body = "Bonjour,\n\nVoici les baisses de prix détectées aujourd'hui :\n\n"
    html_body = """
    <html>
      <head></head>
      <body style="font-family: sans-serif;">
        <h2>Bonjour,</h2>
        <p>Voici les baisses de prix détectées aujourd'hui :</p>
    """
    
    for deal in baisses_de_prix:
        message_affaire = ""
        if deal.get('analyse_affaire') == "tres_bonne":
            message_affaire = "\n   >> C'est une TRÈS bonne affaire ! 🔥🔥🔥"
        elif deal.get('analyse_affaire') == "bonne":
            message_affaire = "\n   >> C'est une bonne affaire ! ✅✅"

        text_body += (
            f"--------------------\n"
            f"Set: {deal['nom_set']}\n"
            f"Site: {deal['site']}\n"
            f"Ancien Prix: {deal['prix_precedent']:.2f}€\n"
            f"NOUVEAU PRIX: {deal['nouveau_prix']:.2f}€{message_affaire}\n"
            f"Lien: {deal['url']}\n"
        )
      
        html_body += f"""
        <hr>
        <div style="padding: 10px;">
            <h3 style="margin-top:0;">{deal['nom_set']}</h3>
            <p style="line-height: 1.5;">
                <b>Site:</b> {deal['site']}<br>
                <b>Ancien Prix:</b> {deal['prix_precedent']:.2f}€<br>
                <b style="color:green; font-size: 1.1em;">NOUVEAU PRIX: {deal['nouveau_prix']:.2f}€</b>
                {message_affaire}
            </p>
            <p><a href="{deal['url']}" style="background-color: #007bff; color: white; padding: 8px 12px; text-decoration: none; border-radius: 5px;">Voir l'offre</a></p>
        </div>
        """
        
    lien_wiki = "https://github.com/Aktawind/lego-price-tracker/wiki"
    text_body += f"\n\nPour une analyse détaillée, consultez votre tableau de bord : {lien_wiki}"
    html_body += f'<hr><p>Pour une analyse détaillée et l\'historique des prix, consultez votre <a href="{lien_wiki}">tableau de bord</a>.</p></body></html>'
    
    # On attache les deux versions (texte et HTML)
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    
    # La partie envoi reste la même
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(EMAIL_ADRESSE, EMAIL_MOT_DE_PASSE)
            smtp_server.send_message(msg)
        logging.info(f"Email récapitulatif de {nombre_baisses} baisse(s) envoyé !")
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi de l'email récapitulatif : {e}")

def obtenir_localisation_ip():
    """
    Interroge le service ipinfo.io pour connaître le code pays de l'adresse IP actuelle.
    Retourne le code pays (ex: 'FR', 'US', 'IE') ou None en cas d'erreur.
    """
    try:
        logging.info("Récupération de la localisation de l'IP...")
        
        # On fait un appel à l'API de ipinfo.io qui renvoie du JSON
        reponse = requests.get("https://ipinfo.io/json", timeout=5)
        
        # Lève une exception si la requête a échoué (ex: statut 4xx ou 5xx)
        reponse.raise_for_status()
        
        # On convertit la réponse JSON en dictionnaire Python
        data = reponse.json()
        
        # On récupère la valeur de la clé 'country', avec 'N/A' comme valeur par défaut
        pays = data.get('country', 'N/A')
        
        logging.info(f"Localisation détectée : Pays={pays}")
        return pays
        
    except requests.exceptions.RequestException as e:
        # Gère spécifiquement les erreurs de réseau (timeout, pas de connexion...)
        logging.error(f"Impossible de contacter le service de localisation IP : {e}")
        return None
    except Exception as e:
        # Gère toutes les autres erreurs possibles (JSON invalide, etc.)
        logging.error(f"Erreur inattendue lors de la récupération de la localisation de l'IP : {e}")
        return None
    
def verifier_les_prix():
    logging.info("Lancement de la vérification des prix")
    
    df_config = charger_configuration_sets(FICHIER_CONFIG_EXCEL)
    if df_config is None: return

    try:
        df_historique = pd.read_excel(FICHIER_EXCEL, dtype={'ID_Set': str})
    except FileNotFoundError:
        logging.info("Fichier Excel d'historique non trouvé. Création d'un nouveau.")
        df_historique = pd.DataFrame(columns=['Date', 'ID_Set', 'Nom_Set', 'Site', 'Prix'])
    
    headers = { 'User-Agent': 'Mozilla/5.0 ...', 'Accept-Language': 'fr-FR,fr;q=0.9' }
    
    lignes_a_ajouter = []
    baisses_de_prix_a_notifier = []
    taches_par_site = regrouper_taches_par_site(df_config)

    for site, taches in taches_par_site.items():
        logging.info(f"--- Début du traitement pour le site : {site} ---")
        site_config = CONFIG_SITES.get(site)
        if not site_config:
            logging.error(f"Configuration manquante pour le site {site}")
            continue
        
        scraper_type = site_config['type']
        
        try:
            scraper_function = getattr(scrapers, f"scrape_{scraper_type}")
        except AttributeError:
            logging.error(f"Aucun scraper trouvé pour le type '{scraper_type}' dans scrapers/__init__.py")
            continue

        driver = None
        if site_config.get("use_selenium", False):
            try:
                driver = creer_driver_selenium(scraper_type)

                # Logique de localisation pour Amazon, faite une seule fois par session
                if scraper_type == "amazon":
                    pays_actuel = obtenir_localisation_ip()
                    if pays_actuel and pays_actuel != 'FR':
                        logging.info(f"IP non-française ({pays_actuel}) détectée. Forçage de la localisation pour Amazon...")
                        try:
                            # On va directement sur la page d'accueil pour que la popup soit disponible
                            driver.get("https://www.amazon.fr/")
                            wait = WebDriverWait(driver, 10)
                            
                            # 1. Cliquer sur le bouton de localisation
                            bouton_localisation = wait.until(
                                EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link"))
                            )
                            bouton_localisation.click()
                            
                            # 2. Attendre que le champ du code postal dans la popup soit visible
                            champ_postal = wait.until(
                                EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput"))
                            )
                            
                            # 3. Entrer le code postal français
                            champ_postal.send_keys("38540")
                            
                            # 4. Cliquer sur le bouton "Actualiser"
                            bouton_actualiser = driver.find_element(By.CSS_SELECTOR, '[data-action="GLUXPostalUpdateAction"] input')
                            bouton_actualiser.click()

                            # 5. Attendre que la popup se ferme et que la page se mette à jour
                            wait.until(EC.staleness_of(bouton_actualiser))
                            logging.info("Localisation française pour Amazon forcée avec succès.")
                            time.sleep(2) # Petite pause pour la stabilisation
                        except Exception as e:
                            logging.warning(f"La procédure de forçage de localisation pour Amazon a échoué : {e}")
                    else:
                        logging.info("IP française (ou non détectée), pas de forçage de localisation nécessaire pour Amazon.")

                if scraper_type == "brickmo":
                    logging.info("Préparation de la session pour Brickmo...")
                    driver.get("https://www.brickmo.com/fr/")
                    driver.add_cookie({'name': 'shop', 'value': '13'})
                    logging.info("Cookie de localisation pour Brickmo ajouté.")
                    # On peut même ajouter une petite pause pour être sûr
                    time.sleep(2)

            except Exception as e:
                logging.error(f"Impossible de démarrer Selenium pour {site}: {e}")
                if driver: driver.quit()
                continue

        for tache in taches:
            logging.info(f"Vérification de '{tache['nom_set']}'...")
            prix_actuel = None
            
            try:
                kwargs = {'url': tache['url']}
                if driver: kwargs['driver'] = driver
                else: kwargs['headers'] = headers
                
                if 'selecteur' in tache and tache['selecteur']:
                    if isinstance(tache['selecteur'], dict):
                        kwargs.update(tache['selecteur'])
                    else:
                        kwargs['selecteur'] = tache['selecteur']
                
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
                    
                    analyse_affaire = "standard" # Par défaut
                    try:
                        config_set_row = df_config.loc[df_config['ID_Set'] == tache['id_set']].iloc[0]
                        nb_pieces = pd.to_numeric(config_set_row.get('nbPieces'), errors='coerce')
                        collection = config_set_row.get('Collection', 'default')
                        image_url = config_set_row.get('Image_URL', '')
                        
                        if pd.notna(nb_pieces):
                            prix_moyen = PRIX_MOYEN_PAR_COLLECTION.get(collection, PRIX_MOYEN_PAR_COLLECTION['default'])
                            prix_juste = nb_pieces * prix_moyen
                            
                            if prix_actuel <= prix_juste * SEUIL_TRES_BONNE_AFFAIRE:
                                analyse_affaire = "tres_bonne"
                            elif prix_actuel <= prix_juste * SEUIL_BONNE_AFFAIRE:
                                analyse_affaire = "bonne"
                    except IndexError:
                        logging.warning(f"Impossible de trouver les infos de config pour {tache['id_set']} pour l'analyse.")

                    baisses_de_prix_a_notifier.append({
                        'nom_set': tache['nom_set'], 'nouveau_prix': prix_actuel,
                        'prix_precedent': prix_precedent, 'site': site, 'url': tache['url'],
                        'image_url': image_url,
                        'analyse_affaire': analyse_affaire # On passe le résultat de l'analyse
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

# --- POINT D'ENTRÉE ---
if __name__ == "__main__":
    if not all([EMAIL_ADRESSE, EMAIL_MOT_DE_PASSE, EMAIL_DESTINATAIRE]):
        logging.error("Variables d'environnement pour l'email non configurées. Arrêt.")
    else:
        verifier_les_prix()