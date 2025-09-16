# Fichier : deal_hunter.py
import requests
from bs4 import BeautifulSoup
import logging
import json
import os
import smtplib
from email.mime.text import MIMEText

# --- CONFIGURATION ---
URL_BONS_PLANS = "https://www.avenuedelabrique.com/promotions-et-bons-plans-lego"
FICHIER_MEMOIRE = "deals_vus.json"
URL_BASE_AVENUE = "https://www.avenuedelabrique.com"

# Configuration Email (à lire depuis les secrets GitHub)
EMAIL_CONFIG = {
    "adresse": os.getenv('GMAIL_ADDRESS'),
    "mot_de_passe": os.getenv('GMAIL_APP_PASSWORD'),
    "destinataire": os.getenv('MAIL_DESTINATAIRE')
}

def charger_deals_vus():
    """Charge la liste des ID de deals déjà vus depuis le fichier JSON."""
    if not os.path.exists(FICHIER_MEMOIRE):
        return set()
    try:
        with open(FICHIER_MEMOIRE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError):
        return set()

def sauvegarder_deals_vus(deals_ids):
    """Sauvegarde la liste mise à jour des ID de deals."""
    with open(FICHIER_MEMOIRE, 'w', encoding='utf-8') as f:
        json.dump(list(deals_ids), f, indent=4)

def envoyer_email_alerte_deals(nouveaux_deals):
    """Envoie un email récapitulatif pour les nouveaux deals trouvés."""
    sujet = f"🔥 Alerte Bons Plans LEGO : {len(nouveaux_deals)} nouvelle(s) promotion(s) trouvée(s) !"
    
    corps_email = "Bonjour,\n\nDe nouvelles promotions LEGO ont été détectées sur Avenue de la Brique :\n\n"
    
    for deal in nouveaux_deals:
        corps_email += (
            f"--------------------\n"
            f"MARCHAND: {deal['marchand']}\n"
            f"OFFRE: {deal['titre']}\n"
            f"DÉTAILS: {deal.get('details', 'N/A')}\n"
            f"LIEN: {deal['url']}\n"
        )
        
    msg = MIMEText(corps_email)
    msg['Subject'] = sujet
    msg['From'] = EMAIL_CONFIG['adresse']
    msg['To'] = EMAIL_CONFIG['destinataire']

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(EMAIL_CONFIG['adresse'], EMAIL_CONFIG['mot_de_passe'])
            smtp_server.send_message(msg)
        logging.info("Email d'alerte pour les nouveaux bons plans envoyé !")
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi de l'email de bons plans : {e}")

def main():
    logging.info("Lancement du chasseur de bons plans...")
    
    deals_vus = charger_deals_vus()
    nouveaux_deals = []
    
    try:
        response = requests.get(URL_BONS_PLANS, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # --- 1. Scraper les Promotions Générales ---
        offres_generales = soup.select('div.pns a.pn')
        logging.info(f"Analyse de {len(offres_generales)} promotions générales...")
        for offre in offres_generales:
            href = offre.get('href')

            # On récupère la date de fin
            date_fin_elem = offre.select_one('.pn-dat')
            date_fin_texte = date_fin_elem.text.replace("Offre valable jusqu'au", "").strip() if date_fin_elem else "sans-date"
            
            # On crée l'ID composite
            deal_id = f"{href}_{date_fin_texte}"
          
            if deal_id not in deals_vus:
                marchand = offre.select_one('.pn-btn strong').text.strip()
                titre = offre.select_one('.pn-lib').text.replace(marchand, '', 1).strip()
                details = offre.select_one('.pn-txt').text.strip()
                url = f"{URL_BASE_AVENUE}{href}"
                
                nouveaux_deals.append({
                    "marchand": marchand,
                    "titre": titre,
                    "details": f"{details} (Valable jusqu'au {date_fin_texte})",
                    "url": url
                })
                deals_vus.add(deal_id)
                logging.info(f"  -> NOUVEAU DEAL GÉNÉRAL TROUVÉ : {marchand} - {titre} (ID: {deal_id})")

        # --- 2. Scraper les Sets en Forte Promotion ---
        '''
        sets_en_promo = soup.select('div.prods a.prodl')
        logging.info(f"Analyse de {len(sets_en_promo)} sets en promotion...")
        for set_promo in sets_en_promo:
            href = set_promo.get('href')
            deal_id = href # Pour les sets individuels, l'URL est un bon ID unique
            
            if deal_id not in deals_vus:
                titre = set_promo.select_one('.prodl-libelle').text.strip()
                ref = set_promo.select_one('.prodl-ref').text.strip()
                prix = set_promo.select_one('.prodl-prix span').text.strip()
                reduc = set_promo.select_one('.prodl-reduc').text.strip()
                url = href
                
                nouveaux_deals.append({
                    "marchand": "Divers (voir offre)",
                    "titre": f"SET PROMO ({reduc}) : {titre} ({ref})",
                    "details": f"Disponible à partir de {prix}",
                    "url": url
                })
                deals_vus.add(deal_id)
                logging.info(f"  -> NOUVEAU SET EN PROMO TROUVÉ : {titre} ({ref})")
        '''

    except Exception as e:
        logging.error(f"Erreur lors du scraping de la page des bons plans : {e}")
        return

    # --- 3. Envoyer les notifications et sauvegarder ---
    if nouveaux_deals:
        logging.info(f"{len(nouveaux_deals)} nouvelles promotions à notifier.")
        envoyer_email_alerte_deals(nouveaux_deals)
        sauvegarder_deals_vus(deals_vus)
    else:
        logging.info("Aucune nouvelle promotion détectée.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if not all(EMAIL_CONFIG.values()):
        logging.warning("Configuration email incomplète. Le script s'exécutera sans envoyer de notifications.")
        main()