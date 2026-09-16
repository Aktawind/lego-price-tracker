import historique_db as hdb


def test_charger_historique_vide_retourne_les_bonnes_colonnes(tmp_path):
    db = str(tmp_path / "test.db")
    df = hdb.charger_historique(fichier_db=db)
    assert list(df.columns) == hdb.COLONNES
    assert df.empty


def test_ajouter_puis_charger(tmp_path):
    db = str(tmp_path / "test.db")
    lignes = [
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '10321', 'Nom_Set': 'Corvette', 'Site': 'Lego', 'Prix': 249.99, 'URL': 'https://lego.com/x'},
        {'Date': '2026-01-02 10:00:00', 'ID_Set': '10321', 'Nom_Set': 'Corvette', 'Site': 'Amazon', 'Prix': 239.99, 'URL': 'https://amazon.fr/x'},
    ]
    hdb.ajouter_lignes(lignes, fichier_db=db)

    df = hdb.charger_historique(fichier_db=db)
    assert len(df) == 2
    assert df['ID_Set'].tolist() == ['10321', '10321']

    # Ajouter n'écrase jamais ce qui existe déjà
    hdb.ajouter_lignes([lignes[0]], fichier_db=db)
    assert len(hdb.charger_historique(fichier_db=db)) == 3


def test_charger_historique_filtre_par_set(tmp_path):
    db = str(tmp_path / "test.db")
    hdb.ajouter_lignes([
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '10321', 'Nom_Set': 'Corvette', 'Site': 'Lego', 'Prix': 249.99, 'URL': ''},
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '99999', 'Nom_Set': 'Autre Set', 'Site': 'Lego', 'Prix': 49.99, 'URL': ''},
    ], fichier_db=db)

    df = hdb.charger_historique(id_set='10321', fichier_db=db)
    assert len(df) == 1
    assert df.iloc[0]['ID_Set'] == '10321'


def test_supprimer_set(tmp_path):
    db = str(tmp_path / "test.db")
    hdb.ajouter_lignes([
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '10321', 'Nom_Set': 'Corvette', 'Site': 'Lego', 'Prix': 249.99, 'URL': ''},
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '99999', 'Nom_Set': 'Autre Set', 'Site': 'Lego', 'Prix': 49.99, 'URL': ''},
    ], fichier_db=db)

    nb_supprimees = hdb.supprimer_set('10321', fichier_db=db)
    assert nb_supprimees == 1

    df = hdb.charger_historique(fichier_db=db)
    assert len(df) == 1
    assert df.iloc[0]['ID_Set'] == '99999'


def test_supprimer_sets_bulk(tmp_path):
    db = str(tmp_path / "test.db")
    hdb.ajouter_lignes([
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '1', 'Nom_Set': 'A', 'Site': 'Lego', 'Prix': 1.0, 'URL': ''},
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '2', 'Nom_Set': 'B', 'Site': 'Lego', 'Prix': 2.0, 'URL': ''},
        {'Date': '2026-01-01 10:00:00', 'ID_Set': '3', 'Nom_Set': 'C', 'Site': 'Lego', 'Prix': 3.0, 'URL': ''},
    ], fichier_db=db)

    hdb.supprimer_sets(['1', '2'], fichier_db=db)
    df = hdb.charger_historique(fichier_db=db)
    assert df['ID_Set'].tolist() == ['3']
