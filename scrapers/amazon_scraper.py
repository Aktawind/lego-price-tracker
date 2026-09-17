import logging
import re
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _extraire_prix_depuis_soup(soup):
    """Cherche un prix dans le HTML déjà chargé d'une page produit Amazon,
    séparé de la navigation Selenium pour être testable sans navigateur."""
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


# La localisation/devise France est forcée une seule fois pour toute la
# session, en amont, par catch_lego_price.py (cookies lc-acbfr/i18n-prefs sur
# le driver partagé) avant le premier appel à scrape() : pas besoin de la
# refaire ici pour chaque URL produit.
def scrape(driver, url):
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(url)

        # On gère les popups qui peuvent apparaître sur la page produit elle-même
        try:
            continuer_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Continuer les achats']")))
            logging.info("  -> Page 'Continuer' détectée. Clic...")
            continuer_button.click()
            wait.until(EC.presence_of_element_located((By.ID, "dp-container")))
        except Exception:
            pass 

        # Récupérer le prix. Amazon utilise plusieurs identifiants de conteneur
        # selon le type de page produit (corePrice_feature_div, ou la mise en
        # page desktop plus récente corePriceDisplay_desktop_feature_div) : on
        # attend l'un OU l'autre plutôt qu'un seul id fixe. Un délai plus long
        # ici, car la page vient de se recharger après le clic sur "Continuer
        # les achats" au-dessus. Si rien n'apparaît dans le délai, on tente
        # quand même l'extraction sur ce qui a fini par charger : le parsing
        # ci-dessous cherche directement les balises de prix dans le HTML,
        # l'attente n'est qu'un délai de courtoisie, pas une condition stricte.
        try:
            WebDriverWait(driver, 15).until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "#corePrice_feature_div, #corePriceDisplay_desktop_feature_div, span.a-offscreen")
            ))
        except Exception:
            logging.warning(f"  -> Conteneur de prix non détecté dans le délai pour {url}, tentative d'extraction quand même...")

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        return _extraire_prix_depuis_soup(soup)

    except Exception as e:
        logging.error(f"Erreur lors du scraping de l'URL Amazon {url}: {type(e).__name__}: {e}")
        driver.save_screenshot(f"error_amazon_{int(time.time())}.png")
        return None