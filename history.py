# history.py - Хранилище истории сообщений
from collections import deque
import config
from vk_utils import get_user_name

message_history = deque(maxlen=config.MESSAGE_HISTORY_MAXLEN)

def add_to_history(user_id, text):
    """Добавляет сообщение в историю"""
    user_name = get_user_name(user_id)
    message_history.append({
        "user_id": user_id,
        "user_name": user_name,
        "text": text,
        "time": time.time()
    })

def get_history(limit=100):
    """Возвращает последние N сообщений из истории"""
    return list(message_history)[-limit:]