# Fichier : envoi_email.py
# Envoi transactionnel via l'API Brevo (https://www.brevo.com), utilisé à la fois
# par email_manager.py (baisses de prix) et deal_hunter.py (bons plans).
# Contrairement à Resend, pas de restriction sur les destinataires une fois
# l'expéditeur vérifié (juste une limite de 300 emails/jour sur le plan gratuit).
import logging

import requests

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def envoyer(sujet, text_body, html_body, email_config):
    """Envoie un email via l'API Brevo. Retourne True en cas de succès."""
    api_key = email_config.get('api_key')
    expediteur = email_config.get('expediteur')
    destinataire = email_config.get('destinataire')

    if not (api_key and expediteur and destinataire):
        logging.error("Configuration email incomplète (BREVO_API_KEY / BREVO_FROM_EMAIL / MAIL_DESTINATAIRE manquant), email non envoyé.")
        return False

    destinataires = [{"email": d.strip()} for d in destinataire.split(',') if d.strip()]

    try:
        reponse = requests.post(
            BREVO_API_URL,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "sender": {"email": expediteur},
                "to": destinataires,
                "subject": sujet,
                "htmlContent": html_body,
                "textContent": text_body,
            },
            timeout=15,
        )
        reponse.raise_for_status()
        logging.info(f"Email envoyé via Brevo : {sujet}")
        return True
    except requests.exceptions.RequestException as e:
        detail = e.response.text if getattr(e, 'response', None) is not None else ''
        logging.error(f"Erreur lors de l'envoi de l'email via Brevo : {e} {detail}")
        return False
