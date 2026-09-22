import pandas as pd

import config_generator
from config_generator import champ_manquant, marque_est_lego, main


def test_champ_manquant():
    assert champ_manquant(None) is True
    assert champ_manquant(float('nan')) is True
    assert champ_manquant('') is True
    assert champ_manquant('   ') is True
    assert champ_manquant('N/A') is True
    assert champ_manquant('nan') is True
    assert champ_manquant('Technic') is False
    assert champ_manquant(1210) is False


def test_marque_est_lego():
    assert marque_est_lego(None) is True
    assert marque_est_lego(float('nan')) is True
    assert marque_est_lego('') is True
    assert marque_est_lego('LEGO') is True
    assert marque_est_lego('lego') is True
    assert marque_est_lego(' Lego ') is True
    assert marque_est_lego('Lumibricks') is False


def test_main_reutilise_lurl_lego_connue_pour_reparer_les_metadonnees(tmp_path, monkeypatch):
    # Certains sets (ex: gammes Pokémon) n'ont pas de fiche accessible via
    # l'URL "ID nu" (product/<id>) -- Lego.com attend le slug complet
    # (product/<nom>-<id>). Si une URL précise est déjà connue pour ce set
    # (stockée lors d'un ajout réussi), l'auto-réparation doit la réutiliser
    # plutôt que de reconstruire une URL "ID nu" qui a de bonnes chances
    # d'échouer à nouveau.
    fichier = tmp_path / "config_sets.xlsx"
    df = pd.DataFrame([{
        "ID_Set": "72151", "Nom_Set": "Évoli", "nbPieces": None,
        "Collection": None, "Image_URL": None, "Marque": "LEGO",
        "URL_Lego": "https://www.lego.com/fr-fr/product/eevee-72151",
    }])
    df.to_excel(fichier, index=False)
    monkeypatch.setattr(config_generator, "FICHIER_CONFIG_EXCEL", str(fichier))
    monkeypatch.setattr(config_generator, "mettre_a_jour_dropdowns_sets", lambda: None)

    urls_utilisees = []

    def fausse_metadata(set_id, url=None):
        urls_utilisees.append(url)
        return {"nom": "Évoli", "nb_pieces": "313", "collection": "Icons", "image_url": "https://x/img.png"}

    monkeypatch.setattr(config_generator, "get_lego_metadata", fausse_metadata)

    main()

    assert urls_utilisees == ["https://www.lego.com/fr-fr/product/eevee-72151"]


def test_main_ne_supprime_jamais_un_set_de_la_config(tmp_path, monkeypatch):
    """Régression : config_sets.xlsx (géré via les formulaires GitHub) est la
    seule source de vérité. main() ne doit plus jamais faire disparaître un
    set de la config, quoi qu'il arrive (il n'y a plus de fichier externe
    'désiré' avec lequel se resynchroniser)."""
    fichier = tmp_path / "config_sets.xlsx"
    df = pd.DataFrame([
        {
            "ID_Set": "10321", "Nom_Set": "Corvette", "nbPieces": "1210",
            "Collection": "Icons", "Image_URL": "https://lego.com/img.png",
            "Marque": "LEGO",
        },
        {
            "ID_Set": "LUMI-LUNA", "Nom_Set": "Luna Cottage", "nbPieces": "2846",
            "Collection": "Lumibricks", "Image_URL": "https://example.com/img.png",
            "Marque": "Lumibricks",
        },
    ])
    df.to_excel(fichier, index=False)
    monkeypatch.setattr(config_generator, "FICHIER_CONFIG_EXCEL", str(fichier))
    monkeypatch.setattr(config_generator, "mettre_a_jour_dropdowns_sets", lambda: None)

    main()

    df_apres = pd.read_excel(fichier, dtype=str)
    assert set(df_apres['ID_Set']) == {"10321", "LUMI-LUNA"}
