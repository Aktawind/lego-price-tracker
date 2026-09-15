import envoi_email


class FausseReponse:
    def __init__(self, status_code=200, text=''):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            erreur = requests.exceptions.HTTPError(f"{self.status_code} error")
            erreur.response = self
            raise erreur


def test_envoyer_config_incomplete_ne_fait_pas_appel_reseau(monkeypatch):
    appelee = []
    monkeypatch.setattr(envoi_email.requests, 'post', lambda *a, **k: appelee.append(1))
    resultat = envoi_email.envoyer('sujet', 'texte', '<p>html</p>', {'api_key': None, 'expediteur': 'a@a.com', 'destinataire': 'b@b.com'})
    assert resultat is False
    assert appelee == []


def test_envoyer_construit_bien_la_requete_brevo(monkeypatch):
    capture = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        capture['url'] = url
        capture['headers'] = headers
        capture['json'] = json
        return FausseReponse(200)

    monkeypatch.setattr(envoi_email.requests, 'post', fake_post)
    resultat = envoi_email.envoyer(
        'Sujet test', 'texte brut', '<p>html</p>',
        {'api_key': 'cle123', 'expediteur': 'alertes@mondomaine.fr', 'destinataire': 'a@a.com, b@b.com'},
    )

    assert resultat is True
    assert capture['url'] == 'https://api.brevo.com/v3/smtp/email'
    assert capture['headers']['api-key'] == 'cle123'
    assert capture['json']['sender'] == {'email': 'alertes@mondomaine.fr'}
    assert capture['json']['to'] == [{'email': 'a@a.com'}, {'email': 'b@b.com'}]
    assert capture['json']['subject'] == 'Sujet test'
    assert capture['json']['htmlContent'] == '<p>html</p>'
    assert capture['json']['textContent'] == 'texte brut'


def test_envoyer_retourne_false_si_erreur_http(monkeypatch):
    monkeypatch.setattr(envoi_email.requests, 'post', lambda *a, **k: FausseReponse(400, '{"message":"bad request"}'))
    resultat = envoi_email.envoyer('s', 't', 'h', {'api_key': 'x', 'expediteur': 'a@a.com', 'destinataire': 'b@b.com'})
    assert resultat is False
