import logging
import re
import time
import requests # Nécessaire pour obtenir_localisation_ip
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- FONCTION UTILITAIRE SPÉCIFIQUE À AMAZON ---
def obtenir_localisation_ip():
    try:
        logging.info("Récupération de la localisation de l'IP...")
        reponse = requests.get("https://ipinfo.io/json", timeout=5)
        reponse.raise_for_status()
        data = reponse.json()
        pays = data.get('country', 'N/A')
        logging.info(f"Localisation détectée : Pays={pays}")
        return pays
    except Exception as e:
        logging.error(f"Impossible de récupérer la localisation de l'IP: {e}")
        return None

# --- SCRAPER PRINCIPAL POUR AMAZON ---
def scrape(driver, url):
    wait = WebDriverWait(driver, 10)
    
    try:
        # ÉTAPE 1 : FORCER LA LOCALISATION SI NÉCESSAIRE
        pays_actuel = obtenir_localisation_ip()
        if pays_actuel and pays_actuel != 'FR':
            logging.info(f"IP non-française ({pays_actuel}) détectée. Forçage de la localisation...")
            try:
                driver.get("https://www.amazon.fr/") # Visiter la page d'accueil pour le contexte
                bouton_localisation = wait.until(EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link")))
                bouton_localisation.click()
                champ_postal = wait.until(EC.visibility_of_element_located((By.ID, "GLUXZipUpdateInput")))
                champ_postal.send_keys("38540")
                bouton_actualiser = driver.find_element(By.CSS_SELECTOR, '[data-action="GLUXPostalUpdateAction"] input')
                bouton_actualiser.click()
                wait.until(EC.staleness_of(bouton_actualiser))
                logging.info("Localisation française pour Amazon forcée avec succès.")
            except Exception as e:
                logging.warning(f"La procédure de forçage de localisation pour Amazon a échoué : {e}")
        else:
            logging.info("IP française (ou non détectée), pas de forçage de localisation nécessaire.")

        # ÉTAPE 2 : ALLER SUR LA PAGE PRODUIT
        driver.get(url)

        # ÉTAPE 3 : GÉRER LES POPUPS SPÉCIFIQUES À LA PAGE PRODUIT
        try:
            continuer_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Continuer les achats']")))
            logging.info("  -> Page 'Continuer' détectée. Clic...")
            continuer_button.click()
            wait.until(EC.presence_of_element_located((By.ID, "dp-container")))
        except Exception:
            pass 

        try:
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.ID, "sp-cc-accept")))
            logging.info("  -> Bannière de cookies trouvée. Clic...")
            bouton_cookies.click()
        except Exception:
            pass 
        
        # ÉTAPE 4 : RÉCUPÉRER LE PRIX
        wait.until(EC.visibility_of_element_located((By.ID, "corePrice_feature_div")))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        element_prix = soup.select_one("span.a-offscreen")
        if element_prix:
            match = re.search(r'(\d+[.,]\d{1,2})', element_prix.get_text())
            if match:
                return float(match.group(1).replace(',', '.'))
        
        partie_entiere_elem = soup.select_one("span.a-price-whole")
        partie_fraction_elem = soup.select_one("span.a-price-fraction")
        if partie_entiere_elem and partie_fraction_elem:
            partie_entiere_propre = "".join(filter(str.isdigit, partie_entiere_elem.get_text()))
            prix_complet_str = f"{partie_entiere_propre}.{partie_fraction_elem.get_text(strip=True)}"
            return float(prix_complet_str)
            
        return None

    except Exception as e:
        logging.error(f"Erreur lors du scraping de l'URL Amazon {url}: {e}")
        driver.save_screenshot(f"error_amazon_{int(time.time())}.png")
        return None