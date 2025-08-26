# 🏥 Medical Fake News Detection System

## 📋 Overview

Un sistema avanzato per il rilevamento e l'analisi di disinformazione medica sui social media, sviluppato come progetto di tesi. Il sistema utilizza tecniche di Natural Language Processing, Machine Learning e Large Language Models per identificare e classificare contenuti potenzialmente fuorvianti in ambito medico-sanitario.

## 🎯 Funzionalità Principali

- **🔍 Analisi Multi-Piattaforma**: Monitoraggio di Twitter, Reddit, YouTube, Facebook, Instagram e fonti RSS
- **🤖 Rilevamento AI**: Utilizzo di modelli linguistici avanzati (GPT, Claude, Gemini) per l'analisi
- **📊 Dashboard Interattiva**: Interfaccia web per la gestione delle campagne di monitoraggio
- **📈 Visualizzazione Dati**: Grafici e report dettagliati sui risultati delle analisi
- **🔬 Validazione Scientifica**: Integrazione con database PubMed per la verifica delle informazioni
- **📱 Design Responsivo**: Interfaccia ottimizzata per desktop e mobile

## 🏗️ Architettura del Sistema

```
medical_fake_news/
├── backend/                 # API Flask per l'elaborazione dei dati
│   ├── app/
│   │   ├── api/            # Endpoints REST
│   │   ├── services/       # Logica di business
│   │   ├── nlp/           # Processamento del linguaggio naturale
│   │   └── core/          # Configurazione e database
├── frontend/               # Interfaccia React
│   ├── src/
│   │   ├── components/    # Componenti riutilizzabili
│   │   ├── pages/         # Pagine dell'applicazione
│   │   └── context/       # Gestione dello stato
└── documentation/          # Documentazione tecnica
```

## 🚀 Quick Start

### Prerequisiti

- **Python 3.9+**
- **Node.js 16+**
- **MongoDB 4.4+**
- **Git**

### 1. Clone del Repository

```bash
git clone <repository-url>
cd medical_fake_news
```

### 2. Setup Backend

```bash
cd backend

# Crea ambiente virtuale
python -m venv venv

# Attiva ambiente (Linux/Mac)
source venv/bin/activate
# Windows: venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt

# Configura variabili d'ambiente
cp .env.example .env
# Modifica .env con le tue configurazioni

# Avvia il server
python app/run.py
```

### 3. Setup Frontend

```bash
cd frontend

# Installa dipendenze
npm install

# Avvia il server di sviluppo
npm start
```

### 4. Accesso all'Applicazione

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000

## ⚙️ Configurazione

### Variabili d'Ambiente Backend

Crea un file `.env` nella cartella `backend/` con:

```env
# Database
MONGO_URI=mongodb://localhost:27017/
DB_NAME=fake_news_db

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-here

# API Keys per LLM
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-gemini-key
CLAUDE_API_KEY=your-claude-key

# Social Media APIs
TWITTER_BEARER_TOKEN=your-twitter-token
REDDIT_CLIENT_ID=your-reddit-id
REDDIT_CLIENT_SECRET=your-reddit-secret
YOUTUBE_API_KEY=your-youtube-key

# PubMed
PUBMED_EMAIL=your-email@domain.com
ENTREZ_API_KEY=your-entrez-key

# CORS Settings
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
```

## 📚 API Documentation

### Principali Endpoints

#### Autenticazione
- `POST /api/register` - Registrazione utente
- `POST /api/login` - Login utente

#### Campagne
- `GET /api/campaigns` - Lista campagne utente
- `POST /api/campaigns` - Crea nuova campagna
- `PUT /api/campaigns/{id}` - Modifica campagna
- `DELETE /api/campaigns/{id}` - Elimina campagna

#### Analisi
- `POST /api/collect` - Avvia raccolta dati
- `POST /api/analysis/trigger` - Avvia analisi
- `GET /api/posts` - Recupera post analizzati

### Esempi di Utilizzo

```bash
# Registrazione
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"user","email":"user@example.com","password":"password123"}'

# Creazione campagna
curl -X POST http://localhost:5000/api/campaigns \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Vaccini COVID","keywords":["vaccino","covid"],"social_platforms":["twitter","reddit"]}'
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
python -m pytest tests/ -v --cov=app
```

### Frontend Tests

```bash
cd frontend
npm test
```

## 🐳 Deploy con Docker

```bash
# Build delle immagini
docker-compose build

# Avvio dei servizi
docker-compose up -d

# Logs
docker-compose logs -f
```

## 📊 Monitoraggio e Metriche

Il sistema include dashboard per:

- **Accuracy del rilevamento**: Precisione nell'identificazione di fake news
- **Volume dei dati**: Numero di post processati per periodo
- **Performance**: Tempi di risposta e throughput delle API
- **Copertura piattaforme**: Distribuzione dei contenuti per social network

## 🔒 Sicurezza

- **Autenticazione JWT** con scadenza token
- **Validazione input** su tutti gli endpoints
- **Rate limiting** per prevenire abusi
- **CORS configurabile** per ambienti multipli
- **Sanitizzazione dati** per prevenire injection attacks

## 🤝 Contribuire

1. Fork del repository
2. Crea un branch per la feature (`git checkout -b feature/nuova-feature`)
3. Commit delle modifiche (`git commit -m 'Aggiunge nuova feature'`)
4. Push del branch (`git push origin feature/nuova-feature`)
5. Apri una Pull Request

## 📝 Licenza

Questo progetto è sviluppato come tesi universitaria. Tutti i diritti riservati.

## 👥 Autore

**[Il Tuo Nome]**
- Email: [tua.email@università.it]
- LinkedIn: [il-tuo-linkedin]
- Università: [Nome Università]
- Corso di Laurea: [Nome Corso]

## 🙏 Ringraziamenti

- Prof. [Nome Relatore] - Supervisione accademica
- Dipartimento di [Nome Dipartimento]
- OpenAI, Anthropic, Google - Per l'accesso alle API dei modelli linguistici
- Comunità open source per le librerie utilizzate

---

## 📋 Status del Progetto

**Versione**: 1.0.0  
**Status**: In Sviluppo  
**Ultimo Aggiornamento**: $(date +%Y-%m-%d)  

### Roadmap

- [x] ✅ Sistema base di rilevamento
- [x] ✅ Interfaccia web responsive
- [x] ✅ Integrazione multi-LLM
- [ ] 🔄 Testing automatizzato completo
- [ ] 📦 Containerizzazione Docker
- [ ] ☁️ Deploy cloud-ready
- [ ] 📊 Dashboard avanzate con ML insights
- [ ] 🔄 CI/CD Pipeline
- [ ] 📖 Documentazione API completa