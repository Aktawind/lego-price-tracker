# Fichier : envoi_email.py
# Envoi transactionnel via l'API Resend (https://resend.com), utilisé à la fois
# par email_manager.py (baisses de prix) et deal_hunter.py (bons plans).
# Remplace l'ancien envoi SMTP via mot de passe d'application Gmail, moins fiable
# sur la délivrabilité long terme.
import logging

import requests

RESEND_API_URL = "https://api.resend.com/emails"


def envoyer(sujet, text_body, html_body, email_config):
    """Envoie un email via l'API Resend. Retourne True en cas de succès."""
    api_key = email_config.get('api_key')
    expediteur = email_config.get('expediteur')
    destinataire = email_config.get('destinataire')

    if not (api_key and destinataire):
        logging.error("Configuration email incomplète (RESEND_API_KEY / MAIL_DESTINATAIRE manquant), email non envoyé.")
        return False

    destinataires = [d.strip() for d in destinataire.split(',') if d.strip()]

    try:
        reponse = requests.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": expediteur,
                "to": destinataires,
                "subject": sujet,
                "html": html_body,
                "text": text_body,
            },
            timeout=15,
        )
        reponse.raise_for_status()
        logging.info(f"Email envoyé via Resend : {sujet}")
        return True
    except requests.exceptions.RequestException as e:
        detail = e.response.text if getattr(e, 'response', None) is not None else ''
        logging.error(f"Erreur lors de l'envoi de l'email via Resend : {e} {detail}")
        return False
