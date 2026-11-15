# commands.py - Полная логика обработки команд
import time
import threading
import re
import random
import json
import os
import requests
import traceback

import config
from vk_utils import (
    vk, BOT_ID, send_message, delete_message,
    get_user_name, get_user_id_from_mention_or_reply,
    build_attachment_string,
    build_keyboard
)
from moderation import contains_bad_words, BAD_WORDS, save_bad_words
from troll import *
from prompts import get_prompt, set_prompt
from ai import ask_deepseek, analyze_chat_with_ai
from history import message_history
from voice import send_audio_message, get_available_audio_files, get_audio_path
from ai import ask_deepseek, analyze_chat_with_ai
from troll import load_phrases
from troll import TROLL_PHRASES, load_phrases, add_troll_phrase, remove_troll_phrase, get_troll_phrases_list, get_random_phrase
from moderation import get_bad_words, set_bad_words, load_bad_words, save_bad_words
from moderation import BAD_WORDS
from moderation import load_bad_words

# =====================================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# =====================================================

admins_cache = {}
rules_enabled = True
rules_text = config.DEFAULT_RULES
greeting_enabled = True
greeting_text = config.DEFAULT_GREETING
nicknames_enabled = True
nicknames = {}
agitation_enabled = False
agitated_users = set()
user_access = {}
links_enabled = True
antispam_enabled = False
antispam_history = {}
current_models = config.DEFAULT_MODELS.copy()
censored_users = set()
banned_users = {}
muted_users = {}
user_reaction = {}  # {peer_id: {user_id: reaction_type}}
slysh_enabled = True
inactivity_data = {}
load_phrases()
load_bad_words()
forced_censored_users = set()  

# Автоматический троллинг (каждые N сообщений)
auto_troll_count = 0
auto_troll_limit = 20
auto_troll_enabled = False

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ РАНГОВ
# =====================================================

user_ranks = {}

def load_ranks():
    global user_ranks
    if os.path.exists(config.RANKS_FILE):
        try:
            with open(config.RANKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                user_ranks = {int(k): v for k, v in data.items()}
            print(f"📊 Загружено рангов: {len(user_ranks)}")
        except:
            user_ranks = {}
    else:
        user_ranks = {}
        save_ranks()

def save_ranks():
    with open(config.RANKS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_ranks, f, ensure_ascii=False, indent=2)

def get_user_rank(user_id):
    if user_id == config.OWNER_ID:
        return 3
    return user_ranks.get(user_id, 0)

def set_user_rank(user_id, rank):
    global user_ranks, admins_cache
    if user_id == config.OWNER_ID:
        return False
    if rank in [1, 2]:
        user_ranks[user_id] = rank
        admins_cache.clear()
        save_ranks()
        return True
    return False

def remove_user_rank(user_id):
    global user_ranks, admins_cache
    if user_id in user_ranks:
        del user_ranks[user_id]
        admins_cache.clear()
        save_ranks()
        return True
    return False

def can_use_command(user_id, command):
    rank = get_user_rank(user_id)
    if rank == 3:
        return True
    owner_only = ["!короновать", "!снять"]
    if command in owner_only:
        return False
    if rank == 2:
        return True
    if rank == 1:
        basota_commands = [
            "!мат", "!удалитьмат", "!натемут", "!аннул", "!хватит",
            "!добавитьфразу", "!удалитьфразу", "!списокфраз",
            "!дис", "!стопдис", "!смпромт"
        ]
        for bc in basota_commands:
            if command.startswith(bc):
                return True
        return False
    return False

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ ПРИВЕТСТВИЙ
# =====================================================

def load_greeting_state():
    global greeting_enabled
    if os.path.exists(config.GREETING_ENABLED_FILE):
        try:
            with open(config.GREETING_ENABLED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                greeting_enabled = data.get("enabled", True)
            print(f"Приветствия {'включены' if greeting_enabled else 'выключены'}")
        except:
            greeting_enabled = True
    else:
        greeting_enabled = True
        save_greeting_state()

def save_greeting_state():
    global greeting_enabled
    with open(config.GREETING_ENABLED_FILE, "w", encoding="utf-8") as f:
        json.dump({"enabled": greeting_enabled}, f, ensure_ascii=False, indent=2)

def load_greeting_text():
    global greeting_text
    if os.path.exists(config.GREETING_TEXT_FILE):
        try:
            with open(config.GREETING_TEXT_FILE, "r", encoding="utf-8") as f:
                greeting_text = f.read().strip()
            print(f"📝 Загружен текст приветствия: {greeting_text[:50]}...")
        except:
            greeting_text = config.DEFAULT_GREETING
    else:
        greeting_text = config.DEFAULT_GREETING
        save_greeting_text()

def save_greeting_text():
    global greeting_text
    with open(config.GREETING_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(greeting_text)

def get_greeting(user_id, user_name_mention):
    plain_name = get_user_name(user_id, mention=False)
    return greeting_text.replace("{mention}", user_name_mention).replace("{user}", plain_name)

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ ПРАВИЛ
# =====================================================

def load_rules_state():
    global rules_enabled
    if os.path.exists(config.RULES_ENABLED_FILE):
        try:
            with open(config.RULES_ENABLED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                rules_enabled = data.get("enabled", True)
            print(f"Правила {'включены' if rules_enabled else 'выключены'}")
        except:
            rules_enabled = True
    else:
        rules_enabled = True
        save_rules_state()

def save_rules_state():
    global rules_enabled
    with open(config.RULES_ENABLED_FILE, "w", encoding="utf-8") as f:
        json.dump({"enabled": rules_enabled}, f, ensure_ascii=False, indent=2)

def load_rules_text():
    global rules_text
    if os.path.exists(config.RULES_TEXT_FILE):
        try:
            with open(config.RULES_TEXT_FILE, "r", encoding="utf-8") as f:
                rules_text = f.read().strip()
            print(f"📜 Загружен текст правил")
        except:
            rules_text = config.DEFAULT_RULES
    else:
        rules_text = config.DEFAULT_RULES
        save_rules_text()

def save_rules_text():
    global rules_text
    with open(config.RULES_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(rules_text)

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ НИКНЕЙМОВ
# =====================================================

def load_nicknames_state():
    global nicknames_enabled
    if os.path.exists(config.NICKNAMES_ENABLED_FILE):
        try:
            with open(config.NICKNAMES_ENABLED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                nicknames_enabled = data.get("enabled", True)
            print(f"Никнеймы {'включены' if nicknames_enabled else 'выключены'}")
        except:
            nicknames_enabled = True
    else:
        nicknames_enabled = True
        save_nicknames_state()

def save_nicknames_state():
    global nicknames_enabled
    with open(config.NICKNAMES_ENABLED_FILE, "w", encoding="utf-8") as f:
        json.dump({"enabled": nicknames_enabled}, f, ensure_ascii=False, indent=2)

def load_nicknames():
    global nicknames
    if os.path.exists(config.NICKNAMES_FILE):
        try:
            with open(config.NICKNAMES_FILE, "r", encoding="utf-8") as f:
                nicknames = {int(k): v for k, v in json.load(f).items()}
            print(f"🏷️ Загружено никнеймов: {len(nicknames)}")
        except:
            nicknames = {}
    else:
        nicknames = {}
        save_nicknames()

def save_nicknames():
    with open(config.NICKNAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(nicknames, f, ensure_ascii=False, indent=2)

def set_nickname(user_id, nickname):
    global nicknames
    nickname = nickname.strip()
    if len(nickname) > 30:
        return False, "Слишком длинный (макс 30 символов)"
    if len(nickname) < 1:
        return False, "Слишком короткий"
    nicknames[user_id] = nickname
    save_nicknames()
    return True, nickname

def remove_nickname(user_id):
    global nicknames
    if user_id in nicknames:
        del nicknames[user_id]
        save_nicknames()
        return True
    return False

def get_display_name(user_id):
    if nicknames_enabled and user_id in nicknames:
        return nicknames[user_id]
    return get_user_name(user_id, mention=False)

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ АГИТАЦИИ
# =====================================================

def load_agitation_state():
    global agitation_enabled
    if os.path.exists(config.AGITATION_FILE):
        try:
            with open(config.AGITATION_FILE, "r", encoding="utf-8") as f:
                agitation_enabled = json.load(f).get("enabled", False)
            print(f"📢 Агитация за цензуру {'включена' if agitation_enabled else 'выключена'}")
        except:
            agitation_enabled = False
    else:
        agitation_enabled = False
        save_agitation_state()

def save_agitation_state():
    with open(config.AGITATION_FILE, "w", encoding="utf-8") as f:
        json.dump({"enabled": agitation_enabled}, f, ensure_ascii=False, indent=2)

def has_been_agitated(user_id):
    return user_id in agitated_users

def mark_agitated(user_id):
    agitated_users.add(user_id)

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ ДОСТУПОВ
# =====================================================

def load_access():
    global user_access
    if os.path.exists(config.ACCESS_FILE):
        try:
            with open(config.ACCESS_FILE, "r", encoding="utf-8") as f:
                user_access = {int(k): v for k, v in json.load(f).items()}
            print(f"🎫 Загружено доступов: {len(user_access)}")
        except:
            user_access = {}
    else:
        user_access = {}
        save_access()

def save_access():
    with open(config.ACCESS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_access, f, ensure_ascii=False, indent=2)

def add_access(user_id, command, amount):
    if user_id not in user_access:
        user_access[user_id] = {"alo": 0, "sudi": 0, "obosnuy": 0, "gs": 0}
    
    cmd_map = {"ало": "alo", "вывод": "sudi", "обоснуй": "obosnuy", "гс": "gs"}
    cmd_key = cmd_map.get(command)
    
    if cmd_key:
        user_access[user_id][cmd_key] += amount
        save_access()
        return True, user_access[user_id][cmd_key]
    return False, 0

def use_access(user_id, command):
    cmd_map = {"alo": "alo", "sudi": "sudi", "obosnuy": "obosnuy", "gs": "gs"}
    cmd_key = cmd_map.get(command)
    
    if not cmd_key:
        return False
    
    if user_id not in user_access:
        return False
    
    if user_access[user_id].get(cmd_key, 0) > 0:
        user_access[user_id][cmd_key] -= 1
        
        if user_access[user_id].get("alo", 0) == 0 and \
           user_access[user_id].get("sudi", 0) == 0 and \
           user_access[user_id].get("obosnuy", 0) == 0 and \
           user_access[user_id].get("gs", 0) == 0:
            del user_access[user_id]
        
        save_access()
        return True
    return False

def get_access_info(user_id):
    if user_id in user_access:
        return user_access[user_id]
    return {"alo": 0, "sudi": 0, "obosnuy": 0, "gs": 0}

def get_access_info_text(user_id):
    info = get_access_info(user_id)
    return f"🎫 Твои доступы:\n• !ало: {info['alo']}\n• !вывод: {info['sudi']}\n• !обоснуй: {info['obosnuy']}\n• !гс: {info.get('gs', 0)}"

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ ССЫЛОК
# =====================================================

def load_links_state():
    global links_enabled
    if os.path.exists(config.LINKS_ENABLED_FILE):
        try:
            with open(config.LINKS_ENABLED_FILE, "r", encoding="utf-8") as f:
                links_enabled = json.load(f).get("enabled", True)
            print(f"🔗 Контроль ссылок {'включен' if links_enabled else 'выключен'}")
        except:
            links_enabled = True
    else:
        links_enabled = True
        save_links_state()

def save_links_state():
    with open(config.LINKS_ENABLED_FILE, "w", encoding="utf-8") as f:
        json.dump({"enabled": links_enabled}, f, ensure_ascii=False, indent=2)

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ АНТИСПАМА
# =====================================================

def load_antispam_state():
    global antispam_enabled
    if os.path.exists(config.ANTISPAM_ENABLED_FILE):
        try:
            with open(config.ANTISPAM_ENABLED_FILE, "r", encoding="utf-8") as f:
                antispam_enabled = json.load(f).get("enabled", False)
            print(f"🛡️ Антиспам (повторы) {'включен' if antispam_enabled else 'выключен'}")
        except:
            antispam_enabled = False
    else:
        antispam_enabled = False
        save_antispam_state()

def save_antispam_state():
    with open(config.ANTISPAM_ENABLED_FILE, "w", encoding="utf-8") as f:
        json.dump({"enabled": antispam_enabled}, f, ensure_ascii=False, indent=2)

def check_spam(user_id, text):
    """
    Проверяет спам: повтор одинаковых сообщений и флуд (частота).
    Возвращает True, если нужно замутить.
    """
    global antispam_history
    if not antispam_enabled:
        return False
    if get_user_rank(user_id) >= 2:
        return False  # админы не проверяются

    current_time = time.time()
    flood_window = config.ANTISPAM_FLOOD_WINDOW
    repeat_window = config.ANTISPAM_REPEAT_WINDOW
    # Используем максимальное окно для хранения (повторы обычно дольше)
    max_window = max(flood_window, repeat_window)

    # Чистим историю пользователя, удаляя записи старше максимального окна
    if user_id in antispam_history:
        antispam_history[user_id] = [
            (ts, txt) for ts, txt in antispam_history[user_id]
            if current_time - ts <= max_window
        ]
    else:
        antispam_history[user_id] = []

    # Добавляем текущее сообщение
    antispam_history[user_id].append((current_time, text))

    # Проверка на флуд (частота) - смотрим за flood_window секунд
    flood_records = [
        (ts, txt) for ts, txt in antispam_history[user_id]
        if current_time - ts <= flood_window
    ]
    if len(flood_records) >= config.ANTISPAM_FLOOD_COUNT:
        return True   # флуд

    # Проверка на повтор одинаковых сообщений - смотрим за repeat_window
    repeat_records = [
        (ts, txt) for ts, txt in antispam_history[user_id]
        if current_time - ts <= repeat_window
    ]
    if len(repeat_records) >= config.ANTISPAM_REPEAT_COUNT:
        # Проверяем, все ли тексты одинаковы
        texts = [txt for _, txt in repeat_records[-config.ANTISPAM_REPEAT_COUNT:]]
        if all(txt == text for txt in texts):
            return True

    return False
# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ МОДЕЛЕЙ
# =====================================================

def load_models():
    global current_models
    if os.path.exists(config.MODELS_FILE):
        try:
            with open(config.MODELS_FILE, "r", encoding="utf-8") as f:
                current_models.update(json.load(f))
            print(f"🤖 Загружены настройки моделей: {current_models}")
        except:
            pass

def save_models():
    with open(config.MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(current_models, f, ensure_ascii=False, indent=2)

def set_model(command, model_name):
    if command in current_models:
        current_models[command] = model_name
        save_models()
        return True
    return False

def get_model(command):
    return current_models.get(command, config.DEFAULT_MODELS.get(command, "google/gemini-3.1-flash-lite"))

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ ЦЕНЗУРЫ
# =====================================================

def load_censored_users():
    global censored_users
    if os.path.exists(config.CENSORED_USERS_FILE):
        try:
            with open(config.CENSORED_USERS_FILE, "r", encoding="utf-8") as f:
                censored_users = set(json.load(f).get("users", []))
            print(f"🔇 Загружено участников под цензурой: {len(censored_users)}")
        except:
            censored_users = set()
    else:
        censored_users = set()
        save_censored_users()

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ ПРИНУДИТЕЛЬНОЙ ЦЕНЗУРЫ
# =====================================================

def load_forced_censored_users():
    global forced_censored_users
    if os.path.exists(config.FORCED_CENSORED_USERS_FILE):
        try:
            with open(config.FORCED_CENSORED_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                forced_censored_users = set(data.get("users", []))
            print(f"🔒 Загружено принудительно на цензуре: {len(forced_censored_users)}")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки forced_censored_users: {e}")
            forced_censored_users = set()
    else:
        forced_censored_users = set()
        save_forced_censored_users()
        print("📄 Файл принудительной цензуры создан (пуст)")

def save_forced_censored_users():
    with open(config.FORCED_CENSORED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": list(forced_censored_users)}, f, ensure_ascii=False, indent=2)

def is_forced_censored(user_id):
    return user_id in forced_censored_users

def add_forced_censored(user_id):
    if user_id not in forced_censored_users:
        forced_censored_users.add(user_id)
        save_forced_censored_users()
        return True
    return False

def remove_forced_censored(user_id):
    if user_id in forced_censored_users:
        forced_censored_users.remove(user_id)
        save_forced_censored_users()
        return True
    return False

def is_user_censored_global(user_id):
    """Проверяет, включена ли цензура (добровольно или принудительно)"""
    return is_user_censored(user_id) or is_forced_censored(user_id)

def save_censored_users():
    with open(config.CENSORED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": list(censored_users)}, f, ensure_ascii=False, indent=2)

def add_censored_user(user_id):
    if user_id not in censored_users:
        censored_users.add(user_id)
        save_censored_users()
        return True
    return False

def remove_censored_user(user_id):
    if user_id in censored_users:
        censored_users.remove(user_id)
        save_censored_users()
        return True
    return False

def is_user_censored(user_id):
    return user_id in censored_users

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ БАНОВ
# =====================================================

def load_bans():
    global banned_users
    if os.path.exists(config.BANS_FILE):
        try:
            with open(config.BANS_FILE, "r", encoding="utf-8") as f:
                banned_users = json.load(f)
            print(f"🔨 Загружено банов: {len(banned_users)}")
        except:
            banned_users = {}
    else:
        banned_users = {}
        save_bans()

def save_bans():
    with open(config.BANS_FILE, "w", encoding="utf-8") as f:
        json.dump(banned_users, f, ensure_ascii=False, indent=2)

def ban_user(peer_id, user_id, reason="", banned_by=None):
    try:
        chat_id = peer_id - 2000000000
        vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
        
        if peer_id not in banned_users:
            banned_users[peer_id] = {}
        
        banned_users[peer_id][user_id] = {
            "reason": reason,
            "banned_by": banned_by,
            "time": time.time()
        }
        save_bans()
        return True
    except Exception as e:
        print(f"Ошибка бана: {e}")
        return False

def is_user_banned(peer_id, user_id):
    if peer_id in banned_users and user_id in banned_users[peer_id]:
        return True
    return False

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ МУТОВ
# =====================================================

def mute_user(peer_id, user_id, duration_minutes=0):
    if peer_id not in muted_users:
        muted_users[peer_id] = {}
    
    if duration_minutes > 0:
        until_time = time.time() + (duration_minutes * 60)
        muted_users[peer_id][user_id] = until_time
        return True, duration_minutes
    else:
        muted_users[peer_id][user_id] = float('inf')
        return True, None

def unmute_user(peer_id, user_id):
    if peer_id in muted_users and user_id in muted_users[peer_id]:
        del muted_users[peer_id][user_id]
        return True
    return False

def is_user_muted(peer_id, user_id):
    if peer_id in muted_users and user_id in muted_users[peer_id]:
        until = muted_users[peer_id][user_id]
        if until == float('inf') or time.time() < until:
            return True
        else:
            del muted_users[peer_id][user_id]
    return False

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ РЕАКЦИЙ
# =====================================================

REACTION_IDS = {"лайк": 1, "каки": 5, "край": 7}

def get_reaction_emoji(reaction_type):
    emojis = {"лайк": "❤️", "каки": "💩", "край": "😭"}
    return emojis.get(reaction_type, "❤️")

def add_reaction(peer_id, cmid, reaction_type):
    reaction_id = REACTION_IDS.get(reaction_type)
    if not reaction_id:
        return False
    try:
        params = {
            'peer_id': peer_id,
            'cmid': cmid,
            'reaction_id': reaction_id,
            'access_token': config.GROUP_TOKEN,
            'v': '5.199'
        }
        requests.post('https://api.vk.com/method/messages.sendReaction', params=params)
        print(f"👍 Поставлена реакция {reaction_type} на сообщение {cmid}")
        return True
    except Exception as e:
        print(f"Ошибка при ставке реакции: {e}")
        return False

def start_reaction(peer_id, target_id, reaction_type):
    if peer_id not in user_reaction:
        user_reaction[peer_id] = {}
    user_reaction[peer_id][target_id] = reaction_type
    user_name = get_user_name(target_id)
    reaction_emoji = get_reaction_emoji(reaction_type)
    send_message(peer_id, f"👹 Терь буду ставить {reaction_emoji} под каждым сообщением {user_name}")

def stop_reaction(peer_id):
    if peer_id in user_reaction:
        user_reaction.pop(peer_id, None)
        send_message(peer_id, f"👹 Реакции отключены для всех")
        return True
    return False

def is_user_has_reaction(peer_id, user_id):
    if peer_id in user_reaction:
        return user_id in user_reaction[peer_id]
    return False

def get_user_reaction(peer_id, user_id):
    if peer_id in user_reaction and user_id in user_reaction[peer_id]:
        return user_reaction[peer_id][user_id]
    return None

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ !слыш
# =====================================================

def load_slysh_state():
    global slysh_enabled
    if os.path.exists(config.SLYSH_ENABLED_FILE):
        try:
            with open(config.SLYSH_ENABLED_FILE, "r", encoding="utf-8") as f:
                slysh_enabled = json.load(f).get("enabled", True)
            print(f"🔊 Состояние !слыш: {'включено' if slysh_enabled else 'выключено'}")
        except:
            slysh_enabled = True
    else:
        slysh_enabled = True
        save_slysh_state()

def save_slysh_state():
    with open(config.SLYSH_ENABLED_FILE, "w", encoding="utf-8") as f:
        json.dump({"enabled": slysh_enabled}, f, ensure_ascii=False, indent=2)

# =====================================================
# ЗАГРУЗКА/СОХРАНЕНИЕ НЕАКТИВНЫХ
# =====================================================

def load_inactivity_data():
    global inactivity_data
    if os.path.exists(config.INACTIVITY_FILE):
        try:
            with open(config.INACTIVITY_FILE, "r", encoding="utf-8") as f:
                inactivity_data = {int(k): v for k, v in json.load(f).items()}
            print(f"⏰ Загружены данные активности: {len(inactivity_data)} пользователей")
        except:
            inactivity_data = {}
    else:
        inactivity_data = {}
        save_inactivity_data()

def save_inactivity_data():
    with open(config.INACTIVITY_FILE, "w", encoding="utf-8") as f:
        json.dump(inactivity_data, f, ensure_ascii=False, indent=2)

def update_user_activity(user_id):
    global inactivity_data
    inactivity_data[user_id] = time.time()
    save_inactivity_data()

def kick_inactive_users(peer_id, days=None):
    if days is None:
        days = config.INACTIVITY_DAYS
    
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        current_members = []
        
        for member in members['items']:
            user_id = member['member_id']
            if user_id > 0:
                current_members.append(user_id)
        
        current_time = time.time()
        threshold = days * 24 * 60 * 60
        kicked = 0
        
        for user_id in current_members:
            if get_user_rank(user_id) >= 2:
                continue
            last_time = inactivity_data.get(user_id, 0)
            if last_time > 0 and (current_time - last_time) > threshold:
                try:
                    chat_id = peer_id - 2000000000
                    vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
                    user_name = get_user_name(user_id, mention=True)
                    send_message(peer_id, f"🚪 {user_name} кикнут за неактивность {days} дней")
                    kicked += 1
                except Exception as e:
                    print(f"❌ Ошибка кика {user_id}: {e}")
        return kicked
    except Exception as e:
        print(f"❌ Ошибка при кике неактивных: {e}")
        return 0

# =====================================================
# АНАЛИЗ КАРТИНОК (base64)
# =====================================================

def get_image_as_base64(image_url):
    try:
        import base64
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "image/jpeg")
        encoded = base64.b64encode(response.content).decode("utf-8")
        return f"data:{content_type};base64,{encoded}"
    except Exception as e:
        print(f"❌ Ошибка скачивания картинки: {e}")
        return None

def get_largest_photo_url(photo):
    sizes = photo.get("sizes", [])
    if not sizes:
        return None
    best_size = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
    return best_size.get("url")

def analyze_image_with_gemini(image_url_or_base64):
    try:
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        system_prompt = get_prompt("obosnuy")
        
        if image_url_or_base64.startswith("data:image"):
            final_url = image_url_or_base64
        else:
            final_url = get_image_as_base64(image_url_or_base64)
            if not final_url:
                return "❌ Не удалось загрузить картинку"
        
        data = {
            "model": get_model("obosnuy"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "image_url", "image_url": {"url": final_url}}
                ]}
            ],
            "max_tokens": 500,
            "temperature": 0.8
        }
        
        response = requests.post(
            "https://routerai.ru/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content'].strip()
            else:
                return "⚠️ Модель не вернула ответ"
        elif response.status_code == 402:
            return "⚠️ Паходу опять бабок надо закинуть"
        else:
            print(f"❌ Ошибка: {response.status_code} - {response.text}")
            return f"⚠️ Ошибка API: {response.status_code}"
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return f"⚠️ Алерт: {e}"

def contains_link(text):
    if not text:
        return False
    link_pattern = re.compile(r'(https?://|www\.)[^\s]+|vk\.com/[^\s]+|youtu\.be/[^\s]+')
    return bool(link_pattern.search(text))

def auto_troll_reply(peer_id, from_id, text):
    global auto_troll_count, auto_troll_limit, auto_troll_enabled
    
    if not auto_troll_enabled:
        return
    
    # Не считаем команды и сообщения от бота
    if text.startswith("!") or from_id == BOT_ID:
        return
    
    auto_troll_count += 1
    
    if auto_troll_count >= auto_troll_limit:
        auto_troll_count = 0
        
        # Запускаем в отдельном потоке, чтобы не блокировать основной цикл
        def do_auto_troll():
            try:
                # Получаем последние 10 сообщений
                last_messages = list(message_history)[-10:]
                if len(last_messages) < 3:
                    return
                
                dialog_parts = [f"{msg['user_name']}: {msg['text']}" for msg in last_messages]
                dialog_text = "\n".join(dialog_parts)
                
                try:
                    answer = ask_deepseek(dialog_text, "slysh")
                    if not answer or len(answer) < 1:
                        print("⚠️ Автотролль: пустой ответ от AI")
                        return
                except Exception as e:
                    print(f"⚠️ Автотролль: ошибка AI - {e}")
                    return
                
                if len(answer) > 200:
                    answer = answer[:200] + "..."
                
                send_message(peer_id, f"{answer}")
                print(f"🤖 Авто-темутинг отправлен")
                
            except Exception as e:
                print(f"❌ Ошибка автотролля: {e}")
                import traceback
                traceback.print_exc()
        
        # Запускаем поток
        threading.Thread(target=do_auto_troll, daemon=True).start()

# =====================================================
# ОСНОВНОЙ ОБРАБОТЧИК
# =====================================================

def handle_message(msg):
    global message_history
    global slysh_enabled
    global rules_enabled
    global rules_text
    global greeting_enabled
    global greeting_text
    global nicknames_enabled  
    global nicknames
    global agitation_enabled
    global agitated_users
    global user_access
    global links_enabled
    global antispam_enabled
    global current_models
    global censored_users
    global banned_users
    global muted_users
    global user_reaction
    global admins_cache
    global user_ranks
    global inactivity_data
    global auto_troll_enabled
    global auto_troll_count
    global auto_troll_limit
    global forced_censored_users
    
    # ==========================================
    # ПОЛУЧАЕМ ДАННЫЕ ИЗ СООБЩЕНИЯ
    # ==========================================
    peer_id = msg.get("peer_id")
    from_id = msg.get("from_id")
    text = msg.get("text", "")
    # Убираем упоминания группы/пользователей в начале
    import re
    text = re.sub(r'^\[(?:id|club)\d+\|[^\]]+\]\s*', '', text).strip()

    # Маппинг по ключевым словам (без эмодзи)
    cmd_map = {
        "грубить в интернете": "!вкл",
        "не нужен твой дурацкий бот": "!выкл",
        "мои доступы": "!моидоступы",
    }

    cmid = msg.get("conversation_message_id")
    text_lower = text.lower()

    print(f"🔍 Текст сообщения: '{text}'")

    # Определяем команду по ключевому слову
    matched_command = None
    for key, cmd in cmd_map.items():
        if key in text_lower:
            matched_command = cmd
            break

    if matched_command:
        text = matched_command
        text_lower = text.lower()
        # Удаляем сообщение с кнопкой (VK шлёт его с упоминанием группы)
        # Делаем это в фоне с задержкой, чтобы команда успела выполниться
        def delete_button_message():
            time.sleep(1.0)
            try:
                delete_message(peer_id, cmid)
                print(f"🗑️ Удалено сообщение от кнопки: cmid={cmid}")
            except Exception as e:
                print(f"⚠️ Не удалось удалить сообщение кнопки: {e}")
        threading.Thread(target=delete_button_message, daemon=True).start()
        
    # ==========================================
    # ОБРАБОТКА ВХОДОВ В ЧАТ
    # ==========================================
    action = msg.get("action", {})
    action_type = action.get("type")
    
    if action_type and peer_id > 2000000000:
        join_events = [
            "chat_invite_user", "chat_invite_user_by_link",
            "chat_invite_user_by_message_request", "chat_invite_user_by_qr",
            "chat_invite_user_by_phone"
        ]
        
        if action_type in join_events:
            member_id = action.get("member_id")
            if not member_id:
                member_id = msg.get("from_id")
            
            if not member_id or member_id == BOT_ID:
                return
            
            if is_user_banned(peer_id, member_id):
                try:
                    chat_id = peer_id - 2000000000
                    vk.messages.removeChatUser(chat_id=chat_id, user_id=member_id)
                    print(f"🚫 Забаненный {get_user_name(member_id)} кикнут")
                except Exception as e:
                    print(f"Ошибка кика: {e}")
                return
            
            if greeting_enabled:
                user_name = get_user_name(member_id)
                welcome_msg = get_greeting(member_id, user_name)
                send_message(peer_id, welcome_msg)
            return
        
        elif action_type in ["chat_kick_user", "chat_kick_user_by_link"]:
            return
        
        elif action_type in ["chat_title_update", "chat_photo_update", "chat_photo_remove"]:
            return
        else:
            return
    
    # ==========================================
    # ПРОПУСКАЕМ ЛИЧКУ И БОТА
    # ==========================================
    if peer_id < 2000000000 or from_id == BOT_ID:
        return
    
    update_user_activity(from_id)
    
    print(f"\n==============================\nСообщение: {text}")
    
    # ==========================================
    # ПРОВЕРКА НА МУТ
    # ==========================================
    if is_user_muted(peer_id, from_id):
        delete_message(peer_id, cmid)
        print(f"🔇 Удалено сообщение от замьюченного {get_user_name(from_id)}")
        return
    
    # ==========================================
    # АНТИСПАМ
    # ==========================================
    if antispam_enabled and check_spam(from_id, text):
        success, _ = mute_user(peer_id, from_id, config.ANTISPAM_MUTE_DURATION)
        if success:
            send_message(peer_id, f"🔇 {get_user_name(from_id, mention=True)} онлирид на {config.ANTISPAM_MUTE_DURATION} минут за флуд нахуй")
        else:
            send_message(peer_id, f"⚠️ Не вышло замутить {get_user_name(from_id, mention=True)} за спам, сообщение удалено")
        delete_message(peer_id, cmid)
        return
    
    # ==========================================
    # ПРОВЕРКА НА РЕАКЦИИ
    # ==========================================
    if is_user_has_reaction(peer_id, from_id):
        if not text.startswith("!"):
            reaction_type = get_user_reaction(peer_id, from_id)
            if reaction_type:
                add_reaction(peer_id, cmid, reaction_type)
    
    # ==========================================
    # ТЕМУТИНГ
    # ==========================================
    if is_user_trolled(peer_id, from_id):
        display_name = get_display_name(from_id)
        clickable_name = f"[id{from_id}|{display_name}]"
        fake_message = get_random_phrase()
        bot_text = f"{clickable_name}: {fake_message}"

        message_history.append({
            "user_id": from_id,
            "user_name": display_name,
            "text": fake_message,
            "time": time.time()
        })

        attachment_string = build_attachment_string(msg.get("attachments", []))
        reply_to = msg.get("reply_message", {}).get("conversation_message_id") if msg.get("reply_message") else None

        try:
            send_message(peer_id, bot_text, attachment_string, reply_to)
        except Exception as e:
            print(f"Ошибка отправки фейка: {e}")

        try:
            delete_message(peer_id, cmid)
        except Exception as e:
            print(f"Ошибка удаления: {e}")
        return
        
    # ==========================================
    # АВТОМАТИЧЕСКИЙ ТРОЛЛИНГ (каждые N сообщений)
    # ==========================================
    auto_troll_reply(peer_id, from_id, text)
    
    # ==========================================
    # СОХРАНЕНИЕ В ИСТОРИЮ
    # ==========================================
    if text and not text.startswith("!"):
        message_history.append({
            "user_id": from_id,
            "user_name": get_user_name(from_id),
            "text": text,
            "time": time.time()
        })
    
    # ==========================================
    # КТО АДМИНЫ (триггер)
    # ==========================================
    if text_lower in ["кто админы", "кто админ", "а судьи кто", "админы", "админ"]:
        if peer_id in admins_cache:
            send_message(peer_id, "\n".join(admins_cache[peer_id]), disable_mentions=True)
            return

        sixers = []
        basota = []
        owner = None
        specials = []
        shown_users = set()

        owner_name = get_user_name(config.OWNER_ID, mention=False)
        owner_clickable = f"[id{config.OWNER_ID}|{owner_name}]"
        owner = f"👑 Пахан - {owner_clickable}"
        shown_users.add(config.OWNER_ID)

        if hasattr(config, 'SPECIAL_ROLES'):
            for user_id, role in config.SPECIAL_ROLES.items():
                user_name = get_user_name(user_id, mention=False)
                clickable = f"[id{user_id}|{user_name}]"
                specials.append(f"{role} {clickable}")
                shown_users.add(user_id)

        for user_id, rank in user_ranks.items():
            if user_id in shown_users:
                continue
            user_name = get_user_name(user_id, mention=False)
            clickable = f"[id{user_id}|{user_name}]"
            if rank == 2:
                sixers.append(clickable)
            elif rank == 1:
                basota.append(clickable)

        final_result = []
        if owner:
            final_result.append(owner)
        if specials:
            final_result.extend(specials)
        if sixers:
            final_result.append(f"⭐ Шестёрки - {', '.join(sixers)}")
        if basota:
            final_result.append(f"💩 Басота - {', '.join(basota)}")

        if not final_result:
            final_result = ["Нет админов, первым буш??"]

        admins_cache[peer_id] = final_result
        send_message(peer_id, "\n".join(final_result), disable_mentions=True)
        return
    
    # ==========================================
    # ПУБЛИЧНЫЕ КОМАНДЫ
    # ==========================================
    
    # !гс - показать список доступных голосовых
    if text.lower() == "!гс":
        files = get_available_audio_files()
        if files:
            send_message(peer_id, f"Доступные голосовые:\n" + "\n".join(f"• {f}" for f in files), reply_to=cmid)
        else:
            send_message(peer_id, "Нет доступных голосовых", reply_to=cmid)
        return

    # !гс [название] - отправить голосовое
    if text.lower().startswith("!гс "):
        voice_name = text[4:].strip()
        
        if get_user_rank(from_id) < 2:
            if not use_access(from_id, "gs"):
                send_message(peer_id, "❌ У тя нет доступов к !гс. Придется сосать пахану", reply_to=cmid)
                delete_message(peer_id, cmid)
                return
        
        audio_path = get_audio_path(voice_name)
        
        if not os.path.exists(audio_path):
            files = get_available_audio_files()
            if files:
                send_message(peer_id, f"❌ Голосовое '{voice_name}' не найдено\n\n Доступные:\n" + "\n".join(f"• {f}" for f in files), reply_to=cmid)
            else:
                send_message(peer_id, f"❌ Голосовое '{voice_name}' не найдено\n Нет доступных голосовых", reply_to=cmid)
            delete_message(peer_id, cmid)
            return
        
        if send_audio_message(peer_id, audio_path):
            print(f"🎵 Отправлено голосовое: {voice_name}")
        else:
            send_message(peer_id, "❌ Не удалось отправить голосовое", reply_to=cmid)
        
        delete_message(peer_id, cmid)
        return
    
    # !ало
    if text.lower().startswith("!ало"):
        if get_user_rank(from_id) >= 1:
            pass
        else:
            if not use_access(from_id, "alo"):
                send_message(peer_id, "❌ У тя нет доступов к !ало. Придется сосать пахану", reply_to=cmid)
                return
        
        question = text[5:].strip()
        reply_msg = msg.get("reply_message")
        
        if reply_msg:
            replied_text = reply_msg.get("text", "").strip()
            replied_user_id = reply_msg.get("from_id")
            replied_user_name = get_user_name(replied_user_id)
            if question:
                final_question = f"Пользователь {replied_user_name} написал: \"{replied_text}\". Его вопрос: {question}"
            else:
                final_question = f"Пользователь {replied_user_name} написал: \"{replied_text}\". Ответь на это сообщение"
            reply_to_cmid = reply_msg.get("conversation_message_id")
        else:
            if not question:
                send_message(peer_id, "❓ Че хочеш то епта??", reply_to=cmid)
                return
            final_question = question
            reply_to_cmid = cmid
        
        def ask_and_reply():
            answer = ask_deepseek(final_question, "alo")
            if len(answer) > 3500:
                answer = answer[:3500] + "..."
            send_message(peer_id, f"💬 {answer}", reply_to=reply_to_cmid)
        
        threading.Thread(target=ask_and_reply, daemon=True).start()
        return
    
    # !вывод
    if text.lower() == "!вывод":
        if get_user_rank(from_id) >= 1:
            pass
        else:
            if not use_access(from_id, "sudi"):
                send_message(peer_id, "❌ У тя нет доступов к !вывод. Придется сосать пахану", reply_to=cmid)
                return
        
        def analyze_and_reply():
            result = analyze_chat_with_ai()
            send_message(peer_id, f"💬 {result}")
        
        threading.Thread(target=analyze_and_reply, daemon=True).start()
        return
    
    # !обоснуй
    if text.lower().startswith("!обоснуй"):
        if get_user_rank(from_id) >= 1:
            pass
        else:
            if not use_access(from_id, "obosnuy"):
                send_message(peer_id, "❌ У тя нет доступов к !обоснуй. Придется сосать пахану", reply_to=cmid)
                return
        
        reply_msg = msg.get("reply_message")
        image_url = None
        replied_user_name = None
        replied_cmid = None
        
        if reply_msg:
            attachments = reply_msg.get("attachments", [])
            replied_cmid = reply_msg.get("conversation_message_id")
            replied_user_id = reply_msg.get("from_id")
            replied_user_name = get_user_name(replied_user_id)
            
            for att in attachments:
                if att.get("type") == "photo":
                    image_url = get_largest_photo_url(att["photo"])
                    break
            
            if not image_url:
                send_message(peer_id, f"❌ В сообщении от {replied_user_name} не вижу нихуя", reply_to=cmid)
                return
        else:
            attachments = msg.get("attachments", [])
            for att in attachments:
                if att.get("type") == "photo":
                    image_url = get_largest_photo_url(att["photo"])
                    break
            
            if not image_url:
                send_message(peer_id, "Че хочеш не пойму, скинь фото попа 1 шт и обосную", reply_to=cmid)
                return
            replied_cmid = cmid
        
        image_data_url = get_image_as_base64(image_url)
        if not image_data_url:
            send_message(peer_id, "❌ Не удалось скачать картинку. Попробуй другую.", reply_to=cmid)
            return
        
        def analyze():
            result = analyze_image_with_gemini(image_data_url)
            if len(result) > 3500:
                result = result[:3500] + "..."
            if replied_user_name:
                send_message(peer_id, f"💬 {replied_user_name}, {result.lower()}", reply_to=replied_cmid)
            else:
                send_message(peer_id, f"💬 {result}", reply_to=replied_cmid)
        
        threading.Thread(target=analyze, daemon=True).start()
        return
    
    # !моидоступы
    if text.lower() == "!моидоступы":
        if get_user_rank(from_id) >= 1:
            send_message(peer_id, "👑 Ты пахан, у тя безлимит!", reply_to=cmid)
        else:
            send_message(peer_id, get_access_info_text(from_id), reply_to=cmid)
        return
    
    # правила
    if text.lower() == "правила":
        if rules_enabled:
            send_message(peer_id, rules_text, reply_to=cmid)
        else:
            send_message(peer_id, "Правил нет делай че хочеш", reply_to=cmid)
        return
    
    # !ник
    if text.lower().startswith("!ник "):
        if not is_user_censored(from_id):
            send_message(peer_id, "❌ Сначала включи цензуру командой !вкл", reply_to=cmid)
            return
        if not nicknames_enabled:
            send_message(peer_id, "❌ Никнеймы отключены администратором", reply_to=cmid)
            return
        
        new_nick = text[5:].strip()
        success, result = set_nickname(from_id, new_nick)
        if success:
            send_message(peer_id, f"👹 Терь ты: {result}", reply_to=cmid)
        else:
            send_message(peer_id, f"❌ {result}", reply_to=cmid)
        return
    
    # !ник-
    if text.lower() == "!ник-":
        if not is_user_censored(from_id):
            send_message(peer_id, "❌ У тебя даже цензуры нет", reply_to=cmid)
            return
        if remove_nickname(from_id):
            send_message(peer_id, f"👹 Терь ты без погоняла в чатике, {get_user_name(from_id, mention=False)}", reply_to=cmid)
        else:
            send_message(peer_id, "❌ У тебя и так нет ника", reply_to=cmid)
        return
    
    # !ники
    if text.lower() == "!ники":
        if not nicknames:
            send_message(peer_id, "❌ Погремух в чате нет", reply_to=cmid)
            return
        sorted_nicks = sorted(nicknames.items(), key=lambda x: x[1].lower())
        result = "📝 Список никнеймов:\n"
        for user_id, nick in sorted_nicks:
            clickable_nick = f"[id{user_id}|{nick}]"
            real_name = get_user_name(user_id, mention=False)
            result += f"{clickable_nick} - {real_name}\n"
            if len(result) > 3500:
                send_message(peer_id, result, disable_mentions=True)
                result = ""
        if result:
            send_message(peer_id, result, reply_to=cmid, disable_mentions=True)
        return
    
    # -смс
    if text.lower() == "-смс":
        if get_user_rank(from_id) < 1:
            send_message(peer_id, "⚠️ Ты кто епта??", reply_to=cmid)
            return
        reply_msg = msg.get("reply_message")
        if not reply_msg:
            send_message(peer_id, "❌ На сообщение ответь командой бля!!", reply_to=cmid)
            return
        target_cmid = reply_msg.get("conversation_message_id")
        if target_cmid:
            delete_message(peer_id, target_cmid)
        delete_message(peer_id, cmid)
        return
    
    # !слыш+
    if text.lower() == "!слыш+":
        if from_id != config.OWNER_ID:
            send_message(peer_id, "⚠️ Токо пахан может включать эту функцию!", reply_to=cmid)
            return
        if not slysh_enabled:
            slysh_enabled = True
            save_slysh_state()
            send_message(peer_id, "Слышу родной", reply_to=cmid)
        else:
            send_message(peer_id, "Я тут, чё ты дёргаешь?", reply_to=cmid)
        return
    
    # !слыш-
    if text.lower() == "!слыш-":
        if from_id != config.OWNER_ID:
            send_message(peer_id, "⚠️ Токо пахан может выключать эту функцию!", reply_to=cmid)
            return
        if slysh_enabled:
            slysh_enabled = False
            save_slysh_state()
            send_message(peer_id, "Сори, я онлирид. Щя токо близким отвечаю", reply_to=cmid)
        else:
            send_message(peer_id, "Слыш я не на месте ты кумаришь??", reply_to=cmid)
        return
    
    # !слыш
    if text.lower().startswith("!слыш"):
        if not slysh_enabled:
            send_message(peer_id, "Сори, я онли рид. Щя токо близким отвечаю", reply_to=cmid)
            return
        
        last_messages = list(message_history)[-10:]
        if len(last_messages) < 3:
            send_message(peer_id, "Слыш а че тут мусолить?", reply_to=cmid)
            return
        
        dialog_parts = [f"{msg['user_name']}: {msg['text']}" for msg in last_messages]
        dialog_text = "\n".join(dialog_parts)
        question = text[6:].strip()
        
        if question:
            prompt = f"""Ты подслушал этот диалог. Тебя спросили: "{question}"
Ответь ОДНИМ КОРОТКИМ предложением (максимум 10-12 слов).

Диалог:
{dialog_text}

Твой короткий ответ:"""
        else:
            prompt = f"""Ты подслушал этот диалог. Влезь в него со своим комментарием.
Ответь ОДНИМ КОРОТКИМ предложением (максимум 10-12 слов).

Диалог:
{dialog_text}

Твой короткий ответ:"""
        
        def slysh_reply():
            answer = ask_deepseek(prompt, "slysh")
            if len(answer) > 200:
                answer = answer[:200] + "..."
            send_message(peer_id, f"{answer}", reply_to=cmid)
        
        threading.Thread(target=slysh_reply, daemon=True).start()
        return
    
    # !вкл - включить добровольную цензуру для себя
    if text.lower() == "!вкл":
        # Если под принудительной — нельзя выключить
        if is_forced_censored(from_id):
            send_message(peer_id, f"👹 {get_user_name(from_id, mention=True)}, ты под принудительной цензурой, отключить может только пахан!", reply_to=cmid)
            return
        
        if is_user_censored(from_id):
            send_message(peer_id, f"⚠️ {get_user_name(from_id, mention=True)}, ты уже на карандаше")
        else:
            add_censored_user(from_id)
            send_message(peer_id, f"{get_user_name(from_id, mention=True)}, можешь базарить смело")
        return

    # !выкл - отключить добровольную цензуру для себя
    if text.lower() == "!выкл":
        # Если под принудительной — нельзя выключить
        if is_forced_censored(from_id):
            send_message(peer_id, f"👹 {get_user_name(from_id, mention=True)}, ты под принудительной цензурой, отключить может только пахан!", reply_to=cmid)
            return
        
        if not is_user_censored(from_id):
            send_message(peer_id, f"⚠️ {get_user_name(from_id, mention=True)}, я тя и так не слушаю")
        else:
            remove_censored_user(from_id)
            send_message(peer_id, f"{get_user_name(from_id, mention=True)}, зря, щя обиженные хуисосы тебе страйков накинут")
        return
        
            # !бот
    if text.lower() == "!бот":
        uptime_seconds = int(time.time() - config.START_TIME)
        uptime_days = uptime_seconds // 86400
        uptime_hours = (uptime_seconds % 86400) // 3600
        uptime_minutes = (uptime_seconds % 3600) // 60
        uptime_seconds = uptime_seconds % 60
        
        if uptime_days > 0:
            uptime_str = f"{uptime_days}д {uptime_hours}ч {uptime_minutes}м {uptime_seconds}с"
        elif uptime_hours > 0:
            uptime_str = f"{uptime_hours}ч {uptime_minutes}м {uptime_seconds}с"
        else:
            uptime_str = f"{uptime_minutes}м {uptime_seconds}с"
        
        ai_ping = "..."
        try:
            start = time.time()
            requests.get("https://routerai.ru/api/v1/auth/key", headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"}, timeout=5)
            ai_ping = int((time.time() - start) * 1000)
        except:
            ai_ping = "❌"
        
        censored_count = len(censored_users)
        bad_words_count = len(get_bad_words())  # 👈 ИСПРАВЛЕНО
        banned_count = len(banned_users)
        
        stats_text = f"""⏱ Время работы: {uptime_str}
🌐 RouterAI: {ai_ping} мс
👹 Матюков: {bad_words_count}
🗿 На цензуре: {censored_count} чел.
☠ Банов: {banned_count}"""
        
        send_message(peer_id, stats_text)
        return
    
    # ==========================================
    # МЕНЮ И КЛАВИАТУРА
    # ==========================================
    if text.lower() == "!меню":
        from vk_utils import build_keyboard
        rows = [
            [("👹 Я буду грубить в интернете!", "!вкл", "negative")],
            [("😭 Мне не нужен твой дурацкий бот!", "!выкл", "primary")],
            [("🎫 Мои доступы", "!моидоступы", "positive")],
        ]
        keyboard = build_keyboard(rows, one_time=False, inline=True)
        send_message(
            peer_id,
            "Жми нахуй:",
            reply_to=cmid,
            keyboard=keyboard
        )
        return
        
    # ==========================================
    # КОМАНДЫ АДМИНОВ
    # ==========================================
    if get_user_rank(from_id) >= 1:
        
        # ==========================================
        # КОМАНДЫ АВТО-ТЕМУТИНГА (только овнер)
        # ==========================================

        # !автотр+ - включить авто-темутинг
        if text.lower() == "!автотр+":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может включать!", reply_to=cmid)
                return
            
            if not auto_troll_enabled:
                auto_troll_enabled = True
                auto_troll_count = 0
                send_message(peer_id, f"👹 Понял тя, терь каждые {auto_troll_limit} сообщений буду влезать в базар", reply_to=cmid)
            else:
                send_message(peer_id, "⚠️ Автотролль уже включен", reply_to=cmid)
            return

        # !автотр- - выключить авто-темутинг
        if text.lower() == "!автотр-":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может выключать!", reply_to=cmid)
                return
            
            if auto_troll_enabled:
                auto_troll_enabled = False
                auto_troll_count = 0
                send_message(peer_id, "👹 Автотролль выключен", reply_to=cmid)
            else:
                send_message(peer_id, "⚠️ Автотролль уже выключен", reply_to=cmid)
            return

        # !счетчиктр N - установить частоту авто-темутинга
        if text.lower().startswith("!счетчиктр "):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может!", reply_to=cmid)
                return
            
            try:
                new_limit = int(text[11:].strip())
                if new_limit < 3 or new_limit > 100:
                    send_message(peer_id, "❌ Число от 3 до 100", reply_to=cmid)
                    return
                auto_troll_limit = new_limit
                auto_troll_count = 0
                send_message(peer_id, f"✅ Теперь буду влезать каждые {auto_troll_limit} сообщений", reply_to=cmid)
            except:
                send_message(peer_id, "❌ Введи число! Пример: !счетчиктр 15", reply_to=cmid)
            return
            
        # ==========================================
        # КОМАНДЫ ПРИНУДИТЕЛЬНОЙ ЦЕНЗУРЫ (только пахан)
        # ==========================================

        # !ценз+ @user - принудительно включить цензуру (только пахан)
        if text.lower().startswith("!ценз+"):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Только пахан может сажать на принудительную цензуру!", reply_to=cmid)
                return
            
            rest = text[6:].strip()   # обрезаем "!ценз+" (6 символов)
            target_id = get_user_id_from_mention_or_reply(rest, msg, peer_id)
            
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!ценз+ @user\nили ответь на сообщение", reply_to=cmid)
                return
            
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Бота нельзя", reply_to=cmid)
                return
            if target_id == from_id:
                send_message(peer_id, "❌ Себя нельзя", reply_to=cmid)
                return
            if target_id == config.OWNER_ID:
                send_message(peer_id, "❌ Нельзя посадить пахана на цензуру!", reply_to=cmid)
                return
            if is_forced_censored(target_id):
                send_message(peer_id, f"⚠️ {get_user_name(target_id, mention=True)} уже под принудительной цензурой", reply_to=cmid)
                return
            
            add_forced_censored(target_id)
            send_message(peer_id, f"👹 {get_user_name(target_id, mention=True)} теперь под принудительной цензурой! Снять может только пахан.", reply_to=cmid)
            return

        # !ценз- @user - снять принудительную цензуру (только пахан)
        if text.lower().startswith("!ценз-"):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Только пахан может снимать принудительную цензуру!", reply_to=cmid)
                return
            
            rest = text[6:].strip()   # обрезаем "!ценз-" (6 символов)
            target_id = get_user_id_from_mention_or_reply(rest, msg, peer_id)
            
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!ценз- @user\nили ответь на сообщение", reply_to=cmid)
                return
            
            if not is_forced_censored(target_id):
                send_message(peer_id, f"⚠️ {get_user_name(target_id, mention=True)} не под принудительной цензурой", reply_to=cmid)
                return
            
            remove_forced_censored(target_id)
            send_message(peer_id, f"👹 {get_user_name(target_id, mention=True)} больше не под принудительной цензурой", reply_to=cmid)
            return
        
        # ==========================================
        # КОМАНДЫ ГОЛОСОВЫХ (только овнер)
        # ==========================================

        # !обновитьгс - обновить список голосовых (показать)
        if text.lower() == "!обновитьгс":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Только пахан может!", reply_to=cmid)
                return
            
            files = get_available_audio_files()
            if files:
                send_message(peer_id, f"🎵 Доступно {len(files)} голосовых:\n" + "\n".join(f"• {f}" for f in files), reply_to=cmid)
            else:
                send_message(peer_id, "📭 Нет голосовых файлов в папке audio/", reply_to=cmid)
            return
    
        # !кикнеактив
        if text.lower().startswith("!кикнеактив"):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может скинуть неактивных", reply_to=cmid)
                return
            parts = text.split()
            days = None
            if len(parts) > 1:
                try:
                    days = int(parts[1])
                    if days < 1 or days > 365:
                        send_message(peer_id, "❌ Укажи количество дней от 1 до 365", reply_to=cmid)
                        return
                except:
                    send_message(peer_id, "❌ Неверный формат. Используй: !кикнеактив [дни]", reply_to=cmid)
                    return
            send_message(peer_id, "⏳ Проверяю неактивных...", reply_to=cmid)
            kicked = kick_inactive_users(peer_id, days)
            if kicked == 0:
                send_message(peer_id, f"👹 Неактивных пользователей (больше {days or config.INACTIVITY_DAYS} дней) не найдено.", reply_to=cmid)
            else:
                send_message(peer_id, f"👹 Кикнуто неактивных: {kicked}", reply_to=cmid)
            return
        
        # !антиспам+
        if text.lower() == "!антиспам+":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "❌ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            if not antispam_enabled:
                antispam_enabled = True
                save_antispam_state()
                send_message(peer_id, "🛡️ Антиспам включен", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Антиспам уже включен", reply_to=cmid)
            return
        
        # !антиспам-
        if text.lower() == "!антиспам-":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "❌ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            if antispam_enabled:
                antispam_enabled = False
                save_antispam_state()
                send_message(peer_id, "🛡️ Антиспам выключен", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Антиспам уже выключен", reply_to=cmid)
            return
        
        # !ссылки+
        if text.lower() == "!ссылки+":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "❌ Ты кто епта?", reply_to=cmid)
                return
            if not links_enabled:
                links_enabled = True
                save_links_state()
                send_message(peer_id, "👹 Ссылки можно", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Ссылки уже разрешены", reply_to=cmid)
            return
        
        # !ссылки-
        if text.lower() == "!ссылки-":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "❌ Ты кто епта?!", reply_to=cmid)
                return
            if links_enabled:
                links_enabled = False
                save_links_state()
                send_message(peer_id, "👹 Ссылки запрещены! Будем наказывать онлиридом", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Ссылки уже запрещены", reply_to=cmid)
            return
        
        # !отобрать
        if text.lower().startswith("!отобрать"):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Только пахан может отбирать доступы!", reply_to=cmid)
                return
            rest = text[9:].strip() if len(text) > 9 else ""
            target_id = get_user_id_from_mention_or_reply(rest, msg, peer_id)
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!отобрать @username\nили ответь на сообщение", reply_to=cmid)
                return
            if target_id == BOT_ID:
                send_message(peer_id, "❌ У бота и так нет", reply_to=cmid)
                return
            if target_id == from_id:
                send_message(peer_id, "❌ Себе нельзя", reply_to=cmid)
                return
            if target_id not in user_access:
                send_message(peer_id, f"❌ У {get_user_name(target_id, mention=True)} и так нет доступов", reply_to=cmid)
                return
            user_name = get_user_name(target_id, mention=True)
            old_access = user_access[target_id].copy()
            del user_access[target_id]
            save_access()
            result = f"👹 {user_name} обнулены все доступы!\n"
            result += f"   !ало: {old_access.get('alo', 0)} → 0\n"
            result += f"   !вывод: {old_access.get('sudi', 0)} → 0\n"
            result += f"   !обоснуй: {old_access.get('obosnuy', 0)} → 0"
            send_message(peer_id, result, reply_to=cmid)
            return
        
        # !дать - выдать доступы
        if text.lower().startswith("!дать "):
            print(f"🔍 Блок !дать выполняется!")
            print(f"🔍 from_id: {from_id}, OWNER_ID: {config.OWNER_ID}")
            
            if from_id != config.OWNER_ID:
                print(f"❌ Не овнер! from_id={from_id}, owner={config.OWNER_ID}")
                send_message(peer_id, "❌ Только пахан может выдавать доступы!", reply_to=cmid)
                return
            
            print(f"✅ Овнер подтверждён!")
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Только пахан может выдавать доступы!", reply_to=cmid)
                return
            
            rest = text[6:].strip()
            target_id = get_user_id_from_mention_or_reply(rest, msg, peer_id)
            
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!дать @username ало 5\nили ответь на сообщение", reply_to=cmid)
                return
            
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Боту не надо", reply_to=cmid)
                return
            
            if target_id == from_id:
                send_message(peer_id, "❌ Себе нельзя", reply_to=cmid)
                return
            
            clean_text = re.sub(r'\[id\d+\|[^\]]+\]\s*', '', rest).strip()
            parts = clean_text.split()
            
            if len(parts) < 2:
                send_message(peer_id, "❌ Укажи команду и количество\nПример: !дать @user ало 5", reply_to=cmid)
                return
            
            command = parts[0].lower()
            try:
                amount = int(parts[1])
                if amount <= 0 or amount > 100:
                    send_message(peer_id, "❌ Количество должно быть от 1 до 100", reply_to=cmid)
                    return
            except:
                send_message(peer_id, "❌ Количество должно быть числом", reply_to=cmid)
                return
          
            if command not in ["ало", "вывод", "обоснуй", "гс"]:
                send_message(peer_id, "❌ Доступные команды: ало, вывод, обоснуй, гс", reply_to=cmid)
                return
            
            success, total = add_access(target_id, command, amount)
            if success:
                user_name = get_user_name(target_id, mention=True)
                send_message(peer_id, f"👹 {user_name} получил {amount} доступ(ов) к команде !{command}. Всего: {total}", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Ошибка", reply_to=cmid)
            return
        
        # !попрошайки
        if text.lower() == "!попрошайки":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может смотреть список!", reply_to=cmid)
                return
            if not user_access:
                send_message(peer_id, "Ни у кого нет доступов", reply_to=cmid)
                return
            result = "🎫 Список доступов:\n\n"
            for user_id, access in user_access.items():
                user_name = get_user_name(user_id, mention=False)
                result += f"{user_name}:\n"
                result += f"   !ало: {access.get('alo', 0)}\n"
                result += f"   !вывод: {access.get('sudi', 0)}\n"
                result += f"   !обоснуй: {access.get('obosnuy', 0)}\n"
                result += f"   !гс: {access.get('gs', 0)}\n\n"  # 👈 ДОБАВЛЕНО
                if len(result) > 3500:
                    send_message(peer_id, result)
                    result = ""
            if result:
                send_message(peer_id, result, reply_to=cmid)
            return
        
        # !агит+
        if text.lower() == "!агит+":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может включать агитацию!", reply_to=cmid)
                return
            if not agitation_enabled:
                agitation_enabled = True
                save_agitation_state()
                send_message(peer_id, "👹 Агитация идет", reply_to=cmid)
            else:
                send_message(peer_id, "⚠️ Агитация уже включена", reply_to=cmid)
            return
        
        # !агит-
        if text.lower() == "!агит-":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Только пахан может выключать агитацию!", reply_to=cmid)
                return
            if agitation_enabled:
                agitation_enabled = False
                save_agitation_state()
                send_message(peer_id, "👹 Агитация не идет", reply_to=cmid)
            else:
                send_message(peer_id, "⚠️ Агитация уже выключена", reply_to=cmid)
            return
        
        # !ники+
        if text.lower() == "!ники+":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может включать никнеймы!", reply_to=cmid)
                return
            if not nicknames_enabled:
                nicknames_enabled = True
                save_nicknames_state()
                send_message(peer_id, "👹 Никнеймы включены!", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Никнеймы уже включены", reply_to=cmid)
            return
        
        # !ники-
        if text.lower() == "!ники-":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "❌ Токо пахан может выключать никнеймы!", reply_to=cmid)
                return
            if nicknames_enabled:
                nicknames_enabled = False
                save_nicknames_state()
                send_message(peer_id, "👹 Никнеймы выключены! Погонял не будет", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Никнеймы уже выключены", reply_to=cmid)
            return
        
        # !правила+
        if text.lower() == "!правила+":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "❌ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            if not rules_enabled:
                rules_enabled = True
                save_rules_state()
                send_message(peer_id, "Правила включены", reply_to=cmid)
            else:
                send_message(peer_id, "❌ Правила уже включены", reply_to=cmid)
            return
        
        # !правила-
        if text.lower() == "!правила-":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "❌ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            if rules_enabled:
                rules_enabled = False
                save_rules_state()
                send_message(peer_id, "Правила выключены", reply_to=cmid)
            else:
                send_message(peer_id, "⚠️ Правила уже выключены", reply_to=cmid)
            return
        
        # !редправила
        if text.lower().startswith("!редправила "):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            new_rules = text[12:].strip()
            if len(new_rules) < 10:
                send_message(peer_id, "⚠️ Правила слишком короткие (минимум 10 символов)", reply_to=cmid)
                return
            rules_text = new_rules
            save_rules_text()
            send_message(peer_id, f"👹 Правила обновлены!\n\n{rules_text}", reply_to=cmid)
            return
        
        # !сбросправила
        if text.lower() == "!сбросправила":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            rules_text = config.DEFAULT_RULES
            save_rules_text()
            send_message(peer_id, f"👹 Правила сброшены до стандартных!\n\n{rules_text}", reply_to=cmid)
            return
        
        # !прив+
        if text.lower() == "!прив+":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            if not greeting_enabled:
                greeting_enabled = True
                save_greeting_state()
                send_message(peer_id, "Приветствия включены", reply_to=cmid)
            else:
                send_message(peer_id, "⚠️ Приветствия уже включены", reply_to=cmid)
            return
        
        # !прив-
        if text.lower() == "!прив-":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            if greeting_enabled:
                greeting_enabled = False
                save_greeting_state()
                send_message(peer_id, "Приветствия выключены", reply_to=cmid)
            else:
                send_message(peer_id, "⚠️ Приветствия уже выключены", reply_to=cmid)
            return
        
        # !приветствие
        if text.lower() == "!приветствие" or text.lower() == "!прив":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            send_message(peer_id, f"🗓 Приветствие беседы:\n{greeting_text}", reply_to=cmid)
            return
        
        # !редприв
        if text.lower().startswith("!редприв "):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            new_greeting = text[9:].strip()
            if len(new_greeting) < 3:
                send_message(peer_id, "⚠️ Приветствие слишком короткое (минимум 3 символа)", reply_to=cmid)
                return
            greeting_text = new_greeting
            save_greeting_text()
            send_message(peer_id, f"👹 Приветствие изменено!\n\nНовое приветствие:\n{greeting_text}", reply_to=cmid)
            return
        
        # !сбросприв
        if text.lower() == "!сбросприв":
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!", reply_to=cmid)
                return
            greeting_text = config.DEFAULT_GREETING
            save_greeting_text()
            send_message(peer_id, f"👹 Приветствие сброшено до стандартного:\n\n{greeting_text}", reply_to=cmid)
            return
        
        # !редмодель
        if text.lower().startswith("!редмодель "):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Только шестёрки и пахан!")
                return
            parts = text[10:].strip().split()
            if len(parts) < 2:
                send_message(peer_id, "⚠️ Использование: !редмодель [ало|вывод|обоснуй|слыш] [deepseek|gemini]")
                return
            command = parts[0].lower()
            model_type = parts[1].lower()
            models_map = {
                "deepseek": "deepseek/deepseek-chat",
                "gemini": "google/gemini-2.5-flash",
                "ds": "deepseek/deepseek-chat",
                "gm": "google/gemini-2.5-flash"
            }
            if model_type not in models_map:
                send_message(peer_id, f"⚠️ Неизвестная модель: {model_type}\nДоступные: deepseek, gemini")
                return
            command_map = {"ало": "alo", "вывод": "sudi", "обоснуй": "obosnuy", "слыш": "slysh"}
            if command not in command_map:
                send_message(peer_id, f"⚠️ Неизвестная команда: {command}\nДоступные: ало, вывод, обоснуй, слыш")
                return
            cmd_key = command_map[command]
            new_model = models_map[model_type]
            if set_model(cmd_key, new_model):
                model_name = "DeepSeek" if "deepseek" in new_model else "Gemini"
                send_message(peer_id, f"👹 Модель для !{command} изменена на {model_name}")
                print(f"Админ {get_user_name(from_id)} сменил модель для !{command} на {model_name}")
            else:
                send_message(peer_id, "❌ Не удалось сменить модель")
            return
        
        # !модели
        if text.lower() == "!модели":
            if get_user_rank(from_id) < 1:
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            models_text = "Текущие модели:\n"
            models_text += f"!ало: {'DeepSeek' if 'deepseek' in current_models['alo'] else 'Gemini'}\n"
            models_text += f"!вывод: {'DeepSeek' if 'deepseek' in current_models['sudi'] else 'Gemini'}\n"
            models_text += f"!обоснуй: {'DeepSeek' if 'deepseek' in current_models['obosnuy'] else 'Gemini'}\n"
            models_text += f"!слыш: {'DeepSeek' if 'deepseek' in current_models.get('slysh', 'deepseek/deepseek-chat') else 'Gemini'}"
            send_message(peer_id, models_text)
            return
        
        # !нах
        if text.lower().startswith("!нах"):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!")
                return
            reason_text = text[4:].strip()
            target_id = get_user_id_from_mention_or_reply(reason_text, msg, peer_id)
            if not target_id:
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    target_id = reply_msg.get("from_id")
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!нах @username причина\n!нах (ответом на сообщение) причина\n!нах vk.com/id123 причина")
                return
            clean_reason = re.sub(r'\[id\d+\|[^\]]+\]\s*', '', reason_text)
            clean_reason = re.sub(r'vk\.com/id\d+\s*', '', clean_reason)
            clean_reason = re.sub(r'https://vk\.com/id\d+\s*', '', clean_reason)
            clean_reason = clean_reason.strip()
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя забанить бота! ебанулся!!")
                return
            if get_user_rank(target_id) >= get_user_rank(from_id):
                send_message(peer_id, "❌ Нельзя забанить админа! ахуел!!!")
                return
            admin_name = get_user_name(from_id)
            user_name = get_user_name(target_id)
            if ban_user(peer_id, target_id, clean_reason, admin_name):
                if clean_reason:
                    send_message(peer_id, f"{user_name} вылетел(а) нахуй из чата по команде {admin_name}\n📝 Причина: {clean_reason}")
                else:
                    send_message(peer_id, f"{user_name} вылетел(а) нахуй из чата по команде {admin_name}")
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    delete_message(peer_id, reply_msg.get("conversation_message_id"))
            else:
                send_message(peer_id, "⚠️ Не удалось забанить, сори. У меня точно админка?")
            return
        
        # !разбан
        if text.lower().startswith("!разбан"):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!")
                return
            search_text = text[7:].strip()
            target_id = get_user_id_from_mention_or_reply(search_text, msg, peer_id)
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!разбан @username\nили ответь на сообщение")
                return
            if peer_id not in banned_users or target_id not in banned_users[peer_id]:
                send_message(peer_id, f"⚠️ {get_user_name(target_id)} точно забанен?")
                return
            ban_info = banned_users[peer_id].pop(target_id)
            save_bans()
            admin_name = get_user_name(from_id)
            user_name = get_user_name(target_id)
            reason = ban_info.get("reason", "")
            if reason:
                send_message(peer_id, f"👹 {user_name} разбанен(а)!\n📝 Был забанен(а) по причине: {reason}\n👑 Разбанен(а) администратором: {admin_name}")
            else:
                send_message(peer_id, f"👹 {user_name} разбанен(а)!\n👑 Разбанен(а) администратором: {admin_name}")
            reply_msg = msg.get("reply_message")
            if reply_msg:
                delete_message(peer_id, reply_msg.get("conversation_message_id"))
            return
        
        # !мут
        if text.lower().startswith("!мут"):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            rest = text[4:].strip()
            parts = rest.split()
            duration = 0
            if parts and parts[0].isdigit():
                duration = int(parts[0])
                search_text = ' '.join(parts[1:])
            else:
                search_text = rest
            target_id = get_user_id_from_mention_or_reply(search_text, msg, peer_id)
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!мут (ответом на сообщение)\n!мут 5 @username\n!мут 5 [id123|Имя]")
                return
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя замутить бота! ебанулся!!")
                return
            if get_user_rank(target_id) >= get_user_rank(from_id):
                send_message(peer_id, "❌ Нельзя бля!!")
                return
            success, dur = mute_user(peer_id, target_id, duration)
            if success:
                if dur:
                    send_message(peer_id, f"🔇 {get_user_name(target_id)} на муте {dur} минут(ы)")
                else:
                    send_message(peer_id, f"🔇 {get_user_name(target_id)} в муте нахуй")
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    delete_message(peer_id, reply_msg.get("conversation_message_id"))
            return
        
        # !базарь
        if text.lower().startswith("!базарь"):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            search_text = text[7:].strip()
            target_id = get_user_id_from_mention_or_reply(search_text, msg, peer_id)
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!базарь (ответом на сообщение)\n!базарь @username")
                return
            if unmute_user(peer_id, target_id):
                send_message(peer_id, f"🔊 {get_user_name(target_id)} можешь базарить")
            else:
                send_message(peer_id, "⚠️ Он не в муте")
            return
        
        # !муты
        if text.lower() in ["!муты", "!списокмутов"]:
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            if peer_id not in muted_users or not muted_users[peer_id]:
                send_message(peer_id, "Паходу никто не хулиганил")
                return
            result = []
            current_time = time.time()
            for user_id, until in muted_users[peer_id].items():
                user_name = get_user_name(user_id)
                if until == float('inf'):
                    time_left = "навсегда"
                elif current_time < until:
                    minutes_left = int((until - current_time) / 60)
                    seconds_left = int((until - current_time) % 60)
                    if minutes_left > 0:
                        time_left = f"{minutes_left} мин {seconds_left} сек"
                    else:
                        time_left = f"{seconds_left} сек"
                else:
                    continue
                result.append(f"🔇 {user_name} — {time_left}")
            if result:
                result_text = "📋 Список хулиганов:\n" + "\n".join(result)
                send_message(peer_id, result_text)
            else:
                send_message(peer_id, "Никто не хулиганил")
            return
        
        # !короновать
        if text.lower().startswith("!короновать "):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "⚠️ Только пахан может короновать!")
                return
            rest = text[12:].strip()
            target_id = get_user_id_from_mention_or_reply(rest, msg, peer_id)
            if not target_id:
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    target_id = reply_msg.get("from_id")
                    numbers = re.findall(r'\d+', rest)
                    if numbers:
                        new_rank = int(numbers[-1])
                    else:
                        send_message(peer_id, "⚠️ Укажи ранг: 1 или 2")
                        return
                else:
                    send_message(peer_id, "❌ Использование:\n!короновать @username 2\nили ответь на сообщение с указанием ранга")
                    return
            else:
                clean_rest = re.sub(r'\[id\d+\|[^\]]+\]', '', rest).strip()
                clean_rest = re.sub(r'vk\.com/id\d+', '', clean_rest).strip()
                numbers = re.findall(r'\d+', clean_rest)
                if numbers:
                    new_rank = int(numbers[0])
                else:
                    send_message(peer_id, "⚠️ Укажи ранг: 1 или 2")
                    return
            if new_rank not in [1, 2]:
                send_message(peer_id, "⚠️ Ранг должен быть 1 (басота) или 2 (шестерка)")
                return
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя давать ранги боту! ебанулся!!")
                return
            if target_id == config.OWNER_ID:
                send_message(peer_id, "❌ Нельзя пахану ранг менять!!")
                return
            rank_names = {1: "басота", 2: "шестерка"}
            if set_user_rank(target_id, new_rank):
                send_message(peer_id, f"👹 {get_user_name(target_id)} теперь {rank_names[new_rank]}!")
            else:
                send_message(peer_id, "❌ Не удалось выдать ранг")
            return
        
        # !снять
        if text.lower().startswith("!снять"):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "⚠️ Только пахан может снимать ранги!")
                return
            search_text = text[6:].strip()
            target_id = get_user_id_from_mention_or_reply(search_text, msg, peer_id)
            if not target_id:
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    target_id = reply_msg.get("from_id")
                else:
                    send_message(peer_id, "❌ Использование:\n!снять @username\nили ответь на сообщение")
                    return
            if target_id == config.OWNER_ID:
                send_message(peer_id, "❌ Да пососи, нельзя раскороновать пахана!!")
                return
            if remove_user_rank(target_id):
                send_message(peer_id, f"{get_user_name(target_id)} теперь непись")
            else:
                send_message(peer_id, "⚠️ У этого пользователя и так нет ранга")
            return
        
        # !мат слово
        if text.lower().startswith("!мат "):
            if not can_use_command(from_id, "!мат"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            new_word = text[len("!мат "):].strip().lower()
            
            if new_word and new_word not in get_bad_words():
                current_words = get_bad_words()
                current_words.append(new_word)
                save_bad_words(current_words)  # 👈 сохраняем ВЕСЬ список
                print(f"✅ Слово '{new_word}' добавлено. Новый список: {get_bad_words()}")
                send_message(peer_id, f"👹 Слово '{new_word}' добавлено")
            elif new_word in get_bad_words():
                send_message(peer_id, f"⚠️ Слово '{new_word}' уже есть")
            else:
                send_message(peer_id, f"⚠️ Некорректное слово")
            return
        
        # !удалитьмат слово
        if text.lower().startswith("!удалитьмат "):
            if not can_use_command(from_id, "!удалитьмат"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            del_word = text[len("!удалитьмат "):].strip().lower()
            
            if del_word in get_bad_words():
                current_words = get_bad_words()
                current_words.remove(del_word)
                save_bad_words(current_words)  # 👈 сохраняем ВЕСЬ список
                send_message(peer_id, f"👹 Слово '{del_word}' удалено")
            else:
                send_message(peer_id, f"⚠️ Слова '{del_word}' нет")
            return
        
        # !натемут
        if text.lower().startswith("!натемут"):
            if not can_use_command(from_id, "!натемут"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            search_text = text[9:].strip()
            target_id = get_user_id_from_mention_or_reply(search_text, msg, peer_id)
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!натемут (ответом на сообщение)\n!натемут @username\n!натемут [id123|Имя]")
                return
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя натемутить бота! ебанулся??")
                return
            if get_user_rank(target_id) >= 2:
                send_message(peer_id, "❌ Нельзя натемутить админа! ахуел!!!")
                return
            if peer_id not in trolled_users:
                trolled_users[peer_id] = []
            if target_id not in trolled_users[peer_id]:
                trolled_users[peer_id].append(target_id)
                user_name = get_user_name(target_id)
                send_message(peer_id, f"👹 {user_name} терь на темуте")
            else:
                send_message(peer_id, f"⚠️ {get_user_name(target_id)} уже на темуте")
            reply_msg = msg.get("reply_message")
            if reply_msg:
                delete_message(peer_id, reply_msg.get("conversation_message_id"))
            return
        
        # !хватит
        if text.lower().startswith("!хватит"):
            if not can_use_command(from_id, "!хватит"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            search_text = text[7:].strip()
            target_id = get_user_id_from_mention_or_reply(search_text, msg, peer_id)
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!хватит (ответом на сообщение)\n!хватит @username\n!хватит [id123|Имя]")
                return
            if peer_id in trolled_users and target_id in trolled_users[peer_id]:
                trolled_users[peer_id].remove(target_id)
                user_name = get_user_name(target_id)
                send_message(peer_id, f"👹 {user_name} может базарить")
                if not trolled_users[peer_id]:
                    del trolled_users[peer_id]
            else:
                send_message(peer_id, f"⚠️ {get_user_name(target_id)} не на темуте")
            return
        
        # !аннул
        if text.lower() == "!аннул":
            if not can_use_command(from_id, "!аннул"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            if peer_id in trolled_users:
                del trolled_users[peer_id]
                send_message(peer_id, "👹 Темутинг остановлен для всех")
            else:
                send_message(peer_id, "❌ Никого не темутили, в себя приди")
            return
        
        # !добавитьфразу
        if text.lower().startswith("!добавитьфразу "):
            if not can_use_command(from_id, "!добавитьфразу"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            new_phrase = text[len("!добавитьфразу "):].strip()
            if new_phrase:
                if add_troll_phrase(new_phrase):
                    send_message(peer_id, f"👹 Фраза добавлена: \"{new_phrase}\"")
                else:
                    send_message(peer_id, f"⚠️ Такая фраза уже есть")
            else:
                send_message(peer_id, "⚠️ Использование: !добавитьфразу текст фразы")
            return
        
        # !удалитьфразу
        if text.lower().startswith("!удалитьфразу "):
            if not can_use_command(from_id, "!удалитьфразу"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            old_phrase = text[len("!удалитьфразу "):].strip()
            if old_phrase:
                if remove_troll_phrase(old_phrase):
                    send_message(peer_id, f"👹 Фраза удалена: \"{old_phrase}\"")
                else:
                    send_message(peer_id, f"⚠️ Фраза не найдена")
            else:
                send_message(peer_id, "⚠️ Использование: !удалитьфразу текст фразы")
            return
        
        # !списокфраз
        if text.lower() == "!списокфраз":
            if not can_use_command(from_id, "!списокфраз"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            phrases = get_troll_phrases_list()
            if phrases:
                text_phrases = "📜 Список фраз для темутинга:\n"
                for i, phrase in enumerate(phrases, 1):
                    line = f"{i}. {phrase}\n"
                    if len(text_phrases + line) > 3500:
                        send_message(peer_id, text_phrases)
                        text_phrases = line
                    else:
                        text_phrases += line
                if text_phrases:
                    send_message(peer_id, text_phrases)
            else:
                send_message(peer_id, "📭 Список фраз пуст.")
            return
        
        # !дис
        if text.lower().startswith("!дис "):
            if not can_use_command(from_id, "!дис"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            parts = text[5:].strip().split()
            if len(parts) < 1:
                send_message(peer_id, "⚠️ Использование: !дис [лайк|каки|край] (ответом или @user)", reply_to=cmid)
                return
            
            reaction_type = parts[0].lower()
            if reaction_type not in config.REACTIONS_LIST:
                send_message(peer_id, f"⚠️ Нет такой реакции! Доступные: лайк, каки, край", reply_to=cmid)
                return
            
            # Пытаемся получить ID из упоминания (всё после команды)
            rest = ' '.join(parts[1:]) if len(parts) > 1 else ""
            target_id = get_user_id_from_mention_or_reply(rest, msg, peer_id)
            
            # Если не нашли по упоминанию — пробуем ответ
            if not target_id:
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    target_id = reply_msg.get("from_id")
            
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!дис лайк @user\nили ответь на сообщение", reply_to=cmid)
                return
            
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя ставить реакции на бота! в себя приди!!", reply_to=cmid)
                return
            
            start_reaction(peer_id, target_id, reaction_type)
            return
        
        # !дис- @user - убрать реакции с конкретного пользователя
        if text.lower().startswith("!дис- "):
            if not can_use_command(from_id, "!дис"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            rest = text[5:].strip()
            target_id = get_user_id_from_mention_or_reply(rest, msg, peer_id)
            
            if not target_id:
                send_message(peer_id, "❌ Использование: !дис- @user", reply_to=cmid)
                return
            
            if peer_id in user_reaction and target_id in user_reaction[peer_id]:
                del user_reaction[peer_id][target_id]
                send_message(peer_id, f"👹 Больше не ставлю реакции {get_user_name(target_id, mention=True)}", reply_to=cmid)
            else:
                send_message(peer_id, f"⚠️ На {get_user_name(target_id, mention=True)} и так нет реакций", reply_to=cmid)
            return
        
        # !стопдис
        if text.lower() == "!стопдис":
            if not can_use_command(from_id, "!стопдис"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            if stop_reaction(peer_id):
                send_message(peer_id, "👹 Реакции отключены")
            else:
                send_message(peer_id, "❌ Ни на кого не ставили реакции")
            return
        
        # !смпромт
        if text.lower().startswith("!смпромт"):
            if not can_use_command(from_id, "!смпромт"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            parts = text[8:].strip().split()
            if not parts:
                send_message(peer_id, "⚠️ Использование: !смпромт [ало|вывод|обоснуй|слыш]")
                return
            target = parts[0].lower()
            if target == "ало":
                send_message(peer_id, f"📝 Промт для !ало:\n\n{get_prompt('alo')}")
            elif target == "вывод":
                send_message(peer_id, f"📝 Промт для !вывод:\n\n{get_prompt('sudi')}")
            elif target == "обоснуй":
                send_message(peer_id, f"📝 Промт для !обоснуй:\n\n{get_prompt('obosnuy')}")
            elif target == "слыш":
                send_message(peer_id, f"📝 Промт для !слыш:\n\n{get_prompt('slysh')}")
            else:
                send_message(peer_id, "⚠️ Доступно: ало, вывод, обоснуй, слыш")
            return
        
        # !редпромт
        if text.lower().startswith("!редпромт "):
            if not can_use_command(from_id, "!редпромт"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            parts = text[10:].strip().split(maxsplit=1)
            if len(parts) < 2:
                send_message(peer_id, "⚠️ Использование: !редпромт [ало|вывод|обоснуй|слыш] [новый промт]")
                return
            target = parts[0].lower()
            new_prompt = parts[1].strip()
            if len(new_prompt) < 10:
                send_message(peer_id, "⚠️ Промт слишком короткий (минимум 10 символов)")
                return
            if target == "ало":
                set_prompt("alo", new_prompt)
                send_message(peer_id, "👹 Промт для !ало изменён!")
            elif target == "вывод":
                set_prompt("sudi", new_prompt)
                send_message(peer_id, "👹 Промт для !вывод изменён!")
            elif target == "обоснуй":
                set_prompt("obosnuy", new_prompt)
                send_message(peer_id, "👹 Промт для !обоснуй изменён!")
            elif target == "слыш":
                set_prompt("slysh", new_prompt)
                send_message(peer_id, "👹 Промт для !слыш изменён!")
            else:
                send_message(peer_id, "⚠️ Доступно: ало, вывод, обоснуй, слыш")
            return
        
        # !сброситьпромт
        if text.lower().startswith("!сброситьпромт"):
            if not can_use_command(from_id, "!сброситьпромт"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            parts = text[15:].strip().split()
            if not parts:
                send_message(peer_id, "⚠️ Использование: !сброситьпромт [ало|вывод|обоснуй|слыш]")
                return
            target = parts[0].lower()
            if target == "ало":
                set_prompt("alo", config.DEFAULT_ALO_PROMPT)
                send_message(peer_id, "👹 Промт для !ало сброшен")
            elif target == "вывод":
                set_prompt("sudi", config.DEFAULT_SUDI_PROMPT)
                send_message(peer_id, "👹 Промт для !вывод сброшен")
            elif target == "обоснуй":
                set_prompt("obosnuy", config.DEFAULT_OBOSNUY_PROMPT)
                send_message(peer_id, "👹 Промт для !обоснуй сброшен")
            elif target == "слыш":
                set_prompt("slysh", config.DEFAULT_SLYSH_PROMPT)
                send_message(peer_id, "👹 Промт для !слыш сброшен")
            else:
                send_message(peer_id, "⚠️ Доступно: ало, вывод, обоснуй, слыш")
            return
        
        # !помощь
        if text.lower() == "!помощь":
            if not can_use_command(from_id, "!помощь"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            help_text = """📖 Команды бота

Модерация:
!мат слово - добавить слово в чёрный список
!удалитьмат слово - удалить слово из чёрного списка
!мут [N] - замутить (ответом/упоминанием, N - минуты)
!базарь - снять мут (ответом/упоминанием)
!муты - список замьюченных
!нах [причина] - забанить (ответом/упоминанием)
!разбан - разбанить (ответом/упоминанием)

Темутинг:
!натемут - начать темутить (ответом/упоминанием)
!хватит - остановить темутить (ответом/упоминанием)
!аннул - остановить темутинг для всех

Фразы для темутинга:
!добавитьфразу "текст" - добавить фразу
!удалитьфразу "текст" - удалить фразу
!списокфраз - показать все фразы

Реакции:
!дис [лайк|каки|край] - ставить реакцию (ответом/упоминанием)
!стопдис - остановить реакции

AI команды:
!ало вопрос - задать вопрос (Gemini/DeepSeek)
!вывод - анализ чата
!обоснуй - анализ картинки
!слыш - общение с ботом

Управление моделями:
!редмодель [ало|вывод|обоснуй] [deepseek|gemini|ds|gm]
!модели - показать текущие модели

Управление промтами:
!смпромт [ало|вывод|обоснуй] - посмотреть промт
!редпромт [ало|вывод|обоснуй] "новый промт" - изменить промт
!сброситьпромт [ало|вывод|обоснуй] - сбросить до стандартного

Для всех:
!вкл - включить цензуру (бот будет удалять твой мат)
!выкл - выключить цензуру
!бот - статистика бота
!помощь - это сообщение"""
            send_message(peer_id, help_text)
            return
    
    # ==========================================
    # КОНТРОЛЬ ССЫЛОК
    # ==========================================
    if not links_enabled and text and contains_link(text):
        if get_user_rank(from_id) < 2:
            success, dur = mute_user(peer_id, from_id, 5)
            if success:
                send_message(peer_id, f"🔇 {get_user_name(from_id, mention=True)} онлирид на 5 минут за ссылки нахуй!")
                delete_message(peer_id, cmid)
                print(f"🔗 Мут за ссылку: {get_user_name(from_id, mention=False)}")
            else:
                delete_message(peer_id, cmid)
                send_message(peer_id, f"⚠️ Не удалось замутить {get_user_name(from_id, mention=True)} за ссылку, сообщение удалено")
            return
    
    # ==========================================
    # АГИТАЦИЯ ЗА ЦЕНЗУРУ
    # ==========================================
    if agitation_enabled and contains_bad_words(text) and not is_user_censored_global(from_id):
        if not has_been_agitated(from_id):
            mark_agitated(from_id)
            from vk_utils import build_keyboard
            user_mention = get_user_name(from_id, mention=True)
            
            # Inline-клавиатура с одной кнопкой
            rows = [
                [("👹 Я буду грубить в интернете!", "!вкл", "negative")],
            ]
            keyboard = build_keyboard(rows, one_time=False, inline=True)
            
            send_message(
                peer_id,
                f"{user_mention}, ты так мило матюкаешься ;3 В целях предотвращения блокировок и страйков от обиженных хуесосов нажми кнопку ниже или напиши !вкл:",
                reply_to=cmid,
                keyboard=keyboard
            )
            print(f"📢 Отправлена агитация пользователю {get_user_name(from_id, mention=False)}")
    
    # ==========================================
    # ПРОВЕРКА МАТА (ЦЕНЗУРА)
    # ==========================================
    print(f"🔍 Проверка мата: '{text}', ценз добр={is_user_censored(from_id)}, прин={is_forced_censored(from_id)}")
    if not contains_bad_words(text):
        print("🟢 Мата нет")
        return

    if not is_user_censored_global(from_id):
        print("🟡 Пользователь не под цензурой")
        return

    # Получаем имя для отображения (никнейм или настоящее имя)
    display_name = get_display_name(from_id)
    # Делаем его кликабельным без упоминания
    clickable_name = f"[id{from_id}|{display_name}]"

    print(f"Найден мат от {display_name} (включена цензура)")

    reply_to_cmid = None
    reply_msg = msg.get("reply_message")
    if reply_msg:
        reply_to_cmid = reply_msg.get("conversation_message_id")

    attachment_string = build_attachment_string(msg.get("attachments", []))
    bot_text = f"{clickable_name}: {text}"

    try:
        send_message(peer_id, bot_text, attachment_string, reply_to_cmid, disable_mentions=True)
        print("Сообщение отправлено с репли")
    except Exception as e:
        print(f"SEND ERROR: {e}")
        return

    time.sleep(config.DELETE_DELAY)
    delete_message(peer_id, cmid)
   
__all__ = [
    'handle_message',
    'load_ranks', 'load_bans', 'load_censored_users',
    'load_models', 'load_slysh_state',
    'load_greeting_state', 'load_greeting_text',
    'load_rules_state', 'load_rules_text',
    'load_nicknames_state', 'load_nicknames',
    'load_agitation_state', 'load_access',
    'load_links_state', 'load_antispam_state',
    'load_inactivity_data',
    'is_user_banned', 'get_user_name', 'greeting_enabled',
    'get_greeting', 'send_message'
]