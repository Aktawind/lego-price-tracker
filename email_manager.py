# Fichier : email_manager.py
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def envoyer_email_recapitulatif(baisses_de_prix, email_config):
    """
    Prend une liste de baisses de prix et les détails de configuration email,
    et envoie un seul email de résumé.
    """
    
    nombre_baisses = len(baisses_de_prix)
    sujet = f"Alerte Prix LEGO : {nombre_baisses} baisse(s) de prix détectée(s) !"
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = sujet
    msg['From'] = email_config['adresse']
    msg['To'] = email_config['destinataire']

    # On prépare les deux versions du corps de l'email
    text_body = "Bonjour,\n\nVoici les baisses de prix détectées aujourd'hui :\n\n"
    html_body = """
    <html><body style="font-family: sans-serif;">
    <h2>Bonjour,</h2><p>Voici les baisses de prix détectées aujourd'hui :</p>
    """
    
    for deal in baisses_de_prix:
        # On ajoute la mention "record" si c'est le cas
        message_record = "🏆 NOUVEAU MEILLEUR PRIX SUR LE MARCHÉ !" if deal.get('est_un_record') else ""
        
        analyse_affaire = deal.get('analyse_affaire')
        message_affaire_txt = ""
        if analyse_affaire == "tres_bonne": message_affaire_txt = "\n   >> C'est une TRÈS bonne affaire 🔥🔥"
        elif analyse_affaire == "bonne": message_affaire_txt = "\n   >> C'est une bonne affaire ✅✅"

        text_body += (
            f"--------------------\n"
            f"Set: {deal['nom_set']}\n"
            f"Site: {deal['site']}\n"
            f"Ancien Meilleur Prix: {deal['prix_precedent']:.2f}€\n"
            f"NOUVEAU MEILLEUR PRIX: {deal['nouveau_prix']:.2f}€\n"
            f"{message_record}{message_affaire_txt}\n"
            f"Lien: {deal['url']}\n"
        )
      
        html_body += f"""
        <hr>
        <div style="padding: 10px;">
            <h3 style="margin-top:0;">{deal['nom_set']}</h3>
            {f'<p style="font-weight: bold; color: #d9534f;">{message_record}</p>' if message_record else ''}
            <p style="line-height: 1.5;">
                <b>Site:</b> {deal['site']}<br>
                <b>Ancien Meilleur Prix:</b> {deal['prix_precedent']:.2f}€<br>
                <b style="color:green; font-size: 1.1em;">NOUVEAU PRIX: {deal['nouveau_prix']:.2f}€</b>
                {message_affaire_txt.replace(chr(10), '<br>')}
            </p>
            <p><a href="{deal['url']}" style="background-color: #007bff; color: white; padding: 8px 12px; text-decoration: none; border-radius: 5px;">Voir l'offre</a></p>
        </div>
        """
        
    lien_wiki = "https://github.com/Aktawind/lego-price-tracker/wiki"
    text_body += f"\n\nPour une analyse détaillée, consultez votre tableau de bord : {lien_wiki}"
    html_body += f'<hr><p>Consultez votre <a href="{lien_wiki}">tableau de bord complet</a>.</p></body></html>'
    
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp_server:
            smtp_server.starttls()
            smtp_server.login(email_config['adresse'], email_config['mot_de_passe'])
            smtp_server.send_message(msg)
        logging.info(f"Email récapitulatif de {nombre_baisses} baisse(s) envoyé !")
    except Exception as e:
        logging.error(f"Erreur lors de l'envoi de l'email récapitulatif : {e}")