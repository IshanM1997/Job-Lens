"""
LinkedInJobSearch — Flask Backend
===================================
Uses Claude AI to:
  1. Extract skills/keywords from uploaded resumes (PDF, DOCX, TXT)
  2. Generate LinkedIn-style job listings matching those skills
  3. Return full job descriptions + real LinkedIn apply URLs

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    python app.py
"""

import io
import os
import json
import re
import uuid
import traceback
from flask import Flask, request, jsonify, make_response
import requests

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


# ── CORS ──────────────────────────────────────────────────────────────────────
@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"]  = "*"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, x-api-key"
    r.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return r

@app.route("/api/<path:p>", methods=["OPTIONS"])
def opt(p): return make_response("", 204)


# ── Helpers ────────────────────────────────────────────────────────────────────

def extract_text_from_file(file_storage) -> str:
    """Extract plain text from PDF, DOCX, or TXT."""
    fname = file_storage.filename.lower()
    raw   = file_storage.read()

    if fname.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join(p.extract_text() or "" for p in reader.pages)

    if fname.endswith(".docx") or fname.endswith(".doc"):
        from docx import Document
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)

    return raw.decode("utf-8", errors="replace")


def call_claude(system: str, user: str, api_key: str, max_tokens=4000) -> str:
    resp = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise ValueError(f"Claude API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["content"][0]["text"]


def build_linkedin_url(title: str, company: str, location: str) -> str:
    """Build a real LinkedIn job search URL for this role."""
    import urllib.parse
    q = urllib.parse.quote_plus(f"{title} {company}")
    loc = urllib.parse.quote_plus(location or "Worldwide")
    return f"https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}"


def build_apply_url(job_id: str, title: str, company: str) -> str:
    """Build a LinkedIn apply URL. Uses search as fallback (no scraping needed)."""
    import urllib.parse
    q = urllib.parse.quote_plus(f"{title} {company}")
    return f"https://www.linkedin.com/jobs/search/?keywords={q}&f_AL=true"


EXTRACT_SYSTEM = """You are a professional resume parser.
Extract the candidate's skills, job titles, years of experience, education, and industry.
Return ONLY a valid JSON object — no markdown fences, no explanation.
Schema:
{
  "name": string or null,
  "current_title": string,
  "skills": [string],
  "experience_years": number,
  "education": string,
  "industries": [string],
  "locations_preferred": [string],
  "summary": string  // 1-2 sentence professional summary
}"""

SEARCH_SYSTEM = """You are a LinkedIn job database.
Given a candidate profile or search keywords, generate realistic LinkedIn job listings.
Return ONLY a valid JSON array — no markdown fences, no extra text.
Each job object must have EXACTLY these fields:
{
  "id": "unique string id",
  "title": "Job Title",
  "company": "Company Name",
  "company_size": "e.g. 1,001–5,000 employees",
  "location": "City, Country (Remote/Hybrid/On-site)",
  "work_type": "Remote" | "Hybrid" | "On-site",
  "employment_type": "Full-time" | "Part-time" | "Contract" | "Internship",
  "salary_range": "e.g. $90,000 – $130,000/yr or Not disclosed",
  "posted_date": "e.g. 2 days ago",
  "applicants": "e.g. 147 applicants",
  "easy_apply": true | false,
  "match_score": number between 60 and 99,
  "match_reasons": [string],  // 2-3 reasons this job matches the candidate
  "skills_required": [string],
  "skills_matched": [string],  // subset of candidate skills that match
  "description": "Full job description, 4-6 paragraphs covering: about the company, role overview, key responsibilities (as a paragraph, not bullets), requirements, nice-to-haves, and what they offer. Make it realistic and detailed, 300-400 words.",
  "about_company": "2-3 sentences about the company",
  "benefits": [string],
  "industry": "e.g. Software Development",
  "seniority": "Entry level" | "Mid-Senior level" | "Senior" | "Director" | "Executive"
}
Generate exactly 12 jobs. Mix seniority levels, companies (FAANG, startups, mid-size), and work types.
Make them highly realistic — real company names, realistic salaries for the role/location, genuine descriptions."""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "api_key_set": bool(ANTHROPIC_API_KEY)})


@app.route("/api/parse-resume", methods=["POST"])
def parse_resume():
    api_key = request.headers.get("x-api-key") or ANTHROPIC_API_KEY
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set. Pass it via x-api-key header."}), 401

    f = request.files.get("resume")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        text = extract_text_from_file(f)
        if not text.strip():
            return jsonify({"error": "Could not extract text from file"}), 422

        result = call_claude(EXTRACT_SYSTEM, f"Parse this resume:\n\n{text[:8000]}", api_key)
        # strip any accidental fences
        result = re.sub(r"^```(?:json)?\n?", "", result.strip())
        result = re.sub(r"\n?```$", "", result.strip())
        profile = json.loads(result)
        return jsonify({"success": True, "profile": profile})

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse Claude response as JSON: {e}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/search", methods=["POST"])
def search_jobs():
    api_key = request.headers.get("x-api-key") or ANTHROPIC_API_KEY
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set."}), 401

    body     = request.get_json() or {}
    keywords = body.get("keywords", "")
    location = body.get("location", "")
    profile  = body.get("profile")   # from resume parse
    filters  = body.get("filters", {})

    if not keywords and not profile:
        return jsonify({"error": "Provide keywords or a parsed resume profile"}), 400

    # Build prompt
    if profile:
        candidate_ctx = f"""Candidate profile (from resume):
- Current title: {profile.get('current_title', 'N/A')}
- Skills: {', '.join(profile.get('skills', [])[:20])}
- Experience: {profile.get('experience_years', '?')} years
- Education: {profile.get('education', 'N/A')}
- Industries: {', '.join(profile.get('industries', []))}
- Summary: {profile.get('summary', '')}
"""
    else:
        candidate_ctx = f"Search query: {keywords}"

    loc_ctx = f"\nPreferred location: {location}" if location else ""
    filter_ctx = ""
    if filters.get("work_type"):
        filter_ctx += f"\nWork type filter: {filters['work_type']}"
    if filters.get("employment_type"):
        filter_ctx += f"\nEmployment type: {filters['employment_type']}"
    if filters.get("experience_level"):
        filter_ctx += f"\nExperience level: {filters['experience_level']}"

    prompt = f"{candidate_ctx}{loc_ctx}{filter_ctx}\n\nGenerate 12 matching LinkedIn job listings."

    try:
        result = call_claude(SEARCH_SYSTEM, prompt, api_key, max_tokens=6000)
        result = re.sub(r"^```(?:json)?\n?", "", result.strip())
        result = re.sub(r"\n?```$", "", result.strip())
        jobs   = json.loads(result)

        # Enrich with LinkedIn URLs
        for job in jobs:
            job["linkedin_search_url"] = build_linkedin_url(
                job["title"], job["company"], job["location"]
            )
            job["apply_url"] = build_apply_url(
                job.get("id", ""), job["title"], job["company"]
            )
            if not job.get("id"):
                job["id"] = str(uuid.uuid4())[:8]

        # Sort by match score
        jobs.sort(key=lambda j: j.get("match_score", 0), reverse=True)

        return jsonify({
            "success": True,
            "total": len(jobs),
            "jobs": jobs,
            "search_context": {
                "keywords": keywords,
                "location": location,
                "used_resume": bool(profile),
            }
        })

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Failed to parse job listings: {e}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/job/<job_id>/similar", methods=["POST"])
def similar_jobs(job_id):
    """Get similar jobs to a given listing."""
    api_key = request.headers.get("x-api-key") or ANTHROPIC_API_KEY
    if not api_key:
        return jsonify({"error": "API key required"}), 401

    body = request.get_json() or {}
    job  = body.get("job", {})

    prompt = f"""Find 4 similar jobs to this role:
Title: {job.get('title')}
Company: {job.get('company')}
Skills: {', '.join(job.get('skills_required', []))}
Industry: {job.get('industry')}

Generate 4 similar job listings at comparable companies."""

    try:
        result = call_claude(SEARCH_SYSTEM, prompt, api_key, max_tokens=3000)
        result = re.sub(r"^```(?:json)?\n?", "", result.strip())
        result = re.sub(r"\n?```$", "", result.strip())
        jobs   = json.loads(result)[:4]
        for job in jobs:
            job["linkedin_search_url"] = build_linkedin_url(job["title"], job["company"], job["location"])
            job["apply_url"] = build_apply_url("", job["title"], job["company"])
            if not job.get("id"): job["id"] = str(uuid.uuid4())[:8]
        return jsonify({"success": True, "jobs": jobs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    key_status = "✅ set" if ANTHROPIC_API_KEY else "❌ NOT SET — export ANTHROPIC_API_KEY=sk-ant-..."
    print(f"""
╔══════════════════════════════════════════════╗
║   LinkedIn Job Search — Flask Backend        ║
╚══════════════════════════════════════════════╝
  API Key  : {key_status}
  Running  : http://localhost:5000
  Press Ctrl+C to stop
""")
    app.run(debug=True, port=5000)
