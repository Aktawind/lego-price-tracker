import os
import time
from urllib.parse import urlparse

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

def accord_pluriel(n, suffixe='s'):
    """'s' à accoler à un mot si n > 1, sinon rien -- pour éviter les tournures
    du type 'baisse(s) de prix détectée(s)' dans les sujets d'email."""
    return suffixe if n > 1 else ''

# --- CONFIGURATION EMAIL (Brevo) ---
# Commune à tous les scripts qui envoient des emails (catch_lego_price.py, deal_hunter.py).
# Contrairement à Resend, Brevo n'offre pas d'expéditeur "bac à sable" partagé :
# il faut toujours un expéditeur vérifié (BREVO_FROM_EMAIL), pas de valeur par
# défaut possible.

def charger_config_email():
    return {
        "api_key": os.getenv("BREVO_API_KEY"),
        "expediteur": os.getenv("BREVO_FROM_EMAIL") or None,
        # Nom affiché à la place de l'adresse technique (ex: ...@12159343.brevosend.com)
        # dans la boîte de réception. BREVO_FROM_NAME est optionnel.
        "expediteur_nom": os.getenv("BREVO_FROM_NAME") or "Lego Price Tracker",
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
    "chez rue du commerce": "Rue du Commerce",
    "chez galaxus": "Galaxus",
}

# --- OUTILS PARTAGÉS POUR LE SCRAPING SELENIUM ---
# Les sites suivis (Avenue de la Brique, Amazon...) bloquent parfois une requête
# ou font planter la session Selenium de façon ponctuelle (timeout, popup
# inattendue, page qui met du temps à charger). Ces deux fonctions sont
# utilisées par avenue_scraper.py et catch_lego_price.py pour retenter une
# fois avant d'abandonner, plutôt que de perdre toute une journée de données
# sur un aléa transitoire.

def driver_est_vivant(driver):
    """Vérifie qu'une session Selenium est toujours utilisable (le driver peut
    planter en cours de route sur un runner CI, sans forcément lever d'exception
    visible côté scraper individuel)."""
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def sauvegarder_diagnostic_scraping(contenu_html, url, driver=None, prefixe="debug"):
    """Sauvegarde le HTML (et une capture d'écran si un navigateur Selenium
    est fourni) d'une page qui n'a pas donné le résultat attendu, nommé
    d'après le domaine et un horodatage. Permet de diagnostiquer un futur
    échec de scraping (CAPTCHA, page de blocage, mise en page différente...)
    sans accès direct au site depuis l'environnement de dev -- utilisé par
    scrapers/standard_scraper.py et config_generator.py."""
    domaine = (urlparse(url).netloc or "site").replace('.', '_').replace(':', '_')
    chemin_base = f"{prefixe}_{domaine}_{int(time.time())}"
    try:
        with open(f"{chemin_base}.html", 'w', encoding='utf-8') as f:
            f.write(contenu_html)
    except Exception:
        pass
    if driver is not None:
        try:
            driver.save_screenshot(f"{chemin_base}.png")
        except Exception:
            pass


def executer_avec_retries(action, max_essais=2, pause_secondes=2, on_echec=None):
    """Exécute `action` (callable sans argument) jusqu'à `max_essais` fois tant
    qu'elle lève une exception. Retourne (True, None) dès qu'un essai réussit,
    ou (False, dernière_exception) si tous les essais ont échoué. `on_echec`
    (optionnel) est appelé entre deux tentatives avec (exception, numéro de
    tentative), pour laisser l'appelant logger un avertissement intermédiaire."""
    derniere_exception = None
    for tentative in range(1, max_essais + 1):
        try:
            action()
            return True, None
        except Exception as e:
            derniere_exception = e
            if tentative < max_essais:
                if on_echec:
                    on_echec(e, tentative)
                time.sleep(pause_secondes)
    return False, derniere_exception