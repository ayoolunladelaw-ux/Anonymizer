# 🔒 Private AI Preprocessor

**Anonymize confidential documents locally, then safely use any cloud AI.**

A hackathon project that solves the #1 blocker to enterprise LLM adoption: legal, healthcare, and finance teams can't use ChatGPT/Claude/Gemini because they'd leak PII.

## The pitch (30 seconds)

> "Your company wants to use AI to summarize contracts, draft emails, and analyze meeting notes. But you can't — every document has names, dollar amounts, and client info that can't leave your network. This tool anonymizes everything locally, sends only the redacted text to the cloud AI, then un-redacts the response on your machine. Claude never sees a single real name. You get the productivity boost. Your legal team sleeps at night."

## How it's different

- 🔒 **Detection runs 100% locally** — uses Microsoft Presidio + spaCy. No data leaves your laptop during anonymization.
- 🔁 **Reversible** — decoder ring stays on your machine, so anonymized AI responses can be un-redacted locally.
- 🎯 **Consistent** — Ayo becomes Party A *everywhere* in the document, not randomly.
- ⚙️ **Configurable** — choose what to detect, how to replace it, sensitivity threshold.
- ☁️ **Proves the concept** — the "Safe Cloud AI" tab demonstrates the full workflow end-to-end.

## Setup (5 minutes)

1. **Install Python 3.10+**
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Download the spaCy English model** (Presidio needs it — one-time, ~15 MB)
   ```bash
   python -m spacy download en_core_web_lg
   ```
4. **Run the app**
   ```bash
   streamlit run app.py
   ```

The Anthropic API key is only needed for the optional "Safe Cloud AI" demo tab — the core anonymization works fully offline.

## Demo script (3 minutes)

**[Tab 1: Anonymize]**
1. Select "Contract snippet" sample. One click.
2. Hit **Anonymize**. Point out it runs locally — no API call, no network activity.
3. Show the **highlighted original** (yellow highlights on detected entities) next to the **clean anonymized output**.
4. Scroll to the **decoder ring**. "Ayo is Party A everywhere. Consistency matters for legal documents."
5. Download both files.

**[Tab 2: De-anonymize]**
6. Paste the anonymized text back. Upload the decoder. Show the original recovered. *"Most redaction tools are one-way. This one isn't."*

**[Tab 3: Safe Cloud AI — the money shot]**
7. Go to the Safe Cloud AI tab. Pick "Summarize in 3 bullet points."
8. Show what Claude will see — only "Party A", "Xdollars", etc.
9. Hit send. Claude returns a summary using the anonymized placeholders.
10. The tool **automatically un-redacts the response locally** — judges see a real-looking summary with real names, even though Claude never saw them.
11. Close line: *"Claude — or any AI — can be useful without being trusted with your secrets."*

## Hackathon positioning

Call it one of these — pick what fits your crowd:
- **"Private AI Preprocessor"** (enterprise/legal)
- **"PII Firewall for LLMs"** (security crowd)
- **"BYO-AI without the data leak"** (dev crowd)

## Day 2 stretch goals

- **PDF + .docx upload** (`pypdf`, `python-docx`) — 30 min
- **Custom recognizers** — let users add their own patterns (e.g., internal project codenames, case numbers)
- **Differential privacy mode** — for numbers, add small random noise instead of replacing
- **Batch mode** — drop a folder, get all files anonymized with a shared decoder
- **"What would be leaked?" scorecard** — show a GDPR-style risk score for the original document
- **Deploy to Streamlit Community Cloud** (free) — let judges try it on their phones

## Technical notes

- Presidio detects 20+ entity types out of the box (PERSON, LOCATION, PHONE_NUMBER, EMAIL_ADDRESS, CREDIT_CARD, US_SSN, IBAN, etc.)
- I added custom recognizers for dollar amounts, Canadian postal codes, and generic North American street addresses
- The consistent-mapping layer is custom — Presidio doesn't do cross-reference tracking by default
- The de-anonymization is pure string replacement (sorted by length to avoid partial overlaps)

## Files

- `app.py` — the full Streamlit application
- `requirements.txt` — Python dependencies
- `README.md` — this file

## Known limitations (be honest with judges)

- spaCy NER misses unusual or non-Western names sometimes — can be tuned with the sensitivity slider, or you can add custom recognizers
- Addresses outside the US/Canada street-suffix format won't match the regex — easy to extend
- `presidio-anonymizer` is imported but we build our own mapping layer on top for reversibility (the built-in anonymizer isn't designed for un-redaction)
