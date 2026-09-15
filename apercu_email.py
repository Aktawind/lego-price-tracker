# Génère un aperçu HTML de l'email, sans l'envoyer ni avoir besoin d'une clé API.
# Usage : python apercu_email.py
import webbrowser
import envoi_email
import email_manager

def fausse_requete_post(url, headers=None, json=None, timeout=None):
    with open('apercu_email.html', 'w', encoding='utf-8') as f:
        f.write(json['html'])
    class FauxReponse:
        def raise_for_status(self): pass
    return FauxReponse()

envoi_email.requests.post = fausse_requete_post

deals_test = [{
    'id_set': '10321', 'nom_set': 'Corvette (TEST)', 'nouveau_prix': 179.99,
    'prix_precedent': 219.99, 'site': 'Amazon', 'url': 'https://www.amazon.fr/',
    'image_url': 'https://www.lego.com/cdn/cs/set/assets/blt2564f1fe0e59bb78/10321.png',
    'analyse_affaire': 'tres_bonne', 'nb_pieces': 1210,
    'contexte_record': "🏆 Prix le plus bas jamais enregistré pour ce set, il n'a jamais été aussi bas !",
    'est_record_absolu': True, 'est_record_6_mois': True,
    'url_wiki': 'https://github.com/Aktawind/lego-price-tracker/wiki/10321-Corvette',
}]

email_manager.envoyer_email_recapitulatif(
    deals_test,
    {'api_key': 'preview', 'expediteur': 'test@example.com', 'destinataire': 'test@example.com'}
)
webbrowser.open('apercu_email.html')