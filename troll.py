# troll.py - Система темутинга
import random
import os
import config
from vk_utils import send_message, delete_message, get_user_name

trolled_users = {}  # {peer_id: [target_id1, target_id2, ...]}
TROLL_PHRASES = []

def load_phrases():
    global TROLL_PHRASES
    phrases = []
    if os.path.exists(config.PHRASES_FILE):
        with open(config.PHRASES_FILE, "r", encoding="utf-8") as f:
            phrases = [line.strip() for line in f if line.strip()]
    if not phrases:
        phrases = [
            "Я лох", "Я ничего не понимаю в этой жизни", "Извините, я тупой",
            "У меня IQ комнатной температуры", "Я согласен с тем, что я даун",
            "Мам, забери меня отсюда", "Кто я? Зачем я здесь?",
            "Я бот, а вы даже не заметили", "Сосите, я вас всех переиграл", "Кек"
        ]
        save_phrases(phrases)
    TROLL_PHRASES = phrases

def save_phrases(phrases):
    with open(config.PHRASES_FILE, "w", encoding="utf-8") as f:
        for phrase in phrases:
            f.write(phrase + "\n")

def start_troll(peer_id, target_id, replied_cmid=None):
    if peer_id not in trolled_users:
        trolled_users[peer_id] = []
    if target_id not in trolled_users[peer_id]:
        trolled_users[peer_id].append(target_id)
        user_name = get_user_name(target_id)
        send_message(peer_id, f"✅ {user_name} терь на темуте")
    if replied_cmid:
        delete_message(peer_id, replied_cmid)

def stop_troll(peer_id, target_id=None):
    if peer_id not in trolled_users:
        return False
    if target_id:
        if target_id in trolled_users[peer_id]:
            trolled_users[peer_id].remove(target_id)
            user_name = get_user_name(target_id)
            send_message(peer_id, f"✅ {user_name} может базарить")
            if not trolled_users[peer_id]:
                del trolled_users[peer_id]
            return True
    else:
        del trolled_users[peer_id]
        send_message(peer_id, f"✅ Темутинг отключен для всех")
        return True
    return False

def is_user_trolled(peer_id, user_id):
    if peer_id in trolled_users:
        return user_id in trolled_users[peer_id]
    return False

def get_random_phrase():
    return random.choice(TROLL_PHRASES)

def add_troll_phrase(phrase):
    if phrase and phrase not in TROLL_PHRASES:
        TROLL_PHRASES.append(phrase)
        save_phrases(TROLL_PHRASES)
        return True
    return False

def remove_troll_phrase(phrase):
    if phrase in TROLL_PHRASES:
        TROLL_PHRASES.remove(phrase)
        save_phrases(TROLL_PHRASES)
        return True
    return False

def get_troll_phrases_list():
    return TROLL_PHRASES.copy()