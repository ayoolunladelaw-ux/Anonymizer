"""
Anonymizer - Private AI Preprocessor (Hackathon Demo)

Runs 100% locally. Detects and redacts PII before you send anything to a cloud LLM.
Optionally demonstrates the "safe cloud workflow" by sending the ANONYMIZED text to Claude.

Run: streamlit run app.py
"""

import streamlit as st
import json
import os
from datetime import datetime
from collections import defaultdict

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="Private AI Preprocessor",
    page_icon="🔒",
    layout="wide",
)

# ---------- STYLES ----------
st.markdown("""
<style>
    .big-title { font-size: 2.4rem; font-weight: 700; margin-bottom: 0; }
    .subtitle { color: #666; margin-top: 0; font-size: 1.05rem; }
    .pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .pill-local { background: #d4f4dd; color: #1e6b3a; }
    .pill-cloud { background: #fde4d0; color: #8a4a1c; }
    .stat-box {
        background: #f4f4f6;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .stat-num { font-size: 2rem; font-weight: 700; color: #c15f3c; }
    .stat-label { font-size: 0.85rem; color: #666; }
    .mapping-row {
        background: #fff;
        border: 1px solid #e5e5e5;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        margin-bottom: 0.4rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .original { color: #c1432c; font-family: monospace; }
    .replacement { color: #2c7a3c; font-family: monospace; font-weight: 600; }
    .type-badge {
        font-size: 0.7rem;
        background: #eee;
        padding: 2px 8px;
        border-radius: 10px;
        color: #555;
    }
    mark.hl {
        background: #fff3a8;
        padding: 0 3px;
        border-radius: 3px;
    }
</style>
""", unsafe_allow_html=True)

# ---------- HEADER ----------
st.markdown('<p class="big-title">🔒 Private AI Preprocessor</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Anonymize confidential documents <b>locally</b>, '
    'then safely use any cloud AI — without leaking a single name, dollar amount, or address.</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<span class="pill pill-local">✅ Detection runs locally</span>'
    '<span class="pill pill-cloud">☁️ Cloud AI only sees anonymized text</span>',
    unsafe_allow_html=True,
)
st.markdown("---")


# ---------- LOAD PRESIDIO (cached) ----------
@st.cache_resource
def load_analyzer():
    """Load Presidio analyzer with custom recognizers. Cached so it loads once per session."""
    analyzer = AnalyzerEngine()

    # Custom: dollar amounts (matches $20,000 / $20000 / $20K / $1.5M / USD 5000)
    money_pattern = Pattern(
        name="money_pattern",
        regex=r"(?:\$|USD\s?|CAD\s?|€|£)\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s?[KMB])?|\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?dollars?\b",
        score=0.85,
    )
    money_recognizer = PatternRecognizer(
        supported_entity="MONEY",
        patterns=[money_pattern],
    )
    analyzer.registry.add_recognizer(money_recognizer)

    # Custom: Canadian postal codes
    postal_pattern = Pattern(
        name="ca_postal",
        regex=r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b",
        score=0.9,
    )
    postal_recognizer = PatternRecognizer(
        supported_entity="POSTAL_CODE",
        patterns=[postal_pattern],
    )
    analyzer.registry.add_recognizer(postal_recognizer)

    # Custom: street addresses (number + street name + suffix)
    street_pattern = Pattern(
        name="street_address",
        regex=r"\b\d{1,5}\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Crescent|Cres|Lane|Ln|Court|Ct|Way|Place|Pl)\b",
        score=0.85,
    )
    street_recognizer = PatternRecognizer(
        supported_entity="STREET_ADDRESS",
        patterns=[street_pattern],
    )
    analyzer.registry.add_recognizer(street_recognizer)

    return analyzer


# ---------- REPLACEMENT MAPPING LOGIC ----------
def build_consistent_mapping(analyzer_results, text, style):
    """
    Given Presidio's findings, build a consistent mapping so the same entity
    always gets the same replacement across the whole document.
    """
    seen = {}  # (entity_type, text_value) -> replacement
    counters = defaultdict(int)
    results_sorted = sorted(analyzer_results, key=lambda r: r.start)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for r in results_sorted:
        original_text = text[r.start:r.end].strip()
        key = (r.entity_type, original_text.lower())
        if key in seen:
            continue

        ent = r.entity_type

        if style == "Party labels":
            if ent == "PERSON":
                label = f"Party {letters[counters['PERSON'] % 26]}"
                counters["PERSON"] += 1
            elif ent == "MONEY":
                label = f"{letters[counters['MONEY'] % 26]}dollars"
                counters["MONEY"] += 1
            elif ent in ("LOCATION", "STREET_ADDRESS"):
                counters["ADDR"] += 1
                label = f"Address {counters['ADDR']}"
            elif ent == "EMAIL_ADDRESS":
                counters["EMAIL"] += 1
                label = f"email{counters['EMAIL']}@example.com"
            elif ent == "PHONE_NUMBER":
                counters["PHONE"] += 1
                label = f"Phone {counters['PHONE']}"
            elif ent == "POSTAL_CODE":
                counters["POSTAL"] += 1
                label = f"Postal {counters['POSTAL']}"
            elif ent == "ORGANIZATION":
                label = f"Company {letters[counters['ORG'] % 26]}"
                counters["ORG"] += 1
            elif ent == "DATE_TIME":
                counters["DATE"] += 1
                label = f"Date {counters['DATE']}"
            elif ent == "CREDIT_CARD":
                counters["CC"] += 1
                label = f"Card {counters['CC']}"
            elif ent == "US_SSN":
                counters["SSN"] += 1
                label = f"SSN {counters['SSN']}"
            elif ent == "IP_ADDRESS":
                counters["IP"] += 1
                label = f"IP {counters['IP']}"
            elif ent == "URL":
                counters["URL"] += 1
                label = f"URL {counters['URL']}"
            else:
                counters[ent] += 1
                label = f"{ent} {counters[ent]}"
        else:  # Descriptive
            counters[ent] += 1
            label = f"{ent}_{counters[ent]:03d}"

        seen[key] = label

    return seen


def apply_mapping(text, analyzer_results, mapping):
    """Apply the mapping by working from the end backwards to keep offsets valid."""
    results_sorted = sorted(analyzer_results, key=lambda r: r.start, reverse=True)
    new_text = text
    applied = []
    for r in results_sorted:
        original_text = text[r.start:r.end].strip()
        key = (r.entity_type, original_text.lower())
        if key not in mapping:
            continue
        replacement = mapping[key]
        new_text = new_text[:r.start] + replacement + new_text[r.end:]
        applied.append({
            "original": original_text,
            "replacement": replacement,
            "type": r.entity_type,
        })
    # Deduplicate while preserving order
    seen_keys = set()
    unique_applied = []
    for a in applied:
        k = (a["original"], a["replacement"])
        if k not in seen_keys:
            seen_keys.add(k)
            unique_applied.append(a)
    return new_text, unique_applied


def deanonymize(anonymized_text, mappings):
    """Reverse anonymization using a mapping list."""
    result = anonymized_text
    # Replace longer placeholders first to avoid partial overlaps
    sorted_maps = sorted(mappings, key=lambda m: -len(m["replacement"]))
    for m in sorted_maps:
        result = result.replace(m["replacement"], m["original"])
    return result


def highlight_text(text, analyzer_results):
    """Wrap detected spans in <mark> tags for the preview."""
    results_sorted = sorted(analyzer_results, key=lambda r: r.start, reverse=True)
    html = text
    for r in results_sorted:
        span = html[r.start:r.end]
        html = html[:r.start] + f'<mark class="hl" title="{r.entity_type}">{span}</mark>' + html[r.end:]
    return html.replace("\n", "<br>")


# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("### Replacement style")
    style = st.radio(
        "",
        ["Party labels", "Descriptive"],
        index=0,
        label_visibility="collapsed",
        help="Party labels → 'Party A'. Descriptive → 'PERSON_001'.",
    )

    st.markdown("### What to detect")
    all_entities = {
        "PERSON": "👤 Names",
        "STREET_ADDRESS": "🏠 Street addresses",
        "LOCATION": "📍 Locations / cities",
        "MONEY": "💰 Dollar amounts",
        "PHONE_NUMBER": "📞 Phone numbers",
        "EMAIL_ADDRESS": "📧 Emails",
        "POSTAL_CODE": "📮 Postal codes",
        "ORGANIZATION": "🏢 Organizations",
        "DATE_TIME": "📅 Dates",
        "CREDIT_CARD": "💳 Credit cards",
        "US_SSN": "🆔 SSN",
        "IP_ADDRESS": "🌐 IP addresses",
        "URL": "🔗 URLs",
    }
    selected_entities = []
    for ent, label in all_entities.items():
        default = ent in ("PERSON", "STREET_ADDRESS", "LOCATION", "MONEY",
                          "PHONE_NUMBER", "EMAIL_ADDRESS", "POSTAL_CODE",
                          "CREDIT_CARD", "US_SSN")
        if st.checkbox(label, value=default, key=f"ent_{ent}"):
            selected_entities.append(ent)

    st.markdown("### Sensitivity")
    threshold = st.slider(
        "Detection threshold",
        0.0, 1.0, 0.35, 0.05,
        help="Lower = catches more (but more false positives). Higher = stricter.",
    )

    st.markdown("---")
    st.caption("🔒 Detection runs entirely on this machine. No data leaves your laptop unless you explicitly opt in on the 'Safe Cloud AI' tab.")


# ---------- MAIN TABS ----------
tab1, tab2, tab3 = st.tabs(["🔒 Anonymize", "🔓 De-anonymize", "☁️ Safe Cloud AI"])

# ===== TAB 1: ANONYMIZE =====
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📄 Original text")
        samples = {
            "(none)": "",
            "Contract snippet": (
                "This agreement is between Ayo Adebayo of 211 Rowntree Avenue, Toronto, "
                "and Marcus Chen of 88 Spadina Road, Toronto. Ayo agrees to pay Marcus "
                "$20,000 on March 15, 2026. Marcus can be reached at marcus.chen@example.com "
                "or (416) 555-0198. Ayo's backup contact is ayo@example.com."
            ),
            "Email": (
                "Hi Sarah,\n\nFollowing up on our call — I've transferred the $5,400 deposit "
                "to the account ending 8821. My new address is 42 Maple Crescent, Winnipeg, "
                "R3M 2K8. Call me at 204-555-0143 if anything comes up.\n\nThanks,\nDavid Goldberg"
            ),
            "Meeting notes": (
                "Attendees: Priya Sharma (CFO), Tom O'Brien (Legal), Aisha Khan (Ops).\n"
                "Priya noted Q3 revenue hit $1.2M, up from $890,000 in Q2. "
                "Tom flagged the contract with Meridian Logistics Inc. expires June 30. "
                "Aisha to email priya.sharma@acmeco.com with the revised forecast by Friday."
            ),
            "Medical note": (
                "Patient Jane Rodriguez, DOB 1978-04-12, visited Dr. Okafor on March 2, 2026. "
                "Address on file: 77 Birch Street, Calgary. Insurance #ABC-123456. "
                "Contact: jane.r@example.com or 403-555-0176."
            ),
        }
        sample = st.selectbox("Load a sample", list(samples.keys()))
        default_text = samples.get(sample, "")
        text_input = st.text_area("Paste text here", value=default_text, height=280, key="input")

        go = st.button("🔒 Anonymize", type="primary", use_container_width=True)

    with col2:
        st.markdown("### 🛡️ Anonymized output")

        if go:
            if not text_input.strip():
                st.error("Please paste some text first.")
            elif not selected_entities:
                st.error("Please select at least one entity type in the sidebar.")
            else:
                with st.spinner("Analyzing locally..."):
                    analyzer = load_analyzer()
                    results = analyzer.analyze(
                        text=text_input,
                        entities=selected_entities,
                        language="en",
                        score_threshold=threshold,
                    )
                    mapping = build_consistent_mapping(results, text_input, style)
                    anonymized, applied_maps = apply_mapping(text_input, results, mapping)

                    st.session_state["original"] = text_input
                    st.session_state["anonymized"] = anonymized
                    st.session_state["mappings"] = applied_maps
                    st.session_state["raw_results"] = results

        if "anonymized" in st.session_state:
            st.text_area(
                "Anonymized",
                value=st.session_state["anonymized"],
                height=280,
                key="output",
            )

    # Highlighted preview
    if "raw_results" in st.session_state and st.session_state["raw_results"]:
        st.markdown("### 🔍 Detected entities (highlighted in original)")
        highlighted = highlight_text(st.session_state["original"], st.session_state["raw_results"])
        st.markdown(f'<div style="background:#fafafa;padding:1rem;border-radius:8px;line-height:1.7;">{highlighted}</div>', unsafe_allow_html=True)

    # Stats & mappings
    if "mappings" in st.session_state and st.session_state["mappings"]:
        mappings = st.session_state["mappings"]
        st.markdown("---")
        st.markdown("### 📊 Summary")

        by_type = defaultdict(int)
        for m in mappings:
            by_type[m["type"]] += 1

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="stat-box"><div class="stat-num">{len(mappings)}</div><div class="stat-label">Replacements</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-box"><div class="stat-num">{by_type.get("PERSON", 0)}</div><div class="stat-label">Names</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="stat-box"><div class="stat-num">{by_type.get("MONEY", 0)}</div><div class="stat-label">Money</div></div>', unsafe_allow_html=True)
        with c4:
            addr_count = by_type.get("STREET_ADDRESS", 0) + by_type.get("LOCATION", 0) + by_type.get("POSTAL_CODE", 0)
            st.markdown(f'<div class="stat-box"><div class="stat-num">{addr_count}</div><div class="stat-label">Addresses</div></div>', unsafe_allow_html=True)

        st.markdown("### 🗝️ Decoder Ring")
        st.caption("Save this securely — it's the only way to reverse the anonymization.")

        for m in mappings:
            st.markdown(
                f'<div class="mapping-row">'
                f'<span class="original">{m["original"]}</span>'
                f'<span style="color:#999;">→</span>'
                f'<span class="replacement">{m["replacement"]}</span>'
                f'<span class="type-badge">{m["type"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "⬇️ Download anonymized text",
                data=st.session_state["anonymized"],
                file_name=f"anonymized_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with d2:
            decoder_payload = {
                "created_at": datetime.now().isoformat(),
                "mappings": mappings,
            }
            st.download_button(
                "🗝️ Download decoder ring",
                data=json.dumps(decoder_payload, indent=2),
                file_name=f"decoder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

# ===== TAB 2: DE-ANONYMIZE =====
with tab2:
    st.markdown("### 🔓 Reverse the anonymization")
    st.caption("Paste anonymized text and upload your decoder ring to recover the original.")

    c1, c2 = st.columns(2)
    with c1:
        anon_text = st.text_area("Anonymized text", height=240)
        decoder_file = st.file_uploader("Decoder ring (JSON)", type=["json"])
        undo = st.button("🔓 De-anonymize", type="primary", use_container_width=True)

    with c2:
        if undo:
            if not anon_text.strip():
                st.error("Paste the anonymized text first.")
            elif not decoder_file:
                st.error("Upload the decoder ring JSON.")
            else:
                try:
                    decoder = json.load(decoder_file)
                    recovered = deanonymize(anon_text, decoder["mappings"])
                    st.text_area("Recovered original", value=recovered, height=320)
                except Exception as e:
                    st.error(f"Error: {e}")

# ===== TAB 3: SAFE CLOUD AI =====
with tab3:
    st.markdown("### ☁️ Safe Cloud AI Workflow")
    st.markdown(
        "**The magic moment.** Send your anonymized text to Claude, "
        "get back an intelligent response, then un-redact it locally. "
        "Claude never sees the real names, addresses, or dollar amounts."
    )

    if "anonymized" not in st.session_state:
        st.info("👈 Run an anonymization on the first tab before trying this.")
    else:
        api_key = st.text_input(
            "Anthropic API Key (optional)",
            type="password",
            value=os.getenv("ANTHROPIC_API_KEY", ""),
            help="Only needed for this tab. Stored only in memory.",
        )

        task = st.selectbox(
            "What should Claude do with the anonymized text?",
            [
                "Summarize in 3 bullet points",
                "Extract key obligations and deadlines",
                "Translate to plain English",
                "Draft a reply",
                "Custom prompt...",
            ],
        )
        if task == "Custom prompt...":
            custom = st.text_input("Your instruction", value="Summarize this document.")
            instruction = custom
        else:
            instruction = task

        st.markdown("#### 📤 What Claude will see:")
        st.code(st.session_state["anonymized"], language="text")

        send = st.button("☁️ Send ANONYMIZED text to Claude", type="primary", use_container_width=True)

        if send:
            if not api_key:
                st.error("Enter your Anthropic API key above.")
            else:
                try:
                    import anthropic
                    client = anthropic.Anthropic(api_key=api_key)
                    with st.spinner("Claude is thinking..."):
                        response = client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=1500,
                            messages=[{
                                "role": "user",
                                "content": f"{instruction}\n\n---\n{st.session_state['anonymized']}\n---"
                            }],
                        )
                    cloud_response = response.content[0].text
                    st.session_state["cloud_response"] = cloud_response

                    # Un-redact the response locally
                    recovered_response = deanonymize(cloud_response, st.session_state["mappings"])
                    st.session_state["recovered_response"] = recovered_response
                except ImportError:
                    st.error("Install the anthropic package: `pip install anthropic`")
                except Exception as e:
                    st.error(f"Error: {e}")

        if "cloud_response" in st.session_state:
            st.markdown("#### 📥 Claude's response (still anonymized):")
            st.code(st.session_state["cloud_response"], language="text")

            st.markdown("#### ✨ Recovered response (decoder ring applied locally):")
            st.success(st.session_state["recovered_response"])

            st.info(
                "🔒 At no point did Claude — or any cloud service — see the original "
                "names, addresses, or dollar amounts. The decoder ring stayed on this machine."
            )
