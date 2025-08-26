import streamlit as st
from openai import OpenAI
from uuid import uuid4          # <-- add this line
from datetime import datetime
import json, re
import requests

# ---- Secure client ----
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---- System prompt ----
SYSTEM_PROMPT = """
You are an AI customer service agent. Your goal is to offer Internet support.

First, introduce yourself pro-actively: “Hello. I’m your virtual assistant.  Please provide your Prolific ID below:"

Next, wait for the user to provide a prolific id.

After user confirms their Prolific ID, ask the user:

"How can I assist you with your Internet issue today?”. Wait for a response form the user.



Next, if the user inquires about the WiFi issue, trouble shooting/ slow WiFi, then provide mobile Internet instructions exactly as described below:

"Sure, I can help you with a solution for slow mobile internet.

Here is a step by step guide to troubleshoot your Mobile WiFi issue:

Restart your phone
o\tPower off the device, wait 10 seconds, and turn it back on.
Forget and reconnect to the WiFi network
o\tGo to Settings > WiFi > Select the network > Forget
o\tReconnect and re-enter the password carefully.
Check data balance (if using cellular hotspot)
o\tEnsure your data plan allows hotspot usage.
o\tSome carriers throttle hotspot speeds or restrict access after usage limits.

”

After you provide the instructions, thank the user and express hope that the answer was helpful.
You must instruct the user to proceed back to the survey to complete all questions about their experience: https://asu.co1.qualtrics.com/jfe/preview/previewId/62fdf4cc-a69f-4255-a321-4d795485d826/SV_3rutUOKtHWkQaA6?Q_CHL=preview&Q_SurveyVersionID=current

If at any point, user asks questions non-related to the modem troubleshooting, then reply: "I am sorry. I was only trained to handle Internet connectivity issues."

IMPORTANT BEHAVIOR:
- On the first assistant turn (no prior user messages), output ONLY the greeting and the request for the Prolific ID. Do NOT include troubleshooting steps and do NOT end the chat.
- Provide the troubleshooting steps only after the user asks about WiFi issues / slow internet.
- After you have provided the troubleshooting instructions and directed the user back to the survey, end your message with a single line containing exactly:
[END_OF_CHAT]
Do not write anything after that token.
"""

st.title("Wireless Support Bot")

# Session state init
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "chat_closed" not in st.session_state:
    st.session_state.chat_closed = False
if "bootstrapped" not in st.session_state:
    st.session_state.bootstrapped = False
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())
if "started_at" not in st.session_state:
    st.session_state.started_at = datetime.utcnow().isoformat() + "Z"
if "prolific_id" not in st.session_state:
    st.session_state.prolific_id = ""
if "saved_once" not in st.session_state:
    st.session_state.saved_once = False

END_TOKEN = "[END_OF_CHAT]"
# =========================
# HELPERS
# =========================

def _messages_without_system():
    return [m for m in st.session_state.messages if m["role"] != "system"]

def _payload(include_system: bool = False):
    msgs = st.session_state.messages if include_system else _messages_without_system()
    return {
        "session_id": st.session_state.session_id,
        "started_at": st.session_state.started_at,
        "ended_at": datetime.utcnow().isoformat() + "Z" if st.session_state.chat_closed else None,
        "prolific_id": st.session_state.prolific_id or None,
        "messages": msgs,
    }

def _maybe_capture_prolific_id(text: str):
    # Best-effort: first user message is treated as an ID, otherwise find an alphanumeric 12+ token.
    if not st.session_state.prolific_id:
        if sum(1 for m in st.session_state.messages if m["role"] == "user") == 0:
            st.session_state.prolific_id = text.strip()
            return
        m = re.search(r"\b([A-Za-z0-9]{12,})\b", text)
        if m:
            st.session_state.prolific_id = m.group(1)

def _save_to_drive_once():
    """POST the full transcript to your Apps Script Web App once (no links shown to users)."""
    if st.session_state.saved_once:
        return
    try:
        base = st.secrets["WEBHOOK_URL"].rstrip("?")
        # Optional token support: if WEBHOOK_TOKEN is provided, append it; else just use base.
        token = st.secrets.get("WEBHOOK_TOKEN")
        url = f"{base}?token={token}" if token else base

        r = requests.post(url, json=_payload(False), timeout=10)
        if r.status_code == 200 and (r.text or "").strip().startswith("OK"):
            st.session_state.saved_once = True
        else:
            st.sidebar.warning(f"Admin note: webhook save failed ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        st.sidebar.warning(f"Admin note: webhook error: {e}")

def _append_assistant_reply_from_model():
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # keep your current model
        messages=st.session_state.messages,
    )
    raw = response.choices[0].message.content or ""
    if END_TOKEN in raw:
        visible = raw.split(END_TOKEN)[0].rstrip()
        st.session_state.chat_closed = True
    else:
        visible = raw

    st.session_state.messages.append({"role": "assistant", "content": visible})

    # If the chat ended this turn, save logs to Drive (admin-only, silent)
    if st.session_state.chat_closed:
        _save_to_drive_once()

# =========================
# AUTO-START (assistant speaks first)
# =========================

if not st.session_state.bootstrapped:
    if len(st.session_state.messages) == 1:
        _append_assistant_reply_from_model()
    st.session_state.bootstrapped = True

# =========================
# RENDER HISTORY
# =========================

for msg in st.session_state.messages[1:]:
    st.write(f"**{msg['role'].capitalize()}:** {msg['content']}")

# =========================
# INPUT HANDLING
# =========================

def send_message():
    if st.session_state.chat_closed:
        return
    text = st.session_state.user_input.strip()
    if not text:
        return
    _maybe_capture_prolific_id(text)
    st.session_state.messages.append({"role": "user", "content": text})
    _append_assistant_reply_from_model()
    st.session_state.user_input = ""
    # No st.rerun() in callbacks (no-op); Streamlit auto-reruns.

if st.session_state.chat_closed:
    st.info("🔒 End of chat. Thank you! Please return to the survey to complete all questions.")
    if st.button("Start a new chat"):
        sid = str(uuid4())
        st.session_state.clear()
        st.session_state.session_id = sid
else:
    st.text_input(
        "You:",
        key="user_input",
        placeholder="Type your message… (press Enter to send)",
        on_change=send_message,
    )
