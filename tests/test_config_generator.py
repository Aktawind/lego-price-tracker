import pandas as pd

from config_generator import champ_manquant, marque_est_lego


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
