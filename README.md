[README.md](https://github.com/user-attachments/files/28950806/README.md)
# 🔍 JobLens — AI-Powered LinkedIn Job Search

Search LinkedIn jobs using your resume or keywords. Powered by Claude AI.

**Stack:** Python (Flask) · Angular 17 · Bootstrap 5

---

## How it works

LinkedIn's API is private, so this app uses **Claude AI** as the intelligence layer:

1. You upload a resume (PDF/DOCX/TXT) or type keywords
2. Claude AI parses your resume to extract skills, experience, and industries
3. Claude AI generates 12 highly realistic LinkedIn-style job listings that match your profile
4. Each result includes: full job description, salary range, required skills, match score, and a **real LinkedIn search/apply URL**

---

## Setup

### Prerequisites
- Python 3.9+
- Node.js 18+ (for Angular)
- An [Anthropic API key](https://console.anthropic.com/) (free tier available)

### Backend

```bash
cd backend
pip install flask pypdf python-docx requests
python app.py
```

Backend runs on `http://localhost:5000`

### Frontend (Angular)

```bash
cd frontend
npm install
npm start          # → http://localhost:4200
```

Or just open `frontend/standalone.html` directly in a browser — no Node.js needed.

### API Key

Paste your Anthropic API key in the input field in the top navbar of the app.
It's stored only in your browser's localStorage.

You can also set it as an environment variable before starting the backend:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

---

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/health` | Health check, shows if API key is set |
| POST | `/api/parse-resume` | Upload PDF/DOCX/TXT, returns extracted profile |
| POST | `/api/search` | Search jobs by keywords or profile |
| POST | `/api/job/:id/similar` | Find similar jobs to a given listing |

---

## Project Structure

```
linkedinjobs/
├── backend/
│   └── app.py                         ← Flask API
└── frontend/
    ├── angular.json / package.json / tsconfig.json / proxy.conf.json
    ├── standalone.html                 ← works without npm
    └── src/
        ├── main.ts
        ├── index.html
        ├── styles.scss
        └── app/
            ├── app.component.ts        ← navbar + router
            ├── app.routes.ts
            ├── models/job.model.ts
            ├── services/job.service.ts
            └── components/
                ├── search/             ← keywords & resume upload
                └── results/           ← two-panel job browser
```

---

## Features

- **Resume parsing** — PDF, DOCX, TXT support; AI extracts skills, experience, industries
- **Keyword search** — Natural language job search with location
- **Advanced filters** — Work type (Remote/Hybrid/On-site), employment type, experience level
- **Match scoring** — Each job gets a % match score with explanation
- **Skill highlighting** — Matched vs unmatched skills shown per job
- **Full JD** — Complete job descriptions, not truncated summaries
- **Apply links** — Real LinkedIn search + apply URLs open in LinkedIn
- **Save jobs** — Bookmark jobs during your session
- **Similar jobs** — Find related roles from the detail view
- **Company info** — About the company, headcount, industry
