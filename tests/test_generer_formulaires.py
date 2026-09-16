import pandas as pd
import yaml

import generer_formulaires as gf


def test_construire_options_formate_id_tiret_nom():
    df = pd.DataFrame([
        {"ID_Set": "10321", "Nom_Set": "Corvette"},
        {"ID_Set": "LUMI-LUNA", "Nom_Set": "Luna Cottage"},
    ])
    options = gf.construire_options(df)
    assert options == ["10321 — Corvette", "LUMI-LUNA — Luna Cottage"]


def test_construire_options_trie_par_id():
    df = pd.DataFrame([
        {"ID_Set": "80121", "Nom_Set": "Auberge"},
        {"ID_Set": "10300", "Nom_Set": "DeLorean"},
    ])
    options = gf.construire_options(df)
    assert options == ["10300 — DeLorean", "80121 — Auberge"]


def test_construire_options_sans_nom_utilise_seulement_id():
    df = pd.DataFrame([{"ID_Set": "10321", "Nom_Set": None}])
    assert gf.construire_options(df) == ["10321"]


def test_construire_options_config_vide_renvoie_valeur_de_repli():
    df = pd.DataFrame(columns=["ID_Set", "Nom_Set"])
    assert gf.construire_options(df) == ["(aucun set suivi actuellement)"]


def test_extraire_id_set_depuis_option_formatee():
    assert gf.extraire_id_set("10321 — Corvette") == "10321"
    assert gf.extraire_id_set("LUMI-LUNA — Luna Cottage") == "LUMI-LUNA"


def test_extraire_id_set_depuis_id_seul():
    assert gf.extraire_id_set("10321") == "10321"


def test_extraire_id_set_valeur_vide():
    assert gf.extraire_id_set("") == ""
    assert gf.extraire_id_set(None) == ""


def _ecrire_formulaire(chemin, label, options=None, type_champ='input'):
    donnees = {
        "name": "Test",
        "body": [
            {
                "type": type_champ,
                "id": "id_set",
                "attributes": {
                    "label": label,
                    **({"options": options} if options is not None else {"placeholder": "ex: 10321"}),
                },
            }
        ],
    }
    with open(chemin, 'w', encoding='utf-8') as f:
        yaml.dump(donnees, f, allow_unicode=True, sort_keys=False)


def test_mettre_a_jour_dropdowns_sets_regenere_les_options(tmp_path, monkeypatch):
    fichier_config = tmp_path / "config_sets.xlsx"
    df = pd.DataFrame([{"ID_Set": "10321", "Nom_Set": "Corvette"}])
    df.to_excel(fichier_config, index=False)

    formulaire_1 = tmp_path / "modifier-set.yml"
    formulaire_2 = tmp_path / "supprimer-set.yml"
    _ecrire_formulaire(formulaire_1, "Set à modifier")
    _ecrire_formulaire(formulaire_2, "Set à retirer")
    monkeypatch.setattr(gf, "FORMULAIRES", [
        (str(formulaire_1), "Set à modifier"),
        (str(formulaire_2), "Set à retirer"),
    ])

    modifie = gf.mettre_a_jour_dropdowns_sets(str(fichier_config))
    assert modifie is True

    with open(formulaire_1, 'r', encoding='utf-8') as f:
        donnees = yaml.safe_load(f)
    champ = donnees['body'][0]
    assert champ['type'] == 'dropdown'
    assert champ['attributes']['label'] == "Set à modifier"
    assert champ['attributes']['options'] == ["10321 — Corvette"]
    assert 'placeholder' not in champ['attributes']


def test_mettre_a_jour_dropdowns_sets_idempotent_si_rien_ne_change(tmp_path, monkeypatch):
    fichier_config = tmp_path / "config_sets.xlsx"
    df = pd.DataFrame([{"ID_Set": "10321", "Nom_Set": "Corvette"}])
    df.to_excel(fichier_config, index=False)

    formulaire_1 = tmp_path / "modifier-set.yml"
    _ecrire_formulaire(formulaire_1, "Set à modifier", options=["10321 — Corvette"], type_champ='dropdown')
    monkeypatch.setattr(gf, "FORMULAIRES", [(str(formulaire_1), "Set à modifier")])

    modifie = gf.mettre_a_jour_dropdowns_sets(str(fichier_config))
    assert modifie is False


def test_mettre_a_jour_dropdowns_sets_config_introuvable(tmp_path, monkeypatch):
    monkeypatch.setattr(gf, "FORMULAIRES", [])
    modifie = gf.mettre_a_jour_dropdowns_sets(str(tmp_path / "inexistant.xlsx"))
    assert modifie is False
