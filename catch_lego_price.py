import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import schedule
import smtplib
from email.mime.text import MIMEText
import urllib3
import json 
import os
import time # On aura besoin de time.sleep

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# On lit la configuration des sets depuis le fichier JSON
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        SETS_A_SURVEILLER = json.load(f)
except FileNotFoundError:
    print("Erreur: Le fichier 'config.json' est introuvable.")
    exit() # On arrête le script si la config est manquante

FICHIER_EXCEL = "prix_lego.xlsx"

EMAIL_ADRESSE = os.getenv('GMAIL_ADDRESS')
EMAIL_MOT_DE_PASSE = os.getenv('GMAIL_APP_PASSWORD')
EMAIL_DESTINATAIRE = os.getenv('MAIL_DESTINATAIRE')

# Vérification que les secrets sont bien chargés
if not all([EMAIL_ADRESSE, EMAIL_MOT_DE_PASSE, EMAIL_DESTINATAIRE]):
    print("Erreur: Les secrets pour l'email (GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MAIL_DESTINATAIRE) ne sont pas configurés.")
    exit()


def recuperer_prix_amazon(url, headers):
    try:
        reponse = requests.get(url, headers=headers, verify=False)
        reponse.raise_for_status()
        soup = BeautifulSoup(reponse.content, 'html.parser')
        partie_entiere_elem = soup.select_one("span.a-price-whole")
        partie_fraction_elem = soup.select_one("span.a-price-fraction")
        if partie_entiere_elem and partie_fraction_elem:
            partie_entiere_texte = partie_entiere_elem.get_text()
            partie_fraction_texte = partie_fraction_elem.get_text(strip=True)
            partie_entiere_propre = "".join(filter(str.isdigit, partie_entiere_texte))
            prix_complet_str = f"{partie_entiere_propre}.{partie_fraction_texte}"
            return float(prix_complet_str)
        return None
    except Exception as e:
        print(f"Erreur en récupérant le prix sur Amazon ({url}): {e}")
        return None
    
def recuperer_prix_amazon_selenium(url, headers):
    """VERSION FINALE++ : Gère la page intermédiaire, les cookies, attend les éléments et prend une capture d'écran en cas d'échec."""
    print("  -> Utilisation de la méthode Selenium pour Amazon...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={headers['User-Agent']}")
    chrome_options.add_argument(f"accept-language={headers['Accept-Language']}")
    
    driver = webdriver.Chrome(options=chrome_options)

    # On définit un temps d'attente maximum pour toutes les recherches
    wait = WebDriverWait(driver, 5) # Attend jusqu'à 5 secondes
    
    try:
        driver.get(url)

         # 1. Gérer la page 'Continuer' (avec recherche dans les iFrames)
        try:
            # On essaie d'abord dans la page principale
            continuer_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@value="Continuer les achats"]')))
            print("  -> Page intermédiaire 'Continuer' détectée dans la page principale. Clic...")
            continuer_button.click()
        except Exception:
            # Si ça échoue, on cherche dans les iFrames
            print("  -> Bouton 'Continuer' non trouvé en principal. Recherche dans les iframes...")
            try:
                # On attend qu'au moins une iframe soit présente
                wait.until(EC.presence_of_element_located((By.TAG_NAME, 'iframe')))
                iframes = driver.find_elements(By.TAG_NAME, 'iframe')
                print(f"  -> {len(iframes)} iframe(s) trouvé(es).")
                
                button_found = False
                for frame in iframes:
                    try:
                        driver.switch_to.frame(frame) # On entre dans l'iframe
                        continuer_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@value="Continuer les achats"]')))
                        print("  -> Bouton 'Continuer' trouvé dans un iframe ! Clic...")
                        continuer_button.click()
                        button_found = True
                        break # On a trouvé le bouton, on sort de la boucle
                    except Exception:
                        continue # Pas dans cet iframe, on passe au suivant
                    finally:
                        driver.switch_to.default_content() # TRÈS IMPORTANT: on revient à la page principale
                
                if not button_found:
                    print("  -> Bouton 'Continuer' non trouvé dans aucun iframe.")
            
            except Exception as e:
                print(f"  -> Aucune iframe trouvée ou erreur lors de la recherche: {e}")

        # 2. Gérer la bannière de cookies AVEC UN WAIT
        try:
            bouton_cookies = wait.until(
                EC.element_to_be_clickable((By.ID, "sp-cc-accept"))
            )
            print("  -> Bannière de cookies trouvée. Clic sur 'Accepter'.")
            bouton_cookies.click()
            wait.until(EC.invisibility_of_element(bouton_cookies))
        except Exception:
            print("  -> Pas de bannière de cookies visible dans le temps imparti.")

        # 3. Attendre l'élément final du prix
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span.a-price-whole")))
        
        # Le reste est inchangé
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        partie_entiere_elem = soup.select_one("span.a-price-whole")
        partie_fraction_elem = soup.select_one("span.a-price-fraction")
        
        if partie_entiere_elem and partie_fraction_elem:
            partie_entiere_texte = partie_entiere_elem.get_text()
            partie_fraction_texte = partie_fraction_elem.get_text(strip=True)
            partie_entiere_propre = "".join(filter(str.isdigit, partie_entiere_texte))
            prix_complet_str = f"{partie_entiere_propre}.{partie_fraction_texte}"
            return float(prix_complet_str)
        return None

    except Exception as e:
        print(f"Erreur finale avec Selenium pour Amazon ({url}): {e}")
        print("  -> Prise d'une capture d'écran pour le débogage : amazon_debug_screenshot.png")
        driver.save_screenshot("amazon_debug_screenshot.png")
        
        # === DUMP HTML COMPLET POUR ANALYSE ULTIME ===
        print("\n--- DEBUT DU CODE HTML DE LA PAGE EN ERREUR ---\n")
        print(driver.page_source)
        print("\n--- FIN DU CODE HTML DE LA PAGE EN ERREUR ---\n")
        
        return None
    finally:
        driver.quit()

def recuperer_prix_standard(url, selecteur, headers):
    try:
        reponse = requests.get(url, headers=headers, verify=False)
        reponse.raise_for_status()
        soup = BeautifulSoup(reponse.content, 'html.parser')
        element_prix = soup.select_one(selecteur)
        if element_prix:
            prix_texte = element_prix.get_text()
            prix_nettoye = prix_texte.replace('\u202f', '').replace('\xa0', '').replace(' ', '').replace('€', '').replace(',', '.').strip()
            return float(prix_nettoye)
        return None
    except Exception as e:
        print(f"Erreur en récupérant le prix pour {url}: {e}")
        return None

def envoyer_email_alerte(nom_set, nouveau_prix, site, url):
    # (code inchangé)
    sujet = f"Alerte Baisse de Prix LEGO : {nom_set}"
    corps = f"Le prix du set LEGO '{nom_set}' a baissé sur {site} !\n\nNouveau prix : {nouveau_prix}€\n\nLien : {url}"
    msg = MIMEText(corps)
    msg['Subject'] = sujet
    msg['From'] = EMAIL_ADRESSE
    msg['To'] = EMAIL_DESTINATAIRE
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
           smtp_server.login(EMAIL_ADRESSE, EMAIL_MOT_DE_PASSE)
           smtp_server.sendmail(EMAIL_ADRESSE, EMAIL_DESTINATAIRE, msg.as_string())
        print(f"Email d'alerte envoyé pour {nom_set} !")
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")

def verifier_les_prix():
    # (code inchangé)
    print(f"\nLancement de la vérification des prix - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        df = pd.read_excel(FICHIER_EXCEL, dtype={'ID_Set': str})
    except FileNotFoundError:
        print("Fichier Excel non trouvé. Création d'un nouveau fichier.")
        df = pd.DataFrame({'Date': pd.Series(dtype='str'),'ID_Set': pd.Series(dtype='str'),'Nom_Set': pd.Series(dtype='str'),'Site': pd.Series(dtype='str'),'Prix': pd.Series(dtype='float')})

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'fr-FR,fr;q=0.9' # <-- LA LIGNE CLÉ !
    }

    lignes_a_ajouter = []
    for set_id, set_info in SETS_A_SURVEILLER.items():
        nom_set = set_info['nom']
        for site, site_info in set_info['sites'].items():
            print(f"Vérification de '{nom_set}' sur {site}...")
            prix_actuel = None
            if site_info['type'] == 'amazon':
                prix_actuel = recuperer_prix_amazon(site_info['url'], headers)
            elif site_info['type'] == 'amazon_selenium':
                prix_actuel = recuperer_prix_amazon_selenium(site_info['url'], headers)
            elif site_info['type'] == 'standard':
                prix_actuel = recuperer_prix_standard(site_info['url'], site_info['selecteur'], headers)
            if prix_actuel is None:
                print(f"  -> Prix non trouvé.")
                continue
            print(f"  -> Prix actuel : {prix_actuel}€")
            df_filtre = df[(df['ID_Set'] == str(set_id)) & (df['Site'] == site)]
            prix_precedent = df_filtre['Prix'].iloc[-1] if not df_filtre.empty else None
            if prix_precedent is None or abs(prix_actuel - prix_precedent) > 0.01:
                print(f"  -> Changement de prix détecté (précédent : {prix_precedent}€). Enregistrement...")
                nouvelle_ligne = {'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'ID_Set': str(set_id), 'Nom_Set': nom_set, 'Site': site, 'Prix': prix_actuel}
                lignes_a_ajouter.append(nouvelle_ligne)
                if prix_precedent is not None and prix_actuel < prix_precedent:
                    print("  -> BAISSE DE PRIX ! Envoi de l'alerte...")
                    envoyer_email_alerte(nom_set, prix_actuel, site, site_info['url'])
            else:
                print("  -> Pas de changement de prix.")
            time.sleep(5)
    if lignes_a_ajouter:
        nouvelles_lignes_df = pd.DataFrame(lignes_a_ajouter)
        df = pd.concat([df, nouvelles_lignes_df], ignore_index=True)
        df.to_excel(FICHIER_EXCEL, index=False)
        print("Modifications enregistrées dans le fichier Excel.")

# Ce bloc garantit que la fonction principale est appelée
# uniquement lorsque le script est exécuté directement.
if __name__ == "__main__":
    verifier_les_prix()