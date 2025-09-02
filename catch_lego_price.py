import pandas as pd
from datetime import datetime
import time
import urllib3
import os
import logging
import requests
import json
from config_shared import PRIX_MOYEN_PAR_COLLECTION, SEUIL_BONNE_AFFAIRE, SEUIL_TRES_BONNE_AFFAIRE

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import scrapers
import email_manager

# --- CONFIGURATION GLOBALE ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
CONFIG_SITES = {
    "Amazon": { "type": "amazon", "use_selenium": True },
    "Lego": { "type": "standard", "selecteur": '[data-test="product-price"]', "use_selenium": False },
    "Auchan": { "type": "standard", "selecteur": ".product-price", "use_selenium": False },
    "Leclerc": { "type": "standard", "selecteur": ".egToM .visually-hidden", "use_selenium": False },
    "Carrefour": { "type": "carrefour", "selecteur": { "euros": ".product-price__content.c-text--size-m", "centimes": ".product-price__content.c-text--size-s" }, "use_selenium": True },
    # Ajoutez d'autres sites ici au besoin
}
FICHIER_EXCEL = "prix_lego.xlsx"
FICHIER_CONFIG_EXCEL = 'config_sets.xlsx'

# On regroupe la configuration email dans un dictionnaire
EMAIL_CONFIG = {
    "adresse": os.getenv('GMAIL_ADDRESS'),
    "mot_de_passe": os.getenv('GMAIL_APP_PASSWORD'),
    "destinataire": os.getenv('MAIL_DESTINATAIRE')
}

# --- FONCTIONS UTILITAIRES ---
def charger_configuration_sets_df(fichier_config):
    """Lit simplement le fichier de configuration Excel et retourne un DataFrame."""
    try:
        df = pd.read_excel(fichier_config, dtype=str)
        df.fillna('', inplace=True)
        return df
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

    return driver

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
    
# --- FONCTION PRINCIPALE ---
def verifier_les_prix():
    logging.info("Lancement de la vérification des prix")
    
    df_config = charger_configuration_sets_df(FICHIER_CONFIG_EXCEL)
    if df_config is None: return

    try:
        df_historique_precedent = pd.read_excel(FICHIER_EXCEL, dtype={'ID_Set': str})
    except FileNotFoundError:
        df_historique_precedent = pd.DataFrame(columns=['Date', 'ID_Set', 'Nom_Set', 'Site', 'Prix', 'URL'])
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9'
    }
        
    # --- ÉTAPE 1 : COLLECTE ---
    lignes_a_ajouter = []
    taches_traitees = set() # Pour le dédoublonnage

    # --- Phase 1a : Traitement Automatique via Avenue de la Brique ---
    logging.info("--- Début du traitement des deals d'Avenue de la Brique ---")
    try:
        with open('deals_du_jour.json', 'r', encoding='utf-8') as f:
            deals_avenue = json.load(f)
    except Exception:
        deals_avenue = {}

    for set_id, offres in deals_avenue.items():
        config_set_row_df = df_config.loc[df_config['ID_Set'] == set_id]
        if config_set_row_df.empty:
            logging.warning(f"Set {set_id} trouvé sur Avenue mais non présent dans la config. Ignoré.")
            continue
        nom_set = config_set_row_df.iloc[0]['Nom_Set']

        for offre in offres:
            site = offre['site']
            prix_actuel = offre['prix']
            url_offre = offre['url']
            
            # On ajoute le prix trouvé à notre collecte du jour
            nouvelle_ligne = {
                'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ID_Set': set_id,
                'Nom_Set': nom_set,
                'Site': site,
                'Prix': prix_actuel,
                'URL': url_offre
            }
            lignes_a_ajouter.append(nouvelle_ligne)
            
            # On marque cette tâche comme "faite" pour ne pas la rescraper manuellement
            taches_traitees.add((set_id, site))

    # --- Phase 1b : Traitement Manuel pour les URL de la configuration ---
    taches_manuelles = regrouper_taches_par_site(df_config)
    
    SCRAPERS = {
        "amazon": scrapers.scrape_amazon,
        "carrefour": scrapers.scrape_carrefour,
        "standard": scrapers.scrape_standard
    }

    for site, taches in taches_manuelles.items():
        # On filtre pour ne pas refaire le travail déjà fait par Avenue
        taches_a_faire = [t for t in taches if (t['id_set'], site) not in taches_traitees]
        
        if not taches_a_faire:
            logging.info(f"--- Traitement manuel pour {site} ignoré (toutes les tâches ont été traitées via Avenue) ---")
            continue

        logging.info(f"--- Début du traitement manuel pour : {site} ---")
        site_config = CONFIG_SITES.get(site)
        if not site_config: continue
        
        scraper_type = site_config.get('type')
        scraper_function = SCRAPERS.get(scraper_type)
        if not scraper_function: continue

        driver = None
        if site_config.get("use_selenium", False):
            try:
                driver = creer_driver_selenium(scraper_type)
                if scraper_type == "amazon":
                    pays_actuel = obtenir_localisation_ip()
                    if pays_actuel and pays_actuel != 'FR':
                        logging.info(f"IP non-française ({pays_actuel}) détectée. Forçage de la localisation pour Amazon...")
                        try:
                            driver.get("https://www.amazon.fr/")
                            wait = WebDriverWait(driver, 10)
                            
                            # === DÉBUT DE LA MODIFICATION ===

                            # 1. On gère les cookies sur la page d'accueil AVANT tout le reste
                            try:
                                bouton_cookies = wait.until(EC.element_to_be_clickable((By.ID, "sp-cc-accept")))
                                bouton_cookies.click()
                                logging.info("  -> Bannière de cookies sur la page d'accueil gérée.")
                                time.sleep(1) # Petite pause pour laisser la bannière disparaître
                            except Exception:
                                logging.info("  -> Pas de bannière de cookies sur la page d'accueil.")

                            # 2. On utilise un sélecteur plus robuste pour le bouton de localisation
                            #    On cherche un lien ou un div qui a un ID contenant "location"
                            xpath_localisation = "//*[@id='nav-global-location-popover-link' or @id='glow-ingress-block']"
                            bouton_localisation = wait.until(
                                EC.element_to_be_clickable((By.XPATH, xpath_localisation))
                            )
                            bouton_localisation.click()
                            
                            # 3. Le reste est inchangé car vos nouveaux extraits HTML le confirment
                            champ_postal = wait.until(EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput")))
                            champ_postal.clear() # On vide le champ au cas où il serait pré-rempli
                            champ_postal.send_keys("38540")
                            
                            bouton_actualiser_container = wait.until(EC.element_to_be_clickable((By.ID, "GLUXZipUpdate")))
                            bouton_actualiser_container.click()
                            
                            # 4. On attend que la page se recharge en vérifiant que le code postal est bien mis à jour
                            wait.until(EC.text_to_be_present_in_element((By.ID, "glow-ingress-line2"), "38540"))
                            logging.info("Localisation française pour Amazon forcée avec succès.")  
                            
                        except Exception as e:
                            # Si la localisation échoue, c'est une erreur critique pour Amazon
                            logging.error(f"La procédure de forçage de localisation pour Amazon a échoué : {e}")
                            driver.quit() # On ferme le driver
                            continue # ON PASSE AU SITE SUIVANT
                            
                    else:
                        logging.info("IP française (ou non détectée), pas de forçage nécessaire pour Amazon.")

            except Exception as e:
                logging.error(f"Impossible de démarrer/préparer Selenium pour {site}: {e}")
                if driver: driver.quit()
                continue

        for tache in taches_a_faire:
            logging.info(f"Vérification de '{tache['nom_set']}'...")
            
            url_propre = tache['url'].strip().rstrip(':/')
            
            try:
                kwargs = {'url': url_propre}
                if driver: kwargs['driver'] = driver
                else: kwargs['headers'] = headers
                
                if 'selecteur' in tache and tache['selecteur']:
                    if isinstance(tache['selecteur'], dict):
                        kwargs.update(tache['selecteur'])
                    else:
                        kwargs['selecteur'] = tache['selecteur']
                
                prix_actuel = scraper_function(**kwargs)
            except Exception as e:
                logging.error(f"Erreur inattendue lors de l'appel du scraper pour {url_propre}: {e}")
                prix_actuel = None # S'assurer que le prix est None en cas d'erreur

            if prix_actuel is not None:
                nouvelle_ligne = {
                    'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'ID_Set': tache['id_set'],
                    'Nom_Set': tache['nom_set'],
                    'Site': site,
                    'Prix': prix_actuel,
                    'URL': url_propre
                }
                lignes_a_ajouter.append(nouvelle_ligne)
            else:
                logging.warning("Prix non trouvé pour cette tâche.")
            
            time.sleep(5)
        
        if driver:
            logging.info(f"Fermeture de la session Selenium pour {site}")
            driver.quit()

    # --- ÉTAPE 2 : ANALYSE ---
    # === PHASE 2 : ANALYSE GLOBALE ET DÉCISION DE NOTIFICATION ===

    if not lignes_a_ajouter:
        logging.info("Aucun prix n'a pu être récupéré aujourd'hui. Fin du script.")
        return

    # On crée un DataFrame avec tous les prix trouvés aujourd'hui
    df_aujourdhui = pd.DataFrame(lignes_a_ajouter)
    
    # On identifie les sets pour lesquels on a des données aujourd'hui
    sets_scannes_ids = df_aujourdhui['ID_Set'].unique()
    
    baisses_de_prix_a_notifier = []
    
    logging.info("Analyse des changements pour les alertes de meilleur prix du marché...")
    for set_id in sets_scannes_ids:
        
        # --- Comparaison J-1 vs J-0 ---
        
        # 1. On récupère les données de ce set pour AUJOURD'HUI
        prix_set_aujourdhui = df_aujourdhui[df_aujourdhui['ID_Set'] == set_id]
        meilleur_prix_aujourdhui = prix_set_aujourdhui['Prix'].min()
        meilleure_offre_aujourdhui = prix_set_aujourdhui.loc[prix_set_aujourdhui['Prix'].idxmin()]
        
        # 2. On récupère l'historique de ce set AVANT aujourd'hui
        df_set_historique_precedent = df_historique_precedent[df_historique_precedent['ID_Set'] == set_id]
        
        if df_set_historique_precedent.empty:
            logging.info(f"Nouveau set {set_id} ou premier prix enregistré. Pas de comparaison possible pour une alerte.")
            continue # C'est la première fois qu'on voit ce set, on ne peut pas comparer.

        # 3. On trouve le dernier meilleur prix connu sur le marché
        #    On prend les derniers prix enregistrés pour chaque site, puis le minimum parmi ceux-là.
        meilleur_prix_precedent = df_set_historique_precedent.sort_values('Date').groupby('Site')['Prix'].last().min()
        
        # === LA CONDITION D'ALERTE FINALE ===
        if meilleur_prix_aujourdhui < meilleur_prix_precedent:
            logging.info(f"🏆 Baisse du meilleur prix marché pour le set {set_id} ! Nouveau meilleur prix: {meilleur_prix_aujourdhui}€ (précédent: {meilleur_prix_precedent}€)")
            
            # On prépare les données pour l'email
            nom_set = meilleure_offre_aujourdhui['Nom_Set']
            site_offre = meilleure_offre_aujourdhui['Site']
            url_offre = meilleure_offre_aujourdhui.get('URL', '#')
            
            # On exécute l'analyse "bonne affaire"
            analyse_affaire = "standard"
            image_url = ''
            try:
                config_set_row = df_config.loc[df_config['ID_Set'] == set_id].iloc[0]
                nb_pieces = pd.to_numeric(config_set_row.get('nbPieces'), errors='coerce')
                collection = config_set_row.get('Collection', 'default')
                image_url = config_set_row.get('Image_URL', '')
                
                if pd.notna(nb_pieces):
                    prix_moyen = PRIX_MOYEN_PAR_COLLECTION.get(collection, PRIX_MOYEN_PAR_COLLECTION['default'])
                    prix_juste = nb_pieces * prix_moyen
                    if meilleur_prix_aujourdhui <= prix_juste * SEUIL_TRES_BONNE_AFFAIRE:
                        analyse_affaire = "tres_bonne"
                    elif meilleur_prix_aujourdhui <= prix_juste * SEUIL_BONNE_AFFAIRE:
                        analyse_affaire = "bonne"
            except IndexError:
                logging.warning(f"Infos de config manquantes pour le set {set_id} pour l'analyse.")

            baisses_de_prix_a_notifier.append({
                'nom_set': nom_set,
                'nouveau_prix': meilleur_prix_aujourdhui,
                'prix_precedent': meilleur_prix_precedent,
                'site': site_offre,
                'url': url_offre,
                'image_url': image_url,
                'analyse_affaire': analyse_affaire,
                'est_un_record': True # On peut utiliser cette clé pour un message spécial
            })
        else:
            logging.info(f"Meilleur prix pour le set {set_id} n'a pas baissé (Actuel: {meilleur_prix_aujourdhui}€ vs Précédent: {meilleur_prix_precedent}€).")

    # --- ÉTAPE 3 : NOTIFICATION ET SAUVEGARDE ---
    if baisses_de_prix_a_notifier:
        email_manager.envoyer_email_recapitulatif(baisses_de_prix_a_notifier, EMAIL_CONFIG)
        
    # On sauvegarde l'historique complet, qui inclut les nouveaux prix du jour
    df_historique_final = pd.concat([df_historique_precedent, df_aujourdhui], ignore_index=True)
    df_historique_final.to_excel(FICHIER_EXCEL, index=False)
    logging.info(f"{len(lignes_a_ajouter)} prix enregistrés/mis à jour dans le fichier Excel.")

# --- POINT D'ENTRÉE ---
if __name__ == "__main__":
    if not all(EMAIL_CONFIG.values()):
        logging.error("Variables d'environnement pour l'email non configurées. Arrêt.")
    else:
        verifier_les_prix()