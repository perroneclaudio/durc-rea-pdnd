from pathlib import Path

from django.conf import settings
from django.db import models
from django.core.files.storage import FileSystemStorage
from django.utils import timezone


class Soggetto(models.Model):
    codice_fiscale = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        verbose_name="Codice fiscale",
    )
    partita_iva = models.CharField(
        max_length=11,
        blank=True,
        db_index=True,
        verbose_name="Partita IVA",
    )
    denominazione = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )
    note = models.TextField(blank=True)

    creato_il = models.DateTimeField(auto_now_add=True)
    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["denominazione", "codice_fiscale"]
        verbose_name = "Soggetto"
        verbose_name_plural = "Soggetti"

    def save(self, *args, **kwargs):
        self.codice_fiscale = self.codice_fiscale.strip().upper()
        self.partita_iva = self.partita_iva.strip()
        self.denominazione = self.denominazione.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.denominazione:
            return f"{self.denominazione} - {self.codice_fiscale}"
        return self.codice_fiscale


def durc_pdf_storage():
    return FileSystemStorage(location=settings.DURC_PDF_ROOT)


def durc_pdf_path(instance, filename):
    anno = timezone.localdate().year
    cf = instance.soggetto.codice_fiscale
    protocollo = instance.protocollo or "senza_protocollo"
    estensione = Path(filename).suffix.lower() or ".pdf"

    return f"{cf}/{anno}/{protocollo}{estensione}"


class Durc(models.Model):

    class Stato(models.TextChoices):
        REGOLARE = "REGOLARE", "Regolare"
        IRREGOLARE = "IRREGOLARE", "Non regolare"
        NON_EFFETTUABILE = "NON_EFFETTUABILE", "Verifica non effettuabile"
        SCONOSCIUTO = "SCONOSCIUTO", "Stato non determinato"

    class EsitoEnte(models.IntegerChoices):
        REGOLARE = 0, "Regolare"
        IRREGOLARE = 1, "Irregolare"
        NON_EFFETTUABILE = 2, "Non effettuabile"

    soggetto = models.ForeignKey(
        Soggetto,
        on_delete=models.PROTECT,
        related_name="durc",
    )

    protocollo = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    denominazione = models.CharField(
        max_length=255,
        blank=True,
    )

    data_documento = models.DateField(
        null=True,
        blank=True,
    )

    data_scadenza = models.DateField(
        null=True,
        blank=True,
        db_index=True,
    )

    stato = models.CharField(
        max_length=25,
        choices=Stato.choices,
        default=Stato.SCONOSCIUTO,
        db_index=True,
    )

    esito_inps = models.SmallIntegerField(
        choices=EsitoEnte.choices,
        null=True,
        blank=True,
    )

    esito_inail = models.SmallIntegerField(
        choices=EsitoEnte.choices,
        null=True,
        blank=True,
    )

    esito_cassa_edile = models.SmallIntegerField(
        choices=EsitoEnte.choices,
        null=True,
        blank=True,
    )

    pdf = models.FileField(
        upload_to=durc_pdf_path,
        storage=durc_pdf_storage,
        blank=True,
    )

    pdf_sha256 = models.CharField(
        max_length=64,
        blank=True,
    )

    pdnd_request_id = models.CharField(
        max_length=255,
        blank=True,
    )

    http_status = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    risposta_inps = models.JSONField(
        default=dict,
        blank=True,
    )

    richiesto_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="durc_richiesti",
    )

    acquisito_il = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-acquisito_il"]
        verbose_name = "DURC"
        verbose_name_plural = "DURC"
        indexes = [
            models.Index(fields=["soggetto", "-acquisito_il"]),
            models.Index(fields=["stato", "data_scadenza"]),
        ]

    @property
    def giorni_alla_scadenza(self):
        if not self.data_scadenza:
            return None
        return (self.data_scadenza - timezone.localdate()).days

    @property
    def stato_scadenza(self):
        giorni = self.giorni_alla_scadenza

        if giorni is None:
            return "SCADENZA_SCONOSCIUTA"

        if giorni < 0:
            return "SCADUTO"

        if giorni <= 30:
            return "IN_SCADENZA"

        return "VALIDO"

    def __str__(self):
        protocollo = self.protocollo or "senza protocollo"
        return f"{self.soggetto.codice_fiscale} - {protocollo}"


class AuditLog(models.Model):

    class Azione(models.TextChoices):
        RICERCA = "RICERCA", "Ricerca"
        CONSULTAZIONE_PDND = "CONSULTAZIONE_PDND", "Consultazione PDND"
        DOWNLOAD_PDF = "DOWNLOAD_PDF", "Download PDF"
        VISUALIZZAZIONE = "VISUALIZZAZIONE", "Visualizzazione DURC"
        MODIFICA = "MODIFICA", "Modifica"
        ALTRO = "ALTRO", "Altro"

    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    azione = models.CharField(
        max_length=30,
        choices=Azione.choices,
        db_index=True,
    )

    soggetto = models.ForeignKey(
        Soggetto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    durc = models.ForeignKey(
        Durc,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    indirizzo_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    dettagli = models.JSONField(
        default=dict,
        blank=True,
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Log DURC"
        verbose_name_plural = "Log DURC"

    def __str__(self):
        return f"{self.timestamp} - {self.azione}"
class ConfigurazionePDND(models.Model):
    nome = models.CharField(
        max_length=100,
        default="Configurazione principale",
    )

    client_id = models.CharField(
        max_length=255,
        blank=True,
    )

    purpose_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Purpose ID",
    )

    kid = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="KID",
    )

    alg = models.CharField(
        max_length=20,
        default="RS256",
        verbose_name="Algoritmo (alg)",
    )

    typ = models.CharField(
        max_length=20,
        default="JWT",
        verbose_name="Tipo token (typ)",
    )

    iss = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Issuer (iss)",
    )

    sub = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Subject (sub)",
    )

    aud = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Audience autenticazione (aud)",
    )

    audience = models.CharField(
        max_length=500,
        blank=True,
    )

    url_autenticazione = models.URLField(
        max_length=500,
        blank=True,
    )

    url_servizio_durc = models.URLField(
        max_length=500,
        blank=True,
    )

    versione_eservice = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Versione e-service",
    )

    percorso_chiave_privata = models.CharField(
        max_length=500,
        default="/run/secrets/pdnd_private_key.pem",
        help_text="Percorso interno al container. La chiave non viene salvata nel database.",
    )

    attiva = models.BooleanField(
        default=False,
    )

    aggiornato_il = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Configurazione DURC"
        verbose_name_plural = "Configurazione DURC"

    def __str__(self):
        return self.nome


class ConfigurazioneEnte(models.Model):
    # Identità dell'applicazione
    nome_applicazione = models.CharField(
        max_length=150,
        verbose_name="Nome applicazione",
    )
    sottotitolo_applicazione = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Sottotitolo applicazione",
    )
    descrizione_applicazione = models.TextField(
        blank=True,
        verbose_name="Descrizione applicazione",
    )

    # Identità dell'ente
    nome_ente = models.CharField(
        max_length=255,
        verbose_name="Nome ente",
    )
    nome_breve_ente = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nome breve ente",
    )
    sito_istituzionale = models.URLField(
        blank=True,
        verbose_name="Sito istituzionale",
    )

    # Dati istituzionali
    codice_fiscale = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="Codice fiscale",
    )
    partita_iva = models.CharField(
        max_length=11,
        blank=True,
        verbose_name="Partita IVA",
    )
    codice_ipa = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Codice IPA",
    )
    codice_univoco_ufficio = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Codice univoco ufficio",
    )

    # Parametri applicativi
    max_pdf_durc_per_soggetto = models.PositiveIntegerField(
        default=10,
        verbose_name="Numero massimo PDF DURC per soggetto",
        help_text=(
            "Numero massimo di PDF DURC conservati fisicamente "
            "per ciascun soggetto. Lo storico dei record DURC "
            "rimane comunque nel database."
        ),
    )

    # Sede e contatti
    indirizzo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Indirizzo",
    )
    cap = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="CAP",
    )
    comune = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Comune",
    )
    provincia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Provincia",
    )
    pec = models.EmailField(
        blank=True,
        verbose_name="PEC",
    )
    email = models.EmailField(
        blank=True,
        verbose_name="Email",
    )
    telefono = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Telefono",
    )

    # Link istituzionali
    url_privacy = models.URLField(
        blank=True,
        verbose_name="Privacy",
    )
    url_cookie = models.URLField(
        blank=True,
        verbose_name="Cookie policy",
    )
    url_accessibilita = models.URLField(
        blank=True,
        verbose_name="Dichiarazione di accessibilità",
    )
    url_note_legali = models.URLField(
        blank=True,
        verbose_name="Note legali",
    )
    url_amministrazione_trasparente = models.URLField(
        blank=True,
        verbose_name="Amministrazione trasparente",
    )
    url_albo_pretorio = models.URLField(
        blank=True,
        verbose_name="Albo pretorio",
    )

    # Footer
    testo_footer = models.TextField(
        blank=True,
        verbose_name="Testo aggiuntivo footer",
    )

    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configurazione ente"
        verbose_name_plural = "Configurazione ente"

    def save(self, *args, **kwargs):
        # Configurazione singleton: esiste sempre e soltanto il record con pk=1.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Evita la cancellazione accidentale della configurazione generale.
        return

    def __str__(self):
        return self.nome_ente or self.nome_applicazione


class ConfigurazioneRegistroImprese(models.Model):
    class Ambiente(models.TextChoices):
        COLLAUDO = "COLLAUDO", "Collaudo"
        PRODUZIONE = "PRODUZIONE", "Produzione"

    nome = models.CharField(
        max_length=100,
        default="Configurazione principale",
    )

    ambiente = models.CharField(
        max_length=20,
        choices=Ambiente.choices,
        default=Ambiente.PRODUZIONE,
    )

    # Parametri PDND
    client_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Client ID",
    )
    purpose_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Purpose ID",
    )
    kid = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="KID",
    )
    alg = models.CharField(
        max_length=20,
        default="RS256",
        verbose_name="Algoritmo (alg)",
    )
    typ = models.CharField(
        max_length=20,
        default="JWT",
        verbose_name="Tipo token (typ)",
    )
    iss = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Issuer (iss)",
    )
    sub = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Subject (sub)",
    )
    aud = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Audience autenticazione (aud)",
    )
    audience = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Audience e-service",
    )

    # Endpoint
    url_autenticazione = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL autenticazione PDND",
    )
    url_base_servizio = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL base Registro Imprese",
        help_text="Esempio produzione: https://pdnd.registroimprese.it",
    )

    percorso_chiave_privata = models.CharField(
        max_length=500,
        default="/run/secrets/pdnd_private_key.pem",
        help_text="Percorso interno al container. La chiave non viene salvata nel database.",
    )

    timeout_secondi = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Timeout HTTP (secondi)",
    )

    attiva = models.BooleanField(
        default=False,
    )

    ultimo_voucher_ok = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Ultimo voucher ottenuto",
    )
    ultima_chiamata_ok = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Ultima chiamata riuscita",
    )
    ultimo_errore = models.TextField(
        blank=True,
        editable=False,
        verbose_name="Ultimo errore",
    )

    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configurazione Registro Imprese"
        verbose_name_plural = "Configurazione Registro Imprese"

    def __str__(self):
        return f"{self.nome} - {self.get_ambiente_display()}"


class VisuraRegistroImprese(models.Model):
    soggetto = models.ForeignKey(
        Soggetto,
        on_delete=models.PROTECT,
        related_name="visure_registro_imprese",
    )

    # Dati principali estratti dalla risposta
    denominazione = models.CharField(max_length=255, blank=True)
    codice_fiscale = models.CharField(max_length=16, blank=True, db_index=True)
    partita_iva = models.CharField(max_length=11, blank=True, db_index=True)

    cciaa = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="CCIAA",
    )
    numero_rea = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        verbose_name="Numero REA",
    )

    forma_giuridica = models.CharField(max_length=255, blank=True)
    stato_impresa = models.CharField(max_length=100, blank=True)

    # PEC risultante dal Registro Imprese al momento dell'acquisizione
    pec = models.EmailField(
        blank=True,
        db_index=True,
        verbose_name="PEC",
    )

    # Sede legale
    sede_comune = models.CharField(max_length=150, blank=True)
    sede_provincia = models.CharField(max_length=10, blank=True)
    sede_toponimo = models.CharField(max_length=100, blank=True)
    sede_via = models.CharField(max_length=255, blank=True)
    sede_civico = models.CharField(max_length=50, blank=True)
    sede_cap = models.CharField(max_length=10, blank=True)
    sede_frazione = models.CharField(max_length=150, blank=True)
    sede_stato = models.CharField(max_length=150, blank=True)

    # Risposta originale: fonte completa e immutata dell'acquisizione.
    xml_originale = models.TextField()

    http_status = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    pdnd_request_id = models.CharField(
        max_length=255,
        blank=True,
    )

    richiesto_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visure_registro_imprese_richieste",
    )

    acquisito_il = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-acquisito_il"]
        verbose_name = "Log Registro Imprese"
        verbose_name_plural = "Log Registro Imprese"
        indexes = [
            models.Index(fields=["soggetto", "-acquisito_il"]),
        ]

    def __str__(self):
        descrizione = self.denominazione or self.codice_fiscale or str(self.soggetto)
        return f"{descrizione} - {self.acquisito_il:%d/%m/%Y %H:%M}"
