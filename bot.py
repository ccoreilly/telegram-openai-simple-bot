import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

OPENAI_COMPLETIONS_ENDPOINT = "https://api.openai.com/v1/chat/completions"

# Memory for active sessions
sessions = {}

WAKE_WORD = "Patatino"
MAX_MESSAGES = 10

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"].get("text", "")

        if not user_text:
            return 'ok'  # Ignore non-text messages

        session = sessions.get(chat_id, {"active": False, "count": 0})

        if WAKE_WORD.lower() in user_text.lower():
            # Wake word detected
            sessions[chat_id] = {"active": True, "count": 0}
            send_message(chat_id, "Hello! I'm now listening.")
            return 'ok'

        if session["active"]:
            # Forward the message to OpenAI
            ai_response, tool_call = ask_openai(user_text)

            send_message(chat_id, ai_response)

            session["count"] += 1

            # Check for stop conditions
            if session["count"] >= MAX_MESSAGES or tool_call == "stop_conversation":
                sessions[chat_id] = {"active": False, "count": 0}
                send_message(chat_id, "Session ended. Say 'Patatino' again to start a new one.")
            else:
                sessions[chat_id] = session  # Update session

    return 'ok'

def ask_openai(user_text):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are an assistant. If the user message becomes unrelated to the previous conversation, you should call a tool: {\"tool_call\": \"stop_conversation\"}. Otherwise, reply normally."},
            {"role": "user", "content": user_text}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "stop_conversation",
                    "description": "End the conversation when the topic is no longer related."
                }
            }
        ]
    }
    response = requests.post(OPENAI_COMPLETIONS_ENDPOINT, headers=headers, json=payload)
    response_json = response.json()

    # Check if the model invoked the tool
    tool_call = None
    if 'choices' in response_json and 'message' in response_json['choices'][0]:
        message = response_json['choices'][0]['message']
        if "tool_calls" in message:
            tool_call = message['tool_calls'][0]['function']['name']

        ai_text = message.get('content', "No response.")

    else:
        ai_text = "Error: couldn't get a response."

    return ai_text.strip(), tool_call

def send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)