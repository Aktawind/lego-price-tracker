import logging
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def scrape(driver, url):
    """Scrape le prix d'un produit sur Brickmo.com."""
    wait = WebDriverWait(driver, 10)
    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'meta[itemprop="price"]')))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        meta_tag = soup.find('meta', itemprop='price')
        if meta_tag and meta_tag.has_attr('content'):
            return float(meta_tag['content'])
            
        logging.warning(f"Balise meta 'price' non trouvée sur {url}")
        return None
        
    except Exception as e:
        logging.error(f"Erreur lors du scraping de Brickmo ({url}): {e}")
        driver.save_screenshot(f"error_brickmo.png")
        return None