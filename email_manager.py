# Fichier : email_manager.py
import logging

import envoi_email
from config_shared import accord_pluriel

COULEUR_RECORD = "#d9534f"
COULEUR_BONNE_AFFAIRE = "#28a745"
COULEUR_NEUTRE = "#007bff"


def _pourcentage_baisse(prix_precedent, nouveau_prix):
    if not prix_precedent:
        return None
    return round((1 - (nouveau_prix / prix_precedent)) * 100)


def _badge_affaire(deal):
    """Construit la liste des petits badges à afficher pour ce deal (record, bonne affaire...)."""
    badges = []
    if deal.get('est_record_absolu'):
        badges.append(("🏆 JAMAIS AUSSI BAS", COULEUR_RECORD))
    elif deal.get('est_record_6_mois'):
        badges.append(("📉 PLUS BAS DEPUIS 6 MOIS", COULEUR_RECORD))

    analyse_affaire = deal.get('analyse_affaire')
    if analyse_affaire == "tres_bonne":
        badges.append(("🔥 TRÈS BONNE AFFAIRE", "#e67e22"))
    elif analyse_affaire == "bonne":
        badges.append(("✅ BONNE AFFAIRE", COULEUR_BONNE_AFFAIRE))
    return badges


def envoyer_email_recapitulatif(baisses_de_prix, email_config):
    """
    Prend une liste de baisses de prix et les détails de configuration email,
    et envoie un seul email de résumé, avec image, badges de record de prix,
    et lien direct vers la fiche du set sur le wiki.
    """

    nombre_baisses = len(baisses_de_prix)
    nombre_records = sum(1 for d in baisses_de_prix if d.get('est_record_absolu'))
    if nombre_records:
        s_record = accord_pluriel(nombre_records)
        s_baisse = accord_pluriel(nombre_baisses)
        sujet = f"🏆 {nombre_records} prix jamais vu{s_record} ! ({nombre_baisses} baisse{s_baisse} au total)"
    else:
        s_baisse = accord_pluriel(nombre_baisses)
        sujet = f"Alerte Prix LEGO : {nombre_baisses} baisse{s_baisse} de prix détectée{s_baisse} !"

    # Version texte (clients mail sans HTML, ou aperçu rapide)
    text_body = "Bonjour,\n\nVoici les baisses de prix détectées aujourd'hui :\n\n"

    # Version HTML : cartes avec image, badges et lien direct vers la fiche du set
    html_body = """
    <html><body style="font-family: Arial, Helvetica, sans-serif; background-color:#f4f4f7; margin:0; padding:20px;">
    <div style="max-width:640px; margin:0 auto;">
    <h2 style="color:#222;">Baisses de prix détectées</h2>
    """

    # Les deals avec le prix jamais vu le plus intéressant en premier
    baisses_triees = sorted(
        baisses_de_prix,
        key=lambda d: (not d.get('est_record_absolu'), not d.get('est_record_6_mois'))
    )

    for deal in baisses_triees:
        nouveau_prix = deal['nouveau_prix']
        prix_precedent = deal['prix_precedent']
        pourcentage = _pourcentage_baisse(prix_precedent, nouveau_prix)
        badges = _badge_affaire(deal)
        contexte_record = deal.get('contexte_record')
        nb_pieces = deal.get('nb_pieces')
        url_wiki = deal.get('url_wiki', '#')
        image_url = deal.get('image_url')

        prix_par_piece_txt = f" ({nouveau_prix / nb_pieces:.3f}€/pièce)" if nb_pieces else ""
        baisse_txt = f" (-{pourcentage}%)" if pourcentage else ""

        # --- Version texte ---
        text_body += (
            f"--------------------\n"
            f"Set: {deal['nom_set']}\n"
            f"Site: {deal['site']}\n"
            f"Ancien Meilleur Prix: {prix_precedent:.2f}€\n"
            f"NOUVEAU MEILLEUR PRIX: {nouveau_prix:.2f}€{baisse_txt}{prix_par_piece_txt}\n"
        )
        if contexte_record:
            text_body += f"{contexte_record}\n"
        text_body += f"Lien: {deal['url']}\n"
        text_body += f"Fiche détaillée : {url_wiki}\n"

        # --- Version HTML ---
        badges_html = "".join(
            f'<span style="display:inline-block; background:{couleur}; color:#fff; font-size:11px; '
            f'font-weight:bold; padding:3px 8px; border-radius:12px; margin:0 4px 4px 0;">{texte}</span>'
            for texte, couleur in badges
        )
        image_html = (
            f'<img src="{image_url}" alt="{deal["nom_set"]}" width="110" '
            f'style="border-radius:6px; display:block;">'
            if image_url else
            '<div style="width:110px; height:110px; background:#eee; border-radius:6px;"></div>'
        )

        html_body += f"""
        <div style="background:#fff; border-radius:8px; padding:16px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <table role="presentation" width="100%" style="border-collapse:collapse;">
                <tr>
                    <td width="120" style="vertical-align:top;">{image_html}</td>
                    <td style="vertical-align:top; padding-left:14px;">
                        <h3 style="margin:0 0 6px 0; font-size:16px;">
                            <a href="{url_wiki}" style="color:#222; text-decoration:none;">{deal['nom_set']}</a>
                        </h3>
                        <div style="margin-bottom:8px;">{badges_html}</div>
                        <p style="margin:0 0 8px 0; color:#555; font-size:13px;">
                            Vendeur : <b>{deal['site']}</b><br>
                            Ancien meilleur prix : <span style="text-decoration:line-through; color:#999;">{prix_precedent:.2f}€</span><br>
                            <span style="color:{COULEUR_BONNE_AFFAIRE}; font-size:1.3em; font-weight:bold;">{nouveau_prix:.2f}€</span>
                            <span style="color:{COULEUR_BONNE_AFFAIRE}; font-weight:bold;">{baisse_txt}</span>
                            <span style="color:#999;">{prix_par_piece_txt}</span>
                        </p>
                        {f'<p style="margin:0 0 10px 0; font-weight:bold; color:{COULEUR_RECORD};">{contexte_record}</p>' if contexte_record else ''}
                        <a href="{deal['url']}" style="display:inline-block; background-color:{COULEUR_NEUTRE}; color:#fff; padding:8px 14px; text-decoration:none; border-radius:5px; font-size:13px; margin-right:8px;">Voir l'offre</a>
                        <a href="{url_wiki}" style="display:inline-block; color:{COULEUR_NEUTRE}; padding:8px 4px; text-decoration:none; font-size:13px;">Historique complet &rarr;</a>
                    </td>
                </tr>
            </table>
        </div>
        """

    lien_wiki = "https://github.com/Aktawind/lego-price-tracker/wiki"
    text_body += f"\n\nPour une analyse détaillée, consultez votre tableau de bord : {lien_wiki}"
    html_body += f'<p style="text-align:center; color:#888; font-size:12px;">Consultez le <a href="{lien_wiki}">tableau de bord complet</a>.</p></div></body></html>'

    envoye = envoi_email.envoyer(sujet, text_body, html_body, email_config)
    if envoye:
        logging.info(f"Email récapitulatif de {nombre_baisses} baisse(s) envoyé !")
    return envoye


def _carte_set_newsletter(deal, couleur_categorie, libelle_categorie):
    nom_set = deal['nom_set']
    prix_actuel = deal['prix_actuel']
    pourcentage = deal['pourcentage_reduction']
    prix_min = deal['prix_min_historique']
    date_min = deal['date_min_historique']
    texte_depuis_baisse = deal.get('texte_depuis_baisse')
    image_url = deal.get('image_url')
    url_wiki = deal.get('url_wiki', '#')

    date_min_txt = date_min.strftime('%B %Y') if date_min is not None else ''
    ligne_record = f"Ce set a été le moins cher à {prix_min:.2f}€ en {date_min_txt}."
    ligne_stabilite = f"Il n'avait pas baissé de prix depuis {texte_depuis_baisse}." if texte_depuis_baisse else ""

    text = (
        f"--------------------\n"
        f"{nom_set}\n"
        f"{prix_actuel:.2f}€ (-{pourcentage}% vs prix Lego.com)\n"
        f"{ligne_record}\n"
    )
    if ligne_stabilite:
        text += f"{ligne_stabilite}\n"
    text += f"Fiche détaillée : {url_wiki}\n"

    image_html = (
        f'<img src="{image_url}" alt="{nom_set}" width="90" style="border-radius:6px; display:block;">'
        if image_url else
        '<div style="width:90px; height:90px; background:#eee; border-radius:6px;"></div>'
    )
    html = f"""
    <div style="background:#fff; border-radius:8px; padding:14px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <table role="presentation" width="100%" style="border-collapse:collapse;">
            <tr>
                <td width="100" style="vertical-align:top;">{image_html}</td>
                <td style="vertical-align:top; padding-left:14px;">
                    <h3 style="margin:0 0 6px 0; font-size:15px;">
                        <a href="{url_wiki}" style="color:#222; text-decoration:none;">{nom_set}</a>
                    </h3>
                    <p style="margin:0 0 6px 0;">
                        <span style="color:{couleur_categorie}; font-size:1.2em; font-weight:bold;">{prix_actuel:.2f}€</span>
                        <span style="color:{couleur_categorie}; font-weight:bold;"> (-{pourcentage}%)</span>
                        <span style="display:inline-block; background:{couleur_categorie}; color:#fff; font-size:10px; font-weight:bold; padding:2px 7px; border-radius:10px; margin-left:6px;">{libelle_categorie}</span>
                    </p>
                    <p style="margin:0; color:#666; font-size:12px;">{ligne_record}{f"<br>{ligne_stabilite}" if ligne_stabilite else ""}</p>
                    <a href="{url_wiki}" style="display:inline-block; margin-top:8px; color:{COULEUR_NEUTRE}; text-decoration:none; font-size:12px;">Historique complet &rarr;</a>
                </td>
            </tr>
        </table>
    </div>
    """
    return text, html


def envoyer_newsletter_hebdomadaire(tres_bonnes_affaires, bonnes_affaires, email_config):
    """Envoie la newsletter hebdomadaire des bonnes affaires : deux sections à la
    suite (très bonnes affaires, puis bonnes affaires), chacune triée par % de
    réduction décroissant par rapport au prix Lego.com de référence."""

    nombre_total = len(tres_bonnes_affaires) + len(bonnes_affaires)
    sujet = f"Newsletter LEGO : {nombre_total} bonne{accord_pluriel(nombre_total)} affaire{accord_pluriel(nombre_total)} cette semaine"

    text_body = "Bonjour,\n\nVoici les bonnes affaires de la semaine sur vos sets suivis :\n\n"
    html_body = """
    <html><body style="font-family: Arial, Helvetica, sans-serif; background-color:#f4f4f7; margin:0; padding:20px;">
    <div style="max-width:640px; margin:0 auto;">
    <h2 style="color:#222;">Newsletter hebdomadaire des bonnes affaires</h2>
    """

    for titre, deals, couleur, libelle in (
        ("Très bonnes affaires", tres_bonnes_affaires, "#e67e22", "🔥 TRÈS BONNE AFFAIRE"),
        ("Bonnes affaires", bonnes_affaires, COULEUR_BONNE_AFFAIRE, "✅ BONNE AFFAIRE"),
    ):
        if not deals:
            continue
        text_body += f"\n=== {titre} ===\n\n"
        html_body += f'<h3 style="color:#333; margin-top:20px;">{titre}</h3>'
        for deal in deals:
            text, html = _carte_set_newsletter(deal, couleur, libelle)
            text_body += text
            html_body += html

    lien_wiki = "https://github.com/Aktawind/lego-price-tracker/wiki"
    text_body += f"\n\nPour une analyse détaillée, consultez votre tableau de bord : {lien_wiki}"
    html_body += f'<p style="text-align:center; color:#888; font-size:12px;">Consultez le <a href="{lien_wiki}">tableau de bord complet</a>.</p></div></body></html>'

    envoye = envoi_email.envoyer(sujet, text_body, html_body, email_config)
    if envoye:
        logging.info(f"Newsletter hebdomadaire envoyée ({nombre_total} bonne(s) affaire(s)) !")
    return envoye
