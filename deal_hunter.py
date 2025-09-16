# Fichier : deal_hunter.py
import requests
from bs4 import BeautifulSoup
import logging
import json
import os
import smtplib
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- CONFIGURATION ---
URL_BONS_PLANS = "https://www.avenuedelabrique.com/promotions-et-bons-plans-lego"
FICHIER_MEMOIRE = "deals_vus.json"
URL_BASE_AVENUE = "https://www.avenuedelabrique.com"

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

def envoyer_email_alerte_deals(nouveaux_deals, email_config):
    """Envoie un email récapitulatif avec une belle mise en page HTML pour les nouveaux deals."""
    
    sujet = f"🔥 Alerte Bons Plans LEGO : {len(nouveaux_deals)} nouvelle(s) promotion(s) trouvée(s) !"
    
    # On crée un email 'alternative' pour avoir une version texte et une version HTML
    msg = MIMEMultipart('alternative')
    msg['Subject'] = sujet
    msg['From'] = email_config['adresse']
    msg['To'] = email_config['destinataire']

    # On prépare les deux versions du corps de l'email
    text_body = "Bonjour,\n\nDe nouvelles promotions LEGO ont été détectées sur Avenue de la Brique.\n\n"
    html_body = """
    <html>
      <head></head>
      <body style="font-family: sans-serif;">
        <h2>Bonjour,</h2>
        <p>De nouvelles promotions LEGO ont été détectées sur Avenue de la Brique :</p>
    """
    
    for deal in nouveaux_deals:
        # Construction de la version TEXTE
        text_body += (
            f"--------------------\n"
            f"MARCHAND: {deal['marchand']}\n"
            f"OFFRE: {deal['titre']}\n"
            f"DÉTAILS: {deal.get('details', 'N/A')}\n"
            f"LIEN: {deal['url']}\n"
        )
        
        # Construction de la version HTML (avec la jolie mise en page)
        html_body += f"""
        <hr>
        <div style="padding: 10px; border-left: 4px solid #f0ad4e; margin-bottom: 10px;">
            <h3 style="margin-top:0; color:#333;">{deal['marchand']} : {deal['titre']}</h3>
            <p style="line-height: 1.5; color: #555;">
                {deal.get('details', '')}
            </p>
            <p><a href="{deal['url']}" style="background-color: #007bff; color: white; padding: 8px 12px; text-decoration: none; border-radius: 5px;">Voir le détail de l'offre</a></p>
        </div>
        """

    text_body += f"\n\nConsultez la page des bons plans pour plus d'informations."
    html_body += f'<hr><p>Ces informations proviennent de la page des bons plans. Consultez votre <a href="https://github.com/Aktawind/lego-price-tracker/wiki">tableau de bord</a> pour le suivi des prix de vos sets.</p></body></html>'
    
    # On attache les deux versions
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(email_config['adresse'], email_config['mot_de_passe'])
            smtp_server.send_message(msg)
        logging.info("Email d'alerte pour les nouveaux bons plans envoyé !")
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi de l'email de bons plans : {e}")

def main():
    logging.info("Lancement du chasseur de bons plans...")

    load_dotenv()
    EMAIL_CONFIG = {
        "adresse": os.getenv('GMAIL_ADDRESS'),
        "mot_de_passe": os.getenv('GMAIL_APP_PASSWORD'),
        "destinataire": os.getenv('MAIL_DESTINATAIRE')
    }
    config_email_complete = all(EMAIL_CONFIG.values())
    
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
        if config_email_complete:
            logging.info(f"{len(nouveaux_deals)} nouvelles promotions à notifier.")
            envoyer_email_alerte_deals(nouveaux_deals, EMAIL_CONFIG)
        else:
            logging.warning("Aucun email envoyé pour les deals car la configuration est incomplète.")
        sauvegarder_deals_vus(deals_vus)
    else:
        logging.info("Aucune nouvelle promotion détectée.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.warning("Configuration email incomplète. Le script s'exécutera sans envoyer de notifications.")
    main()