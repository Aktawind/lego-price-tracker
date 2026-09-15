import os

# --- ANALYSE DES PRIX ---

# Dictionnaire de connaissance des prix moyens par pièce
PRIX_MOYEN_PAR_COLLECTION = {
    "Architecture": 0.088,
    "Art": 0.073,
    "The Botanical Collection": 0.0817,
    "Creator 3-en-1": 0.0835,
    "Disney™": 0.102,
    "Harry Potter™": 0.0941,
    "LEGO® Icons": 0.0883,
    "Ideas": 0.0940,
    "One Piece": 0.0886,
    "Speed Champions": 0.0886,
    "Star Wars™": 0.1024, 
    "LEGO® Super Mario™": 0.1108,
    "Technic": 0.1211,
    "LEGO® Education": 0.100,
    "default": 0.100
}

# Les valeurs représentent le pourcentage du "prix juste"
SEUIL_TRES_BONNE_AFFAIRE = 0.70  # 30% de réduction ou plus (prix <= 70% du prix juste)
SEUIL_BONNE_AFFAIRE = 0.80      # Entre 20% et 29% de réduction (prix <= 80% du prix juste)
# Tout ce qui est au-dessus du prix juste est considéré comme une "mauvaise affaire"

WIKI_URL_PUBLIQUE = "https://github.com/Aktawind/lego-price-tracker/wiki"

def construire_slug_wiki(id_set, nom_set):
    """Construit le slug de page wiki utilisé par generer_wiki.py, pour pouvoir
    pointer directement vers la fiche d'un set (et pas juste la page d'accueil)."""
    nom_pour_url = str(nom_set).replace(':', '').replace(' ', '-')
    return f"{id_set}-{nom_pour_url}"

def construire_url_wiki_set(id_set, nom_set):
    """URL complète de la fiche wiki d'un set donné."""
    return f"{WIKI_URL_PUBLIQUE}/{construire_slug_wiki(id_set, nom_set)}"

# --- CONFIGURATION EMAIL (Brevo) ---
# Commune à tous les scripts qui envoient des emails (catch_lego_price.py, deal_hunter.py).
# Contrairement à Resend, Brevo n'offre pas d'expéditeur "bac à sable" partagé :
# il faut toujours un expéditeur vérifié (BREVO_FROM_EMAIL), pas de valeur par
# défaut possible.

def charger_config_email():
    return {
        "api_key": os.getenv("BREVO_API_KEY"),
        "expediteur": os.getenv("BREVO_FROM_EMAIL") or None,
        "destinataire": os.getenv("MAIL_DESTINATAIRE"),
    }

def email_config_complete(email_config):
    return bool(email_config.get("api_key") and email_config.get("expediteur") and email_config.get("destinataire"))

# Liste des vendeurs à récupérer sur le site Avenue de la Brique
MAP_VENDEURS = {
    "chez amazon": "Amazon",
    "chez cdiscount": "Cdiscount",
    "chez fnac": "Fnac",
    "chez e.leclerc": "Leclerc",
    "chez auchan": "Auchan",
    "chez carrefour": "Carrefour",
    "chez la grande récré": "La Grande Récré",
    "chez ltoys": "Ltoys",
    "chez lego": "Lego",
    "chez jouéclub": "JouéClub",
    "chez kidinn": "KidInn",
    "chez rue du commerce": "Rue du Commerce"
}