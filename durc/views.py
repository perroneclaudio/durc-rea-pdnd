from urllib.parse import urlencode
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import AuditLog, Durc, Soggetto, VisuraRegistroImprese


@login_required
def dashboard(request):
    query = request.GET.get("q", "").strip()

    soggetti = Soggetto.objects.all()

    if query:
        soggetti = soggetti.filter(
            Q(codice_fiscale__icontains=query)
            | Q(partita_iva__icontains=query)
            | Q(denominazione__icontains=query)
        )

    soggetti = soggetti.order_by("denominazione", "codice_fiscale")

    risultati = []

    for soggetto in soggetti[:100]:
        ultimo_durc = soggetto.durc.order_by("-acquisito_il").first()

        risultati.append(
            {
                "soggetto": soggetto,
                "ultimo_durc": ultimo_durc,
            }
        )

    context = {
        "query": query,
        "risultati": risultati,
        "numero_soggetti": Soggetto.objects.count(),
        "numero_durc": Durc.objects.count(),
    }

    return render(request, "durc/dashboard.html", context)


@login_required
def durc_pdf(request, pk):
    durc = get_object_or_404(Durc, pk=pk)

    if not durc.pdf:
        messages.warning(
            request,
            "Nessun PDF archiviato per questo DURC.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=durc.soggetto_id,
        )

    try:
        file_pdf = durc.pdf.open("rb")
    except OSError:
        messages.error(
            request,
            "Il PDF risulta archiviato nel database ma non è accessibile nello storage.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=durc.soggetto_id,
        )

    nome_file = (
        f"{durc.protocollo}.pdf"
        if durc.protocollo
        else f"durc_{durc.pk}.pdf"
    )

    AuditLog.objects.create(
        utente=request.user,
        azione=AuditLog.Azione.DOWNLOAD_PDF,
        soggetto=durc.soggetto,
        durc=durc,
        indirizzo_ip=request.META.get("REMOTE_ADDR"),
        dettagli={
            "protocollo": durc.protocollo,
            "nome_file": nome_file,
            "pdf_sha256": durc.pdf_sha256,
        },
    )

    return FileResponse(
        file_pdf,
        as_attachment=True,
        filename=nome_file,
        content_type="application/pdf",
    )


@login_required
def soggetto_detail(request, pk):
    soggetto = get_object_or_404(Soggetto, pk=pk)

    storico = soggetto.durc.select_related(
        "richiesto_da"
    ).order_by("-acquisito_il")

    ultimo_durc = storico.first()

    durc_valido_con_pdf = (
        storico
        .filter(
            stato=Durc.Stato.REGOLARE,
            data_scadenza__gte=timezone.localdate(),
        )
        .exclude(pdf="")
        .first()
    )

    storico_registro_imprese = (
        soggetto.visure_registro_imprese
        .select_related("richiesto_da")
        .order_by("-acquisito_il")
    )

    ultima_visura = storico_registro_imprese.first()

    return render(
        request,
        "durc/soggetto_detail.html",
        {
            "soggetto": soggetto,
            "storico": storico,
            "ultimo_durc": ultimo_durc,
            "durc_valido_con_pdf": durc_valido_con_pdf,
            "storico_registro_imprese": storico_registro_imprese,
            "ultima_visura": ultima_visura,
        },
    )
from django.contrib import messages
from django.shortcuts import redirect
from requests.exceptions import RequestException

from .pdnd import PDNDError, consulta_durc, download_durc
from .durc_service import (
    salva_durc_da_risposta_inps,
    salva_pdf_durc,
)
from .registro_imprese import (
    parse_registro_imprese_xml,
    parse_ricerca_registro_imprese_xml,
    prepara_documento_registro_imprese,
    salva_visura_registro_imprese,
)
from .registro_imprese_pdf import genera_pdf_registro_imprese
from .registro_imprese_client import (
    RegistroImpreseError,
    consulta_registro_imprese,
    ricerca_registro_imprese_denominazione,
)
from xml.etree.ElementTree import ParseError


def _audit_richiesta_durc(
    request,
    codice_fiscale,
    *,
    soggetto=None,
    durc=None,
    http_status=None,
    esito="",
):
    dettagli = {
        "servizio": "DURC",
        "codice_fiscale": codice_fiscale,
        "esito": esito,
    }

    if http_status is not None:
        dettagli["http_status"] = http_status

    if durc is not None and durc.protocollo:
        dettagli["protocollo"] = durc.protocollo

    AuditLog.objects.create(
        utente=request.user,
        azione=AuditLog.Azione.CONSULTAZIONE_PDND,
        soggetto=soggetto,
        durc=durc,
        indirizzo_ip=request.META.get("REMOTE_ADDR"),
        dettagli=dettagli,
    )


def _acquisisci_durc(request, codice_fiscale, soggetto=None):
    codice_fiscale = codice_fiscale.strip().upper()

    try:
        risultato = consulta_durc(
            codice_fiscale,
            utente=request.user,
        )

    except PDNDError:
        _audit_richiesta_durc(
            request,
            codice_fiscale,
            soggetto=soggetto,
            esito="ERRORE_PDND",
        )
        messages.error(
            request,
            "Errore durante la comunicazione con PDND/INPS.",
        )
        return soggetto

    except RequestException:
        _audit_richiesta_durc(
            request,
            codice_fiscale,
            soggetto=soggetto,
            esito="ERRORE_CONNESSIONE_INPS",
        )
        messages.error(
            request,
            "Impossibile contattare il servizio INPS.",
        )
        return soggetto

    status = risultato["http_status"]
    body = risultato["body"]

    if status == 200:
        if soggetto is None:
            soggetto, _ = Soggetto.objects.get_or_create(
                codice_fiscale=codice_fiscale,
                defaults={
                    "denominazione": str(
                        body.get("denominazione") or ""
                    ).strip(),
                },
            )

        durc = salva_durc_da_risposta_inps(
            soggetto=soggetto,
            risultato=risultato,
            utente=request.user,
        )

        _audit_richiesta_durc(
            request,
            codice_fiscale,
            soggetto=soggetto,
            durc=durc,
            http_status=status,
            esito="DURC_ACQUISITO",
        )

        try:
            risultato_pdf = download_durc(
                durc.protocollo,
                lang="ITA",
                utente=request.user,
            )

            salva_pdf_durc(
                durc,
                risultato_pdf,
            )

        except (PDNDError, RequestException, ValueError):
            messages.warning(
                request,
                f"DURC {durc.protocollo or 'senza protocollo'} "
                "acquisito, ma il PDF non è stato archiviato.",
            )

        else:
            messages.success(
                request,
                f"DURC {durc.protocollo or 'senza protocollo'} "
                "acquisito e archiviato con il relativo PDF.",
            )

        return soggetto

    if status == 404:
        esito_audit = "DURC_NON_DISPONIBILE"
        messages.warning(
            request,
            "Nessun DURC regolare in corso di validità disponibile.",
        )

    elif status == 401:
        esito_audit = "AUTENTICAZIONE_RIFIUTATA"
        messages.error(
            request,
            "INPS ha rifiutato l'autenticazione della richiesta.",
        )

    else:
        esito_audit = "ERRORE_HTTP"
        messages.error(
            request,
            f"INPS ha restituito un errore HTTP {status}.",
        )

    _audit_richiesta_durc(
        request,
        codice_fiscale,
        soggetto=soggetto,
        http_status=status,
        esito=esito_audit,
    )

    return soggetto


@login_required
def consulta_durc_soggetto(request, pk):
    soggetto = get_object_or_404(Soggetto, pk=pk)

    if request.method != "POST":
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    _acquisisci_durc(
        request,
        soggetto.codice_fiscale,
        soggetto=soggetto,
    )

    return redirect(
        "durc:soggetto_detail",
        pk=soggetto.pk,
    )


@login_required
def consulta_durc_codice_fiscale(request):
    if request.method != "POST":
        return redirect("durc:dashboard")

    codice_fiscale = (
        request.POST.get("codice_fiscale", "")
        .strip()
        .upper()
    )

    if not codice_fiscale:
        messages.error(
            request,
            "Inserire un codice fiscale.",
        )
        return redirect("durc:dashboard")

    soggetto = Soggetto.objects.filter(
        codice_fiscale=codice_fiscale
    ).first()

    soggetto = _acquisisci_durc(
        request,
        codice_fiscale,
        soggetto=soggetto,
    )

    if soggetto is not None:
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    query = urlencode({"q": codice_fiscale})
    return HttpResponseRedirect(f"/?{query}")


@login_required
def consulta_registro_imprese_soggetto(request, pk):
    soggetto = get_object_or_404(Soggetto, pk=pk)

    if request.method != "POST":
        return redirect("durc:soggetto_detail", pk=soggetto.pk)

    try:
        risultato = consulta_registro_imprese(
            soggetto.codice_fiscale
        )

    except RegistroImpreseError:
        messages.error(
            request,
            "Errore durante la comunicazione con Registro Imprese.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    status = risultato["http_status"]

    if status != 200:
        if status == 401:
            messages.error(
                request,
                "Registro Imprese ha rifiutato "
                "l'autenticazione della richiesta.",
            )
        elif status == 429:
            messages.warning(
                request,
                "Limite temporaneo di richieste Registro "
                "Imprese raggiunto. Riprovare più tardi.",
            )
        elif status == 503:
            messages.warning(
                request,
                "Il servizio Registro Imprese è "
                "temporaneamente non disponibile.",
            )
        else:
            messages.error(
                request,
                f"Registro Imprese ha restituito HTTP {status}.",
            )

        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    xml_text = risultato["xml"]

    try:
        parsed = parse_registro_imprese_xml(xml_text)

    except ParseError:
        messages.error(
            request,
            "Registro Imprese ha restituito una risposta "
            "XML non valida.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    if not parsed["sezioni"]["dati-identificativi"]:
        messages.warning(
            request,
            "Nessuna impresa corrispondente al codice "
            "fiscale è stata restituita dal Registro Imprese.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    visura = salva_visura_registro_imprese(
        soggetto=soggetto,
        xml_text=xml_text,
        utente=request.user,
        http_status=status,
        pdnd_request_id=risultato.get(
            "pdnd_request_id",
            "",
        ),
    )

    if visura.pec:
        messages.success(
            request,
            "Dati Registro Imprese acquisiti correttamente. "
            f"PEC risultante: {visura.pec}",
        )
    else:
        messages.success(
            request,
            "Dati Registro Imprese acquisiti correttamente. "
            "Nessun indirizzo PEC presente nella risposta.",
        )

    return redirect(
        "durc:soggetto_detail",
        pk=soggetto.pk,
    )


@login_required
def consulta_registro_imprese_codice_fiscale(request):
    if request.method != "POST":
        return redirect("durc:dashboard")

    codice_fiscale = (
        request.POST.get("codice_fiscale", "")
        .strip()
        .upper()
    )

    if not codice_fiscale:
        messages.error(
            request,
            "Inserire un codice fiscale.",
        )
        return redirect("durc:dashboard")

    # Se il soggetto esiste già localmente, apriamo direttamente la scheda.
    soggetto = Soggetto.objects.filter(
        Q(codice_fiscale=codice_fiscale)
        | Q(partita_iva=codice_fiscale)
    ).first()

    if soggetto:
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    try:
        risultato = consulta_registro_imprese(
            codice_fiscale
        )

    except RegistroImpreseError:
        messages.error(
            request,
            "Errore durante la comunicazione con Registro Imprese.",
        )
        return HttpResponseRedirect(
            "/?" + urlencode({"q": codice_fiscale})
        )

    status = risultato["http_status"]
    xml_text = risultato["xml"]

    # Il servizio Registro Imprese restituisce HTTP 400 anche quando
    # il codice fiscale è formalmente accettato ma non corrisponde
    # ad alcuna impresa.
    if (
        status == 400
        and "Impresa o documento inesistente" in xml_text
    ):
        if len(codice_fiscale) == 16:
            soggetto = Soggetto.objects.create(
                codice_fiscale=codice_fiscale,
                partita_iva="",
                denominazione="",
            )

            messages.info(
                request,
                "Nessuna posizione trovata nel Registro Imprese. "
                "Il soggetto è stato comunque creato.",
            )

            return redirect(
                "durc:soggetto_detail",
                pk=soggetto.pk,
            )

        return render(
            request,
            "durc/conferma_soggetto_senza_ri.html",
            {
                "valore_inserito": codice_fiscale,
            },
        )

    if status != 200:
        messages.error(
            request,
            f"Registro Imprese ha restituito HTTP {status}.",
        )
        return redirect("durc:dashboard")

    try:
        parsed = parse_registro_imprese_xml(xml_text)

    except ParseError:
        messages.error(
            request,
            "Registro Imprese ha restituito una risposta XML non valida.",
        )
        return HttpResponseRedirect(
            "/?" + urlencode({"q": codice_fiscale})
        )

    if not parsed["sezioni"]["dati-identificativi"]:

        if len(codice_fiscale) == 16:
            soggetto = Soggetto.objects.create(
                codice_fiscale=codice_fiscale,
                partita_iva="",
                denominazione="",
            )

            messages.info(
                request,
                "Nessuna posizione trovata nel Registro Imprese. "
                "Il soggetto è stato comunque creato.",
            )

            return redirect(
                "durc:soggetto_detail",
                pk=soggetto.pk,
            )

        return render(
            request,
            "durc/conferma_soggetto_senza_ri.html",
            {
                "valore_inserito": codice_fiscale,
            },
        )

    dati = parsed["dati_principali"]

    soggetto = Soggetto.objects.create(
        codice_fiscale=dati["codice_fiscale"] or codice_fiscale,
        partita_iva=dati["partita_iva"],
        denominazione=dati["denominazione"],
    )

    salva_visura_registro_imprese(
        soggetto=soggetto,
        xml_text=xml_text,
        utente=request.user,
        http_status=status,
        pdnd_request_id=risultato.get(
            "pdnd_request_id",
            "",
        ),
    )

    messages.success(
        request,
        "Impresa acquisita dal Registro Imprese.",
    )

    return redirect(
        "durc:soggetto_detail",
        pk=soggetto.pk,
    )


@login_required
def ricerca_registro_imprese_denominazione_view(request):
    if request.method != "POST":
        return redirect("durc:dashboard")

    denominazione = request.POST.get(
        "denominazione",
        "",
    ).strip()

    sigla_provincia = request.POST.get(
        "sigla_provincia",
        "",
    ).strip().upper()

    if len(denominazione) < 2:
        messages.error(
            request,
            "Inserire almeno 2 caratteri per la denominazione.",
        )
        return redirect("durc:dashboard")

    try:
        risultato = ricerca_registro_imprese_denominazione(
            denominazione,
            sigla_provincia,
        )

    except RegistroImpreseError:
        messages.error(
            request,
            "Errore durante la comunicazione con Registro Imprese.",
        )
        return HttpResponseRedirect(
            "/?" + urlencode({"q": denominazione})
        )

    if risultato["http_status"] != 200:
        messages.error(
            request,
            "Registro Imprese ha restituito HTTP "
            f"{risultato['http_status']}.",
        )
        return HttpResponseRedirect(
            "/?" + urlencode({"q": denominazione})
        )

    try:
        imprese = parse_ricerca_registro_imprese_xml(
            risultato["xml"]
        )

    except ParseError:
        messages.error(
            request,
            "Registro Imprese ha restituito una risposta XML non valida.",
        )
        return HttpResponseRedirect(
            "/?" + urlencode({"q": denominazione})
        )

    return render(
        request,
        "durc/registro_imprese_risultati.html",
        {
            "denominazione": denominazione,
            "sigla_provincia": sigla_provincia,
            "imprese": imprese,
            "numero_risultati": len(imprese),
            "limite_raggiunto": len(imprese) >= 200,
        },
    )


@login_required
def registro_imprese_dettaglio(request, pk):
    visura = get_object_or_404(
        VisuraRegistroImprese.objects.select_related(
            "soggetto",
            "richiesto_da",
        ),
        pk=pk,
    )

    try:
        documento = prepara_documento_registro_imprese(
            visura.xml_originale
        )
    except ParseError:
        messages.error(
            request,
            "L'XML archiviato per questa acquisizione non è valido.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=visura.soggetto.pk,
        )

    return render(
        request,
        "durc/registro_imprese_dettaglio.html",
        {
            "visura": visura,
            "soggetto": visura.soggetto,
            "documento": documento,
        },
    )


@login_required
def registro_imprese_pdf_ultima(request, pk):
    soggetto = get_object_or_404(
        Soggetto,
        pk=pk,
    )

    visura = (
        soggetto.visure_registro_imprese
        .order_by("-acquisito_il")
        .first()
    )

    if visura is None:
        messages.warning(
            request,
            "Non sono presenti acquisizioni Registro Imprese "
            "per questa azienda.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    try:
        contenuto = genera_pdf_registro_imprese(
            visura
        )
    except ParseError:
        messages.error(
            request,
            "Non è possibile generare il PDF: "
            "l'XML archiviato non è valido.",
        )
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    nome_base = (
        visura.codice_fiscale
        or str(soggetto.pk)
    )

    data = timezone.localtime(
        visura.acquisito_il
    ).strftime("%Y%m%d_%H%M")

    filename = (
        f"registro_imprese_{nome_base}_{data}.pdf"
    )

    response = HttpResponse(
        contenuto,
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    return response


@login_required
def crea_soggetto_minimo(request):
    if request.method != "POST":
        return redirect("durc:dashboard")

    codice_fiscale = (
        request.POST.get("codice_fiscale", "")
        .strip()
        .upper()
    )

    partita_iva = (
        request.POST.get("partita_iva", "")
        .strip()
    )

    if not codice_fiscale:
        messages.error(
            request,
            "Il codice fiscale è necessario per creare il soggetto.",
        )
        return redirect("durc:dashboard")

    soggetto = Soggetto.objects.filter(
        codice_fiscale=codice_fiscale
    ).first()

    if soggetto:
        return redirect(
            "durc:soggetto_detail",
            pk=soggetto.pk,
        )

    soggetto = Soggetto.objects.create(
        codice_fiscale=codice_fiscale,
        partita_iva=partita_iva,
        denominazione="",
    )

    messages.success(
        request,
        "Soggetto creato. "
        "Non risultano al momento dati acquisiti dal Registro Imprese.",
    )

    return redirect(
        "durc:soggetto_detail",
        pk=soggetto.pk,
    )
