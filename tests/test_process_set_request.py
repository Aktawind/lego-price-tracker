import pandas as pd
import pytest

import process_set_request as psr
import historique_db as hdb


def test_parser_formulaire_extrait_les_champs_et_ignore_no_response():
    body = (
        "### Marque\n\nLEGO\n\n"
        "### ID_Set (référence unique)\n\n10321\n\n"
        "### Nom du set\n\n_No response_\n\n"
        "### URL Amazon\n\nhttps://www.amazon.fr/dp/XXXX\n\n"
        "### Prix d'alerte (optionnel)\n\n45\n"
    )
    champs = psr.parser_formulaire(body)
    assert champs["Marque"] == "LEGO"
    assert champs["ID_Set (référence unique)"] == "10321"
    assert champs["Nom du set"] == ""
    assert champs["URL Amazon"] == "https://www.amazon.fr/dp/XXXX"
    assert champs["Prix d'alerte (optionnel)"] == "45"


def test_parser_formulaire_corps_vide():
    assert psr.parser_formulaire("") == {}
    assert psr.parser_formulaire(None) == {}


@pytest.fixture
def config_vide(tmp_path, monkeypatch):
    fichier = tmp_path / "config_sets.xlsx"
    df = pd.DataFrame(columns=["ID_Set", "Nom_Set", "nbPieces", "Collection", "Image_URL", "Marque", "Prix_Alerte"])
    df.to_excel(fichier, index=False)
    monkeypatch.setattr(psr, "FICHIER_CONFIG_EXCEL", str(fichier))

    db = tmp_path / "prix_lego.db"
    monkeypatch.setattr(hdb, "FICHIER_DB", str(db))

    commentaires = []
    monkeypatch.setattr(psr, "commenter_issue", lambda message: commentaires.append(message))
    return fichier, commentaires


def test_traiter_ajout_set_non_lego_sans_nom_echoue(config_vide, monkeypatch):
    fichier, commentaires = config_vide
    champs = {"Marque": "Lumibricks", "ID_Set (référence unique)": "LUMI-1"}
    resultat = psr.traiter_ajout(champs)
    assert resultat is False
    assert any("obligatoire" in c for c in commentaires)


def test_traiter_ajout_set_non_lego_avec_infos_completes(config_vide, monkeypatch):
    fichier, commentaires = config_vide
    champs = {
        "Marque": "Lumibricks",
        "ID_Set (référence unique)": "LUMI-1",
        "Nom du set": "Faucon Custom",
        "Image_URL": "https://example.com/img.png",
        "URL Amazon": "https://www.amazon.fr/dp/YYYY",
        "Prix d'alerte (optionnel)": "89.90",
    }
    resultat = psr.traiter_ajout(champs)
    assert resultat is True

    df = pd.read_excel(fichier, dtype=str)
    assert "LUMI-1" in df['ID_Set'].values
    ligne = df[df['ID_Set'] == 'LUMI-1'].iloc[0]
    assert ligne['Marque'] == 'Lumibricks'
    assert ligne['Nom_Set'] == 'Faucon Custom'
    assert ligne['URL_Amazon'] == 'https://www.amazon.fr/dp/YYYY'
    assert float(ligne['Prix_Alerte']) == 89.90
    assert any("ajouté au suivi" in c for c in commentaires)


def test_traiter_ajout_lego_utilise_get_lego_metadata(config_vide, monkeypatch):
    fichier, commentaires = config_vide
    monkeypatch.setattr(psr, "get_lego_metadata", lambda set_id: {
        "nom": "Corvette", "nb_pieces": "1210", "collection": "Icons",
        "image_url": "https://lego.com/img.png", "url_lego": "https://lego.com/fr-fr/product/10321",
    })
    champs = {"Marque": "LEGO", "ID_Set (référence unique)": "10321"}
    resultat = psr.traiter_ajout(champs)
    assert resultat is True

    df = pd.read_excel(fichier, dtype=str)
    ligne = df[df['ID_Set'] == '10321'].iloc[0]
    assert ligne['Nom_Set'] == 'Corvette'
    assert ligne['Marque'] == 'LEGO'


def test_traiter_ajout_id_invalide_est_refuse(config_vide):
    fichier, commentaires = config_vide
    resultat = psr.traiter_ajout({"Marque": "LEGO", "ID_Set (référence unique)": "avec espace"})
    assert resultat is False
    assert any("invalide" in c for c in commentaires)


def test_traiter_ajout_set_deja_existant(config_vide):
    fichier, commentaires = config_vide
    df = pd.DataFrame([{"ID_Set": "10321", "Nom_Set": "Corvette"}])
    df.to_excel(fichier, index=False)

    resultat = psr.traiter_ajout({"Marque": "LEGO", "ID_Set (référence unique)": "10321"})
    assert resultat is False
    assert any("déjà suivi" in c for c in commentaires)


def test_traiter_suppression(config_vide):
    fichier, commentaires = config_vide
    df = pd.DataFrame([{"ID_Set": "10321", "Nom_Set": "Corvette"}])
    df.to_excel(fichier, index=False)
    hdb.ajouter_lignes([{'Date': '2026-01-01 10:00:00', 'ID_Set': '10321', 'Nom_Set': 'Corvette', 'Site': 'Lego', 'Prix': 1.0, 'URL': ''}])

    resultat = psr.traiter_suppression({"ID_Set à retirer": "10321"})
    assert resultat is True

    df_apres = pd.read_excel(fichier, dtype=str)
    assert "10321" not in df_apres['ID_Set'].values
    assert hdb.charger_historique(id_set='10321').empty
    assert any("retiré du suivi" in c for c in commentaires)


def test_traiter_suppression_set_inconnu(config_vide):
    fichier, commentaires = config_vide
    resultat = psr.traiter_suppression({"ID_Set à retirer": "99999"})
    assert resultat is False
    assert any("n'a pas été trouvé" in c for c in commentaires)
