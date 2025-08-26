from bs4 import BeautifulSoup
import requests
import logging

def scrape(url, headers):
    """Scrape le prix d'un produit sur Brickmo.com."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        meta_tag = soup.find('meta', itemprop='price')
        if meta_tag and meta_tag.has_attr('content'):
            return float(meta_tag['content'])
            
        logging.warning(f"Balise meta 'price' non trouvée sur {url}")
        return None
    except Exception as e:
        logging.error(f"Erreur lors du scraping de Brickmo ({url}): {e}")
        return None