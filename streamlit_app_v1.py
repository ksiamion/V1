import streamlit as st
from openai import OpenAI

# ---- Secure client ----
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---- System prompt ----
SYSTEM_PROMPT = """
You are an AI customer service agent. Your goal is to offer Internet support.

First, introduce yourself pro-actively: “Hello. I’m a bot assistant Jerry.  Please provide your Prolific ID below:

Wait for the user to provide a prolific id.

Next ask the user: How can I assist you with your Internet issue today?”. Wait for a response form the user.

Next, if the user inquires about the WiFi trouble shooting/ slow WiFi, then provide mobile Internet instructions exactly as described below:

"Sure, I can help you with a solution for slow mobile internet.

Here is a step by step guide to troubleshoot your Mobile WiFi issue:

Restart your phone/tablet
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

If at any point, user asks questions non-related to the modem troubleshooting, then reply: "I am sorry. I was only trained to handle Internet connectivity issues. Please contact Reihane Boghrati if you have any additional inquires unrelated to the WiFi troubleshooting."

IMPORTANT BEHAVIOR:
- On the first assistant turn (no prior user messages), output ONLY the greeting and the request for the Prolific ID, then ask how you can assist. Do NOT include troubleshooting steps and do NOT end the chat.
- Provide the troubleshooting steps only after the user asks about WiFi issues / slow internet.
- After you have provided the troubleshooting instructions and directed the user back to the survey, end your message with a single line containing exactly:
[END_OF_CHAT]
Do not write anything after that token.
"""

# ---- Title ----
st.title("Wireless Support Bot")

# ---- Initialize state BEFORE widgets ----
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "chat_closed" not in st.session_state:
    st.session_state.chat_closed = False
if "bootstrapped" not in st.session_state:
    # Ensures we only auto-start once
    st.session_state.bootstrapped = False

END_TOKEN = "[END_OF_CHAT]"

def _append_assistant_reply_from_model():
    """Call the model with current messages, append assistant reply, and close if end token seen."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # keep your existing model; update if needed
        messages=st.session_state.messages,
    )
    raw = response.choices[0].message.content or ""
    if END_TOKEN in raw:
        visible = raw.split(END_TOKEN)[0].rstrip()
        st.session_state.chat_closed = True
    else:
        visible = raw
    st.session_state.messages.append({"role": "assistant", "content": visible})

# ---- Auto-start: have the bot speak first ----
if not st.session_state.bootstrapped:
    # Only system message present → get the first assistant turn
    if len(st.session_state.messages) == 1:
        _append_assistant_reply_from_model()
    st.session_state.bootstrapped = True
    st.rerun()

# ---- Display chat history (skip system) ----
for msg in st.session_state.messages[1:]:
    st.write(f"**{msg['role'].capitalize()}:** {msg['content']}")

def _close_chat_ui():
    st.info("🔒 End of chat. Thank you! Please return to the survey to complete all questions.")
    if st.button("Start a new chat"):
        for k in ("messages", "user_input", "chat_closed", "bootstrapped"):
            st.session_state.pop(k, None)
        st.rerun()

# ---- Callback to send & clear safely ----
def send_message():
    if st.session_state.chat_closed:
        return
    text = st.session_state.user_input
    if not text:
        return

    # Add user message
    st.session_state.messages.append({"role": "user", "content": text})

    # Get assistant reply and maybe close chat
    _append_assistant_reply_from_model()

    # Clear input and rerun
    st.session_state.user_input = ""
    st.rerun()

# ---- UI ----
if st.session_state.chat_closed:
    _close_chat_ui()
else:
    st.text_input(
        "You:",
        key="user_input",
        placeholder="Type your message… (press Enter to send)",
        on_change=send_message,  # safe send/clear
    )
