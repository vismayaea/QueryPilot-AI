# QueryPilot AI — Frontend Client

The web interface for QueryPilot AI, built with **React 19**, **Vite 8**, **TypeScript**, and **Tailwind CSS**.

---

## Features

- **Centered Question-First Experience:** Refined QueryPilot AI header, natural-language composer with focus transitions, and dynamic suggested inquiry pills.
- **Forest-Green Design System:** Bespoke high-contrast palette featuring deep forest green (`#123D2C` / `#0B2E22`), pale sage (`#E6EDE5`), and warm off-white background (`#F7F7F2`).
- **Data Visualization & Result Tables:** Tabular result viewing with automatic Recharts bar and line visualization tailored to returned SQL data.
- **Non-Intrusive Secondary Drawers:**
  - **Dataset Selection Modal:** Browse and switch between isolated SQLite datasets.
  - **Schema Drawer:** Inspect column headers, inferred SQLite types, and sample data values.
  - **Inquiry Chronicle Drawer:** Review session query history, execution timestamps, and yielded row counts.
  - **CSV Upload Modal:** Drag-and-drop tabular CSV file ingestion with client-side header and file validation.

---

## Development

### Prerequisites

- Node.js 18+
- npm

### Installation

```bash
npm install
```

### Run Locally

```bash
npm run dev
```

The application runs at `http://localhost:3000`. In development, Vite automatically proxies `/api` requests to `http://127.0.0.1:8000`.

### Production Build

```bash
npm run build
```

Compiles TypeScript and outputs production assets to `dist/`.

---

## Configuration

In production, if the frontend is hosted on a separate domain from the FastAPI backend, set the backend API base URL:

```bash
VITE_API_BASE_URL=https://your-backend-api-domain.com
```

If left blank or omitted, requests use relative paths (`/api/...`), ideal for reverse-proxy or unified domain deployments.
