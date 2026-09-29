from .models import ConfigurazioneEnte


def configurazione_ente(request):
    return {
        "configurazione_ente": ConfigurazioneEnte.objects.first(),
    }
