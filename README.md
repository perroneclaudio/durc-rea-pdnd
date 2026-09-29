<img width="558" height="202" alt="image" src="https://github.com/user-attachments/assets/891bd846-0551-4c75-bb2c-59bfe1a1a401" />



# DURC / Registro Imprese via PDND

Applicazione web Django per la consultazione di servizi della **PDND – Piattaforma Digitale Nazionale Dati**, con particolare riferimento a:

- **DURC in corso di validità**
- **Registro Imprese**

Le due consultazioni sono indipendenti: un soggetto può essere consultato ai fini DURC anche se non risulta iscritto al Registro Imprese.

---

## Funzionalità principali

### DURC

- consultazione per codice fiscale tramite PDND / INPS;
- consultazione dalla scheda del soggetto;
- creazione di uno storico distinto per ogni acquisizione;
- conservazione della risposta JSON originale restituita da INPS;
- memorizzazione di protocollo, data documento, data scadenza ed esiti INPS / INAIL / Cassa Edile;
- download automatico del PDF quando disponibile;
- validazione minima del contenuto PDF;
- calcolo e memorizzazione dell'hash SHA-256;
- archivio PDF persistente su volume Docker dedicato;
- download autenticato del PDF dall'interfaccia;
- retention configurabile dei PDF per singolo soggetto;
- tracciamento delle consultazioni DURC e dei download PDF tramite `AuditLog`.

### Registro Imprese

- ricerca per codice fiscale;
- ricerca per denominazione, con provincia opzionale;
- acquisizione del dettaglio impresa;
- salvataggio dello storico delle acquisizioni;
- conservazione dell'XML originale ricevuto dal servizio;
- estrazione e visualizzazione strutturata dei principali dati dell'impresa;
- generazione PDF della più recente acquisizione Registro Imprese;
- configurazione PDND indipendente da quella DURC.

### Applicazione

- gestione dei soggetti;
- ricerca locale per codice fiscale, partita IVA e denominazione;
- autenticazione locale Django;
- autenticazione LDAP / Active Directory opzionale;
- configurazione applicativa tramite Django Admin;
- PostgreSQL come database;
- esecuzione tramite Docker Compose;
- file statici gestiti tramite WhiteNoise;
- container web eseguito con utente non privilegiato.

---

## Principio di funzionamento

`Soggetto` è l'entità centrale dell'applicazione.

Le consultazioni esterne **DURC** e **Registro Imprese** sono volutamente indipendenti. Il Registro Imprese non costituisce un prerequisito per la consultazione del DURC.

Ogni nuova acquisizione viene conservata come record storico distinto: una nuova risposta non sovrascrive quella precedente.

---

## Stack tecnologico

- Python 3.12
- Django 5.2
- PostgreSQL 17
- Gunicorn
- WhiteNoise
- Docker / Docker Compose
- Requests
- PyJWT
- django-auth-ldap
- ReportLab

Le versioni effettivamente installate sono definite in [`requirements.txt`](requirements.txt).

---

# Installazione

Il progetto può essere eseguito sia su **Linux** sia su **Windows tramite Docker Desktop**.

La configurazione Docker predefinita pubblica l'applicazione su:

```text
127.0.0.1:10006
```

quindi, senza modifiche, l'applicazione è raggiungibile **solo dal computer host** su:

```text
http://localhost:10006
```

Questa impostazione è adatta sia a un'installazione locale sia a un server pubblicato tramite reverse proxy.

---

## Installazione su Linux

### 1. Prerequisiti

Sono necessari:

- Docker Engine;
- Docker Compose v2;
- Git.

Per utilizzare effettivamente gli e-service PDND servono inoltre i relativi client, finalità, autorizzazioni e materiale crittografico.

Per il DURC INPS possono essere richieste procedure di abilitazione ulteriori rispetto alla normale configurazione PDND.

### 2. Clonare il repository

```bash
git clone https://github.com/perroneclaudio/durc-rea-pdnd.git
cd durc-rea-pdnd
```

### 3. Creare il file `.env`

```bash
cp .env.example .env
```

Configurazione minima per un utilizzo locale:

```env
# Django
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:10006

# PostgreSQL
POSTGRES_DB=durc
POSTGRES_USER=durc
POSTGRES_PASSWORD=change-me
DB_HOST=db
DB_PORT=5432

# LDAP / Active Directory
LDAP_ENABLED=false
LDAP_SERVER_URI=ldap://dc1.example.local:389
LDAP_SERVER_URI_BACKUP=ldap://dc2.example.local:389
LDAP_UPN_DOMAIN=example.local
LDAP_START_TLS=false
LDAP_NETWORK_TIMEOUT=5
LDAP_TIMEOUT=5
```

Per generare una chiave Django casuale:

```bash
openssl rand -base64 48
```

Il file `.env` è escluso dal repository.

> **Nota PostgreSQL**
>
> L'healthcheck del `docker-compose.yml` usa `pg_isready -U durc -d durc`.
> Per l'installazione standard è quindi opportuno mantenere `POSTGRES_USER=durc` e `POSTGRES_DB=durc`.
> Se questi valori vengono modificati, deve essere aggiornato anche l'healthcheck.

### 4. Preparare la directory delle chiavi

```bash
mkdir -p secrets
chmod 700 secrets
```

Il `docker-compose.yml` monta la directory in sola lettura all'interno del container come:

```text
/run/secrets
```

Esempi di percorsi interni:

```text
/run/secrets/pdnd_private_key.pem
/run/secrets/pdnd_registro_imprese_private_key.pem
```

I nomi dei file non sono obbligatori: il percorso effettivo viene configurato dalla Django Admin.

DURC e Registro Imprese possono utilizzare chiavi distinte.

### 5. Build e avvio

```bash
docker compose up -d --build
docker compose ps
```

### 6. Applicare le migration

```bash
docker compose exec web python manage.py migrate
```

### 7. Creare il primo amministratore

```bash
docker compose exec web python manage.py createsuperuser
```

### 8. Verificare l'installazione

```bash
docker compose exec web python manage.py check
```

Aprire quindi:

```text
http://localhost:10006
```

Django Admin:

```text
http://localhost:10006/admin/
```

---

## Installazione su Windows con Docker Desktop

### 1. Prerequisiti

Sono necessari:

- Docker Desktop con motore Linux avviato;
- Git for Windows;
- PowerShell.

Verificare Docker con:

```powershell
docker version
```

L'output deve contenere sia la sezione **Client** sia la sezione **Server**.

### 2. Clonare il repository

```powershell
cd $HOME
git clone https://github.com/perroneclaudio/durc-rea-pdnd.git
cd durc-rea-pdnd
```

### 3. Creare il file `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Per un utilizzo locale senza reverse proxy:

```env
# Django
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:10006

# PostgreSQL
POSTGRES_DB=durc
POSTGRES_USER=durc
POSTGRES_PASSWORD=change-me
DB_HOST=db
DB_PORT=5432

# LDAP / Active Directory
LDAP_ENABLED=false
LDAP_SERVER_URI=ldap://dc1.example.local:389
LDAP_SERVER_URI_BACKUP=ldap://dc2.example.local:389
LDAP_UPN_DOMAIN=example.local
LDAP_START_TLS=false
LDAP_NETWORK_TIMEOUT=5
LDAP_TIMEOUT=5
```

Con `LDAP_ENABLED=false` i valori LDAP di esempio non vengono utilizzati.

### 4. Creare la directory delle chiavi

```powershell
New-Item -ItemType Directory -Force secrets
```

### 5. Build e avvio

```powershell
docker compose up -d --build
docker compose ps
```

### 6. Applicare le migration

```powershell
docker compose exec web python manage.py migrate
```

### 7. Creare il primo amministratore

```powershell
docker compose exec web python manage.py createsuperuser
```

### 8. Verificare l'installazione

```powershell
docker compose exec web python manage.py check
```

Aprire quindi:

```text
http://localhost:10006
```

Django Admin:

```text
http://localhost:10006/admin/
```

Non è necessario configurare un reverse proxy per l'utilizzo locale.

---

# Configurazione iniziale

Dalla Django Admin devono essere configurati almeno:

- **Configurazione ente**;
- **Configurazione DURC**;
- **Configurazione Registro Imprese**, se il relativo servizio viene utilizzato;
- utenti applicativi.

Le chiavi private non vengono memorizzate nel database: viene salvato soltanto il percorso del file presente nel container.

---

# Configurazione Ente

La configurazione dell'ente contiene:

- identità e denominazione dell'applicazione;
- dati dell'ente;
- codice fiscale dell'ente;
- sede e contatti;
- collegamenti istituzionali;
- testo del footer;
- parametri applicativi.

## Numero massimo di PDF DURC per soggetto

Il campo:

```text
Numero massimo PDF DURC per soggetto
```

controlla quanti PDF DURC vengono conservati fisicamente per ciascun soggetto.

Il valore predefinito è:

```text
10
```

Il limite è configurabile dalla Django Admin senza modificare il codice.

La modifica del valore viene applicata quando viene archiviato un nuovo PDF DURC per il soggetto interessato.

Lo **storico dei record DURC nel database non viene eliminato** dalla retention.

---

# Utenti e identità INPS

Gli utenti possono essere creati dalla Django Admin.

Per un utente locale sono normalmente utilizzati:

- **Nome utente**: username di accesso;
- **Password**: password Django;
- **Attivo**: deve essere abilitato;
- **Staff**: necessario solo per accedere alla Django Admin;
- **Email** e **Cognome**: utilizzabili normalmente.

## Campo `Nome`: codice fiscale dell'operatore

In questa applicazione il campo Django **Nome** (`first_name`) viene utilizzato intenzionalmente per memorizzare il **codice fiscale dell'operatore** inviato a INPS nell'header:

```text
INPS-Identity-UserId
```

Esempio fittizio:

```text
Nome utente: rossi.demo
Nome: ABCDEF12G34H567I
Cognome: Rossi
```

La logica è:

```text
campo Nome valorizzato
        ↓
INPS-Identity-UserId = valore del campo Nome

campo Nome vuoto
        ↓
INPS-Identity-UserId = codice fiscale dell'ente
```

Il valore viene normalizzato in maiuscolo.

Se il campo **Nome** è valorizzato ma non contiene esattamente 16 caratteri alfanumerici, la consultazione DURC viene bloccata.

Il fallback al codice fiscale dell'ente avviene soltanto quando il campo Nome è vuoto.

---

# Autenticazione

## Autenticazione locale

Con:

```env
LDAP_ENABLED=false
```

viene utilizzata l'autenticazione Django locale.

## LDAP / Active Directory

Per abilitare LDAP:

```env
LDAP_ENABLED=true
```

Sono configurabili:

- server LDAP principale;
- server LDAP secondario;
- dominio UPN;
- StartTLS opzionale;
- timeout di rete e LDAP.

Gli utenti LDAP **devono già esistere in Django**: l'applicazione non crea automaticamente nuovi utenti a partire da Active Directory.

Il backend `SelectiveLDAPBackend` distingue il metodo di autenticazione in base alla password dell'utente Django:

- password locale utilizzabile → autenticazione locale;
- password locale non utilizzabile → autenticazione LDAP.

Anche per gli utenti LDAP il campo Django **Nome** deve contenere il codice fiscale dell'operatore se si vuole trasmettere il CF personale a INPS. Se il campo è vuoto viene utilizzato il codice fiscale dell'ente.

## StartTLS

Per utilizzare StartTLS:

```env
LDAP_START_TLS=true
LDAP_SERVER_URI=ldap://dc1.example.local:389
```

Il container deve potersi fidare della CA che ha emesso il certificato del Domain Controller.

---

# Configurazione PDND – DURC

La sezione **Configurazione DURC** comprende i parametri necessari per ottenere il voucher PDND e invocare il servizio INPS:

- Client ID;
- Purpose ID;
- KID;
- algoritmo e tipo JWT;
- `iss`;
- `sub`;
- audience di autenticazione;
- audience dell'e-service;
- URL di autenticazione;
- URL del servizio DURC;
- versione e-service;
- percorso della chiave privata;
- stato attivo/non attivo.

L'applicazione utilizza la prima configurazione marcata come attiva.

## Attivazione dell'e-service DURC INPS

La normale configurazione su PDND può non essere sufficiente, da sola, per rendere operativo l'e-service DURC INPS.

Prima di diagnosticare come errore applicativo eventuali rifiuti del servizio, verificare le procedure operative richieste dal provider.

Riferimento pubblico utile:

<https://github.com/pagopa/pdnd-interop-frontend/issues/2226>

Le procedure esterne all'applicazione possono cambiare nel tempo: fare sempre riferimento alla documentazione ufficiale e alle indicazioni correnti del provider.

---

# Configurazione PDND – Registro Imprese

La configurazione Registro Imprese è indipendente da quella DURC e contiene i propri:

- Client ID;
- Purpose ID;
- KID;
- parametri JWT;
- audience;
- URL di autenticazione PDND;
- URL base del servizio;
- timeout HTTP;
- percorso della chiave privata;
- stato attivo/non attivo.

La Django Admin mostra inoltre:

- presenza della chiave privata;
- completezza della configurazione;
- ultimo voucher ottenuto;
- ultima chiamata riuscita;
- ultimo errore applicativo registrato.

L'URL base di produzione previsto dal modello è, ad esempio:

```text
https://pdnd.registroimprese.it
```

Devono comunque essere utilizzati i valori associati alla propria adesione PDND.

---

# Flusso DURC

La consultazione viene effettuata per codice fiscale.

Quando INPS restituisce un DURC disponibile:

1. viene creato un nuovo record `Durc`;
2. viene conservata la risposta JSON originale;
3. vengono salvati protocollo, date ed esiti;
4. viene registrato l'utente che ha effettuato la richiesta;
5. viene registrata la consultazione nell'audit;
6. viene richiesto il PDF tramite il servizio INPS;
7. il contenuto Base64 viene decodificato;
8. viene verificato che il contenuto inizi con una firma PDF valida;
9. viene calcolato l'hash SHA-256;
10. il PDF viene archiviato nel volume dedicato;
11. viene applicata la retention configurata per il soggetto.

Una nuova acquisizione non sovrascrive quella precedente.

È quindi possibile avere più record storici con lo stesso protocollo.

## DURC non disponibile

L'assenza di un DURC regolare in corso di validità **non equivale automaticamente a una dichiarazione di irregolarità contributiva**.

L'applicazione distingue il caso di DURC non disponibile dagli stati memorizzati per i documenti effettivamente acquisiti.

---

# Storico DURC e retention PDF

Lo storico DURC nel database non è limitato al numero di PDF conservati.

Per ogni acquisizione possono rimanere memorizzati:

- protocollo;
- denominazione;
- data documento;
- data scadenza;
- stato;
- esiti dei singoli enti;
- utente richiedente;
- data di acquisizione;
- risposta JSON INPS;
- HTTP status;
- hash SHA-256 del PDF, quando acquisito.

La retention riguarda invece il **file PDF fisico**.

Quando il numero dei PDF supera il limite configurato:

1. i record DURC restano nel database;
2. vengono mantenuti i PDF più recenti;
3. i PDF eccedenti vengono eliminati dallo storage;
4. il campo `pdf` dei record interessati viene svuotato;
5. l'hash SHA-256 già memorizzato viene mantenuto;
6. l'interfaccia non offre il download dei PDF non più presenti.

---

# Archivio PDF DURC

Nel container i PDF DURC vengono salvati sotto:

```text
/app/data/durc
```

La struttura dei file è:

```text
/app/data/durc/<CODICE_FISCALE>/<ANNO>/<PROTOCOLLO>.pdf
```

In caso di nomi già esistenti, lo storage Django può aggiungere automaticamente un suffisso al nome del file.

Lo storage è persistente tramite il volume:

```text
durc-pdf-data
```

L'immagine Docker prepara i percorsi scrivibili dell'applicazione per l'utente non privilegiato `appuser` (UID 1000).

È preferibile non eliminare manualmente i PDF dal volume, perché il relativo riferimento è memorizzato anche nel database.

---

# Registro Imprese

## Ricerca per codice fiscale

L'applicazione può interrogare il dettaglio Registro Imprese tramite codice fiscale.

Quando la risposta è valida:

- i dati principali vengono estratti e associati al soggetto;
- viene conservato l'XML originale ricevuto;
- viene creato un record storico `VisuraRegistroImprese`;
- possono essere visualizzati i dati strutturati dell'acquisizione.

## Ricerca per denominazione

È disponibile anche la ricerca per denominazione, con eventuale filtro per provincia.

La ricerca restituisce un elenco di imprese selezionabili per la successiva acquisizione del dettaglio.

## PDF Registro Imprese

L'applicazione può generare un PDF a partire dalla più recente acquisizione Registro Imprese disponibile per il soggetto.

Il PDF è generato dall'applicazione sulla base dei dati acquisiti e non sostituisce la fonte XML originale, che rimane conservata nello storico.

---

# Audit

Il modello `AuditLog` registra le principali operazioni DURC.

## Consultazioni DURC

Ogni richiesta DURC genera una voce con azione:

```text
CONSULTAZIONE_PDND
```

Nei dettagli vengono registrati, quando disponibili:

- servizio;
- codice fiscale consultato;
- esito applicativo;
- HTTP status;
- protocollo DURC.

## Download PDF DURC

Il download dall'interfaccia genera una voce con azione:

```text
DOWNLOAD_PDF
```

contenente, tra gli altri:

- utente;
- soggetto;
- DURC;
- timestamp;
- nome del file;
- SHA-256;
- indirizzo IP visto dall'applicazione.

Quando l'applicazione è dietro reverse proxy, `REMOTE_ADDR` può corrispondere al proxy o alla rete Docker. L'eventuale gestione dell'IP originale del client deve essere configurata in modo coerente con l'infrastruttura di pubblicazione.

---

# Persistenza Docker

Il progetto utilizza tre volumi Docker:

```text
durc-postgres-data
durc-media-data
durc-pdf-data
```

rispettivamente per:

- PostgreSQL;
- media Django;
- PDF DURC.

La directory locale:

```text
./secrets
```

viene invece montata in sola lettura nel container web.

## Attenzione ai volumi

Il comando:

```bash
docker compose down -v
```

elimina anche i volumi del progetto e può quindi cancellare database e PDF persistenti.

Non utilizzarlo su un'installazione da conservare senza avere verificato i backup.

---

# File statici e WhiteNoise

Il progetto utilizza **WhiteNoise** per servire i file statici Django.

Durante il build dell'immagine Docker viene eseguito automaticamente:

```bash
python manage.py collectstatic --noinput
```

Non è quindi necessario eseguire manualmente `collectstatic` durante una normale installazione.

Gli statici vengono serviti dall'applicazione anche in assenza di reverse proxy, compresi quelli della Django Admin.

---

# Reverse proxy

Gunicorn ascolta sulla porta `8000` del container, pubblicata sull'host come:

```text
127.0.0.1:10006:8000
```

La configurazione è adatta all'uso con reverse proxy come Nginx, Caddy, Traefik o Apache HTTP Server.

Esempio `.env` per un dominio HTTPS:

```env
DJANGO_ALLOWED_HOSTS=durc.example.it
DJANGO_CSRF_TRUSTED_ORIGINS=https://durc.example.it
```

Il reverse proxy deve inoltrare le richieste verso:

```text
http://127.0.0.1:10006
```

Con la configurazione standard, WhiteNoise gestisce anche `/static/`: non è necessario mantenere una copia della directory `staticfiles` sull'host.

## Utilizzo senza reverse proxy

Per l'utilizzo sullo stesso host non è necessario modificare `docker-compose.yml`.

Con:

```yaml
ports:
  - "127.0.0.1:10006:8000"
```

l'applicazione è disponibile su:

```text
http://localhost:10006
```

Se invece si vuole renderla raggiungibile direttamente da altri host della LAN, occorre modificare consapevolmente il bind, ad esempio:

```yaml
ports:
  - "10006:8000"
```

e configurare coerentemente:

```env
DJANGO_ALLOWED_HOSTS=192.168.1.50
DJANGO_CSRF_TRUSTED_ORIGINS=http://192.168.1.50:10006
```

L'esposizione diretta di Gunicorn in HTTP non è raccomandata per un servizio pubblicato su Internet.

---

# Sicurezza del container e del repository

Il `Dockerfile` esegue Gunicorn con un utente applicativo non privilegiato (`appuser`, UID 1000).

Il file `.dockerignore` esclude dal contesto di build, tra gli altri:

- `.git`;
- `.env` e varianti;
- `secrets/`;
- media;
- statici generati;
- file SQLite;
- documentazione interna esclusa.

Il file `.gitignore` esclude inoltre i principali file locali o sensibili dal versionamento.

Prima di pubblicare fork o copie del repository è comunque opportuno controllare anche l'intera cronologia Git e assicurarsi che non siano mai state versionate credenziali, chiavi, token o dati reali.

---

# Backup

In produzione è opportuno predisporre backup periodici di:

- database PostgreSQL;
- volume `durc-pdf-data`;
- configurazione `.env`;
- directory `secrets/`, con modalità coerenti con la sensibilità delle chiavi private.

Le chiavi private e i file contenenti credenziali non devono essere inseriti in repository pubblici.

---

# Aggiornamento

Prima di aggiornare un'installazione esistente è consigliato effettuare un backup.

Se non sono presenti modifiche locali da conservare, è possibile riallineare la copia installata al contenuto corrente del branch `main` con:

```bash
git fetch origin
git reset --hard origin/main
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py check
```

> `git reset --hard origin/main` elimina eventuali modifiche locali non committate o non presenti sul branch remoto.

Verificare inoltre eventuali variazioni a `.env.example` e alle migration.

---

# Comandi utili

```bash
# Stato dei container
docker compose ps

# Log applicazione
docker compose logs --tail=100 web

# Log PostgreSQL
docker compose logs --tail=100 db

# Build e avvio
docker compose up -d --build

# Riavvio
docker compose restart

# Controllo Django
docker compose exec web python manage.py check

# Migration
docker compose exec web python manage.py migrate

# Creazione superuser
docker compose exec web python manage.py createsuperuser

# Shell Django
docker compose exec web python manage.py shell

# Elenco volumi
docker volume ls
```

---

# Accesso agli e-service

L'installazione del software **non abilita automaticamente** l'accesso agli e-service.

Per utilizzare DURC e Registro Imprese sono necessari i rispettivi:

- client;
- finalità;
- chiavi;
- autorizzazioni;
- configurazioni previste dalla propria adesione PDND.

---
# Riconoscimenti

Il flusso di autenticazione PDND e le consultazioni DURC/Registro Imprese
sono state sviluppate prendendo spunto anche dall'esperienza pubblica di
[OpenMSP](https://github.com/lsantalu/OpenMSP) (OpenCED), un portale
multi-servizio per l'interoperabilità PDND. Il codice di questo repository
è comunque una implementazione indipendente.

# Licenza

Il progetto è distribuito secondo i termini della **GNU Affero General Public License v3.0 (AGPL-3.0)**.

Il testo completo è disponibile nel file [`LICENSE`](LICENSE).
