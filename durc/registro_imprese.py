from xml.etree import ElementTree as ET


SEZIONI_REGISTRO_IMPRESE = (
    "dati-identificativi",
    "info-attivita",
    "albi-ruoli-licenze-ridotti",
    "persone-sede",
    "localizzazioni",
    "elenco-soci",
    "trasferimenti-quote",
    "pratiche-soggetti-controllanti",
    "info-statuto",
    "amministrazione-controllo",
    "info-patrimoniali-finanziarie",
    "scritta-pco-s",
)


def _local_name(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _text(elem):
    if elem is None:
        return ""
    return (elem.text or "").strip()


def _find_first_by_local_name(root, name):
    for elem in root.iter():
        if _local_name(elem.tag) == name:
            return elem
    return None


def _serialize_element(elem):
    """
    Converte ricorsivamente un elemento XML in una struttura Python,
    mantenendo:
    - nome del tag
    - attributi
    - testo
    - figli
    """
    nodo = {
        "tag": _local_name(elem.tag),
    }

    if elem.attrib:
        nodo["attributi"] = dict(elem.attrib)

    testo = _text(elem)
    if testo:
        nodo["testo"] = testo

    figli = [_serialize_element(child) for child in list(elem)]
    if figli:
        nodo["figli"] = figli

    return nodo


def _extract_sections(root):
    """
    Estrae tutti i blocchi principali previsti dal dettaglio
    Registro Imprese.

    Ogni sezione è rappresentata come lista per non introdurre
    assunzioni sulla cardinalità: anche se normalmente un blocco
    compare una sola volta, il parser conserva eventuali ripetizioni.
    """
    sezioni = {nome: [] for nome in SEZIONI_REGISTRO_IMPRESE}

    for elem in root.iter():
        nome = _local_name(elem.tag)

        if nome in sezioni:
            sezioni[nome].append(_serialize_element(elem))

    return sezioni


def _extract_main_data(root):
    dati = {
        "denominazione": "",
        "codice_fiscale": "",
        "partita_iva": "",
        "cciaa": "",
        "numero_rea": "",
        "forma_giuridica": "",
        "stato_impresa": "",
        "pec": "",
        "sede_comune": "",
        "sede_provincia": "",
        "sede_toponimo": "",
        "sede_via": "",
        "sede_civico": "",
        "sede_cap": "",
        "sede_frazione": "",
        "sede_stato": "",
    }

    identificativi = _find_first_by_local_name(
        root,
        "dati-identificativi",
    )

    if identificativi is None:
        return dati

    dati["denominazione"] = identificativi.attrib.get(
        "denominazione",
        "",
    )
    dati["codice_fiscale"] = identificativi.attrib.get(
        "c-fiscale",
        "",
    )
    dati["partita_iva"] = identificativi.attrib.get(
        "partita-iva",
        "",
    )
    dati["cciaa"] = identificativi.attrib.get(
        "cciaa",
        "",
    )
    dati["numero_rea"] = identificativi.attrib.get(
        "n-rea",
        "",
    )
    dati["stato_impresa"] = (
        identificativi.attrib.get("stato-impresa", "")
        or identificativi.attrib.get("stato-ditta", "")
    )

    for child in identificativi:
        nome = _local_name(child.tag)

        if nome == "forma-giuridica":
            dati["forma_giuridica"] = _text(child)

        elif nome == "indirizzo-posta-certificata":
            dati["pec"] = _text(child)

        elif nome == "indirizzo-localizzazione":
            dati["sede_comune"] = child.attrib.get(
                "comune",
                "",
            )
            dati["sede_provincia"] = child.attrib.get(
                "provincia",
                "",
            )
            dati["sede_toponimo"] = child.attrib.get(
                "toponimo",
                "",
            )
            dati["sede_via"] = child.attrib.get(
                "via",
                "",
            )
            dati["sede_civico"] = child.attrib.get(
                "n-civico",
                "",
            )
            dati["sede_cap"] = child.attrib.get(
                "cap",
                "",
            )
            dati["sede_frazione"] = child.attrib.get(
                "frazione",
                "",
            )
            dati["sede_stato"] = child.attrib.get(
                "stato",
                "",
            )

    return dati


def parse_registro_imprese_xml(xml_text):
    """
    Analizza la risposta XML dell'e-service Registro Imprese.

    Restituisce:
    - dati_principali:
        dati normalizzati per DB, ricerca e interfaccia;
    - sezioni:
        blocchi funzionali del Registro Imprese;
    - struttura:
        rappresentazione ricorsiva completa dell'XML.

    Nessun dato dell'XML originale viene eliminato.
    """
    root = ET.fromstring(xml_text)

    return {
        "dati_principali": _extract_main_data(root),
        "sezioni": _extract_sections(root),
        "struttura": _serialize_element(root),
    }


def salva_visura_registro_imprese(
    *,
    soggetto,
    xml_text,
    utente=None,
    http_status=200,
    pdnd_request_id="",
):
    """
    Registra una nuova acquisizione Registro Imprese.

    L'XML originale viene conservato integralmente.
    I dati principali vengono estratti solo per indicizzazione,
    ricerca e visualizzazione rapida.

    Ogni acquisizione genera una nuova riga e non modifica
    quelle precedenti.
    """
    from .models import VisuraRegistroImprese

    risultato = parse_registro_imprese_xml(xml_text)
    dati = risultato["dati_principali"]

    return VisuraRegistroImprese.objects.create(
        soggetto=soggetto,
        denominazione=dati["denominazione"],
        codice_fiscale=dati["codice_fiscale"],
        partita_iva=dati["partita_iva"],
        cciaa=dati["cciaa"],
        numero_rea=dati["numero_rea"],
        forma_giuridica=dati["forma_giuridica"],
        stato_impresa=dati["stato_impresa"],
        pec=dati["pec"],
        sede_comune=dati["sede_comune"],
        sede_provincia=dati["sede_provincia"],
        sede_toponimo=dati["sede_toponimo"],
        sede_via=dati["sede_via"],
        sede_civico=dati["sede_civico"],
        sede_cap=dati["sede_cap"],
        sede_frazione=dati["sede_frazione"],
        sede_stato=dati["sede_stato"],
        xml_originale=xml_text,
        http_status=http_status,
        pdnd_request_id=pdnd_request_id or "",
        richiesto_da=utente,
    )


def parse_ricerca_registro_imprese_xml(xml_text):
    """
    Analizza la risposta di /ricerca/denominazione.

    Restituisce una lista di imprese senza imporre limiti
    ulteriori rispetto a quelli dell'e-service.
    """
    root = ET.fromstring(xml_text)

    risultati = []

    def child_text(parent, name):
        for child in parent:
            if _local_name(child.tag) == name:
                return _text(child)
        return ""

    for elem in root.iter():
        if _local_name(elem.tag) != "Impresa":
            continue

        indirizzo = None

        for child in elem:
            if _local_name(child.tag) == "IndirizzoSedeLegale":
                indirizzo = child
                break

        risultato = {
            "progressivo": child_text(elem, "ProgressivoImpresa"),
            "cciaa": child_text(elem, "Cciaa"),
            "numero_rea": (
                child_text(elem, "NRea")
                or child_text(elem, "NumeroRD")
            ),
            "numero_rd": child_text(elem, "NumeroRD"),
            "denominazione": child_text(elem, "Denominazione"),
            "natura_giuridica": child_text(elem, "NaturaGiuridica"),
            "forma_giuridica": child_text(elem, "DescNaturaGiuridica"),
            "codice_fiscale": child_text(elem, "CodiceFiscale"),
            "stato_impresa": (
                child_text(elem, "StatoImpresa")
                or child_text(elem, "StatoDitta")
            ),
            "pec": child_text(elem, "PEC"),
            "sede_provincia": "",
            "sede_comune": "",
            "sede_toponimo": "",
            "sede_via": "",
            "sede_civico": "",
            "sede_cap": "",
        }

        if indirizzo is not None:
            risultato["sede_provincia"] = child_text(
                indirizzo,
                "ProvinciaSede",
            )
            risultato["sede_comune"] = child_text(
                indirizzo,
                "ComuneSede",
            )
            risultato["sede_toponimo"] = child_text(
                indirizzo,
                "ToponimoSede",
            )
            risultato["sede_via"] = child_text(
                indirizzo,
                "ViaSede",
            )
            risultato["sede_civico"] = child_text(
                indirizzo,
                "NcivicoSede",
            )
            risultato["sede_cap"] = child_text(
                indirizzo,
                "CapSede",
            )

        risultati.append(risultato)

    return risultati


ETICHETTE_REGISTRO_IMPRESE = {
    "dati-identificativi": "Dati identificativi",
    "info-attivita": "Attività",
    "albi-ruoli-licenze-ridotti": "Albi, ruoli e licenze",
    "persone-sede": "Persone e cariche",
    "persona": "Persona",
    "persona-fisica": "Persona fisica",
    "persona-giuridica": "Persona giuridica",
    "localizzazioni": "Sedi secondarie e unità locali",
    "localizzazione": "Localizzazione",
    "elenco-soci": "Soci e titolari di partecipazioni",
    "trasferimenti-quote": "Trasferimenti di quote",
    "pratiche-soggetti-controllanti": "Soggetti controllanti",
    "info-statuto": "Informazioni statutarie",
    "amministrazione-controllo": "Amministrazione e controllo",
    "info-patrimoniali-finanziarie": "Dati patrimoniali e finanziari",
    "scritta-pco-s": "Procedure concorsuali",
    "indirizzo-localizzazione": "Indirizzo",
    "indirizzo-posta-certificata": "PEC",
    "forma-giuridica": "Forma giuridica",
    "attivita-esercitata": "Attività esercitata",
    "attivita-prevalente": "Attività prevalente",
    "attivita-secondaria-esercitata": "Attività secondaria",
    "classificazioni-ateco": "Classificazioni ATECO",
    "classificazione-ateco": "Classificazione ATECO",
    "atti-conferimento-cariche": "Atti e cariche",
    "atto-conferimento-cariche": "Atto di conferimento cariche",
    "cariche": "Cariche",
    "carica": "Carica",
    "poteri-persona": "Poteri",
    "riquadri": "Partecipazioni",
    "riquadro": "Partecipazione",
    "titolari": "Titolari",
    "titolare": "Titolare",
    "anagrafica-titolare": "Anagrafica titolare",
    "diritto-partecipazione": "Diritto di partecipazione",
    "capitale-sociale": "Capitale sociale",
    "deliberato": "Deliberato",
    "sottoscritto": "Sottoscritto",
    "versato": "Versato",
}


def _etichetta_registro_imprese(nome):
    if not nome:
        return ""

    if nome in ETICHETTE_REGISTRO_IMPRESE:
        return ETICHETTE_REGISTRO_IMPRESE[nome]

    testo = nome.replace("-", " ").replace("_", " ").strip()

    # Alcuni nomi XML iniziano con prefissi convenzionali.
    prefissi = {
        "c ": "Codice ",
        "dt ": "Data ",
        "n ": "Numero ",
        "f ": "Indicatore ",
        "p ": "Progressivo ",
    }

    for prefisso, sostituzione in prefissi.items():
        if testo.startswith(prefisso):
            testo = sostituzione + testo[len(prefisso):]
            break

    return testo[:1].upper() + testo[1:]


def _prepara_nodo_documento(nodo):
    attributi = []

    for nome, valore in nodo.get("attributi", {}).items():
        if valore in ("", None):
            continue

        attributi.append({
            "nome": nome,
            "label": _etichetta_registro_imprese(nome),
            "valore": valore,
        })

    figli = [
        _prepara_nodo_documento(figlio)
        for figlio in nodo.get("figli", [])
    ]

    return {
        "tag": nodo["tag"],
        "label": _etichetta_registro_imprese(nodo["tag"]),
        "testo": nodo.get("testo", ""),
        "attributi": attributi,
        "figli": figli,
    }


def prepara_documento_registro_imprese(xml_text):
    """
    Prepara tutti i blocchi presenti nella risposta Registro Imprese
    per visualizzazione HTML e futura generazione PDF.

    Non elimina sezioni, elementi ripetuti o attributi.
    """
    parsed = parse_registro_imprese_xml(xml_text)

    sezioni = []

    for nome in SEZIONI_REGISTRO_IMPRESE:
        blocchi = parsed["sezioni"].get(nome, [])

        if not blocchi:
            continue

        sezioni.append({
            "nome": nome,
            "titolo": _etichetta_registro_imprese(nome),
            "blocchi": [
                _prepara_nodo_documento(blocco)
                for blocco in blocchi
            ],
        })

    return {
        "dati_principali": parsed["dati_principali"],
        "sezioni": sezioni,
    }
