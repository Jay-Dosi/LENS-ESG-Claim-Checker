# ESG Claim Verification Assistant (LENS)

**Production-Grade Greenwashing Detection Tool**

An AI-powered greenwashing risk detection tool that verifies corporate sustainability claims against publicly available satellite and news data. Built with **Cohere (Command R)**, **LangChain**, and **spaCy** for production deployment.

---

## 🎯 Overview

The ESG Claim Verification Assistant ingests corporate sustainability reports (PDFs), extracts carbon and emissions-related claims using Cohere (via LangChain), cross-references those claims against OpenWeatherMap air quality data and Google News data, and produces an explainable, transparent risk score.

**Key Features:**
- 📄 PDF text extraction with intelligent chunking
- 🤖 AI-powered claim extraction using Cohere (Command R)
- 🔗 LLM orchestration via LangChain
- 🔍 Local entity extraction for facility identification using spaCy
- 🗺️ Interactive facility mapping with precision manual location pinning
- 🌡️ Historical air quality analysis via OpenWeatherMap API
- 📰 News sentiment analysis via Google News RSS
- 📊 Transparent, AI-generated risk scoring and explanations

---

## 🏗️ Architecture

### Tech Stack
- **Frontend:** React, Vite, Tailwind CSS, Leaflet (Maps)
- **Backend:** FastAPI (Python), Uvicorn
- **AI/LLM:** Cohere API (Command R), LangChain
- **NLP:** spaCy (`en_core_web_md`)
- **Storage/State:** Chroma DB (In-memory configuration)
- **External Data:** OpenWeatherMap API, Google News RSS

### Core Workflow

1. **Upload & Extract:** User uploads a sustainability report (PDF). The backend extracts text using PyMuPDF.
2. **AI Claim Extraction:** LangChain orchestrates a call to Cohere to extract specific ESG claims (e.g., "We reduced scope 1 emissions by 20% at our Texas Plant") in a strict JSON format.
3. **Entity Recognition:** spaCy scans the claims and the full document text to identify physical locations and facility names (NER).
4. **Data Gathering:** 
   - Facilities are mapped to geographic coordinates.
   - OpenWeatherMap provides historical Air Quality Index (AQI) and pollution data for those coordinates.
   - Google News RSS is queried for related negative press or controversies.
5. **Scoring & Explanation:** A deterministic risk score is calculated, and Cohere generates a final, explainable 4-bullet summary verifying the claims against the external evidence.

---

## 🚀 Getting Started

### Prerequisites
- Node.js (v20+)
- Python (3.11+)
- Cohere API Key (Free tier available at [dashboard.cohere.com/api-keys](https://dashboard.cohere.com/api-keys))
- OpenWeatherMap API Key (Free tier available)

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_md

# Configure Environment Variables
cp .env.example .env
```

Add your API keys to the `.env` file:
```env
COHERE_API_KEY=your_cohere_api_key_here
OPENWEATHERMAP_API_KEY=your_openweathermap_api_key_here
```

Start the backend:
```bash
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Visit `http://localhost:5173` in your browser.

---

## 🚀 Deployment (Render)

This project is configured for easy deployment on [Render](https://render.com) using the included `render.yaml` blueprint.

1. Connect your repository to Render.
2. Render will automatically detect the `render.yaml` blueprint.
3. Provide your `COHERE_API_KEY` and `OPENWEATHERMAP_API_KEY` in the Render dashboard when prompted.
4. The build script automatically handles installing Python dependencies, downloading the spaCy model, and building the React frontend.

---

## ⚖️ License
MIT License
