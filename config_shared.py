# --- ANALYSE DES PRIX ---

# Dictionnaire de connaissance des prix moyens par pièce
PRIX_MOYEN_PAR_COLLECTION = {
    "Star Wars™": 0.129, 
    "Technic": 0.126, 
    "Disney™": 0.121,
    "LEGO® Super Mario™": 0.101, 
    "Ideas": 0.094, 
    "LEGO® Icons": 0.088,
    "The Botanical Collection": 0.067, 
    "One Piece": 0.088,
    "Architecture": 0.080,
    "Art": 0.057,
    "Harry Potter™": 0.100,
    "Creator 3-en-1": 0.084,
    "Speed Champions": 0.090,
    "default": 0.100
}

# Les valeurs représentent le pourcentage du "prix juste"
SEUIL_TRES_BONNE_AFFAIRE = 0.70  # 30% de réduction ou plus (prix <= 70% du prix juste)
SEUIL_BONNE_AFFAIRE = 0.80      # Entre 20% et 29% de réduction (prix <= 80% du prix juste)
# Tout ce qui est au-dessus du prix juste est considéré comme une "mauvaise affaire"