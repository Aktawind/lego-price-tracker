import requests
from bs4 import BeautifulSoup
import logging
import re

# --- CONFIGURATION DU TEST ---
# L'URL de la page produit sur Avenue de la Brique
URL_AVENUE = "https://www.avenuedelabrique.com/lego-harry-potter/76450-book-nook-le-poudlard-express/p10886"

# Les vendeurs que nous voulons spécifiquement trouver
VENDEURS_CIBLES = [
    "amazon", "cdiscount", "fnac", "e.leclerc",
    "auchan", "carrefour", "la grande récré", "ltoys", "jouéclub", "kidinn"
]

def scrape_avenue_de_la_brique(url):
    """
    Scrape une page produit d'Avenue de la Brique pour extraire les URL des revendeurs.
    """
    logging.info(f"Scraping de la page : {url}")
    urls_trouvees = {}
    
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # On trouve tous les conteneurs d'offres
        offres = soup.find_all('div', class_='prodf-px')
        logging.info(f"{len(offres)} offres trouvées sur la page.")
        
        for offre in offres:
            # Récupérer le nom du vendeur depuis l'attribut 'alt' de l'image
            logo_img = offre.select_one('.prodf-px-logo img')
            if not logo_img or not logo_img.has_attr('alt'):
                continue
                
            alt_text = logo_img['alt'].lower()
            
            # Récupérer le lien de l'offre
            lien_tag = offre.find('a')
            if not lien_tag or not lien_tag.has_attr('href'):
                continue
            
            # On vérifie si le vendeur est dans notre liste cible
            for vendeur_cible in VENDEURS_CIBLES:
                if vendeur_cible in alt_text:
                    # On a trouvé un vendeur qui nous intéresse !
                    url_relative = lien_tag['href']
                    url_absolue = f"https://www.avenuedelabrique.com{url_relative}"
                    
                    # On stocke l'URL. Le nom du vendeur est normalisé pour correspondre à nos clés.
                    nom_vendeur_normalise = vendeur_cible.replace(' ', '').capitalize()
                    if nom_vendeur_normalise == "E.leclerc": nom_vendeur_normalise = "Leclerc"

                    if nom_vendeur_normalise not in urls_trouvees:
                        urls_trouvees[nom_vendeur_normalise] = url_absolue
                        logging.info(f"  -> Trouvé : {nom_vendeur_normalise} -> {url_absolue}")
                    break # On passe à l'offre suivante
                    
        return urls_trouvees

    except Exception as e:
        logging.error(f"Erreur lors du scraping d'Avenue de la Brique : {e}")
        return None

# --- EXÉCUTION DU TEST ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    resultats = scrape_avenue_de_la_brique(URL_AVENUE)
    
    if resultats:
        print("\n--- RÉSULTATS ---")
        for vendeur, url in resultats.items():
            print(f"{vendeur}: {url}")
    else:
        print("\n--- AUCUN RÉSULTAT ---")