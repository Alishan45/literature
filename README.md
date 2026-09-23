# 📚 Literature Research Email Automation

An AI-powered tool that automatically generates and sends personalized academic outreach emails to professors, using Google Gemini language models and a curated literature research database.

---

## 🚀 Features

- **AI-Generated Emails** — Uses Google Gemini models to draft professional, personalized emails for each professor
- **Bulk Outreach** — Reads professor data from a CSV and processes them at scale
- **Deduplication** — Tracks sent emails via `EMAIL_LOG.csv` to avoid re-sending
- **Multi-Model Testing** — `model_test.py` dry-runs multiple Gemini models to find the best performer
- **Progress Tracking** — `check_remaining.py` shows how many professors still need to be contacted
- **Dry Run Mode** — Test email generation without actually sending anything

---

## 📁 Project Structure

```
literature/
├── chinese.py              # Main email generation & sending script
├── model_test.py           # Dry-run tester across multiple Gemini models
├── check_remaining.py      # Shows remaining professors to contact
├── list_models.py          # Lists available Gemini models from API
├── literature.csv          # Professor database (name, email, institution, etc.)
├── EMAIL_LOG.csv           # Log of all sent emails (auto-updated)
├── requirements.txt        # Python dependencies
├── .env                    # API keys & SMTP credentials (not committed)
├── generated_emails/       # Saved copies of generated email drafts
└── CV.pdf / THESIS.pdf     # Attachments used in outreach emails
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

### 4. Configure environment variables

Create a `.env` file in the project root with the following:

```env
# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# SMTP Email Settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=your_app_password_here
```

> **Note:** Use a [Gmail App Password](https://support.google.com/accounts/answer/185833), not your regular Gmail password.

---

## 🧪 Usage

### Run the main email sender
```bash
python chinese.py
```

### Test which Gemini models work best (dry run)
```bash
python model_test.py
```

### Check how many professors remain to be contacted
```bash
python check_remaining.py
```

### List available Gemini models
```bash
python list_models.py
```

### Dry run (generate emails without sending)
```bash
DRY_RUN=True python chinese.py
```

### Limit number of emails sent
```bash
MAX_EMAILS=5 python chinese.py
```

---

## 🔧 Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `GEMINI_MODELS` | Comma-separated model names to use |
| `SMTP_HOST` | SMTP server host (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP server port (e.g. `587`) |
| `SMTP_EMAIL` | Sender email address |
| `SMTP_PASSWORD` | Email app password |
| `DRY_RUN` | Set to `True` to skip actual sending |
| `MAX_EMAILS` | Maximum number of emails to process per run |

---

## 📊 Email Logging

All sent emails are recorded in `EMAIL_LOG.csv` with:
- Professor name & email
- Send timestamp
- Email status (`SENT` / `FAILED`)
- Model used

This ensures no professor is emailed twice across multiple runs.

---

## 🛡️ Security Notes

- **Never commit your `.env` file** — it is listed in `.gitignore`
- Revoke and regenerate API keys if they are accidentally exposed
- Use Gmail App Passwords instead of your main account password

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `pypdf` | Reading PDF attachments (CV, Thesis) |
| `python-dotenv` | Loading environment variables from `.env` |
| `requests` | HTTP calls to the Gemini API |

---

## 👤 Author

**Ali Shan** — [Alishan45](https://github.com/Alishan45)
