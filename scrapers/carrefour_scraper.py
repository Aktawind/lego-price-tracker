# Fichier : scrapers/carrefour_scraper.py

import logging
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape(driver, url, euros, centimes):
    """
    Prend un driver Selenium déjà ouvert et scrape un prix éclaté sur Carrefour.fr.
    Gère la bannière de cookies avant de chercher le prix.
    
    Args:
        driver: L'instance du driver Selenium.
        url (str): L'URL de la page produit.
        euros (str): Le sélecteur CSS pour la partie entière du prix.
        centimes (str): Le sélecteur CSS pour la partie décimale du prix.
    """
    logging.info(f"  -> Scraping (prix éclaté) de {url}")
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(url)
        
        # --- GESTIONNAIRE DE COOKIES ---
        try:
            # Sélecteur XPath robuste pour trouver les boutons d'acceptation de cookies
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
            # Attendre que la bannière disparaisse pour être sûr
            wait.until(EC.invisibility_of_element(bouton_cookies))
        except Exception:
            logging.info("  -> Pas de bannière de cookies gérée visible.")
        
        # Attendre que les deux parties du prix soient visibles sur la page
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, euros)))
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, centimes)))
        
        # Récupérer le code source final de la page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extraire les deux parties du prix
        partie_entiere_elem = soup.select_one(euros)
        partie_fraction_elem = soup.select_one(centimes)
        
        if partie_entiere_elem and partie_fraction_elem:
            # Nettoyer et assembler les deux parties
            partie_entiere = partie_entiere_elem.get_text(strip=True).replace(',', '').replace('.', '')
            partie_fraction = partie_fraction_elem.get_text(strip=True).replace(',', '').replace('.', '')
            
            prix_complet_str = f"{partie_entiere}.{partie_fraction}"
            return float(prix_complet_str)
            
        logging.warning(f"Impossible de trouver les deux parties du prix sur {url}")
        return None

    except Exception as e:
        logging.error(f"Erreur lors du scraping (prix éclaté) de {url}: {e}")
        driver.save_screenshot(f"error_carrefour_{int(time.time())}.png")
        return None