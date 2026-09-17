import json
import logging
import re
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


def _extraire_prix_json_ld(soup):
    """Cherche un prix dans les données structurées JSON-LD (schema.org Product/Offer).
    Souvent plus stable qu'un sélecteur CSS, qui casse à chaque refonte du site
    (ex: le sélecteur de prix de lego.com a cessé de fonctionner après un changement
    de design, alors que ces données pensées pour le SEO n'ont pas bougé)."""
    try:
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
            except (json.JSONDecodeError, TypeError):
                continue
            objets = data if isinstance(data, list) else [data]
            for objet in objets:
                if not isinstance(objet, dict):
                    continue
                offres = objet.get('offers')
                candidats = offres if isinstance(offres, list) else [offres]
                for offre in candidats:
                    if not isinstance(offre, dict):
                        continue
                    for cle in ('price', 'lowPrice'):
                        brut = offre.get(cle)
                        if brut in (None, ''):
                            continue
                        try:
                            return float(str(brut).replace(',', '.'))
                        except ValueError:
                            continue
    except Exception:
        pass
    return None


def scrape(url, selecteur, headers=None, driver=None):
    """Récupère un prix soit via une simple requête HTTP (headers),
    soit via un navigateur Selenium (driver) quand le site bloque les
    requêtes non-navigateur (ex: Lego.com renvoie 403 en requests brut)."""
    try:
        if driver is not None:
            driver.get(url)
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selecteur)))
            except Exception:
                pass  # On tente quand même de parser ce qui a pu charger
            soup = BeautifulSoup(driver.page_source, 'html.parser')
        else:
            reponse = requests.get(url, headers=headers, verify=False, timeout=10)
            reponse.raise_for_status()
            soup = BeautifulSoup(reponse.content, 'html.parser')

        element_prix = soup.select_one(selecteur)
        if element_prix:
            prix_texte_brut = element_prix.get_text()

            match = re.search(r'\b(\d+[.,]\d{1,2})\b', prix_texte_brut)
            if match:
                return float(match.group(1).replace(',', '.'))

            match_entier = re.search(r'(\d+)\s*€', prix_texte_brut)
            if match_entier:
                return float(match_entier.group(1))

            logging.warning(f"Aucun motif de prix trouvé dans le texte '{prix_texte_brut.strip()}'")
        else:
            logging.warning(f"Sélecteur '{selecteur}' non trouvé sur {url}, tentative via les données JSON-LD...")

        # Filet de sécurité : le sélecteur CSS n'a rien donné (absent, ou texte
        # sans motif de prix reconnaissable). On tente les données structurées
        # avant d'abandonner.
        prix_json_ld = _extraire_prix_json_ld(soup)
        if prix_json_ld is not None:
            logging.info(f"  -> Prix trouvé via les données JSON-LD : {prix_json_ld}€")
            return prix_json_ld

        # Diagnostic : distingue "pas de JSON-LD du tout sur la page" (page
        # d'erreur, blocage anti-bot...) de "JSON-LD présent mais sans prix
        # exploitable" (ex: set en rupture de stock, structure différente),
        # pour pouvoir diagnostiquer un futur échec sans accès direct au site.
        if soup.find_all('script', type='application/ld+json'):
            logging.warning(f"  -> Données JSON-LD présentes sur {url} mais aucun prix exploitable n'y a été trouvé.")
        else:
            logging.warning(f"  -> Aucune donnée JSON-LD trouvée sur {url}.")

        return None

    except Exception as e:
        logging.error(f"Erreur en récupérant le prix pour {url}: {e}")
        return None
