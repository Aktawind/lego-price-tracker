# Fichier : historique_db.py
# Stockage de l'historique des prix en SQLite plutôt qu'en xlsx.
# Avant, le script rechargeait tout l'historique en mémoire puis réécrivait le
# fichier Excel en entier à chaque run (~9600 lignes et ça grossit chaque jour).
# Ici on se contente d'ajouter les nouvelles lignes (INSERT), sans jamais
# réécrire ce qui existe déjà.
import logging
import sqlite3
from contextlib import contextmanager

import pandas as pd

FICHIER_DB = "prix_lego.db"

COLONNES = ['Date', 'ID_Set', 'Nom_Set', 'Site', 'Prix', 'URL']

SCHEMA = """
CREATE TABLE IF NOT EXISTS prix (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    id_set TEXT NOT NULL,
    nom_set TEXT,
    site TEXT NOT NULL,
    prix REAL NOT NULL,
    url TEXT
);
CREATE INDEX IF NOT EXISTS idx_prix_id_set ON prix (id_set);
CREATE INDEX IF NOT EXISTS idx_prix_date ON prix (date);
"""


@contextmanager
def connexion(fichier_db=None):
    conn = sqlite3.connect(fichier_db or FICHIER_DB)
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def charger_historique(id_set=None, fichier_db=None):
    """Retourne l'historique des prix en DataFrame pandas, avec les mêmes noms
    de colonnes que l'ancien prix_lego.xlsx (Date, ID_Set, Nom_Set, Site, Prix, URL)."""
    requete = (
        "SELECT date AS Date, id_set AS ID_Set, nom_set AS Nom_Set, "
        "site AS Site, prix AS Prix, url AS URL FROM prix"
    )
    with connexion(fichier_db) as conn:
        if id_set is not None:
            df = pd.read_sql_query(requete + " WHERE id_set = ? ORDER BY date", conn, params=(str(id_set),))
        else:
            df = pd.read_sql_query(requete + " ORDER BY date", conn)

    if df.empty:
        return pd.DataFrame(columns=COLONNES)
    df['ID_Set'] = df['ID_Set'].astype(str)
    return df


def ajouter_lignes(lignes, fichier_db=None):
    """Ajoute de nouvelles lignes de prix (liste de dicts avec les clés Date,
    ID_Set, Nom_Set, Site, Prix, URL) SANS jamais réécrire l'historique existant."""
    if not lignes:
        return
    with connexion(fichier_db) as conn:
        conn.executemany(
            "INSERT INTO prix (date, id_set, nom_set, site, prix, url) "
            "VALUES (:Date, :ID_Set, :Nom_Set, :Site, :Prix, :URL)",
            lignes,
        )
    logging.info(f"{len(lignes)} nouvelle(s) ligne(s) de prix ajoutée(s) à {fichier_db or FICHIER_DB}.")


def supprimer_set(id_set, fichier_db=None):
    """Supprime tout l'historique d'un set (set acheté / retiré du suivi). Retourne
    le nombre de lignes supprimées."""
    with connexion(fichier_db) as conn:
        curseur = conn.execute("DELETE FROM prix WHERE id_set = ?", (str(id_set),))
        return curseur.rowcount


def supprimer_sets(ids_set, fichier_db=None):
    """Variante bulk de supprimer_set pour une liste/un set d'ID_Set."""
    ids_set = list(ids_set)
    if not ids_set:
        return 0
    with connexion(fichier_db) as conn:
        curseur = conn.executemany(
            "DELETE FROM prix WHERE id_set = ?", [(str(i),) for i in ids_set]
        )
        return curseur.rowcount
