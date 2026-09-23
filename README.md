# 📚 China Professor Email Agent — Multi-Gemini

An AI-powered academic outreach tool that automatically generates and sends **highly personalized** cold emails to Chinese university professors on behalf of a prospective Master's student applying via the **CSC/ANSO scholarship**. Each email is uniquely crafted using Google Gemini LLMs based on the professor's research area, proposed research topic, and the applicant's CV.

---

## ✨ Features

- **AI-Personalized Emails** — Uses Google Gemini to write unique, scholarly emails for each professor referencing their specific research
- **Multi-Model Fallback** — Tries multiple Gemini models in order; automatically skips rate-limited or exhausted models
- **Research Match Scoring** — Gemini scores 0–100 how well the applicant's interests align with the professor's work; low-scoring professors are skipped
- **Deduplication** — Tracks all sent emails in `EMAIL_LOG.csv` to prevent re-sending across multiple runs
- **PDF Attachments** — Automatically attaches the applicant's CV and Thesis PDF to every email
- **CV Text Extraction** — Reads and embeds CV content into the Gemini prompt for richer personalization
- **Dry Run Mode** — Generate and preview emails without actually sending anything
- **Review Before Send** — Optional manual approval step before each email is sent
- **Draft Saving** — Every generated email is saved to `generated_emails/` as a plain text file
- **Progress Tracking** — `check_remaining.py` shows how many professors still need to be contacted
- **Model Testing** — `model_test.py` benchmarks each Gemini model with a real dry-run against the first professor

---

## 📁 Project Structure

```
literature/
├── chinese.py              # Main email generation & sending agent
├── model_test.py           # Dry-run benchmark across multiple Gemini models
├── check_remaining.py      # Reports how many professors are yet to be emailed
├── list_models.py          # Lists all available Gemini models from the API
├── literature.csv          # Professor database (name, email, university, research)
├── EMAIL_LOG.csv           # Auto-updated log of all email attempts
├── requirements.txt        # Python dependencies
├── .env                    # API keys & SMTP credentials (NOT committed)
├── CV.pdf                  # Applicant CV — attached to every email
├── THESIS.pdf              # Applicant thesis — attached to every email
├── generated_emails/       # Saved plain-text drafts of every generated email
└── gemini_debug/           # Debug logs for failed Gemini API calls
```

---

## ⚙️ Setup

### 1. Clone the repository
```bash
git clone https://github.com/Alishan45/literature.git
cd literature
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your PDF files
Place your CV and thesis in the project root:
```
CV.pdf
THESIS.pdf
```

### 5. Configure environment variables

Create a `.env` file in the project root:

```env
# ── Google Gemini ──────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key_here

# Comma-separated list of models to try in order (fallback chain)
GEMINI_MODELS=gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite

# ── Gmail SMTP ────────────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password

# ── Applicant Info (overrides script defaults) ────────────────────
APPLICANT_NAME=Your Full Name
APPLICANT_DEGREE=BS (Hons) English Literature
APPLICANT_UNIVERSITY=University of the Punjab
APPLICANT_WEBSITE=https://yourportfolio.com/

# ── Execution Settings ────────────────────────────────────────────
DRY_RUN=False           # Set True to preview emails without sending
MAX_EMAILS=0            # 0 = no limit; set e.g. 10 to process 10 at a time
EMAIL_DELAY_SECONDS=1   # Delay between emails to avoid spam filters
MIN_RESEARCH_SCORE=5    # Skip professors whose match score is below this
REVIEW_BEFORE_SEND=False  # Set True for manual approval before each send
```

> **Note:** Use a [Gmail App Password](https://support.google.com/accounts/answer/185833), not your regular Gmail password. Enable 2FA on your Google account first.

---

## 🗂️ CSV Format

The professor database (`literature.csv`) must contain these columns:

| Column | Description |
|--------|-------------|
| `university_name` | Name of the professor's university |
| `professor_name` | Full name of the professor |
| `email` | Professor's email address |
| `research_area` | Their general research domain |
| `last_research` | Their most recent research topic or publication |
| `research_topic` | The specific research topic the applicant proposes to pursue under this professor |

---

## 🧪 Usage

### Run the main email agent
```bash
python chinese.py
```

### Dry run — generate & preview emails without sending
```bash
# Via .env
DRY_RUN=True python chinese.py

# Or set directly
set DRY_RUN=True && python chinese.py    # Windows
```

### Limit the number of emails processed
```bash
set MAX_EMAILS=5 && python chinese.py
```

### Test which Gemini models produce the best emails
```bash
python model_test.py
```

### Check remaining professors (not yet emailed)
```bash
python check_remaining.py
```

### List available Gemini models
```bash
python list_models.py
```

---

## 🔁 How It Works

```
literature.csv
     │
     ▼
For each professor:
  1. Validate professor record (name, email, university)
  2. Skip if already in EMAIL_LOG.csv (SENT)
  3. Extract CV text from CV.pdf
  4. Build Gemini prompt with professor data + applicant CV + research topic
  5. Call Gemini API (with multi-model fallback on rate limit / failure)
  6. Gemini returns: research_match_score, email subject, email body
  7. Validate & clean the generated email
  8. Skip if research_match_score < MIN_RESEARCH_SCORE
  9. Save draft to generated_emails/
 10. Send via Gmail SMTP with CV.pdf + THESIS.pdf attached
 11. Log result to EMAIL_LOG.csv
```

---

## 📊 Email Log

All attempts are recorded in `EMAIL_LOG.csv` with:

| Field | Description |
|-------|-------------|
| `Timestamp` | Date and time of the attempt |
| `Professor_Name` | Professor's full name |
| `Professor_Email` | Professor's email address |
| `University_Name` | University name |
| `Subject` | Generated email subject line |
| `Research_Match_Score` | Gemini's 0–100 relevance score |
| `Gemini_Model` | Which model generated the email |
| `Gemini_Status` | SUCCESS / FAILED |
| `Email_Status` | SENT / DRY_RUN_NOT_SENT / SKIPPED_LOW_SCORE / SEND_FAILED |
| `Mode` | LIVE or DRY_RUN |
| `Error` | Error message if something went wrong |

---

## 🔧 All Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODELS` | `gemini-3.5-flash,...` | Comma-separated fallback model chain |
| `GEMINI_RETRIES` | `3` | Retries per model before switching |
| `GEMINI_RETRY_DELAY` | `5` | Base delay (seconds) between retries |
| `API_TIMEOUT` | `90` | Gemini API request timeout (seconds) |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_EMAIL` | *(required)* | Sender email address |
| `SMTP_PASSWORD` | *(required)* | Gmail App Password |
| `CSV_FILE` | `literature.csv` | Professor database filename |
| `CV_FILE` | `CV.pdf` | CV filename to attach |
| `THESIS_FILE` | `THESIS.pdf` | Thesis filename to attach |
| `DRY_RUN` | `False` | Preview only, don't send |
| `MAX_EMAILS` | `0` (all) | Max professors to process per run |
| `EMAIL_DELAY_SECONDS` | `1` | Seconds to wait between sends |
| `MIN_RESEARCH_SCORE` | `5` | Minimum Gemini match score to send |
| `REVIEW_BEFORE_SEND` | `False` | Manually approve each email before sending |
| `APPLICANT_NAME` | `Akasha Iqbal` | Applicant's full name |
| `APPLICANT_DEGREE` | `BS (Hons) English Literature` | Applicant's degree |
| `APPLICANT_UNIVERSITY` | `University of the Punjab` | Applicant's university |
| `APPLICANT_WEBSITE` | — | Applicant's portfolio/website URL |

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `pypdf` | Extract text from CV.pdf for Gemini prompt |
| `python-dotenv` | Load `.env` configuration |
| `requests` | HTTP calls to the Gemini REST API |

---

## 🛡️ Security Notes

- **Never commit your `.env` file** — it is listed in `.gitignore`
- Use **Gmail App Passwords** — never your main account password
- Revoke and regenerate your `GEMINI_API_KEY` if accidentally exposed

---

## 👤 Author

**Ali Shan** — [Alishan45](https://github.com/Alishan45)
