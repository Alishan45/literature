"""
=======================================================================
       CHINA PROFESSOR EMAIL AGENT - MULTI-GEMINI
=======================================================================
"""

import os
import csv
import re
import json
import time
import smtplib
import ssl
import hashlib
import random
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage

import requests
from dotenv import load_dotenv

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None

# ================================================================
# LOAD ENVIRONMENT
# ================================================================
load_dotenv()

# Helper to safely strip quotes from env variables
def get_env_str(key, default=""):
    val = os.getenv(key, default)
    if val is None:
        return ""
    return str(val).strip(' "\'')

# ================================================================
# BASE DIRECTORY
# ================================================================
BASE_DIR = Path(__file__).resolve().parent

CSV_FILE = BASE_DIR / get_env_str("CSV_FILE", "literature.csv")
CV_FILE = BASE_DIR / get_env_str("CV_FILE", "CV.pdf")
THESIS_FILE = BASE_DIR / get_env_str("THESIS_FILE", "THESIS.pdf")
EMAIL_LOG_FILE = BASE_DIR / "EMAIL_LOG.csv"
GENERATED_EMAILS_DIR = BASE_DIR / "generated_emails"
GEMINI_DEBUG_DIR = BASE_DIR / "gemini_debug"

GENERATED_EMAILS_DIR.mkdir(exist_ok=True)
GEMINI_DEBUG_DIR.mkdir(exist_ok=True)

# ================================================================
# GEMINI CONFIGURATION
# ================================================================
GEMINI_API_KEY = get_env_str("GEMINI_API_KEY", "")

GEMINI_MODELS = [
    model.strip()
    for model in get_env_str(
        "GEMINI_MODELS",
        "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-flash-lite-latest"
    ).split(",")
    if model.strip()
]
ACTIVE_MODELS_FILE = BASE_DIR / ".gemini_active_models.json"

def _load_active_models():
    """Load models from JSON file if it exists, otherwise fall back to GEMINI_MODELS."""
    if ACTIVE_MODELS_FILE.exists():
        try:
            with open(ACTIVE_MODELS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            models = [m.strip() for m in data.get("models", []) if m.strip()]
            if models:
                return models
        except Exception:
            pass
    return list(GEMINI_MODELS)

ACTIVE_GEMINI_MODELS = _load_active_models()

GEMINI_RETRIES_PER_MODEL = int(get_env_str("GEMINI_RETRIES", get_env_str("GEMINI_MAX_RETRIES", "3")))
GEMINI_RETRY_DELAY = int(get_env_str("GEMINI_RETRY_DELAY", "5"))
API_TIMEOUT = int(get_env_str("API_TIMEOUT", "90"))

# ================================================================
# GMAIL CONFIGURATION
# ================================================================
SMTP_EMAIL = get_env_str("SMTP_EMAIL", get_env_str("EMAIL_ADDRESS", ""))
SMTP_PASSWORD = get_env_str("SMTP_PASSWORD", get_env_str("EMAIL_APP_PASSWORD", ""))
SMTP_HOST = get_env_str("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(get_env_str("SMTP_PORT", "587"))

# ================================================================
# EXECUTION SETTINGS
# ================================================================
DRY_RUN = get_env_str("DRY_RUN", "False").lower() == "true"
REVIEW_BEFORE_SEND = get_env_str("REVIEW_BEFORE_SEND", "False").lower() == "true"
MAX_EMAILS = int(get_env_str("MAX_EMAILS", "0"))
EMAIL_DELAY_SECONDS = int(get_env_str("EMAIL_DELAY_SECONDS", "1"))
MIN_RESEARCH_SCORE = int(get_env_str("MIN_RESEARCH_SCORE", "5"))  # skip if score < this

# ================================================================
# APPLICANT INFORMATION
# ================================================================
APPLICANT_NAME = get_env_str("APPLICANT_NAME", "Akasha Iqbal")
APPLICANT_DEGREE = get_env_str("APPLICANT_DEGREE", "BS (Hons) English Literature")
APPLICANT_UNIVERSITY = get_env_str("APPLICANT_UNIVERSITY", "University of the Punjab")
APPLICANT_GPA = get_env_str("APPLICANT_GPA", "3.18/4.00")
APPLICANT_IELTS = get_env_str("APPLICANT_IELTS", "Not applicable")
APPLICANT_WEBSITE = get_env_str("APPLICANT_WEBSITE", "https://akashaiqbal.vercel.app/")
APPLICANT_INTERESTS = get_env_str("APPLICANT_INTERESTS", (
    "Feminist Literary Studies, Gender Studies, Gender Representation, "
    "Gender Equality, Feminist Theory, Contemporary Literature, "
    "Dystopian Literature, Literary Criticism, Cultural Studies, "
    "Women's Literature, Gender and Society, Identity and Agency, "
    "Patriarchy and Resistance, Postcolonial Feminism, Intersectionality, "
    "Queer Theory, Critical Theory, Comparative Literature, "
    "Narrative Studies, Contemporary Fiction"
))
APPLICANT_GOAL = get_env_str("APPLICANT_GOAL", (
    "I am seeking admission to an English-taught Master's program at a Chinese university "
    "and I am very interested in joining your research group. My background in English Literature "
    "with a focus on gender studies, feminist theory, and contemporary fiction has prepared me "
    "to contribute meaningfully to your ongoing research. I would like to know whether you are "
    "accepting graduate students and whether you could provide guidance on admission, "
    "supervision, and CSC/ANSO scholarship funding opportunities."
))

SUBJECT_VARIANTS = [
    "Prospective Master's Student: Interest in Joining Your Research Group (CSC/ANSO)",
    "Request to Join Your Research Group – CSC/ANSO Master's Applicant",
    "CSC/ANSO Master's Applicant Seeking to Join Your Research Group",
    "Interest in Joining Your Research Group – CSC/ANSO Scholarship Inquiry",
    "Prospective CSC/ANSO Scholar: Request to Join Your Research Group",
]

# ================================================================
# CSV COLUMNS & LOGGING
# ================================================================
# The CSV file from the user has these exact columns:
EXPECTED_COLUMNS = ["university_name", "professor_name", "email", "research_area", "last_research", "research_topic"]

LOG_COLUMNS = [
    "Timestamp", "Professor_Name", "Professor_Email", "University_Name",
    "Subject", "Research_Match_Score", "Gemini_Model", "Gemini_Status",
    "Google_Search_Used", "Research_Sources", "Email_Status", "Mode", "Error"
]
RESET, GREEN, RED, YELLOW, CYAN, BOLD = "\033[0m", "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[1m"

# ================================================================
# STRICT JSON SCHEMA (Types MUST be uppercase for Gemini REST API)
# ================================================================
GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "research_match_score": {"type": "INTEGER"},
        "research_overlap": {"type": "ARRAY", "items": {"type": "STRING"}},
        "research_relevance": {"type": "STRING"},
        "reason_for_contact": {"type": "STRING"},
        "research_summary": {"type": "STRING"},
        "subject": {"type": "STRING"},
        "email_body": {"type": "STRING"}
    },
    "required": [
        "research_match_score", "research_overlap", "research_relevance",
        "reason_for_contact", "research_summary",
        "subject", "email_body"
    ]
}

class GeminiQuotaError(RuntimeError):
    """Raised when the API key/project has no usable Gemini quota."""


# ================================================================
# BASIC UTILITIES
# ================================================================
def clean_text(value):
    return "" if value is None else str(value).strip()

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*]', "_", clean_text(value))
    return re.sub(r"\s+", "_", value)[:150]

def normalize_email(email):
    return clean_text(email).lower()

def write_active_models():
    with open(ACTIVE_MODELS_FILE, "w", encoding="utf-8") as file:
        json.dump({"models": ACTIVE_GEMINI_MODELS, "updated_at": now_string()}, file, indent=2)

def remove_exhausted_model(model):
    if model in ACTIVE_GEMINI_MODELS:
        ACTIVE_GEMINI_MODELS.remove(model)
        write_active_models()
        print(f"{YELLOW}⚠ Removed exhausted model from temporary active list: {model}{RESET}")

def gemini_http_error(response, model):
    """Return a useful API error without hiding the provider's diagnosis."""
    try:
        payload = response.json()
        message = payload.get("error", {}).get("message", "")
        status = payload.get("error", {}).get("status", "")
        if message:
            return f"{model}: HTTP {response.status_code} {status}: {message}"
    except (ValueError, AttributeError):
        pass
    return f"{model}: Gemini HTTP {response.status_code}: {response.text[:1000]}"

def is_model_quota_error(error):
    error = clean_text(error).lower()
    return "resource_exhausted" in error and "model:" in error

# ================================================================
# HEADER & ENV CHECK
# ================================================================
def print_header():
    print("\n" + "=" * 78)
    print("       CHINA PROFESSOR EMAIL AGENT - MULTI-GEMINI")
    print("=" * 78 + "\n")
    print(f"CSV FILE              = {CSV_FILE.name}")
    print(f"DRY_RUN               = {DRY_RUN}")
    print(f"MAX_EMAILS            = {'ALL' if MAX_EMAILS == 0 else MAX_EMAILS}")
    print(f"EMAIL_DELAY_SECONDS   = {EMAIL_DELAY_SECONDS}\n")
    print("Gemini fallback models:")
    for index, model in enumerate(ACTIVE_GEMINI_MODELS, start=1): print(f"  {index}. {model}")
    print(f"Active model list: {ACTIVE_MODELS_FILE.name}")
    print(f"\nGEMINI_RETRIES_PER_MODEL = {GEMINI_RETRIES_PER_MODEL}\n")

def check_environment():
    missing = [v for v, k in [("GEMINI_API_KEY", GEMINI_API_KEY), ("GEMINI_MODELS", GEMINI_MODELS), 
                              ("SMTP_EMAIL", SMTP_EMAIL), ("SMTP_PASSWORD", SMTP_PASSWORD)] if not k]
    if missing:
        print(f"{RED}Missing environment variables:{RESET}")
        for item in missing: print(f"  - {item}")
        return False
    print(f"{GREEN}✓ Gemini & Gmail credentials found.{RESET}")
    return True

def check_attachments():
    print(f"\n{CYAN}Checking attachments...{RESET}")
    attachments_ok = True
    for label, attachment in [("CV", CV_FILE), ("Thesis", THESIS_FILE)]:
        if not attachment.is_file():
            print(f"{RED}✗ {label} not found: {attachment}{RESET}")
            attachments_ok = False
        else:
            print(f"{GREEN}✓ {label} found: {attachment.name}{RESET}")
    return attachments_ok

def extract_pdf_text(pdf_path):
    if not pdf_path.is_file():
        print(f"{YELLOW}Warning: PDF not found: {pdf_path}{RESET}")
        return ""
    if PdfReader is None:
        print(f"{YELLOW}Warning: No PDF text extractor is installed. Install dependencies with: python -m pip install -r requirements.txt{RESET}")
        return ""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        print(f"{YELLOW}Warning: Could not open PDF {pdf_path.name}: {exc}{RESET}")
        return ""

    extracted_pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            print(f"{YELLOW}Warning: Could not extract text from {pdf_path.name} page {page_number}: {exc}{RESET}")
            page_text = ""
        if page_text.strip():
            extracted_pages.append(page_text)
    return "\n".join(extracted_pages)[:15000]

def load_professors():
    print(f"\n{CYAN}Loading professor database...{RESET}")
    if not CSV_FILE.exists(): raise FileNotFoundError(f"CSV file not found:\n{CSV_FILE}")
    professors = []
    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        headers = [clean_text(h) for h in reader.fieldnames]
        
        # Check that all required columns are present
        missing = [col for col in EXPECTED_COLUMNS if col not in headers]
        if missing:
            raise ValueError(f"CSV is missing required columns:\n" + "\n".join(f" - {x}" for x in missing))
        
        for row_number, row in enumerate(reader, start=2):
            # Map CSV columns to internal keys used by the rest of the script
            # Combine research_area and last_research for a richer description
            research_area = clean_text(row.get("research_area", ""))
            last_research = clean_text(row.get("last_research", ""))
            research_topic = clean_text(row.get("research_topic", ""))
            combined_research = research_area
            if last_research:
                if combined_research:
                    combined_research += "; " + last_research
                else:
                    combined_research = last_research

            professors.append({
                "University_Name": clean_text(row.get("university_name", "")),
                "Professor_Name": clean_text(row.get("professor_name", "")),
                "Professor_Email": clean_text(row.get("email", "")),
                # Use combined research info for the prompt
                "Latest_Research_or_Research_Areas": combined_research,
                # The specific research topic the applicant wants to pursue under this professor
                "Applicant_Proposed_Research_Topic": research_topic,
                # We don't have a URL column; keep empty
                "Professor_Profile_URL": "",
                "_csv_row": row_number
            })
    print(f"{GREEN}✓ Loaded {len(professors)} professor records.{RESET}")
    return professors

# ================================================================
# EMAIL VALIDATION & LOGGING
# ================================================================
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

def is_valid_email(email):
    email = clean_text(email)
    return bool(email and len(email) <= 254 and EMAIL_PATTERN.match(email))

def validate_professor(professor):
    if not professor.get("Professor_Name"): return False, "Missing Professor_Name"
    if not professor.get("University_Name"): return False, "Missing University_Name"
    if not is_valid_email(professor.get("Professor_Email")): return False, f"Invalid email format: {professor.get('Professor_Email')}"
    return True, "OK"

def ensure_email_log():
    if not EMAIL_LOG_FILE.exists():
        with open(EMAIL_LOG_FILE, "w", encoding="utf-8", newline="") as file:
            csv.DictWriter(file, fieldnames=LOG_COLUMNS).writeheader()

def read_sent_emails():
    """Read EMAIL_LOG.csv and return a set of normalised emails that were SENT.
    Always parses using the current LOG_COLUMNS fieldnames so the data columns
    are correctly mapped even if the file header is from an older schema."""
    ensure_email_log()
    sent = set()
    try:
        with open(EMAIL_LOG_FILE, "r", encoding="utf-8", newline="") as file:
            # Always supply LOG_COLUMNS so data always lines up correctly.
            # Skip the actual header row by checking Professor_Email value.
            reader = csv.DictReader(file, fieldnames=LOG_COLUMNS)
            for row in reader:
                # Skip the header row itself
                if clean_text(row.get("Professor_Email", "")).lower() == "professor_email":
                    continue
                email_status = clean_text(row.get("Email_Status", "")).upper()
                professor_email = clean_text(row.get("Professor_Email", ""))
                if email_status == "SENT" and professor_email:
                    sent.add(normalize_email(professor_email))
    except Exception:
        pass
    return sent


def write_log(professor, subject="", score="", gemini_model="", gemini_status="", google_search_used="", research_sources="", email_status="", mode="", error=""):
    ensure_email_log()
    row = {
        "Timestamp": now_string(), "Professor_Name": professor.get("Professor_Name", ""),
        "Professor_Email": professor.get("Professor_Email", ""), "University_Name": professor.get("University_Name", ""),
        "Subject": subject, "Research_Match_Score": score, "Gemini_Model": gemini_model,
        "Gemini_Status": gemini_status, "Google_Search_Used": google_search_used,
        "Research_Sources": research_sources, "Email_Status": email_status, "Mode": mode, "Error": error
    }
    with open(EMAIL_LOG_FILE, "a", encoding="utf-8", newline="") as file:
        csv.DictWriter(file, fieldnames=LOG_COLUMNS).writerow(row)

# ================================================================
# GEMINI PROMPT
# ================================================================
def build_gemini_prompt(professor, cv_text, regeneration_error="", is_first_model=False):
    professor_json = json.dumps(professor, ensure_ascii=False, indent=2)
    regeneration_section = ""
    if regeneration_error:
        regeneration_section = f"\nTHIS IS A REGENERATION. Previous failed: {regeneration_error}. Fix it silently."

    original_formatting = """Use this structure:

Dear Professor [Surname],

Paragraph 1: Introduce the applicant warmly. Express genuine, specific admiration for the
professor's research. Mention the CSC/ANSO scholarship application and request supervision
and an acceptance letter. Make the professor feel their specific work is valued — not a
generic opening.

Paragraph 2 (THE MOST IMPORTANT): Reference the 'Applicant_Proposed_Research_Topic' from
the professor data. Articulate clearly how this specific topic aligns with the professor's
expertise and recent work. Show intellectual depth — mention 1-2 concrete aspects of the
professor's work and explain why the applicant is excited to contribute to it. This must
read as if written by a genuinely enthusiastic, well-read scholar, not a template.

Paragraph 3: Briefly highlight the applicant's academic background (degree, university,
relevant skills in research and writing). Mention any relevant experience that makes the
applicant a strong candidate for this professor's group.

Paragraph 4: Politely and directly ask whether the professor is currently accepting
Master's students and whether they would be willing to supervise the applicant.

Thank you for your time and consideration. I look forward to hearing from you.

Best regards,

{APPLICANT_NAME}
{APPLICANT_DEGREE}
{APPLICANT_UNIVERSITY}
{APPLICANT_WEBSITE}

STRICT RULES:
1. research_match_score must be integer 0-100.
2. Do not invent professor facts. Email MUST be between 200-270 words.
3. The subject must be specific and compelling — mention the research topic and CSC/ANSO.
   Do NOT use a generic subject line. Reference the professor's actual research area.
4. Vary the subject wording naturally instead of reusing a generic subject.
5. Return ONLY the JSON object conforming to the schema.
6. Do NOT mention the applicant's CGPA or GPA anywhere in the email body.
7. The tone should be scholarly, enthusiastic, and respectful. The professor must feel that
   this email was written specifically for them — not mass-mailed.
8. Use the 'Applicant_Proposed_Research_Topic' as the core intellectual hook of the email.
   This is the applicant's proposed contribution to the professor's research group.
9. Output the email body as clean plain text with one blank line between paragraphs. Never
   return the entire email as a single paragraph. Do not use HTML or Markdown.
"""

    strict_formatting = """Use this exact structure, matching the paragraph breaks exactly:

Dear Professor [Surname],

I am writing to express my sincere interest in joining your research group at [University Name] as a Master's student under the Chinese Government Scholarship (CSC/ANSO). Having carefully studied your work on [specific research areas from professor data], I am deeply inspired by your approach to [specific aspect of professor's research]. I am reaching out to respectfully request your supervision and an acceptance letter in support of my CSC application.

Your scholarship on [specific research area] resonates profoundly with the research I am eager to undertake: [rephrase Applicant_Proposed_Research_Topic in 1–2 compelling sentences showing intellectual alignment with the professor's work]. I am particularly drawn to how your insights on [professor's research] can illuminate [specific aspect of the proposed topic], and I am excited to develop this line of inquiry under your expert guidance.

I hold a {APPLICANT_DEGREE} from the {APPLICANT_UNIVERSITY}, where I developed strong skills in literary analysis, critical theory, and academic research. My academic background has prepared me to engage rigorously with the scholarly discourse your group pursues, and I am eager to contribute meaningfully to your ongoing projects.

Could you kindly let me know whether you are currently accepting new Master's students? I would be deeply grateful for the opportunity to discuss how I might contribute to your research group.

Thank you sincerely for your time and consideration.

I look forward to hearing from you.

Best regards,

{APPLICANT_NAME}
{APPLICANT_DEGREE}
{APPLICANT_UNIVERSITY}
{APPLICANT_WEBSITE}

STRICT RULES:
1. research_match_score must be integer 0-100.
2. Do not invent professor facts. Email MUST be between 200-270 words.
3. The subject must be specific and compelling — reference the professor's actual research
   area and the CSC/ANSO scholarship. Do NOT use a vague generic subject.
4. Vary the subject wording naturally. Do not reuse a canned subject template.
5. Return ONLY the JSON object conforming to the schema.
6. Do NOT mention the applicant's CGPA or GPA anywhere in the email body.
7. The tone must be scholarly, warm, and highly personalised. The professor must feel this
   email was written specifically for them and their work.
8. The 'Applicant_Proposed_Research_Topic' is the intellectual centrepiece of the email.
   Use it to show concrete alignment between the applicant and the professor's expertise.
9. Output the email body as clean plain text with one blank line between paragraphs. Never
   return the entire email as a single paragraph, and keep the greeting, body paragraphs,
   closing, and signature properly separated. Do not use HTML, Markdown, literal escaped
   newline characters like "\\n" (use standard JSON newlines instead), or excessive whitespace."""

    formatting_requirements = original_formatting if is_first_model else strict_formatting

    prompt = f"""
You are preparing ONE professional academic inquiry email.

IMPORTANT RESEARCH WORKFLOW:
- Use ONLY the provided 'Latest_Research_or_Research_Areas'. Do not perform web searches.

============================================================
PROFESSOR DATA
============================================================
{professor_json}

============================================================
APPLICANT
============================================================
Name: {APPLICANT_NAME}
Degree: {APPLICANT_DEGREE}
University: {APPLICANT_UNIVERSITY}
IELTS: {APPLICANT_IELTS}
Research interests: {APPLICANT_INTERESTS}
Goal: {APPLICANT_GOAL}

============================================================
CV TEXT
============================================================
{cv_text}

============================================================
EMAIL FORMATTING REQUIREMENTS
============================================================
{formatting_requirements}
{regeneration_section}
"""
    return prompt

# ================================================================
# HTTP & GEMINI PARSING
# ================================================================
def gemini_request(prompt, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2, 
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json", 
            "responseSchema": GEMINI_RESPONSE_SCHEMA
        }
    }
    
    return requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)

def extract_gemini_text(data):
    candidates = data.get("candidates", [])
    if not candidates: raise ValueError(f"Gemini returned no candidates.")
    
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason", "UNKNOWN")
    texts = [part["text"] for part in candidate.get("content", {}).get("parts", []) if "text" in part]
    
    if not texts:
        raise ValueError(f"Gemini returned no text content. Finish Reason: {finish_reason}")
    if finish_reason == "MAX_TOKENS":
        raise ValueError("Gemini response was truncated at the token limit; retrying with a larger response budget.")
    return "".join(texts)

def parse_json_response(text):
    text = clean_text(text)
    if not text: raise ValueError("Empty response.")
    try: return json.loads(text)
    except: pass
    
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    try: return json.loads(cleaned)
    except: pass
    
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1: 
        preview = text[:250].replace('\n', ' ')
        raise ValueError(f"No JSON object found. Gemini responded with: '{preview}...'")
        
    try:
        return json.loads(cleaned[start:end + 1])
    except Exception as exc:
        raise ValueError(f"JSON parsing failed: {exc}. Snippet: {cleaned[start:start+100]}")

def save_gemini_debug(professor, attempt, raw_text, error="", http_status=None, model=""):
    name = safe_filename(professor.get("Professor_Name", "unknown"))
    path = GEMINI_DEBUG_DIR / f"{name}_{safe_filename(model)}_attempt_{attempt}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(path, "w", encoding="utf-8") as file:
        file.write(f"GEMINI DIAGNOSTIC\n{'='*70}\nProfessor: {professor.get('Professor_Name', '')}\nModel: {model}\nAttempt: {attempt}\nHTTP status: {http_status}\nError: {error}\n\nRAW RESPONSE\n{'-'*70}\n{raw_text or '<EMPTY>'}")
    return path

# ================================================================
# EMAIL BODY CLEANING & VALIDATION
# ================================================================
def get_professor_surname(name):
    return clean_text(name).split()[-1] if clean_text(name) else ""

def get_subject_variant(professor):
    email = normalize_email(professor.get("Professor_Email", ""))
    index = int(hashlib.sha256(email.encode("utf-8")).hexdigest(), 16) % len(SUBJECT_VARIANTS)
    return SUBJECT_VARIANTS[index]

def clean_email_body(body, professor_name):
    # ── 1. Strip markdown / formatting artefacts ──────────────────────
    body = clean_text(body)
    body = re.sub(r'\*{1,3}', '', body)          # *, **, ***
    body = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', body)  # _italic_, __bold__
    body = re.sub(r'^#{1,6}\s*', '', body, flags=re.MULTILINE)  # headings
    body = re.sub(r'`[^`]*`', lambda m: m.group(0).strip('`'), body)  # inline code

    # ── 2. Normalise line endings ─────────────────────────────────────
    body = body.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    body = body.replace("\r\n", "\n").replace("\r", "\n")

    # ── 3. Remove any leading Subject/Email Body label lines ──────────
    body = re.sub(r"^(Subject|Email Body)\s*:\s*.*?\n+", "", body, flags=re.IGNORECASE).strip("\"' ")

    # ── 4. Ensure professional greeting ──────────────────────────────
    surname = get_professor_surname(professor_name)
    if not re.match(r"^(Dear|Hello|Hi)\b", body, flags=re.IGNORECASE):
        body = f"Dear Professor {surname},\n\n{body}" if surname else f"Dear Professor,\n\n{body}"

    # ── 5. Smart paragraph insertion ─────────────────────────────────
    # Only inject a paragraph break when a known paragraph-starter phrase
    # follows a sentence-ending character (. ! ?) optionally followed by
    # whitespace/newlines.  This prevents splitting mid-sentence fragments
    # like "...and\nI look forward to contributing...".
    PARA_STARTERS = [
        r"I recently", r"During my", r"Furthermore", r"Moreover",
        r"My current", r"I am currently", r"Could you please",
        r"Could you kindly", r"Thank you", r"I look forward",
        r"I hold a", r"I would be", r"Are you currently",
    ]
    for starter in PARA_STARTERS:
        # Match: sentence-end punctuation → optional whitespace/newlines → starter
        body = re.sub(
            rf"([.!?])\s*\n*\s*({starter})",
            rf"\1\n\n\2",
            body,
            flags=re.IGNORECASE,
        )

    # ── 6. Strip any trailing closing / signature Gemini may have added ──
    # Remove "Thank you..." and "I look forward..." sentences 
    # so we can re-append a clean, controlled closing block.
    body = re.sub(
        r"\n*Thank you (sincerely )?for your time and consideration\.?\s*",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\n*I look forward to hearing from you\.?\s*",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(r"\s*Best regards,?.*$", "", body, flags=re.IGNORECASE | re.DOTALL).strip()

    # ── 7. Re-append controlled, well-formatted closing ───────────────
    body += (
        f"\n\nThank you for your time and consideration.\n"
        f"\nI look forward to hearing from you."
        f"\n\nBest regards,\n\n"
        f"{APPLICANT_NAME}\n{APPLICANT_DEGREE}\n{APPLICANT_UNIVERSITY}\n{APPLICANT_WEBSITE}"
    )

    # ── 8. Collapse excessive blank lines ─────────────────────────────
    return re.sub(r"\n{3,}", "\n\n", body).strip()

def validate_generated_email(subject, body):
    subject, body = clean_text(subject), clean_text(body)
    if not subject or not body: return False, "Missing subject or body"
    if len(body) < 150: return False, "Email body is too short"

    lower_body = body.lower()
    if any(p in lower_body for p in ["as an ai", "chatgpt", "gemini", "ai-generated"]): return False, "Forbidden AI phrase detected"
    if any(p in lower_body for p in ["system prompt", "research_match_score", "email_body"]): return False, "Instruction leakage"
    if not re.search(r"^(Dear|Hello|Hi)\b", body, flags=re.IGNORECASE): return False, "Missing professional greeting"

    # Check that the body asks about supervision/admission OR joining the research group
    supervision_keywords = ["supervis", "master", "accepting", "admission", "acceptance letter", "research group", "joining"]
    if not any(w in lower_body for w in supervision_keywords):
        return False, "Email does not clearly ask about Master's supervision, admission, or joining the research group"

    if "gpa" in lower_body or "cgpa" in lower_body:
        return False, "Email incorrectly contains CGPA/GPA."

    # Ensure the controlled closing block was appended correctly
    if "best regards" not in lower_body:
        return False, "Email is missing the closing signature"
    if "i look forward" not in lower_body:
        return False, "Email is missing the closing 'I look forward' line"

    return True, "OK"

def validate_gemini_result(result, professor):
    required = ["research_match_score", "research_overlap", "research_relevance", "reason_for_contact", "research_summary", "subject", "email_body"]
    if missing := [key for key in required if key not in result]: raise ValueError(f"Missing Gemini fields: {', '.join(missing)}")
    
    result["research_match_score"] = int(result["research_match_score"])
    if not isinstance(result["research_overlap"], list) or not result["research_overlap"]: raise ValueError("research_overlap must be a non-empty array.")
    result["email_body"] = clean_email_body(result["email_body"], professor.get("Professor_Name", ""))

    # Keep Gemini's personalised subject if it looks reasonable;
    # fall back to the hash-based variant only when it is missing or too short.
    gemini_subject = clean_text(result.get("subject", ""))
    if len(gemini_subject) < 20:
        result["subject"] = get_subject_variant(professor)
    else:
        result["subject"] = gemini_subject

    valid, reason = validate_generated_email(result["subject"], result["email_body"])
    if not valid: raise ValueError(reason)
    return result

# ================================================================
# GEMINI GENERATION LOOP
# ================================================================
def calculate_retry_delay(attempt, response=None, status_code=None):
    if response is not None and response.headers.get("Retry-After"):
        try: return max(1, int(float(response.headers.get("Retry-After"))))
        except ValueError: pass
        
    delay = GEMINI_RETRY_DELAY * (2 ** (attempt - 1))
    return min(120, int(delay * random.uniform(0.9, 1.1)))

def call_gemini(professor, cv_text):
    previous_error = ""
    last_error = ""
    if not ACTIVE_GEMINI_MODELS:
        raise RuntimeError("No active Gemini models remain. Check model quotas or update GEMINI_MODELS.")

    models_to_try = list(ACTIVE_GEMINI_MODELS)
    for model_index, model in enumerate(models_to_try, start=1):
        is_first_model = (model_index == 1)
        print(f"\n{CYAN}==================================================\nGemini model {model_index}/{len(models_to_try)}: {model}\n=================================================={RESET}")
        
        for attempt in range(1, GEMINI_RETRIES_PER_MODEL + 1):
            print(f"{CYAN}→ Generation attempt {attempt}/{GEMINI_RETRIES_PER_MODEL}{RESET}")
            prompt = build_gemini_prompt(professor, cv_text, previous_error, is_first_model)
            
            try:
                response = gemini_request(prompt, model)
                status, raw_text = response.status_code, response.text
                
                # IMMEDIATE SKIP ON RATE LIMIT (NO COOLDOWN WAIT)
                if status == 429:
                    error = gemini_http_error(response, model)
                    save_gemini_debug(professor, f"{model_index}_{attempt}", raw_text, error, status, model)
                    if "RESOURCE_EXHAUSTED" in error and not is_model_quota_error(error):
                        raise GeminiQuotaError(
                            f"Gemini project quota exhausted for the configured API key/project. "
                            f"Check billing and quota at https://ai.google.dev/gemini-api/docs/rate-limits. "
                            f"Provider response: {error}"
                        )
                    if is_model_quota_error(error):
                        remove_exhausted_model(model)
                    print(f"{YELLOW}⚠ {error}. Switching immediately to the next model...{RESET}")
                    last_error = error
                    break # Break the attempt loop to trigger the model switch instantly
                    
                if status != 200:
                    error = f"{model}: Gemini HTTP {status}: {raw_text[:1000]}"
                    save_gemini_debug(professor, f"{model_index}_{attempt}", raw_text, error, status, model)
                    print(f"{RED}✗ {error}{RESET}")
                    last_error = error
                    if attempt < GEMINI_RETRIES_PER_MODEL:
                        time.sleep(calculate_retry_delay(attempt, response, status_code=status))
                        continue
                    break
                    
                print(f"{GREEN}✓ HTTP response received from {model}{RESET}")
                data = response.json()
                raw_text = extract_gemini_text(data)
                
                result = parse_json_response(raw_text)
                result = validate_gemini_result(result, professor)
                print(f"{GREEN}✓ Valid professional email generated.\n✓ Model used: {model}{RESET}")
                result["_model_used"] = model
                return result
                
            except GeminiQuotaError:
                raise
            except Exception as exc:
                last_error = str(exc)
                save_gemini_debug(professor, f"{model_index}_{attempt}", raw_text if 'raw_text' in locals() else "", last_error, response.status_code if 'response' in locals() else None, model)
                print(f"{RED}✗ {model} failed:{RESET} {last_error}")
                previous_error = last_error
                if attempt < GEMINI_RETRIES_PER_MODEL:
                    time.sleep(calculate_retry_delay(attempt, 'response' in locals() and response or None))
                    
        # If we broke out due to 429 or exhausted attempts:
        print(f"{YELLOW}⚠ Model exhausted: {model}{RESET}")
        if model_index < len(models_to_try):
            print(f"{CYAN}→ Switching to next model: {models_to_try[model_index]}{RESET}")
            time.sleep(1) # tiny delay just to avoid spamming connections
            
    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

# ================================================================
# SAVING, PREVIEW & SENDING
# ================================================================
def save_draft(professor, result):
    path = GENERATED_EMAILS_DIR / f"{safe_filename(professor.get('Professor_Name', 'unknown'))}_{safe_filename(professor.get('Professor_Email', 'unknown'))}.txt"
    with open(path, "w", encoding="utf-8") as file:
        file.write(f"Professor: {professor['Professor_Name']}\nUniversity: {professor['University_Name']}\nEmail: {professor['Professor_Email']}\n")
        file.write(f"Gemini Model: {result.get('_model_used', '')}\nResearch Match: {result['research_match_score']}/100\n\nResearch Summary:\n{result['research_summary']}\n\nSubject: {result['subject']}\n\nEmail Body:\n{'-'*70}\n{result['email_body']}\n")
    return path

def show_email_preview(professor, result):
    print(f"\n{'='*78}\n{BOLD}EMAIL PREVIEW{RESET}\n{'='*78}\nProfessor: {professor['Professor_Name']}\nUniversity: {professor['University_Name']}\nEmail: {professor['Professor_Email']}")
    print(f"{BOLD}Subject:{RESET}\n{result['subject']}\n\n{BOLD}Body:{RESET}\n{'-'*78}\n{result['email_body']}\n{'-'*78}\n")

def send_email(professor, subject, body):
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = SMTP_EMAIL, professor["Professor_Email"], subject
    message.set_content(body)
    message.add_alternative(body.replace('\n', '<br>'), subtype='html')
    
    for label, attachment in [("CV", CV_FILE), ("thesis", THESIS_FILE)]:
        if attachment.is_file():
            with open(attachment, "rb") as file:
                message.add_attachment(file.read(), maintype="application", subtype="pdf", filename=attachment.name)
            print(f"{GREEN}✓ Attached {label}: {attachment.name}{RESET}")
        else:
            print(f"{YELLOW}⚠ {label} file not found – skipping attachment: {attachment.name}{RESET}")
    
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(message)

# ================================================================
# PROCESS ONE PROFESSOR
# ================================================================
def process_professor(professor, cv_text, sent_emails):
    print(f"\n{'='*78}\n{BOLD}Professor: {professor['Professor_Name']}{RESET}\nUniversity: {professor['University_Name']}\nEmail: {professor['Professor_Email']}")
    
    valid, reason = validate_professor(professor)
    if not valid:
        print(f"{YELLOW}SKIPPED: {reason}{RESET}")
        write_log(professor, email_status="SKIPPED_INVALID_ROW", mode="DRY_RUN" if DRY_RUN else "LIVE", error=reason)
        return {"state": "skipped"}
        
    if normalize_email(professor["Professor_Email"]) in sent_emails:
        print(f"{YELLOW}SKIPPED: Email was already sent previously.{RESET}")
        write_log(professor, email_status="SKIPPED_ALREADY_SENT", mode="DRY_RUN" if DRY_RUN else "LIVE")
        return {"state": "skipped"}
        
    print(f"\n{CYAN}→ Generating personalized email...{RESET}")
    try: result = call_gemini(professor, cv_text)
    except GeminiQuotaError as exc:
        print(f"{RED}✗ {exc}{RESET}")
        write_log(professor, email_status="GEMINI_QUOTA_EXHAUSTED", mode="DRY_RUN" if DRY_RUN else "LIVE", error=str(exc))
        return {"state": "quota_exhausted"}
    except Exception as exc:
        print(f"{RED}✗ Gemini failed:{RESET} {exc}")
        write_log(professor, email_status="GEMINI_FAILED", mode="DRY_RUN" if DRY_RUN else "LIVE", error=str(exc))
        return {"state": "failed"}
        
    try: print(f"{GREEN}✓ Draft saved: {save_draft(professor, result).name}{RESET}")
    except Exception as exc: print(f"{YELLOW}Warning: draft save failed: {exc}{RESET}")

    show_email_preview(professor, result)

    # ── Score gate ────────────────────────────────────────────────
    score = int(result.get("research_match_score", 0) or 0)
    if score < MIN_RESEARCH_SCORE:
        print(f"{YELLOW}SKIPPED: Research match score {score} is below minimum threshold ({MIN_RESEARCH_SCORE}).{RESET}")
        write_log(professor, subject=result["subject"], score=score, gemini_model=result.get("_model_used", ""), gemini_status="SUCCESS", email_status="SKIPPED_LOW_SCORE", mode="DRY_RUN" if DRY_RUN else "LIVE")
        return {"state": "skipped"}
    # ─────────────────────────────────────────────────────────────

    if DRY_RUN:
        print(f"\n{YELLOW}DRY RUN: Email NOT sent.{RESET}")
        write_log(professor, subject=result["subject"], score=result["research_match_score"], gemini_model=result.get("_model_used", ""), gemini_status="SUCCESS", email_status="DRY_RUN_NOT_SENT", mode="DRY_RUN")
        return {"state": "generated"}
        
    if REVIEW_BEFORE_SEND and input("\nSend this email? [y]es / [n]o / [s]kip: ").strip().lower() not in {"y", "yes"}:
        print(f"{YELLOW}Email not sent.{RESET}")
        write_log(professor, subject=result["subject"], gemini_status="SUCCESS", email_status="SKIPPED_REVIEW", mode="LIVE")
        return {"state": "skipped"}
            
    print(f"\n{CYAN}→ Sending via Gmail SMTP...{RESET}")
    try:
        send_email(professor, result["subject"], result["email_body"])
        print(f"\n{GREEN}✓ EMAIL SENT SUCCESSFULLY{RESET}")
        write_log(professor, subject=result["subject"], score=result["research_match_score"], gemini_model=result.get("_model_used", ""), gemini_status="SUCCESS", email_status="SENT", mode="LIVE")
        sent_emails.add(normalize_email(professor["Professor_Email"]))
        return {"state": "sent"}
    except Exception as exc:
        print(f"{RED}✗ Gmail sending failed: {exc}{RESET}")
        write_log(professor, subject=result["subject"], gemini_status="SUCCESS", email_status="SEND_FAILED", mode="LIVE", error=str(exc))
        return {"state": "failed"}

# ================================================================
# MAIN ENTRY
# ================================================================
def main():
    # NOTE: do NOT call write_active_models() here — that would overwrite the
    # JSON file (and any previously-removed exhausted models) with the full
    # hardcoded list before we even start. We only write the file when a model
    # is actually removed during a run.
    print_header()
    if not check_environment() or not check_attachments(): return
    try: professors = load_professors()
    except Exception as exc:
        print(f"{RED}Could not load professor database:{RESET}\n{exc}"); return
        
    sent_emails = read_sent_emails()
    print(f"\n{CYAN}Previously sent unique emails: {len(sent_emails)}{RESET}\n\n{CYAN}Reading applicant CV...{RESET}")
    
    cv_text = extract_pdf_text(CV_FILE)
    if cv_text: print(f"{GREEN}✓ CV text extracted ({len(cv_text)} characters).{RESET}")
    else: print(f"{YELLOW}⚠ CV text could not be extracted.{RESET}")
    
    processed = generated = sent = skipped = failed = 0
    for professor in professors:
        if 0 < MAX_EMAILS <= processed: break
        processed += 1
        state = process_professor(professor, cv_text, sent_emails)["state"]
        
        if state == "sent": sent += 1
        elif state == "generated": generated += 1
        elif state == "skipped": skipped += 1
        elif state == "failed": failed += 1
        elif state == "quota_exhausted":
            failed += 1
            print(f"{YELLOW}Stopping batch because the Gemini project quota is exhausted.{RESET}")
            break
        
        if not DRY_RUN and state == "sent" and processed < len(professors):
            print(f"\n{YELLOW}Waiting {EMAIL_DELAY_SECONDS} seconds before next professor...{RESET}")
            time.sleep(EMAIL_DELAY_SECONDS)
            
    print(f"\n{'='*78}\n{BOLD}                     FINAL SUMMARY{RESET}\n{'='*78}\nTotal database records:      {len(professors)}\nProcessed:                   {processed}\nEmails generated:            {generated}\nEmails sent:                 {sent}\nSkipped:                     {skipped}\nFailed:                      {failed}\n")

if __name__ == "__main__":
    main()