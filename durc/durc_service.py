from datetime import timedelta

from django.utils.dateparse import parse_date, parse_datetime

from .models import ConfigurazioneEnte, Durc


def _data_inps(value):
    if not value:
        return None

    value = str(value).strip()

    dt = parse_datetime(value)
    if dt:
        return dt.date()

    return parse_date(value[:10])


def _esito(value):
    if value in (None, ""):
        return None

    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    if value in (0, 1, 2):
        return value

    return None


def salva_durc_da_risposta_inps(
    *,
    soggetto,
    risultato,
    utente=None,
):
    body = risultato.get("body") or {}

    data_documento = _data_inps(body.get("del"))

    data_scadenza = (
        data_documento + timedelta(days=120)
        if data_documento
        else None
    )

    durc = Durc.objects.create(
        soggetto=soggetto,
        protocollo=str(body.get("protocollo") or "").strip(),
        denominazione=str(body.get("denominazione") or "").strip(),
        data_documento=data_documento,
        data_scadenza=data_scadenza,
        stato=Durc.Stato.REGOLARE,
        esito_inps=_esito(body.get("esitoInps")),
        esito_inail=_esito(body.get("esitoInail")),
        esito_cassa_edile=_esito(body.get("esitoCe")),
        pdnd_request_id="",
        http_status=risultato.get("http_status"),
        richiesto_da=utente,
        risposta_inps=body,
    )

    return durc


def salva_pdf_durc(durc, risultato):
    import base64
    import hashlib

    from django.core.files.base import ContentFile

    status = risultato.get("http_status")

    if status != 200:
        raise ValueError(
            f"Download PDF DURC fallito con HTTP {status}."
        )

    body = risultato.get("body") or {}
    contenuto_base64 = body.get("base64")

    if not contenuto_base64:
        raise ValueError(
            "INPS ha risposto senza il contenuto PDF."
        )

    try:
        pdf_bytes = base64.b64decode(
            contenuto_base64,
            validate=True,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Il contenuto PDF restituito da INPS non è un base64 valido."
        ) from exc

    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError(
            "Il contenuto restituito da INPS non è un PDF valido."
        )

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    nome_file = (
        f"{durc.protocollo}.pdf"
        if durc.protocollo
        else f"durc_{durc.pk}.pdf"
    )

    durc.pdf.save(
        nome_file,
        ContentFile(pdf_bytes),
        save=False,
    )

    durc.pdf_sha256 = sha256

    durc.save(
        update_fields=[
            "pdf",
            "pdf_sha256",
        ]
    )

    configurazione_ente = ConfigurazioneEnte.objects.first()

    limite_pdf = (
        configurazione_ente.max_pdf_durc_per_soggetto
        if configurazione_ente
        else 10
    )

    applica_retention_pdf_durc(
        durc.soggetto,
        limite=limite_pdf,
    )

    return durc


def applica_retention_pdf_durc(soggetto, limite=10):
    """
    Mantiene fisicamente solo i PDF delle acquisizioni DURC più recenti
    del soggetto.

    I record DURC restano nel database e il relativo SHA256 viene
    mantenuto anche quando il file PDF viene eliminato.
    """
    durc_con_pdf = list(
        soggetto.durc
        .exclude(pdf="")
        .order_by("-acquisito_il", "-pk")
    )

    eccedenti = durc_con_pdf[limite:]

    eliminati = 0

    for durc in eccedenti:
        if not durc.pdf:
            continue

        try:
            durc.pdf.delete(save=False)
        except OSError:
            # Se lo storage non è accessibile, lasciamo il riferimento
            # invariato e riproveremo alla prossima applicazione
            # della retention.
            continue

        durc.pdf = ""
        durc.save(update_fields=["pdf"])
        eliminati += 1

    return eliminati
