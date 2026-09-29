from urllib.parse import quote
import logging
import time
import uuid

import jwt
import requests

from .models import ConfigurazionePDND, ConfigurazioneEnte


logger = logging.getLogger(__name__)


CLIENT_ASSERTION_TYPE = (
    "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
)


class PDNDError(Exception):
    pass


def get_config():
    config = ConfigurazionePDND.objects.filter(attiva=True).first()

    if not config:
        raise PDNDError("Nessuna configurazione PDND attiva.")

    required = {
        "client_id": config.client_id,
        "purpose_id": config.purpose_id,
        "kid": config.kid,
        "iss": config.iss,
        "sub": config.sub,
        "aud": config.aud,
        "url_autenticazione": config.url_autenticazione,
        "percorso_chiave_privata": config.percorso_chiave_privata,
    }

    mancanti = [nome for nome, valore in required.items() if not valore]

    if mancanti:
        raise PDNDError(
            "Parametri PDND mancanti: " + ", ".join(mancanti)
        )

    return config


def genera_client_assertion(config=None):
    if config is None:
        config = get_config()

    try:
        with open(config.percorso_chiave_privata, "rb") as f:
            private_key = f.read()
    except OSError as exc:
        logger.exception(
            "Impossibile leggere la chiave privata PDND."
        )
        raise PDNDError(
            "Impossibile leggere la chiave privata PDND."
        ) from exc

    now = int(time.time())

    payload = {
        "iss": config.iss,
        "sub": config.sub,
        "aud": config.aud,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + 600,
        "purposeId": config.purpose_id,
    }

    headers = {
        "kid": config.kid,
        "alg": config.alg or "RS256",
        "typ": config.typ or "JWT",
    }

    assertion = jwt.encode(
        payload,
        private_key,
        algorithm=config.alg or "RS256",
        headers=headers,
    )

    return assertion, payload


def richiedi_voucher(config=None):
    """
    Richiede un voucher PDND.

    Se config non viene specificata utilizza la configurazione
    DURC storica. In questo modo la funzione resta compatibile
    con il codice esistente ma può essere riutilizzata da altri
    e-service PDND.
    """
    if config is None:
        config = get_config()

    required = {
        "client_id": config.client_id,
        "purpose_id": config.purpose_id,
        "kid": config.kid,
        "iss": config.iss,
        "sub": config.sub,
        "aud": config.aud,
        "url_autenticazione": config.url_autenticazione,
        "percorso_chiave_privata": config.percorso_chiave_privata,
    }

    mancanti = [
        nome for nome, valore in required.items()
        if not valore
    ]

    if mancanti:
        raise PDNDError(
            "Parametri PDND mancanti: " + ", ".join(mancanti)
        )

    assertion, payload = genera_client_assertion(config)

    response = requests.post(
        config.url_autenticazione,
        data={
            "client_id": config.client_id,
            "client_assertion": assertion,
            "client_assertion_type": CLIENT_ASSERTION_TYPE,
            "grant_type": "client_credentials",
        },
        timeout=getattr(config, "timeout_secondi", 30) or 30,
    )

    try:
        body = response.json()
    except ValueError:
        body = {
            "raw_response": response.text[:1000],
        }

    if not response.ok:
        logger.error(
            "Richiesta voucher PDND fallita con HTTP %s.",
            response.status_code,
        )
        raise PDNDError(
            f"Errore PDND HTTP {response.status_code}."
        )

    if "access_token" not in body:
        raise PDNDError(
            "PDND ha risposto senza access_token."
        )

    return {
        "access_token": body["access_token"],
        "expires_in": body.get("expires_in"),
        "jti": payload["jti"],
        "http_status": response.status_code,
    }

def get_inps_identity_user_id(utente=None):
    configurazione_ente = ConfigurazioneEnte.objects.first()

    if utente is not None:
        codice_fiscale_utente = str(
            getattr(utente, "first_name", "") or ""
        ).strip().upper()

        if codice_fiscale_utente:
            if (
                len(codice_fiscale_utente) != 16
                or not codice_fiscale_utente.isalnum()
            ):
                raise PDNDError(
                    "Il campo Nome dell'utente deve contenere "
                    "un codice fiscale valido di 16 caratteri."
                )

            return codice_fiscale_utente

    if not configurazione_ente or not configurazione_ente.codice_fiscale:
        raise PDNDError(
            "Codice fiscale dell'ente non configurato."
        )

    return configurazione_ente.codice_fiscale.strip().upper()

def consulta_durc(codice_fiscale, utente=None):
    config = get_config()
    inps_identity_user_id = get_inps_identity_user_id(
        utente=utente,
    )

    codice_fiscale = codice_fiscale.strip().upper()

    if not codice_fiscale:
        raise PDNDError("Codice fiscale mancante.")

    voucher = richiedi_voucher()

    url = (
        config.url_servizio_durc.rstrip("/")
        + "/getDurcInCorsoDiValidita"
    )

    headers = {
        "Authorization": f"Bearer {voucher['access_token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "INPS-Identity-UserId": inps_identity_user_id,
        "INPS-Identity-CodiceUfficio": "001",
    }

    payload = {
        "codicefiscale": codice_fiscale,
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
    )

    try:
        body = response.json()
    except ValueError:
        body = {
            "raw_response": response.text[:2000],
        }

    return {
        "http_status": response.status_code,
        "body": body,
        "voucher_jti": voucher["jti"],
    }



def download_durc(protocollo, lang="ITA", utente=None):
    config = get_config()
    inps_identity_user_id = get_inps_identity_user_id(
        utente=utente,
    )

    protocollo = str(protocollo or "").strip()
    lang = str(lang or "ITA").strip().upper()

    if not protocollo:
        raise PDNDError("Protocollo DURC mancante.")

    if lang not in ("ITA", "DE"):
        raise PDNDError("Lingua DURC non valida.")

    voucher = richiedi_voucher()

    url = (
        config.url_servizio_durc.rstrip("/")
        + "/downloadDURC/"
        + quote(protocollo, safe="")
        + "/"
        + lang
    )

    headers = {
        "Authorization": f"Bearer {voucher['access_token']}",
        "Accept": "application/json",
        "INPS-Identity-UserId": inps_identity_user_id,
        "INPS-Identity-CodiceUfficio": "001",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    try:
        body = response.json()
    except ValueError:
        body = {
            "raw_response": response.text[:2000],
        }

    return {
        "http_status": response.status_code,
        "body": body,
        "voucher_jti": voucher["jti"],
    }
