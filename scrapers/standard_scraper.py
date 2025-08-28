import logging
import re
import requests
from bs4 import BeautifulSoup

def scrape(url, headers, selecteur):
    try:
        reponse = requests.get(url, headers=headers, verify=False, timeout=10)
        reponse.raise_for_status()
        soup = BeautifulSoup(reponse.content, 'html.parser')
        
        element_prix = soup.select_one(selecteur)
        if not element_prix:
            logging.warning(f"Sélecteur '{selecteur}' non trouvé sur {url}")
            return None
            
        prix_texte_brut = element_prix.get_text()
        
        match = re.search(r'\b(\d+[.,]\d{1,2})\b', prix_texte_brut)
        if match:
            return float(match.group(1).replace(',', '.'))
            
        match_entier = re.search(r'(\d+)\s*€', prix_texte_brut)
        if match_entier:
            return float(match_entier.group(1))

        logging.warning(f"Aucun motif de prix trouvé dans le texte '{prix_texte_brut.strip()}'")
        return None
        
    except Exception as e:
        logging.error(f"Erreur en récupérant le prix pour {url}: {e}")
        return None