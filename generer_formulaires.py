# Fichier : generer_formulaires.py
# Tient à jour les menus déroulants "quel set ?" des formulaires GitHub
# Modifier/Retirer, pour ne plus jamais avoir à taper un ID_Set à la main (et
# risquer une coquille comme "LUMI_LUNA" au lieu de "LUMI-LUNA").
import logging

import pandas as pd
import yaml

FICHIER_CONFIG_EXCEL = "config_sets.xlsx"
SEPARATEUR = " — "

FORMULAIRES = [
    (".github/ISSUE_TEMPLATE/modifier-set.yml", "Set à modifier"),
    (".github/ISSUE_TEMPLATE/supprimer-set.yml", "Set à retirer"),
]


def construire_options(df_config):
    """Une entrée de menu déroulant par set suivi, triée par ID, au format
    'ID — Nom' pour rester lisible humainement tout en gardant l'ID exact."""
    options = []
    for _, row in df_config.sort_values('ID_Set').iterrows():
        id_set = str(row['ID_Set']).strip()
        nom_brut = row.get('Nom_Set')
        nom = '' if pd.isna(nom_brut) else str(nom_brut).strip()
        options.append(f"{id_set}{SEPARATEUR}{nom}" if nom else id_set)
    return options or ["(aucun set suivi actuellement)"]


def extraire_id_set(valeur_choisie):
    """Retrouve l'ID_Set exact à partir de la valeur choisie dans le menu
    déroulant ('ID — Nom' -> 'ID')."""
    return (valeur_choisie or "").split(SEPARATEUR, 1)[0].strip()


def mettre_a_jour_dropdowns_sets(fichier_config=FICHIER_CONFIG_EXCEL):
    """Régénère le menu déroulant du champ 'id_set' dans les formulaires
    Modifier/Retirer, à partir du contenu actuel de config_sets.xlsx.
    Retourne True si au moins un fichier a été modifié."""
    try:
        df_config = pd.read_excel(fichier_config, dtype=str)
    except FileNotFoundError:
        logging.warning(f"'{fichier_config}' introuvable, menus déroulants non mis à jour.")
        return False

    options = construire_options(df_config)
    modifie = False

    for chemin, label in FORMULAIRES:
        try:
            with open(chemin, 'r', encoding='utf-8') as f:
                donnees = yaml.safe_load(f)
        except FileNotFoundError:
            logging.warning(f"'{chemin}' introuvable, ignoré.")
            continue

        champ_trouve = False
        modifie_ce_fichier = False
        for champ in donnees.get('body', []):
            if champ.get('id') == 'id_set':
                champ_trouve = True
                if champ.get('type') != 'dropdown' or champ['attributes'].get('options') != options:
                    champ['type'] = 'dropdown'
                    champ['attributes']['label'] = label
                    champ['attributes'].pop('placeholder', None)
                    champ['attributes']['options'] = options
                    modifie_ce_fichier = True
                break

        if not champ_trouve:
            logging.warning(f"Champ 'id_set' non trouvé dans '{chemin}', ignoré.")
            continue

        if modifie_ce_fichier:
            with open(chemin, 'w', encoding='utf-8') as f:
                yaml.dump(donnees, f, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
            modifie = True

    if modifie:
        logging.info(f"Menus déroulants des formulaires mis à jour ({len(options)} set(s)).")
    return modifie


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    mettre_a_jour_dropdowns_sets()
