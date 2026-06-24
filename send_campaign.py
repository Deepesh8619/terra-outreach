"""
TERRA Outreach — AI-Powered Email Campaign

Everything is configured in the Google Sheet "Config" tab.
Anyone on the team can change prompts, credentials, or settings there.

Usage:
    streamlit run send_campaign.py

Setup (one-time):
    1. Google Service Account credentials.json in this folder
    2. Fill in Config sheet: gmail, app password, openai key
    3. Add leads to Sheet1 with columns: Company, email, Likely Contact, Country, Personalization Angle, Remarks
    4. Run: streamlit run send_campaign.py
"""

import gspread
import openai
import re
import smtplib
import csv
import os
import random
import time
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SHEET_ID = "1oB1GPjGY9d8VB5lvIDkJTMfRD2rd-S9sA5ov3uR8cag"
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "send_log.csv")


# ── Google Sheet helpers ────────────────────────────────────────────────

def get_sheet_client():
    if os.path.exists(CREDENTIALS_FILE):
        return gspread.service_account(filename=CREDENTIALS_FILE)
    from google.oauth2.service_account import Credentials
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def load_config():
    gc = get_sheet_client()
    spreadsheet = gc.open_by_key(SHEET_ID)
    config_sheet = spreadsheet.worksheet("Config")
    rows = config_sheet.get_all_records()
    config = {}
    for row in rows:
        key = str(row.get("Setting", "")).strip()
        value = str(row.get("Value", "")).strip()
        if key:
            config[key] = value
    return config


def load_leads(sheet_name="Sheet1"):
    gc = get_sheet_client()
    spreadsheet = gc.open_by_key(SHEET_ID)
    sheet = spreadsheet.worksheet(sheet_name)
    return sheet, sheet.get_all_records()


def update_sent_timestamp(sheet, row_index, timestamp):
    headers = sheet.row_values(1)
    if "Sent At" not in headers:
        col = len(headers) + 1
        sheet.update_cell(1, col, "Sent At")
    else:
        col = headers.index("Sent At") + 1
    sheet.update_cell(row_index, col, timestamp)


def get_sent_emails():
    sent = set()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status") == "sent":
                    sent.add(row.get("email", "").lower())
    return sent


# ── Email generation & sending ──────────────────────────────────────────

def generate_email(lead, config):
    client = openai.OpenAI(api_key=config["openai_api_key"])

    company = lead.get("Company", "")
    contact = lead.get("Likely Contact", "")
    country = lead.get("Country", "")
    angle = lead.get("Personalization Angle", "")
    remarks = lead.get("Remarks", "")
    sender_name = config.get("sender_name", "Deepesh Sharma")

    ai_prompt = config.get("ai_prompt", "Write a B2B outreach email for {company}")
    subject_prompt = config.get("subject_prompt", "Write a subject line for {company}")

    greeting_name = contact.split(",")[0].split("/")[0].strip() if contact else company

    body_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": ai_prompt.format(
            company=company, contact=contact, country=country,
            angle=angle, remarks=remarks, sender_name=sender_name,
            greeting_name=greeting_name
        )}],
        temperature=0.9,
        max_tokens=400,
    )
    body_text = body_resp.choices[0].message.content.strip()

    subj_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": subject_prompt.format(
            company=company, angle=angle, remarks=remarks, country=country
        )}],
        temperature=1.0,
        max_tokens=30,
    )
    subject = subj_resp.choices[0].message.content.strip().strip('"').strip("'")

    body_text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1 (\2)', body_text)

    body_html = ""
    for para in body_text.split("\n\n"):
        para = para.strip()
        if para:
            para = re.sub(r'(https?://\S+)', r'<a href="\1">\1</a>', para)
            body_html += "<p>" + para + "</p>\n"

    return subject, body_text, body_html


def send_via_gmail(to_email, to_name, subject, body_text, body_html, config):
    gmail = config["gmail_address"]
    password = config["gmail_app_password"]
    sender_name = config.get("sender_name", "Deepesh Sharma")

    msg = MIMEMultipart("alternative")
    msg["From"] = sender_name + " <" + gmail + ">"
    msg["To"] = (to_name.strip() + " <" + to_email + ">") if to_name and to_name.strip() else to_email
    msg["Subject"] = subject
    msg["Reply-To"] = gmail

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail, password)
        server.sendmail(gmail, to_email, msg.as_string())


def log_send(lead, subject, status, error=""):
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["timestamp", "company", "email", "subject", "status", "error"])
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            lead.get("Company", ""),
            lead.get("email", ""),
            subject,
            status,
            error,
        ])


# ── Streamlit UI ────────────────────────────────────────────────────────

st.set_page_config(page_title="TERRA Outreach", page_icon="🌿", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0A0705; }
    h1, h2, h3 { color: #C8956B !important; }
    .stMarkdown p, .stMarkdown li { color: #BEB5AD; }
    div[data-testid="stMetric"] { background: #141110; border: 1px solid #2A2320; border-radius: 8px; padding: 16px; }
    div[data-testid="stMetric"] label { color: #8A7E75 !important; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #C8956B !important; }
</style>
""", unsafe_allow_html=True)

st.title("TERRA Outreach")
st.caption("AI-powered email campaigns — config lives in your Google Sheet")

# load config
try:
    config = load_config()
except Exception as e:
    st.error("Could not load Config sheet: " + str(e))
    st.stop()

# validate config
missing = []
for key in ["gmail_address", "gmail_app_password", "openai_api_key"]:
    if not config.get(key):
        missing.append(key)

if missing:
    st.error("Missing in Config sheet: **" + ", ".join(missing) + "**. Go fill them in.")
    st.markdown("[Open Google Sheet](https://docs.google.com/spreadsheets/d/" + SHEET_ID + ")")
    st.stop()

# show current config summary
st.subheader("Config")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Sending as", config.get("sender_name", "—"))
col2.metric("Gmail", config.get("gmail_address", "—")[:20] + "...")
col3.metric("Daily Limit", config.get("daily_limit", "12"))
col4.metric("Gap", config.get("gap_min_seconds", "60") + "-" + config.get("gap_max_seconds", "180") + "s")

st.markdown("---")

# load leads
leads_sheet = config.get("leads_sheet_name", "Sheet1")
try:
    leads_sheet_obj, all_leads = load_leads(leads_sheet)
except Exception as e:
    st.error("Could not load leads from '" + leads_sheet + "': " + str(e))
    st.stop()

for idx, lead in enumerate(all_leads):
    lead["_row"] = idx + 2

leads_with_email = [r for r in all_leads if r.get("email")]

# deduplicate
seen = set()
unique_leads = []
for r in leads_with_email:
    email = r["email"].lower().strip()
    if email not in seen:
        seen.add(email)
        unique_leads.append(r)

# filter already sent
sent_emails = get_sent_emails()
new_leads = [r for r in unique_leads if r["email"].lower().strip() not in sent_emails]

st.subheader("Leads")
col1, col2, col3 = st.columns(3)
col1.metric("Total in Sheet", len(all_leads))
col2.metric("Already Sent", len(sent_emails))
col3.metric("Ready to Send", len(new_leads))

if not new_leads:
    st.success("All leads have been emailed.")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Reset & Send Again to All", type="primary", use_container_width=True):
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            st.rerun()
    with col_b:
        st.markdown("[Add more leads in Google Sheet](https://docs.google.com/spreadsheets/d/" + SHEET_ID + ")")
    st.stop()

# show lead preview
with st.expander("Preview leads to send (" + str(len(new_leads)) + ")"):
    for i, lead in enumerate(new_leads):
        st.text(str(i+1) + ". " + lead.get("Company", "?") + " — " + lead.get("email", "") + " (" + lead.get("Country", "") + ")")

st.markdown("---")

# send controls
st.subheader("Send Campaign")

daily_limit = int(config.get("daily_limit", "12"))
to_send = min(len(new_leads), daily_limit)

mode = st.radio("Mode", ["Dry Run (preview only)", "Send for Real"], horizontal=True)
send_for_real = mode == "Send for Real"

if send_for_real:
    st.warning("This will send " + str(to_send) + " real emails from " + config["gmail_address"])

if st.button("Start Campaign", type="primary", use_container_width=True):
    gap_min = int(config.get("gap_min_seconds", "60"))
    gap_max = int(config.get("gap_max_seconds", "180"))

    random.shuffle(new_leads)
    batch = new_leads[:daily_limit]

    progress = st.progress(0)
    status_text = st.empty()
    log_area = st.container()

    sent = 0
    failed = 0

    for i, lead in enumerate(batch):
        email = lead["email"].strip()
        company = lead.get("Company", "")
        contact = lead.get("Likely Contact", "") or company

        progress.progress((i + 1) / len(batch))
        status_text.text("Processing " + str(i+1) + "/" + str(len(batch)) + ": " + company)

        # stagger
        if sent > 0:
            gap = random.uniform(gap_min, gap_max)
            mins = int(gap // 60)
            secs = int(gap % 60)
            status_text.text("Waiting " + str(mins) + "m " + str(secs) + "s before next send...")
            if send_for_real:
                time.sleep(gap)

        # generate email
        try:
            subject, body_text, body_html = generate_email(lead, config)
        except Exception as e:
            log_area.error("AI error for " + company + ": " + str(e))
            log_send(lead, "—", "ai_error", str(e))
            failed += 1
            continue

        if not send_for_real:
            log_area.success("DRY RUN: " + company + " (" + email + ")")
            with log_area.expander("Preview: " + subject):
                st.markdown(body_html, unsafe_allow_html=True)
            log_send(lead, subject, "dry_run")
            sent += 1
            continue

        # send
        try:
            send_via_gmail(email, contact, subject, body_text, body_html, config)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_area.success("SENT: " + company + " (" + email + ") — " + subject)
            log_send(lead, subject, "sent")
            try:
                update_sent_timestamp(leads_sheet_obj, lead["_row"], ts)
            except Exception:
                pass
            sent += 1
        except Exception as e:
            log_area.error("FAILED: " + company + " — " + str(e))
            log_send(lead, subject, "failed", str(e))
            failed += 1

    progress.progress(1.0)
    status_text.empty()

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Sent", sent)
    col2.metric("Failed", failed)
    col3.metric("Remaining", len(new_leads) - sent - failed)

    if send_for_real and sent > 0:
        st.balloons()
        st.success("Campaign complete! " + str(sent) + " emails sent.")
    elif not send_for_real:
        st.info("Dry run complete. Switch to 'Send for Real' when ready.")
