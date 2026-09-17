import logging
import re
import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _sauvegarder_diagnostic(driver, prefixe):
    """Sauvegarde une capture d'écran + le HTML de la page courante. On n'a
    aucun accès direct à amazon.fr depuis l'environnement de dev pour
    comprendre pourquoi une page ne donne pas de prix (CAPTCHA ? page de
    vérification anti-bot ? mise en page différente ?) : ces fichiers sont
    remontés comme artefact du run GitHub Actions (voir lego_tracker.yml)
    pour pouvoir être consultés après coup."""
    horodatage = int(time.time())
    try:
        driver.save_screenshot(f"{prefixe}_{horodatage}.png")
    except Exception:
        pass
    try:
        with open(f"{prefixe}_{horodatage}.html", 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
    except Exception:
        pass


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

        # La bannière de consentement cookies (RGPD) peut réapparaître sur une
        # page produit fraîchement chargée même si elle a déjà été fermée une
        # fois ailleurs dans la session, et bloque les clics suivants tant
        # qu'elle est affichée.
        try:
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.ID, "sp-cc-accept")))
            bouton_cookies.click()
            time.sleep(1)
        except Exception:
            pass

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
        prix = _extraire_prix_depuis_soup(soup)
        if prix is None:
            logging.warning(f"  -> Aucun prix trouvé sur {url} (titre de la page : '{driver.title}'). Capture de diagnostic enregistrée.")
            _sauvegarder_diagnostic(driver, "debug_amazon")
        return prix

    except Exception as e:
        logging.error(f"Erreur lors du scraping de l'URL Amazon {url}: {type(e).__name__}: {e}")
        _sauvegarder_diagnostic(driver, "error_amazon")
        return None