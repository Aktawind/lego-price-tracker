import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from config_shared import charger_config_email
import email_manager

email_config = charger_config_email()

if not email_config.get('api_key'):
    email_config['api_key'] = input("Clé API Resend (re_...) : ").strip()

if not email_config.get('destinataire'):
    email_config['destinataire'] = input("Adresse email de destination : ").strip()

print(f"Envoi vers : {email_config['destinataire']} avec une clé de {len(email_config['api_key'])} caractères")

deals_test = [{
    'id_set': '10321', 'nom_set': 'Corvette (TEST)', 'nouveau_prix': 179.99,
    'prix_precedent': 219.99, 'site': 'Amazon', 'url': 'https://www.amazon.fr/',
    'image_url': 'https://www.lego.com/cdn/cs/set/assets/blt2564f1fe0e59bb78/10321.png',
    'analyse_affaire': 'tres_bonne', 'nb_pieces': 1210,
    'contexte_record': 'Prix le plus bas jamais enregistre !',
    'est_record_absolu': True, 'est_record_6_mois': True,
    'url_wiki': 'https://github.com/Aktawind/lego-price-tracker/wiki/10321-Corvette',
}]

if email_manager.envoyer_email_recapitulatif(deals_test, email_config):
    print(f"Email envoyé vers {email_config['destinataire']} !")
else:
    print("Échec de l'envoi — regarde le message ERROR affiché juste au-dessus.")