"""One-time script to create the Config tab in your Google Sheet."""
import gspread
import os

SHEET_ID = "15shdxey8xe0S7LFmtrvDDVFKEk34_5GTRuDwJXiJBXk"
CREDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")

gc = gspread.service_account(filename=CREDS)
spreadsheet = gc.open_by_key(SHEET_ID)

# create Config sheet if it doesn't exist
try:
    config_sheet = spreadsheet.worksheet("Config")
    print("Config sheet already exists, updating...")
    config_sheet.clear()
except gspread.exceptions.WorksheetNotFound:
    config_sheet = spreadsheet.add_worksheet(title="Config", rows=20, cols=3)
    print("Created Config sheet")

# write config structure
config_data = [
    ["Setting", "Value", "Description"],
    ["gmail_address", "", "Gmail address to send from"],
    ["gmail_app_password", "", "Gmail App Password (16 chars from Google)"],
    ["openai_api_key", "", "OpenAI API key for email generation"],
    ["sender_name", "Deepesh Sharma", "Name shown in From field"],
    ["daily_limit", "12", "Max emails per day (keep under 15 for Gmail)"],
    ["gap_min_seconds", "60", "Minimum seconds between emails"],
    ["gap_max_seconds", "180", "Maximum seconds between emails"],
    ["ai_prompt", """You are writing a short B2B outreach email on behalf of {sender_name} from TERRA, a plant-based (vegan) leather supplier. Write a personalized cold email to this lead.

Lead info:
- Company: {company}
- Contact role: {contact}
- Country: {country}
- Personalization angle: {angle}
- Remarks: {remarks}

Rules:
- Start with a personalized opening using the angle/remarks (1-2 sentences)
- Briefly introduce TERRA: plant-based leather sheets & rolls, 6 materials (cactus, mycelium, pineapple leaf, apple, grape, cork), 40+ countries, MOQ 50 sqm
- Offer a free swatch kit
- End with a soft CTA (reply to get samples, or a quick call)
- Sign off as {sender_name}, TERRA — Plant Leather Supply
- Include website: terraveganleather.com
- Tone: professional but warm, not salesy or pushy
- Keep it under 150 words
- Do NOT use generic filler
- Do NOT use exclamation marks excessively
- Return ONLY the email body (no subject line)""", "Prompt sent to OpenAI to generate each email. Use {company}, {contact}, {country}, {angle}, {remarks}, {sender_name}"],
    ["subject_prompt", """Write a short email subject line (under 8 words) for a B2B cold email to {company}, a {remarks} brand in {country}. Offering plant-based leather materials. Angle: {angle}. No spam words, no ALL CAPS, no exclamation marks. Return ONLY the subject line.""", "Prompt for generating subject lines"],
    ["leads_sheet_name", "Sheet1", "Name of the sheet tab containing leads"],
]

config_sheet.update("A1:C" + str(len(config_data)), config_data)

# format header
config_sheet.format("A1:C1", {"textFormat": {"bold": True}})

print("Config sheet populated! Go fill in your credentials in the sheet.")
print(f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}")
