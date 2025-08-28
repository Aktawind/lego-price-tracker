import logging
import re
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape(driver, url):
    wait = WebDriverWait(driver, 10)
    
    try:
        driver.get(url)

        try:
            continuer_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Continuer les achats']")))
            logging.info("  -> Page 'Continuer' détectée. Clic...")
            continuer_button.click()
            wait.until(EC.presence_of_element_located((By.ID, "dp-container")))
        except Exception:
            pass # C'est normal si ce n'est pas là

        try:
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.ID, "sp-cc-accept")))
            logging.info("  -> Bannière de cookies trouvée. Clic...")
            bouton_cookies.click()
        except Exception:
            pass # C'est normal si ce n'est pas là
        
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