# --- ANALYSE DES PRIX ---

# Dictionnaire de connaissance des prix moyens par pièce
PRIX_MOYEN_PAR_COLLECTION = {
    "Architecture": 0.088,
    "Art": 0.073,
    "The Botanical Collection": 0.0817,
    "Creator 3-en-1": 0.0835,
    "Disney™": 0.102,
    "Harry Potter™": 0.0941,
    "LEGO® Icons": 0.0883,
    "Ideas": 0.0940,
    "One Piece": 0.0886,
    "Speed Champions": 0.0886,
    "Star Wars™": 0.1024, 
    "LEGO® Super Mario™": 0.1108, 
    "Technic": 0.1211, 
    "default": 0.100
}

# Les valeurs représentent le pourcentage du "prix juste"
SEUIL_TRES_BONNE_AFFAIRE = 0.70  # 30% de réduction ou plus (prix <= 70% du prix juste)
SEUIL_BONNE_AFFAIRE = 0.80      # Entre 20% et 29% de réduction (prix <= 80% du prix juste)
# Tout ce qui est au-dessus du prix juste est considéré comme une "mauvaise affaire"

# Liste des vendeurs à récupérer sur le site Avenue de la Brique
MAP_VENDEURS = {
    "chez amazon": "Amazon",
    "chez cdiscount": "Cdiscount",
    "chez fnac": "Fnac",
    "chez e.leclerc": "Leclerc",
    "chez auchan": "Auchan",
    "chez carrefour": "Carrefour",
    "chez la grande récré": "La Grande Récré",
    "chez ltoys": "Ltoys",
    "chez lego": "Lego",
    "chez jouéclub": "JouéClub",
    "chez kidinn": "KidInn",
    "chez rue du commerce": "Rue du Commerce"
}