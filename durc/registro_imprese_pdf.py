from html import escape
from io import BytesIO

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Indenter,
)

from .registro_imprese import prepara_documento_registro_imprese


def _safe(value):
    if value is None:
        return ""
    return escape(str(value))


def _numero_pagina(canvas, doc):
    canvas.saveState()

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))

    canvas.drawString(
        18 * mm,
        10 * mm,
        "Registro Imprese - dati acquisiti tramite PDND",
    )

    canvas.drawRightString(
        A4[0] - 18 * mm,
        10 * mm,
        f"Pagina {doc.page}",
    )

    canvas.restoreState()


def _aggiungi_nodo(story, nodo, styles, livello=0):
    label = nodo.get("label", "")
    testo = nodo.get("testo", "")
    attributi = nodo.get("attributi", [])
    figli = nodo.get("figli", [])

    # Nodo foglia
    if not figli:
        if testo:
            story.append(
                Paragraph(
                    f"<b>{_safe(label)}:</b> {_safe(testo)}",
                    styles["Field"],
                )
            )

        for attributo in attributi:
            story.append(
                Paragraph(
                    f"<b>{_safe(attributo['label'])}:</b> "
                    f"{_safe(attributo['valore'])}",
                    styles["Field"],
                )
            )

        return

    # Nodo contenitore
    if label:
        story.append(
            Paragraph(
                _safe(label),
                styles["NodeTitle"],
            )
        )

    if testo:
        story.append(
            Paragraph(
                _safe(testo),
                styles["Value"],
            )
        )

    for attributo in attributi:
        story.append(
            Paragraph(
                f"<b>{_safe(attributo['label'])}:</b> "
                f"{_safe(attributo['valore'])}",
                styles["Field"],
            )
        )

    story.append(
        Indenter(left=5 * mm)
    )

    for figlio in figli:
        _aggiungi_nodo(
            story,
            figlio,
            styles,
            livello + 1,
        )

    story.append(
        Indenter(left=-5 * mm)
    )


def genera_pdf_registro_imprese(visura):
    """
    Genera il PDF a partire dall'XML originale
    dell'acquisizione Registro Imprese.

    La struttura è volutamente generica per preservare
    tutti i dati restituiti dall'e-service.
    """
    documento = prepara_documento_registro_imprese(
        visura.xml_originale
    )

    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=(
            f"Registro Imprese - "
            f"{visura.denominazione or visura.codice_fiscale}"
        ),
        author="Servizi Imprese",
    )

    base = getSampleStyleSheet()

    styles = {
        "Title": ParagraphStyle(
            "RiTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
            textColor=colors.HexColor("#1f2937"),
        ),

        "Subtitle": ParagraphStyle(
            "RiSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
            spaceAfter=7 * mm,
        ),

        "Company": ParagraphStyle(
            "RiCompany",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            spaceAfter=5 * mm,
            textColor=colors.HexColor("#111827"),
        ),

        "Section": ParagraphStyle(
            "RiSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
            textColor=colors.HexColor("#1f4f7a"),
        ),

        "NodeTitle": ParagraphStyle(
            "RiNodeTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            spaceBefore=3 * mm,
            spaceAfter=1 * mm,
            textColor=colors.HexColor("#333333"),
        ),

        "Field": ParagraphStyle(
            "RiField",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            spaceAfter=1.5 * mm,
        ),

        "Value": ParagraphStyle(
            "RiValue",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            spaceAfter=2 * mm,
        ),
    }

    story = []

    story.append(
        Paragraph(
            "Registro Imprese",
            styles["Title"],
        )
    )

    story.append(
        Paragraph(
            "Dati impresa",
            styles["Subtitle"],
        )
    )

    story.append(
        Paragraph(
            _safe(
                visura.denominazione
                or visura.soggetto.denominazione
                or visura.codice_fiscale
            ),
            styles["Company"],
        )
    )

    if visura.codice_fiscale:
        story.append(
            Paragraph(
                f"<b>Codice fiscale:</b> "
                f"{_safe(visura.codice_fiscale)}",
                styles["Field"],
            )
        )

    if visura.partita_iva:
        story.append(
            Paragraph(
                f"<b>Partita IVA:</b> "
                f"{_safe(visura.partita_iva)}",
                styles["Field"],
            )
        )

    if visura.cciaa or visura.numero_rea:
        rea = " ".join(
            x
            for x in [
                visura.cciaa,
                visura.numero_rea,
            ]
            if x
        )

        story.append(
            Paragraph(
                f"<b>REA:</b> {_safe(rea)}",
                styles["Field"],
            )
        )

    if visura.pec:
        story.append(
            Paragraph(
                f"<b>PEC:</b> {_safe(visura.pec)}",
                styles["Field"],
            )
        )

    acquisito = timezone.localtime(
        visura.acquisito_il
    ).strftime("%d/%m/%Y %H:%M")

    story.append(
        Paragraph(
            f"<b>Dati acquisiti il:</b> {acquisito}",
            styles["Field"],
        )
    )

    story.append(
        Spacer(1, 5 * mm)
    )

    for sezione in documento["sezioni"]:
        story.append(
            Paragraph(
                _safe(sezione["titolo"]),
                styles["Section"],
            )
        )

        for nodo in sezione["blocchi"]:

            # Evita solo la duplicazione del titolo principale
            # della sezione.
            if (
                nodo.get("label", "").strip().lower()
                == sezione["titolo"].strip().lower()
            ):
                for attributo in nodo.get(
                    "attributi",
                    [],
                ):
                    story.append(
                        Paragraph(
                            f"<b>{_safe(attributo['label'])}:</b> "
                            f"{_safe(attributo['valore'])}",
                            styles["Field"],
                        )
                    )

                if nodo.get("testo"):
                    story.append(
                        Paragraph(
                            _safe(nodo["testo"]),
                            styles["Value"],
                        )
                    )

                for figlio in nodo.get(
                    "figli",
                    [],
                ):
                    _aggiungi_nodo(
                        story,
                        figlio,
                        styles,
                    )

            else:
                _aggiungi_nodo(
                    story,
                    nodo,
                    styles,
                )

    pdf.build(
        story,
        onFirstPage=_numero_pagina,
        onLaterPages=_numero_pagina,
    )

    return buffer.getvalue()
