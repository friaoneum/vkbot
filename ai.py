# ai.py - AI-функции (DeepSeek, Gemini, OpenRouter)
import requests
import json
import config
from prompts import get_prompt
from vk_utils import vk
from history import message_history

def ask_deepseek(question, prompt_type="alo"):
    try:
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        system_prompt = get_prompt(prompt_type)
        data = {
            "model": config.DEFAULT_MODELS.get(prompt_type, "google/gemini-3.1-flash-lite"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(
            "https://routerai.ru/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        elif response.status_code == 429:
            return "⚠️ Лимит запросов на сегодня. До завтра."
        else:
            return f"⚠️ Алерт API: {response.status_code}"
    except Exception as e:
        return f"⚠️ Алерт: {e}"

def analyze_chat_with_ai():
    if len(message_history) < 5:
        return "📊 Недостаточно сообщений для вывода. Нужно хотя бы 5-10 сообщений."
    
    dialog_text = ""
    for msg in list(message_history)[-100:]:
        dialog_text += f"{msg['user_name']}: {msg['text']}\n"
    
    system_prompt = get_prompt("sudi")
    question = f"Вот диалог:\n{dialog_text}\n\nТвой вывод:"
    
    try:
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": config.DEFAULT_MODELS.get("sudi", "google/gemini-3.1-flash-lite"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(
            "https://routerai.ru/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"⚠️ Алерт API: {response.status_code}"
    except Exception as e:
        return f"⚠️ Алерт: {e}"