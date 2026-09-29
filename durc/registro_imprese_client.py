import logging

import requests
from django.utils import timezone

from .models import ConfigurazioneRegistroImprese
from .pdnd import PDNDError, richiedi_voucher


logger = logging.getLogger(__name__)


class RegistroImpreseError(Exception):
    pass


def get_config_registro_imprese():
    config = ConfigurazioneRegistroImprese.objects.filter(
        attiva=True
    ).first()

    if not config:
        raise RegistroImpreseError(
            "Nessuna configurazione Registro Imprese attiva."
        )

    required = {
        "client_id": config.client_id,
        "purpose_id": config.purpose_id,
        "kid": config.kid,
        "iss": config.iss,
        "sub": config.sub,
        "aud": config.aud,
        "url_autenticazione": config.url_autenticazione,
        "url_base_servizio": config.url_base_servizio,
        "percorso_chiave_privata": config.percorso_chiave_privata,
    }

    mancanti = [
        nome
        for nome, valore in required.items()
        if not valore
    ]

    if mancanti:
        raise RegistroImpreseError(
            "Parametri Registro Imprese mancanti: "
            + ", ".join(mancanti)
        )

    return config


def _salva_errore_config(config, messaggio):
    ConfigurazioneRegistroImprese.objects.filter(
        pk=config.pk
    ).update(
        ultimo_errore=str(messaggio)[:2000]
    )


def consulta_registro_imprese(codice_fiscale):
    """
    Consulta il dettaglio impresa tramite Codice Fiscale.

    Non salva automaticamente alcuna VisuraRegistroImprese:
    restituisce la risposta dell'e-service al chiamante, che potrà
    validarla, analizzarla e decidere se persisterla.
    """
    config = get_config_registro_imprese()

    codice_fiscale = (codice_fiscale or "").strip().upper()

    if not codice_fiscale:
        raise RegistroImpreseError(
            "Codice fiscale mancante."
        )

    try:
        voucher = richiedi_voucher(config)
    except PDNDError as exc:
        logger.exception(
            "Errore ottenimento voucher PDND per Registro Imprese."
        )
        _salva_errore_config(
            config,
            "Errore ottenimento voucher PDND.",
        )
        raise RegistroImpreseError(
            "Impossibile ottenere il voucher PDND."
        ) from exc

    ConfigurazioneRegistroImprese.objects.filter(
        pk=config.pk
    ).update(
        ultimo_voucher_ok=timezone.now(),
        ultimo_errore="",
    )

    url = (
        config.url_base_servizio.rstrip("/")
        + "/rest/pcad/v1/dettaglio/codicefiscale"
    )

    headers = {
        "Authorization": f"Bearer {voucher['access_token']}",
        "Accept": "application/xml",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "codiceFiscale": codice_fiscale,
            },
            timeout=config.timeout_secondi or 30,
        )
    except requests.RequestException as exc:
        logger.exception(
            "Errore di comunicazione con Registro Imprese."
        )
        _salva_errore_config(
            config,
            "Errore di comunicazione con Registro Imprese.",
        )
        raise RegistroImpreseError(
            "Errore di comunicazione con Registro Imprese."
        ) from exc

    request_id = (
        response.headers.get("X-Request-ID")
        or response.headers.get("X-Request-Id")
        or response.headers.get("Request-ID")
        or ""
    )

    if response.status_code != 200:
        _salva_errore_config(
            config,
            f"Registro Imprese HTTP {response.status_code}",
        )

        return {
            "http_status": response.status_code,
            "xml": response.text,
            "content_type": response.headers.get(
                "Content-Type",
                "",
            ),
            "pdnd_request_id": request_id,
            "voucher_jti": voucher["jti"],
        }

    ConfigurazioneRegistroImprese.objects.filter(
        pk=config.pk
    ).update(
        ultima_chiamata_ok=timezone.now(),
        ultimo_errore="",
    )

    return {
        "http_status": response.status_code,
        "xml": response.text,
        "content_type": response.headers.get(
            "Content-Type",
            "",
        ),
        "pdnd_request_id": request_id,
        "voucher_jti": voucher["jti"],
    }


def ricerca_registro_imprese_denominazione(
    denominazione,
    sigla_provincia="",
):
    """
    Ricerca imprese per denominazione.

    Restituisce la risposta XML dell'e-service.
    Non salva alcun dato nel database.
    """
    config = get_config_registro_imprese()

    denominazione = (denominazione or "").strip()
    sigla_provincia = (sigla_provincia or "").strip().upper()

    if len(denominazione) < 2:
        raise RegistroImpreseError(
            "La denominazione deve contenere almeno 2 caratteri."
        )

    try:
        voucher = richiedi_voucher(config)
    except PDNDError as exc:
        logger.exception(
            "Errore ottenimento voucher PDND per Registro Imprese."
        )
        _salva_errore_config(
            config,
            "Errore ottenimento voucher PDND.",
        )
        raise RegistroImpreseError(
            "Impossibile ottenere il voucher PDND."
        ) from exc

    ConfigurazioneRegistroImprese.objects.filter(
        pk=config.pk
    ).update(
        ultimo_voucher_ok=timezone.now(),
        ultimo_errore="",
    )

    url = (
        config.url_base_servizio.rstrip("/")
        + "/rest/pcad/v1/ricerca/denominazione"
    )

    params = {
        "denominazione": denominazione,
    }

    if sigla_provincia:
        params["siglaProvincia"] = sigla_provincia

    try:
        response = requests.get(
            url,
            headers={
                "Authorization": "Bearer " + voucher["access_token"],
                "Accept": "application/xml",
            },
            params=params,
            timeout=config.timeout_secondi or 30,
        )
    except requests.RequestException as exc:
        logger.exception(
            "Errore di comunicazione con Registro Imprese."
        )
        _salva_errore_config(
            config,
            "Errore di comunicazione con Registro Imprese.",
        )
        raise RegistroImpreseError(
            "Errore di comunicazione con Registro Imprese."
        ) from exc

    request_id = (
        response.headers.get("X-Request-ID")
        or response.headers.get("X-Request-Id")
        or response.headers.get("Request-ID")
        or ""
    )

    if response.status_code == 200:
        ConfigurazioneRegistroImprese.objects.filter(
            pk=config.pk
        ).update(
            ultima_chiamata_ok=timezone.now(),
            ultimo_errore="",
        )
    else:
        _salva_errore_config(
            config,
            f"Registro Imprese HTTP {response.status_code}",
        )

    return {
        "http_status": response.status_code,
        "xml": response.text,
        "content_type": response.headers.get(
            "Content-Type",
            "",
        ),
        "pdnd_request_id": request_id,
        "voucher_jti": voucher["jti"],
    }
