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
