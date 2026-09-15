# Fichier : process_set_request.py
# Traite les issues GitHub créées via les formulaires "Ajouter un set" /
# "Retirer un set" (voir .github/ISSUE_TEMPLATE/) : met à jour config_sets.xlsx
# (et prix_lego.xlsx pour une suppression), commit + push, puis commente et
# ferme l'issue pour informer l'utilisateur du résultat.
import os
import re
import logging
import subprocess

import pandas as pd
import requests

from config_generator import get_lego_metadata, FICHIER_CONFIG_EXCEL, FICHIER_HISTORIQUE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")  # "owner/repo"
ISSUE_NUMBER = os.getenv("ISSUE_NUMBER")
ISSUE_BODY = os.getenv("ISSUE_BODY", "")
ISSUE_LABELS = os.getenv("ISSUE_LABELS", "")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

URLS_PAR_CHAMP = {
    "URL Lego.com": "URL_Lego",
    "URL Amazon": "URL_Amazon",
    "URL Auchan": "URL_Auchan",
    "URL Leclerc": "URL_Leclerc",
    "URL Carrefour": "URL_Carrefour",
    "URL Avenue de la Brique": "URL_AvenueDeLaBrique",
}


def parser_formulaire(body):
    """Transforme le corps Markdown d'un GitHub Issue Form en dict {label: valeur}."""
    champs = {}
    sections = re.split(r"^### +", body or "", flags=re.MULTILINE)[1:]
    for section in sections:
        lignes = section.strip().splitlines()
        if not lignes:
            continue
        label = lignes[0].strip()
        valeur = "\n".join(lignes[1:]).strip()
        if valeur.lower() in ("_no response_", ""):
            valeur = ""
        champs[label] = valeur
    return champs


def commenter_issue(message):
    if not (GITHUB_TOKEN and GITHUB_REPOSITORY and ISSUE_NUMBER):
        logging.error("Contexte GitHub incomplet, impossible de commenter l'issue.")
        return
    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/{ISSUE_NUMBER}/comments"
    reponse = requests.post(url, headers=HEADERS, json={"body": message}, timeout=15)
    if not reponse.ok:
        logging.error(f"Échec de la publication du commentaire : {reponse.status_code} {reponse.text}")


def fermer_issue():
    if not (GITHUB_TOKEN and GITHUB_REPOSITORY and ISSUE_NUMBER):
        return
    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/{ISSUE_NUMBER}"
    requests.patch(url, headers=HEADERS, json={"state": "closed"}, timeout=15)


def charger_config():
    try:
        return pd.read_excel(FICHIER_CONFIG_EXCEL, dtype=str)
    except FileNotFoundError:
        return pd.DataFrame(columns=["ID_Set"])


def traiter_ajout(champs):
    df_config = charger_config()
    for col in ("Marque", "Prix_Alerte"):
        if col not in df_config.columns:
            df_config[col] = None

    id_set = (champs.get("ID_Set (référence unique)") or "").strip()
    if not id_set or not re.fullmatch(r"[A-Za-z0-9_-]+", id_set):
        commenter_issue(
            "❌ `ID_Set` manquant ou invalide (uniquement lettres, chiffres, `-` et `_`). "
            "Modifie le formulaire et rouvre une demande."
        )
        return False

    if 'ID_Set' in df_config.columns and id_set in df_config['ID_Set'].astype(str).values:
        commenter_issue(f"⚠️ Le set `{id_set}` est déjà suivi, aucune action effectuée.")
        return False

    marque = (champs.get("Marque") or "LEGO").strip() or "LEGO"
    est_lego = marque.strip().upper() == "LEGO"

    if not est_lego:
        nom_set = champs.get("Nom du set")
        image_url = champs.get("Image_URL")
        if not nom_set:
            commenter_issue(
                f"❌ Pour une marque autre que LEGO (`{marque}`), le champ **Nom du set** est obligatoire "
                "(pas de fiche Lego.com à scraper automatiquement)."
            )
            return False
        nom_marque_affiche = "Autre" if marque.startswith("Autre") else marque
        nouvelle_ligne = {
            "ID_Set": id_set,
            "Nom_Set": nom_set,
            "nbPieces": champs.get("Nombre de pièces") or None,
            "Collection": nom_marque_affiche,
            "Image_URL": image_url or '',
            "Marque": nom_marque_affiche,
        }
    else:
        metadata = get_lego_metadata(id_set)
        if not metadata:
            commenter_issue(
                f"❌ Impossible de récupérer les informations du set LEGO `{id_set}` sur Lego.com "
                "(référence invalide, ou site temporairement bloquant). Tu peux réessayer plus tard, "
                "ou ajouter le set manuellement en renseignant Nom/Image dans le formulaire."
            )
            return False
        nouvelle_ligne = {
            "ID_Set": id_set,
            "Nom_Set": metadata['nom'],
            "nbPieces": metadata['nb_pieces'],
            "Collection": metadata['collection'],
            "Image_URL": metadata['image_url'],
            "URL_Lego": metadata['url_lego'],
            "Marque": "LEGO",
        }

    for champ, colonne in URLS_PAR_CHAMP.items():
        valeur = champs.get(champ)
        if valeur:
            nouvelle_ligne[colonne] = valeur.strip()

    prix_alerte = champs.get("Prix d'alerte (optionnel)")
    if prix_alerte:
        try:
            nouvelle_ligne["Prix_Alerte"] = float(prix_alerte.replace(',', '.'))
        except ValueError:
            logging.warning(f"Prix d'alerte invalide ignoré : '{prix_alerte}'")

    df_config = pd.concat([df_config, pd.DataFrame([nouvelle_ligne])], ignore_index=True)
    df_config = df_config.sort_values('ID_Set').reset_index(drop=True)
    df_config.to_excel(FICHIER_CONFIG_EXCEL, index=False)

    resume = "\n".join(f"- **{k}** : {v}" for k, v in nouvelle_ligne.items() if v)
    commenter_issue(
        f"✅ Set `{id_set}` ajouté au suivi !\n\n{resume}\n\n"
        f"Il apparaîtra dans le prochain rapport quotidien et sur le [wiki](https://github.com/{GITHUB_REPOSITORY}/wiki)."
    )
    return True


def traiter_suppression(champs):
    df_config = charger_config()
    id_set = (champs.get("ID_Set à retirer") or "").strip()

    if 'ID_Set' not in df_config.columns or id_set not in df_config['ID_Set'].astype(str).values:
        commenter_issue(f"⚠️ Le set `{id_set}` n'a pas été trouvé dans le suivi, aucune action effectuée.")
        return False

    df_config = df_config[df_config['ID_Set'].astype(str) != id_set]
    df_config.to_excel(FICHIER_CONFIG_EXCEL, index=False)

    try:
        df_historique = pd.read_excel(FICHIER_HISTORIQUE, dtype=str)
        df_historique = df_historique[df_historique['ID_Set'].astype(str) != id_set]
        df_historique.to_excel(FICHIER_HISTORIQUE, index=False)
    except FileNotFoundError:
        pass

    commenter_issue(f"🗑️ Set `{id_set}` retiré du suivi (configuration et historique nettoyés).")
    return True


def commiter_et_pousser():
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=False)
    subprocess.run(["git", "add", FICHIER_CONFIG_EXCEL, FICHIER_HISTORIQUE], check=False)

    resultat = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if resultat.returncode != 0:
        subprocess.run(["git", "commit", "-m", f"Traitement de la demande #{ISSUE_NUMBER}"], check=True)
        subprocess.run(["git", "push"], check=True)
        logging.info("Changements commités et poussés.")
    else:
        logging.info("Rien à committer.")


def main():
    if not ISSUE_BODY:
        logging.error("Corps de l'issue vide, abandon.")
        return

    champs = parser_formulaire(ISSUE_BODY)
    labels = [l.strip() for l in ISSUE_LABELS.split(',') if l.strip()]

    if 'ajout-set' in labels:
        succes = traiter_ajout(champs)
    elif 'suppression-set' in labels:
        succes = traiter_suppression(champs)
    else:
        logging.info("Issue sans label reconnu (ajout-set/suppression-set), rien à faire.")
        return

    if succes:
        commiter_et_pousser()
        fermer_issue()


if __name__ == "__main__":
    main()
