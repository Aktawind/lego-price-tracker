# Fichier : scrapers/standard_scraper.py

import logging
import re
import requests
from bs4 import BeautifulSoup

def scrape(url, headers, selecteur):
    """
    Scrape le prix sur un site standard qui ne nécessite pas Selenium.
    Utilise requests pour la rapidité et une regex robuste pour l'extraction.
    
    Args:
        url (str): L'URL de la page produit.
        headers (dict): Les en-têtes de la requête (User-Agent, etc.).
        selecteur (str): Le sélecteur CSS pour trouver l'élément contenant le prix.
    """
    try:
        # On utilise verify=False pour éviter les erreurs SSL sur certains réseaux
        reponse = requests.get(url, headers=headers, verify=False, timeout=10)
        reponse.raise_for_status() # Lève une erreur si le statut n'est pas 200 (OK)
        
        soup = BeautifulSoup(reponse.content, 'html.parser')
        
        # 1. On utilise le sélecteur fourni pour trouver la "boîte" qui contient le prix.
        element_prix = soup.select_one(selecteur)
        
        if not element_prix:
            logging.warning(f"Sélecteur '{selecteur}' non trouvé sur la page {url}")
            return None
            
        # 2. On prend UNIQUEMENT le texte de cette boîte pour une recherche ciblée.
        prix_texte_brut = element_prix.get_text()
        logging.info(f"  -> Texte brut trouvé avec le sélecteur '{selecteur}': '{prix_texte_brut.strip()}'")

        # 3. On applique notre regex "chirurgicale" sur ce petit bout de texte.
        #    Plan A : Chercher un nombre avec des décimales (ex: 49,99 ou 49.99)
        match = re.search(r'\b(\d+[.,]\d{1,2})\b', prix_texte_brut)
        if match:
            prix_str = match.group(1).replace(',', '.')
            return float(prix_str)
            
        # Plan B : Si aucun prix décimal n'est trouvé, chercher un entier
        #          suivi explicitement du symbole € pour éviter les faux positifs.
        match_entier = re.search(r'(\d+)\s*€', prix_texte_brut)
        if match_entier:
            return float(match_entier.group(1))

        # Si aucune des deux méthodes n'a fonctionné
        logging.warning(f"Aucun motif de prix trouvé dans le texte '{prix_texte_brut.strip()}'")
        return None
        
    except requests.exceptions.RequestException as e:
        # Gère les erreurs de connexion, timeout, etc.
        logging.error(f"Erreur de requête pour {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Erreur inattendue en récupérant le prix pour {url}: {e}")
        return None