# QueryPilot AI

QueryPilot AI is an intelligent, natural-language-to-SQL conversational analysis platform. It enables users to upload custom CSV datasets, ask questions in plain English, and receive safe, validated SQL queries, tabular results, interactive visualizations, and deterministic explanations.

Built with a modern decoupled architecture featuring a **React 19 + Vite + TypeScript** frontend, a **FastAPI** backend, **Google Gemini** integration with bounded-retry resilience, and strict **SQLGlot AST** security validation against isolated SQLite sandboxes.

---

## Key Features

- **Natural Language Data Discovery:** Translates plain English inquiries into syntactically correct SQLite queries using Google Gemini.
- **Dynamic CSV Ingestion & Sandboxing:** Upload any tabular CSV file (up to 10 MB). The engine automatically normalizes column headers, infers data types, provisions an isolated SQLite database (`<dataset_id>.db`), and indexes dataset metadata.
- **Strict SQL Security Guardrails (SQLGlot):**
  - Enforces read-only `SELECT` and safe Common Table Expressions (`WITH ... SELECT`).
  - Completely blocks destructive operations (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`).
  - Rejects multi-statement queries and unauthorized table access.
  - Automatically injects and enforces a strict maximum row limit of `LIMIT 100`.
  - Enforces a 5.0-second execution timeout via SQLite progress handlers.
- **Premium Question-First Interface:**
  - High-contrast forest-green (`#123D2C`) and warm off-white (`#F7F7F2`) visual system.
  - Centered workspace with auto-suggested question pills based on the active dataset's schema.
  - Interactive data tables with automatic Recharts bar and line visualizations.
  - Non-intrusive expandable drawers for dataset switching, schema inspection, and session query chronicle.
- **Production-Grade Resilience & Privacy:**
  - Differentiated HTTP status handling (401 for auth, 429 for quota exhaustion, 503 for model overload, 504 for timeout).
  - Bounded exponential retries for transient upstream failures.
  - Safe credential scrubbing that redacts API keys and tokens from logs and responses.
  - Zero dataset rows transmitted to the LLM (only column names, inferred types, and representative sample values are sent).

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│              QueryPilot AI Frontend (React 19)              │
│        Vite · TypeScript · Tailwind CSS · Motion · Recharts │
└──────────────────────────────┬──────────────────────────────┘
                               │  REST API (JSON)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Backend Service                     │
│               app.py (CORS, Validation, Router)             │
├──────────────────────────────┬──────────────────────────────┤
│      core/dataset_manager    │      core/query_service      │
│  - CSV parsing & validation  │  - Schema prompt synthesis   │
│  - Isolated SQLite DB files  │  - Google Gemini invocation  │
│  - Metadata persistence      │  - SQLGlot AST validation    │
│                              │  - Read-only SQLite execution│
└──────────────┬───────────────┴──────────────┬───────────────┘
               │                              │
               ▼                              ▼
    ┌────────────────────┐         ┌────────────────────┐
    │  data/datasets/    │         │   Google Gemini    │
    │  <id>.db (SQLite)  │         │   Developer API    │
    │  <id>.json (Meta)  │         │ gemini-3.5-flash-  │
    └────────────────────┘         │       lite         │
                                   └────────────────────┘
```

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite 8, Tailwind CSS, Motion for React, Recharts, PrismJS, Lucide React |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, SQLGlot, Pandas, NumPy, python-dotenv |
| **AI / LLM** | Google Gemini (`gemini-3.5-flash-lite`), LangChain Google GenAI, Google GenAI SDK |
| **Storage** | SQLite3 (isolated per dataset with read-only URI connections) |
| **Testing** | Pytest (72 unit and regression tests) |

---

## Getting Started

### Prerequisites

- **Python 3.11** or higher
- **Node.js 18** or higher (with npm)
- A **Google Gemini API Key** (obtainable from [Google AI Studio](https://aistudio.google.com/app/apikey))

---

### 1. Clone the Repository

```bash
git clone https://github.com/vismayaea/QueryPilot-AI.git
cd QueryPilot-AI
```

---

### 2. Backend Setup

#### Using `uv` (Recommended)

```powershell
# Create virtual environment and install dependencies
uv venv
.\.venv\Scripts\activate
uv sync
```

#### Using standard `pip`

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

#### Configure Environment Variables

Copy the example environment file:

```powershell
copy .env.example .env
```

Open `.env` and configure your credentials:

```ini
# Google Gemini API Key (Required)
GOOGLE_API_KEY=your_actual_google_api_key_here

# Configured Gemini model (Default: gemini-3.5-flash-lite)
GEMINI_MODEL=gemini-3.5-flash-lite

# Optional: Persistent dataset storage directory (Defaults to ./data/datasets)
DATASETS_DIR=./data/datasets

# Optional: LangSmith tracing
LANGCHAIN_TRACING_V2=false
```

#### Start the Backend Server

```powershell
uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at `http://127.0.0.1:8000` (API documentation at `http://127.0.0.1:8000/docs`).

---

### 3. Frontend Setup

In a new terminal window:

```powershell
cd frontend
npm install
npm run dev
```

The application will launch at **`http://localhost:3000`**. The development server automatically proxies `/api` requests to `http://127.0.0.1:8000`.

---

## Production Build & Testing

### Run Backend Tests

The test suite includes 72 tests covering CSV upload validation, dataset isolation, SQLGlot security checks, and Gemini error handling:

```powershell
.\.venv\Scripts\pytest -v
```

### Build the Frontend Bundle

```powershell
cd frontend
npm run build
```

This compiles TypeScript and outputs an optimized production bundle into `frontend/dist/`.

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status and stage indicator |
| `POST` | `/api/upload` | Upload and sandbox a CSV file into an isolated SQLite database |
| `GET` | `/api/datasets` | List all available uploaded datasets |
| `GET` | `/api/datasets/{id}` | Retrieve schema and metadata for a specific dataset |
| `POST` | `/api/query` | Submit a natural language question for Gemini text-to-SQL execution |

### Example Query Request

```http
POST /api/query
Content-Type: application/json

{
  "dataset_id": "a1b2c3d4e5f67890123456789abcdef0",
  "question": "What is the average salary by department?"
}
```

### Example Query Response

```json
{
  "success": true,
  "dataset_id": "a1b2c3d4e5f67890123456789abcdef0",
  "question": "What is the average salary by department?",
  "sql": "SELECT \"department\", AVG(\"salary\") AS \"avg_salary\" FROM \"uploaded_data\" GROUP BY \"department\" LIMIT 100",
  "columns": ["department", "avg_salary"],
  "rows": [
    ["Engineering", 125000.0],
    ["Marketing", 85000.0]
  ],
  "row_count": 2,
  "answer": "Found 2 records matching your query."
}
```

---

## Deployment Configuration

When deploying the backend and frontend separately (e.g. Render, Railway, or Vercel):

1. **Backend Environment Variables:**
   - `GOOGLE_API_KEY`: Set privately in your host provider's dashboard.
   - `GEMINI_MODEL`: Set to `gemini-3.5-flash-lite`.
   - `PORT`: Set by the cloud provider (e.g., `8000`).
   - `DATASETS_DIR`: Point to a persistent disk mount path to retain uploaded datasets across restarts.
2. **Frontend Environment Variables:**
   - `VITE_API_BASE_URL`: Set to your deployed backend URL (e.g. `https://querypilot-api.onrender.com`).
3. **CORS:**
   - Configured in `app.py` to allow cross-origin requests from the deployed frontend client.

---

## Project Structure

```text
QueryPilot-AI/
├── .env.example             # Template for environment variables
├── .gitignore               # Excludes secrets, node_modules, datasets, virtual environments
├── pyproject.toml           # Python package metadata and dependencies
├── requirements.txt         # Locked production Python dependencies
├── uv.lock                  # Exact dependency lockfile
├── app.py                   # FastAPI application routes and error handling
├── core/
│   ├── api_client.py        # Python API client utility
│   ├── csv_loader.py        # CSV parsing, header normalization, and type inference
│   ├── dataset_manager.py   # SQLite database provisioning and metadata handling
│   └── query_service.py     # Gemini text-to-SQL, bounded retries, and SQLGlot validation
├── frontend/
│   ├── package.json         # React frontend dependencies and scripts
│   ├── vite.config.ts       # Vite configuration with /api development proxy
│   ├── tailwind.config.js   # Forest-green & warm off-white design tokens
│   ├── src/
│   │   ├── App.tsx          # Main application layout and state management
│   │   ├── api.ts           # Frontend HTTP client
│   │   ├── components/      # Composer, results, modals, headers, and drawers
│   │   └── types.ts         # TypeScript schema and query interfaces
├── tests/                   # 72 automated pytest test cases
└── README.md                # Project documentation
```

---

## Attribution & Acknowledgments

- This project was initially adapted from [kevinbfrank/text-to-sql-agent](https://github.com/kevinbfrank/text-to-sql-agent) and substantially evolved into the QueryPilot AI full-stack platform.
- Powered by [Google Gemini](https://ai.google.dev/) and [LangChain](https://www.langchain.com/).
- AST SQL security analysis powered by [SQLGlot](https://sqlglot.com/).
- UI design tokens and components built with [Tailwind CSS](https://tailwindcss.com/) and [Motion for React](https://motion.dev/).

---

## License

This project is licensed under the [MIT License](LICENSE).
