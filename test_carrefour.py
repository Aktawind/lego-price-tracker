import time
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# --- CONFIGURATION DU TEST ---
# Mettez ici l'URL exacte du produit Carrefour que vous voulez tester
URL_CARREFOUR = "https://www.carrefour.fr/p/lego-bonsai-d-erable-rouge-du-japon-decoration-vegetale-10348-lego-5702017814674"

# Les sélecteurs que nous avons identifiés pour le prix éclaté
SELECTEUR_EUROS = ".product-price__content.c-text--size-m"
SELECTEUR_CENTIMES = ".product-price__content.c-text--size-s"

# Configuration du logging pour avoir des messages clairs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_carrefour_scraper():
    """
    Script de test isolé pour le scraping d'une page produit Carrefour.
    """
    logging.info(f"Début du test pour Carrefour sur l'URL : {URL_CARREFOUR}")
    
    # --- Création du Driver Selenium "Furtif" ---
    options = Options()
    # Mettez la ligne suivante en commentaire pour voir le navigateur s'exécuter
    # options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    
    # On applique la cape d'invisibilité
    stealth(driver, languages=["fr-FR", "fr"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
    
    wait = WebDriverWait(driver, 10)
    prix_final = None
    
    try:
        driver.get(URL_CARREFOUR)
        
        # --- Gestionnaire de Cookies Universel ---
        try:
            xpath_cookies = (
                "//button[contains(text(), 'Tout accepter')]"
                " | //button[contains(text(), 'Accepter & Fermer')]"
                " | //a[contains(text(), 'Continuer sans accepter')]"
                " | //button[@id='onetrust-accept-btn-handler']"
            )
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_cookies)))
            logging.info(f"Bannière de cookies trouvée. Clic sur '{bouton_cookies.text}'...")
            bouton_cookies.click()
            wait.until(EC.invisibility_of_element(bouton_cookies))
        except Exception:
            logging.info("Pas de bannière de cookies gérée visible.")
        
        # --- Extraction du Prix Éclaté ---
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, SELECTEUR_EUROS)))
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, SELECTEUR_CENTIMES)))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        partie_entiere_elem = soup.select_one(SELECTEUR_EUROS)
        partie_fraction_elem = soup.select_one(SELECTEUR_CENTIMES)
        
        if partie_entiere_elem and partie_fraction_elem:
            partie_entiere = partie_entiere_elem.get_text(strip=True)
            partie_fraction = partie_fraction_elem.get_text(strip=True).replace(',', '')
            prix_complet_str = f"{partie_entiere}.{partie_fraction}"
            prix_final = float(prix_complet_str)
        
    except Exception as e:
        logging.error(f"Une erreur est survenue : {e}")
        driver.save_screenshot("debug_test_carrefour.png")
        logging.info("Capture d'écran de débogage sauvegardée : debug_test_carrefour.png")
        
    finally:
        driver.quit()

    # --- Affichage du Résultat ---
    if prix_final is not None:
        print("\n" + "="*30)
        print(f"✅ SUCCÈS ! Prix trouvé pour Carrefour : {prix_final}€")
        print("="*30)
    else:
        print("\n" + "="*30)
        print("❌ ÉCHEC. Le prix n'a pas pu être trouvé.")
        print("="*30)

# --- Point d'Entrée du Script ---
if __name__ == "__main__":
    test_carrefour_scraper()