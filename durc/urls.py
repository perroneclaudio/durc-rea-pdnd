from django.urls import path

from . import views

app_name = "durc"

urlpatterns = [
    path(
        "soggetto/crea/",
        views.crea_soggetto_minimo,
        name="crea_soggetto_minimo",
    ),
    path(
        "durc/<int:pk>/pdf/",
        views.durc_pdf,
        name="durc_pdf",
    ),
    path(
        "soggetto/<int:pk>/registro-imprese/pdf/",
        views.registro_imprese_pdf_ultima,
        name="registro_imprese_pdf_ultima",
    ),
    path(
        "registro-imprese/acquisizione/<int:pk>/",
        views.registro_imprese_dettaglio,
        name="registro_imprese_dettaglio",
    ),
    path(
    "consulta-cf/",
    views.consulta_durc_codice_fiscale,
    name="consulta_durc_codice_fiscale",
),
    path(
        "registro-imprese/consulta-cf/",
        views.consulta_registro_imprese_codice_fiscale,
        name="consulta_registro_imprese_codice_fiscale",
    ),
    path(
        "registro-imprese/ricerca-denominazione/",
        views.ricerca_registro_imprese_denominazione_view,
        name="ricerca_registro_imprese_denominazione",
    ),
    path("", views.dashboard, name="dashboard"),
    path("soggetto/<int:pk>/", views.soggetto_detail, name="soggetto_detail"),
    path(
        "soggetto/<int:pk>/consulta/",
        views.consulta_durc_soggetto,
        name="consulta_durc_soggetto",
    ),
    path(
        "soggetto/<int:pk>/registro-imprese/consulta/",
        views.consulta_registro_imprese_soggetto,
        name="consulta_registro_imprese_soggetto",
    ),
]
