import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# --- CONFIGURATION DES TESTS ---
# Collez ici les URL des produits que vous voulez tester
URLS_A_TESTER = {
    #"SmythsToys": "https://www.smythstoys.com/fr/fr-fr/jouets/lego/lego-botanicals/lego-icons-10368-chrysantheme/p/236761",
    "Brickmo": "https://www.brickmo.com/en/new-at-brickmo/lego/65737/lego-icons-10368-chrysanthemum-10368",
    #"Cultura": "https://www.cultura.com/p-legor-10368-extra-botanicals-icons-1-10555952.html"
}

# --- FONCTION DE SCRAPING UNIVERSELLE POUR LES TESTS ---
def scrape_site(nom_site, url):
    print(f"--- Test du site : {nom_site} ---")
    
    # Configuration Selenium Stealth (notre meilleure arme)
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
    stealth(driver, languages=["fr-FR", "fr"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
    
    wait = WebDriverWait(driver, 15) # On met un peu plus de temps d'attente

    try:
        driver.get(url)
        
        # --- GESTIONNAIRE DE COOKIES UNIVERSEL ---
        try:
            xpath_cookies = (
                "//button[contains(text(), 'Tout accepter')]"
                " | //button[contains(text(), 'Accepter & Fermer')]"
                " | //button[contains(text(), 'accepter et fermer')]"
                " | //a[contains(text(), 'Continuer sans accepter')]"
                " | //button[contains(text(), 'Continuer sans accepter')]"
                " | //button[@id='onetrust-accept-btn-handler']"
                " | //button[contains(text(), 'J’accepte')]"
            )
            bouton_cookies = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_cookies)))
            print(f"Bannière de cookies trouvée. Clic sur '{bouton_cookies.text}'...")
            bouton_cookies.click()
            wait.until(EC.invisibility_of_element(bouton_cookies))
        except Exception:
            print("Pas de bannière de cookies gérée visible.")

        # --- LOGIQUE DE SCRAPING SPÉCIFIQUE À CHAQUE SITE ---
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        prix = None

        if nom_site == "SmythsToys":
            # Votre code : <span class="text-price-xl">14</span>
            # On cherche un élément avec cette classe, mais on prend le parent pour avoir tout le prix
            prix_container = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-cy="product-price-display"]')))
            prix_texte = prix_container.text
            match = re.search(r'(\d+[.,]\d{2})', prix_texte.replace(',', '.'))
            if match:
                prix = float(match.group(1))

        elif nom_site == "Brickmo":
            # Votre code : <meta itemprop="price" content="10.95">
            # C'est la source de données la plus fiable qui soit !
            meta_tag = soup.find('meta', itemprop='price')
            if meta_tag and meta_tag.has_attr('content'):
                prix = float(meta_tag['content'])

        elif nom_site == "Cultura":
            # Votre code : prix éclaté <div ...>449<span ...>,99€</span></div>
            # On prend le conteneur parent
            prix_container = soup.find('div', class_='price--big')
            if prix_container:
                prix_texte = prix_container.get_text(strip=True) # Va donner "449,99€"
                match = re.search(r'(\d+[.,]\d{2})', prix_texte.replace(',', '.'))
                if match:
                    prix = float(match.group(1))

        if prix:
            print(f"✅ SUCCÈS ! Prix trouvé : {prix}€")
        else:
            print("❌ ÉCHEC. Prix non trouvé.")
            # En cas d'échec, on sauvegarde une capture pour le débogage
            driver.save_screenshot(f"debug_screenshot_{nom_site}.png")
            print(f"Capture d'écran de débogage sauvegardée : debug_screenshot_{nom_site}.png")

    except Exception as e:
        print(f"❌ ERREUR MAJEURE : {e}")
        driver.save_screenshot(f"debug_screenshot_{nom_site}.png")
        print(f"Capture d'écran de débogage sauvegardée : debug_screenshot_{nom_site}.png")
    finally:
        driver.quit()

# --- EXÉCUTION DES TESTS ---
if __name__ == "__main__":
    for site, url_produit in URLS_A_TESTER.items():
        scrape_site(site, url_produit)
        print("\n" + "="*30 + "\n")