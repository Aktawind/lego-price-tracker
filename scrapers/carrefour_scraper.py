import logging
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape(driver, url, euros, centimes):
    logging.info(f"  -> Scraping (prix éclaté) de {url}")
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(url)
        
        try:
            xpath_cookies = (
                "//button[contains(text(), 'Tout accepter')]"
                " | //button[contains(text(), 'Accepter & Fermer')]"
                " | //a[contains(text(), 'Continuer sans accepter')]"
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
            partie_entiere = partie_entiere_elem.get_text(strip=True).replace(',', '')
            partie_fraction = partie_fraction_elem.get_text(strip=True).replace(',', '')
            prix_complet_str = f"{partie_entiere}.{partie_fraction}"
            return float(prix_complet_str)
        return None

    except Exception as e:
        logging.error(f"Erreur lors du scraping (prix éclaté) de {url}: {e}")
        driver.save_screenshot(f"error_carrefour_{int(time.time())}.png")
        return None