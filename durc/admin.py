from django.contrib import admin

from .models import (
    AuditLog,
    ConfigurazioneEnte,
    ConfigurazionePDND,
    ConfigurazioneRegistroImprese,
    Durc,
    Soggetto,
    VisuraRegistroImprese,
)


@admin.register(Soggetto)
class SoggettoAdmin(admin.ModelAdmin):
    list_display = (
        "denominazione",
        "codice_fiscale",
        "partita_iva",
        "aggiornato_il",
    )
    search_fields = (
        "denominazione",
        "codice_fiscale",
        "partita_iva",
    )


@admin.register(Durc)
class DurcAdmin(admin.ModelAdmin):
    list_display = (
        "soggetto",
        "protocollo",
        "stato",
        "data_documento",
        "data_scadenza",
        "acquisito_il",
        "richiesto_da",
    )

    list_filter = (
        "stato",
        "data_scadenza",
        "acquisito_il",
    )

    search_fields = (
        "soggetto__codice_fiscale",
        "soggetto__partita_iva",
        "soggetto__denominazione",
        "protocollo",
    )

    readonly_fields = (
        "acquisito_il",
        "pdf_sha256",
        "pdnd_request_id",
        "http_status",
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "utente",
        "azione",
        "soggetto",
        "durc",
        "indirizzo_ip",
    )

    list_filter = (
        "azione",
        "timestamp",
    )

    search_fields = (
        "soggetto__codice_fiscale",
        "soggetto__denominazione",
        "utente__username",
    )

    readonly_fields = (
        "timestamp",
    )
import os


@admin.register(ConfigurazionePDND)
class ConfigurazionePDNDAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "client_id",
        "purpose_id",
        "kid",
        "attiva",
        "chiave_privata_presente",
        "aggiornato_il",
    )

    readonly_fields = (
        "chiave_privata_presente",
        "aggiornato_il",
    )

    fieldsets = (
        (
            "Configurazione",
            {
		"fields": (
   		 "nome",
		 "attiva",
		 "client_id",
   		 "purpose_id",
   		 "kid",
   		 "alg",
   		 "typ",
    		 "iss",
   		 "sub",
   		 "aud",
   		 "audience",
   		 "url_autenticazione",
   		 "url_servizio_durc",
   		 "versione_eservice",
	)               

            },
        ),
        (
            "Chiave privata",
            {
                "fields": (
                    "percorso_chiave_privata",
                    "chiave_privata_presente",
                )
            },
        ),
        (
            "Informazioni",
            {
                "fields": (
                    "aggiornato_il",
                )
            },
        ),
    )

    @admin.display(
        boolean=True,
        description="Chiave privata presente",
    )
    def chiave_privata_presente(self, obj):
        if not obj or not obj.percorso_chiave_privata:
            return False

        return os.path.isfile(obj.percorso_chiave_privata)


@admin.register(ConfigurazioneEnte)
class ConfigurazioneEnteAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Applicazione",
            {
                "fields": (
                    "nome_applicazione",
                    "sottotitolo_applicazione",
                    "descrizione_applicazione",
                )
            },
        ),
        (
            "Identità dell'ente",
            {
                "fields": (
                    "nome_ente",
                    "nome_breve_ente",
                    "sito_istituzionale",
                )
            },
        ),
        (
            "Dati istituzionali",
            {
                "fields": (
                    "codice_fiscale",
                    "partita_iva",
                    "codice_ipa",
                    "codice_univoco_ufficio",
                )
            },
        ),
        (
            "Parametri applicativi",
            {
                "fields": (
                    "max_pdf_durc_per_soggetto",
                )
            },
        ),
        (
            "Sede",
            {
                "fields": (
                    "indirizzo",
                    "cap",
                    "comune",
                    "provincia",
                )
            },
        ),
        (
            "Contatti",
            {
                "fields": (
                    "pec",
                    "email",
                    "telefono",
                )
            },
        ),
        (
            "Link istituzionali",
            {
                "fields": (
                    "url_privacy",
                    "url_cookie",
                    "url_accessibilita",
                    "url_note_legali",
                    "url_amministrazione_trasparente",
                    "url_albo_pretorio",
                )
            },
        ),
        (
            "Footer",
            {
                "fields": (
                    "testo_footer",
                )
            },
        ),
        (
            "Informazioni",
            {
                "fields": (
                    "aggiornato_il",
                )
            },
        ),
    )

    readonly_fields = ("aggiornato_il",)

    def has_add_permission(self, request):
        if ConfigurazioneEnte.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConfigurazioneRegistroImprese)
class ConfigurazioneRegistroImpreseAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "ambiente",
        "attiva",
        "chiave_privata_presente",
        "configurazione_completa",
        "ultimo_voucher_ok",
        "ultima_chiamata_ok",
        "aggiornato_il",
    )

    readonly_fields = (
        "chiave_privata_presente",
        "configurazione_completa",
        "endpoint_status",
        "endpoint_ricerca_cf",
        "endpoint_dettaglio_cf",
        "ultimo_voucher_ok",
        "ultima_chiamata_ok",
        "ultimo_errore",
        "aggiornato_il",
    )

    fieldsets = (
        (
            "Configurazione",
            {
                "fields": (
                    "nome",
                    "ambiente",
                    "attiva",
                    "timeout_secondi",
                )
            },
        ),
        (
            "Parametri PDND",
            {
                "fields": (
                    "client_id",
                    "purpose_id",
                    "kid",
                    "alg",
                    "typ",
                    "iss",
                    "sub",
                    "aud",
                    "audience",
                    "url_autenticazione",
                )
            },
        ),
        (
            "Registro Imprese",
            {
                "fields": (
                    "url_base_servizio",
                    "endpoint_status",
                    "endpoint_ricerca_cf",
                    "endpoint_dettaglio_cf",
                )
            },
        ),
        (
            "Chiave privata",
            {
                "fields": (
                    "percorso_chiave_privata",
                    "chiave_privata_presente",
                )
            },
        ),
        (
            "Stato",
            {
                "fields": (
                    "configurazione_completa",
                    "ultimo_voucher_ok",
                    "ultima_chiamata_ok",
                    "ultimo_errore",
                    "aggiornato_il",
                )
            },
        ),
    )

    @admin.display(boolean=True, description="Chiave privata presente")
    def chiave_privata_presente(self, obj):
        if not obj or not obj.percorso_chiave_privata:
            return False
        return os.path.isfile(obj.percorso_chiave_privata)

    @admin.display(boolean=True, description="Configurazione completa")
    def configurazione_completa(self, obj):
        if not obj:
            return False
        campi = (
            obj.client_id,
            obj.purpose_id,
            obj.kid,
            obj.iss,
            obj.sub,
            obj.aud,
            obj.url_autenticazione,
            obj.url_base_servizio,
            obj.percorso_chiave_privata,
        )
        return all(campi)

    @admin.display(description="Endpoint stato")
    def endpoint_status(self, obj):
        if not obj or not obj.url_base_servizio:
            return "-"
        return obj.url_base_servizio.rstrip("/") + "/rest/pcad/v1/status"

    @admin.display(description="Endpoint ricerca CF")
    def endpoint_ricerca_cf(self, obj):
        if not obj or not obj.url_base_servizio:
            return "-"
        return obj.url_base_servizio.rstrip("/") + "/rest/pcad/v1/ricerca/codicefiscale"

    @admin.display(description="Endpoint dettaglio CF")
    def endpoint_dettaglio_cf(self, obj):
        if not obj or not obj.url_base_servizio:
            return "-"
        return obj.url_base_servizio.rstrip("/") + "/rest/pcad/v1/dettaglio/codicefiscale"


@admin.register(VisuraRegistroImprese)
class VisuraRegistroImpreseAdmin(admin.ModelAdmin):
    list_display = (
        "acquisito_il",
        "denominazione",
        "codice_fiscale",
        "partita_iva",
        "cciaa",
        "numero_rea",
        "pec",
        "stato_impresa",
        "richiesto_da",
    )

    list_filter = (
        "stato_impresa",
        "sede_provincia",
        "acquisito_il",
    )

    search_fields = (
        "denominazione",
        "codice_fiscale",
        "partita_iva",
        "numero_rea",
        "pec",
        "soggetto__denominazione",
        "soggetto__codice_fiscale",
    )

    readonly_fields = (
        "acquisito_il",
        "xml_originale",
        "http_status",
        "pdnd_request_id",
    )

    fieldsets = (
        (
            "Impresa",
            {
                "fields": (
                    "soggetto",
                    "denominazione",
                    "codice_fiscale",
                    "partita_iva",
                    "cciaa",
                    "numero_rea",
                    "forma_giuridica",
                    "stato_impresa",
                    "pec",
                )
            },
        ),
        (
            "Sede legale",
            {
                "fields": (
                    "sede_toponimo",
                    "sede_via",
                    "sede_civico",
                    "sede_cap",
                    "sede_comune",
                    "sede_provincia",
                    "sede_frazione",
                    "sede_stato",
                )
            },
        ),
        (
            "Acquisizione",
            {
                "fields": (
                    "richiesto_da",
                    "acquisito_il",
                    "http_status",
                    "pdnd_request_id",
                    "note",
                )
            },
        ),
        (
            "Risposta originale Registro Imprese",
            {
                "fields": (
                    "xml_originale",
                ),
                "classes": ("collapse",),
            },
        ),
    )
