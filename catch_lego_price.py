import pandas as pd
from datetime import datetime, timedelta
import time
import urllib3
import os
import logging
import requests
import json
from config_shared import (
    PRIX_MOYEN_PAR_COLLECTION, SEUIL_BONNE_AFFAIRE, SEUIL_TRES_BONNE_AFFAIRE,
    construire_url_wiki_set, charger_config_email, email_config_complete,
    driver_est_vivant, executer_avec_retries,
)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

import scrapers
import email_manager
import historique_db

# --- CONFIGURATION GLOBALE ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
CONFIG_SITES = {
    "Amazon": { "type": "amazon", "use_selenium": True },
    # Lego.com bloque les requêtes HTTP "brutes" (403 Forbidden) : on passe par un
    # vrai navigateur Selenium, comme pour les autres sites protégés par un anti-bot.
    "Lego": { "type": "standard", "selecteur": '[data-test="product-price"]', "use_selenium": True },
    "Auchan": { "type": "standard", "selecteur": ".product-price", "use_selenium": False },
    "Leclerc": { "type": "standard", "selecteur": ".egToM .visually-hidden", "use_selenium": False },
    "Carrefour": { "type": "carrefour", "selecteur": { "euros": ".product-price__content.c-text--size-m", "centimes": ".product-price__content.c-text--size-s" }, "use_selenium": True },
    # Ajoutez d'autres sites ici au besoin
}
FICHIER_CONFIG_EXCEL = 'config_sets.xlsx'

# On regroupe la configuration email dans un dictionnaire
EMAIL_CONFIG = charger_config_email()

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
    """
    Crée et retourne une instance configurée du driver Chrome.
    Applique le mode 'stealth' pour les types de scrapers spécifiés.
    """
    logging.info(f"Création d'un driver Selenium (type: {scraper_type})")
    
    # Configuration "paranoïaque" pour un mimétisme humain maximal
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
    
    # Création de l'instance du driver
    driver = webdriver.Chrome(options=options)

    # --- Application conditionnelle du mode Stealth ---
    # Mettez ici la liste de tous les types de scrapers qui nécessitent le camouflage
    # "standard" est inclus car c'est le type utilisé pour le scraping direct de
    # Lego.com, qui bloque les navigateurs non "furtifs" avec un 403.
    types_furtifs = ["fnac", "carrefour", "kingjouet", "standard"] # Ajoutez/retirez des types au besoin

    if scraper_type in types_furtifs:
        logging.info("  -> Activation du mode Stealth pour ce scraper.")
        stealth(driver,
                languages=["fr-FR", "fr"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True)
                
    return driver

def notification_autorisee_par_seuil(nouveau_prix, prix_alerte):
    """Une baisse n'est notifiée que si aucun seuil n'est configuré pour ce
    set, ou si le nouveau prix passe sous ce seuil. Permet d'ignorer les
    micro-baisses sans intérêt (ex: 50€ -> 49€) quand un prix cible a été
    défini (colonne Prix_Alerte)."""
    return prix_alerte is None or nouveau_prix <= prix_alerte


def analyser_record_prix(df_set_historique_precedent, nouveau_prix, fenetre_recente_jours=182):
    """Compare le nouveau prix à tout l'historique connu (pas juste le dernier prix
    par site) pour dire si c'est un prix jamais vu, ou le plus bas depuis N mois.
    Retourne (message_lisible, est_record_absolu, est_record_recent)."""
    if df_set_historique_precedent.empty:
        return None, False, False

    prix_min_absolu = df_set_historique_precedent['Prix'].min()
    est_record_absolu = nouveau_prix <= prix_min_absolu

    date_limite = datetime.now() - timedelta(days=fenetre_recente_jours)
    dates_historique = pd.to_datetime(df_set_historique_precedent['Date'], errors='coerce')
    df_recent = df_set_historique_precedent[dates_historique >= date_limite]
    prix_min_recent = df_recent['Prix'].min() if not df_recent.empty else prix_min_absolu
    est_record_recent = nouveau_prix <= prix_min_recent

    mois = round(fenetre_recente_jours / 30.4)
    if est_record_absolu:
        return f"🏆 Prix le plus bas jamais enregistré pour ce set, il n'a jamais été aussi bas !", True, True
    elif est_record_recent:
        return f"📉 Plus bas prix des {mois} derniers mois !", False, True
    return None, False, False

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

    df_historique_precedent = historique_db.charger_historique()
    
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

                        def _tenter_forcer_localisation():
                            driver.get("https://www.amazon.fr/")
                            wait_local = WebDriverWait(driver, 10)

                            # 1. La bannière de consentement cookies (RGPD) apparaît sur
                            #    chaque nouvelle session et bloque le reste de la page tant
                            #    qu'elle n'est pas fermée (clics suivants interceptés sans
                            #    erreur visible). Un précédent nettoyage de ce code avait
                            #    supprimé cette étape par erreur en la confondant avec le
                            #    forçage de localisation ci-dessous — deux choses distinctes.
                            try:
                                bouton_cookies = wait_local.until(EC.element_to_be_clickable((By.ID, "sp-cc-accept")))
                                bouton_cookies.click()
                                time.sleep(1)
                            except Exception:
                                pass  # Pas de bannière cette fois (ou déjà acceptée) : on continue.

                            # 2. Devise/langue : cookies directs qu'Amazon lit pour ça, fiables
                            #    et sans dépendance à un élément d'UI qui peut ne jamais
                            #    apparaître (vérification anti-bot, A/B test...).
                            driver.add_cookie({"name": "lc-acbfr", "value": "fr_FR", "domain": ".amazon.fr"})
                            driver.add_cookie({"name": "i18n-prefs", "value": "EUR", "domain": ".amazon.fr"})
                            driver.get("https://www.amazon.fr/")

                            # 3. Adresse de livraison : contrairement à la devise/langue,
                            #    Amazon valide ce changement côté serveur et ça ne peut pas
                            #    se forcer par un simple cookie fabriqué localement — il faut
                            #    une vraie interaction avec le popup. Best-effort : si cette
                            #    étape échoue (bouton introuvable, disposition différente...),
                            #    on continue quand même avec la devise/langue déjà forcées
                            #    plutôt que d'abandonner toutes les vérifications Amazon du
                            #    jour comme avant.
                            try:
                                xpath_localisation = "//*[@id='nav-global-location-popover-link' or @id='glow-ingress-block']"
                                bouton_localisation = wait_local.until(EC.element_to_be_clickable((By.XPATH, xpath_localisation)))
                                bouton_localisation.click()
                                champ_postal = wait_local.until(EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput")))
                                champ_postal.clear()
                                champ_postal.send_keys("38540")
                                bouton_actualiser = wait_local.until(EC.element_to_be_clickable((By.ID, "GLUXZipUpdate")))
                                bouton_actualiser.click()
                                wait_local.until(EC.text_to_be_present_in_element((By.ID, "glow-ingress-line2"), "38540"))
                                logging.info("  -> Adresse de livraison mise à jour vers la France.")
                            except Exception as e:
                                logging.warning(
                                    f"  -> Adresse de livraison non mise à jour ({type(e).__name__}: {e}), "
                                    "on continue avec la devise/langue forcées uniquement."
                                )

                        succes, erreur = executer_avec_retries(
                            _tenter_forcer_localisation, max_essais=2, pause_secondes=3,
                            on_echec=lambda e, tentative: logging.warning(
                                f"Tentative {tentative} de forçage de localisation Amazon échouée, nouvel essai... ({type(e).__name__}: {e})"
                            ),
                        )
                        if succes:
                            logging.info("Localisation française pour Amazon forcée avec succès (cookies lc-acbfr/i18n-prefs).")
                        else:
                            # Si la localisation échoue malgré la nouvelle tentative, c'est une erreur critique pour Amazon
                            logging.error(f"La procédure de forçage de localisation pour Amazon a échoué : {type(erreur).__name__}: {erreur}")
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

            # Si la session Selenium a planté (crash du navigateur), on la
            # recrée avant de continuer plutôt que de laisser échouer silencieusement
            # toutes les tâches restantes pour ce site.
            if driver is not None and not driver_est_vivant(driver):
                logging.warning(f"Session Selenium invalide détectée pour {site}, redémarrage du driver...")
                try:
                    driver.quit()
                except Exception:
                    pass
                try:
                    driver = creer_driver_selenium(scraper_type)
                except Exception as e:
                    logging.error(f"Impossible de recréer le driver Selenium pour {site}: {e}")
                    driver = None

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
            # On prépare les données pour l'email
            nom_set = meilleure_offre_aujourdhui['Nom_Set']
            site_offre = meilleure_offre_aujourdhui['Site']
            url_offre = meilleure_offre_aujourdhui.get('URL', '#')

            # On exécute l'analyse "bonne affaire" + on récupère les infos de config du set
            analyse_affaire = "standard"
            image_url = ''
            nb_pieces = None
            marque = 'LEGO'
            prix_alerte = None
            try:
                config_set_row = df_config.loc[df_config['ID_Set'] == set_id].iloc[0]
                nb_pieces = pd.to_numeric(config_set_row.get('nbPieces'), errors='coerce')
                collection_brute = config_set_row.get('Collection')
                collection = collection_brute if pd.notna(collection_brute) and str(collection_brute).strip() else None
                image_url = config_set_row.get('Image_URL', '')
                marque_brute = config_set_row.get('Marque')
                marque = marque_brute if pd.notna(marque_brute) and str(marque_brute).strip() else 'LEGO'
                prix_alerte = pd.to_numeric(config_set_row.get('Prix_Alerte'), errors='coerce')
                if pd.isna(prix_alerte):
                    prix_alerte = None

                # On préfère toujours l'URL officielle/manuelle renseignée dans la config
                # (page produit stable) plutôt que le lien de redirection "go/px" d'Avenue
                # de la Brique, qui expire ou devient invalide avec le temps.
                colonne_url_config = f"URL_{site_offre.replace('.', '_').replace(' ', '_')}"
                url_manuelle = config_set_row.get(colonne_url_config)
                if pd.notna(url_manuelle) and str(url_manuelle).strip():
                    url_offre = str(url_manuelle).strip()

                # Le référentiel de prix moyen au pièce ne vaut que pour les gammes LEGO
                # officielles ; on ne calcule pas de "bonne affaire" pour les autres marques.
                if marque.strip().upper() == 'LEGO' and pd.notna(nb_pieces):
                    prix_moyen = PRIX_MOYEN_PAR_COLLECTION.get(collection, PRIX_MOYEN_PAR_COLLECTION['default'])
                    prix_juste = nb_pieces * prix_moyen
                    if meilleur_prix_aujourdhui <= prix_juste * SEUIL_TRES_BONNE_AFFAIRE:
                        analyse_affaire = "tres_bonne"
                    elif meilleur_prix_aujourdhui <= prix_juste * SEUIL_BONNE_AFFAIRE:
                        analyse_affaire = "bonne"
            except IndexError:
                logging.warning(f"Infos de config manquantes pour le set {set_id} pour l'analyse.")

            # --- On ne notifie que si la baisse est "intéressante" ---
            # Si un prix cible a été défini pour ce set, on n'alerte que si le nouveau
            # prix passe sous ce seuil (ex: la Corvette qui passe de 50€ à 49€ n'a pas
            # d'intérêt si le seuil configuré est 45€).
            if not notification_autorisee_par_seuil(meilleur_prix_aujourdhui, prix_alerte):
                logging.info(f"Baisse détectée pour le set {set_id} ({meilleur_prix_aujourdhui}€) mais au-dessus du seuil d'alerte configuré ({prix_alerte}€). Pas de notification.")
                continue

            # --- Vraie analyse historique : est-ce un prix jamais vu / du jamais vu depuis longtemps ? ---
            contexte_record, est_record_absolu, est_record_6_mois = analyser_record_prix(
                df_set_historique_precedent, meilleur_prix_aujourdhui
            )
            logging.info(f"🏆 Baisse du meilleur prix marché pour le set {set_id} ! Nouveau meilleur prix: {meilleur_prix_aujourdhui}€ (précédent: {meilleur_prix_precedent}€). {contexte_record or ''}")

            baisses_de_prix_a_notifier.append({
                'id_set': set_id,
                'nom_set': nom_set,
                'nouveau_prix': meilleur_prix_aujourdhui,
                'prix_precedent': meilleur_prix_precedent,
                'site': site_offre,
                'url': url_offre,
                'image_url': image_url,
                'analyse_affaire': analyse_affaire,
                'nb_pieces': nb_pieces if pd.notna(nb_pieces) else None,
                'contexte_record': contexte_record,
                'est_record_absolu': est_record_absolu,
                'est_record_6_mois': est_record_6_mois,
                'url_wiki': construire_url_wiki_set(set_id, nom_set),
            })
        else:
            logging.info(f"Meilleur prix pour le set {set_id} n'a pas baissé (Actuel: {meilleur_prix_aujourdhui}€ vs Précédent: {meilleur_prix_precedent}€).")

    # --- ÉTAPE 3 : NOTIFICATION ET SAUVEGARDE ---
    if baisses_de_prix_a_notifier:
        email_manager.envoyer_email_recapitulatif(baisses_de_prix_a_notifier, EMAIL_CONFIG)
        
    # On n'ajoute que les nouveaux prix du jour : pas besoin de recharger/réécrire
    # tout l'historique existant comme avec l'ancien fichier Excel.
    historique_db.ajouter_lignes(lignes_a_ajouter)

# --- POINT D'ENTRÉE ---
if __name__ == "__main__":
    if not email_config_complete(EMAIL_CONFIG):
        logging.error("Variables d'environnement pour l'email non configurées (BREVO_API_KEY / BREVO_FROM_EMAIL / MAIL_DESTINATAIRE). Arrêt.")
    else:
        verifier_les_prix()