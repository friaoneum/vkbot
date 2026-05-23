import vk_api
import random
import time
import os
import json
import threading
import requests
import re
from collections import deque
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

import config

# =====================================================
# СИСТЕМА ВЫБОРОЧНОЙ ЦЕНЗУРЫ (по желанию участника)
# =====================================================

censored_users = set()  # {user_id1, user_id2, ...}

def load_censored_users():
    """Загружает список участников, включивших цензуру"""
    global censored_users
    if os.path.exists(config.CENSORED_USERS_FILE):
        try:
            with open(config.CENSORED_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                censored_users = set(data.get("users", []))
            print(f"🔇 Загружено участников под цензурой: {len(censored_users)}")
        except:
            censored_users = set()
    else:
        censored_users = set()
        save_censored_users()

def save_censored_users():
    """Сохраняет список участников, включивших цензуру"""
    with open(config.CENSORED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": list(censored_users)}, f, ensure_ascii=False, indent=2)

def add_censored_user(user_id):
    """Добавляет участника в список (включает цензуру)"""
    if user_id not in censored_users:
        censored_users.add(user_id)
        save_censored_users()
        return True
    return False

def remove_censored_user(user_id):
    """Удаляет участника из списка (отключает цензуру)"""
    if user_id in censored_users:
        censored_users.remove(user_id)
        save_censored_users()
        return True
    return False

def is_user_censored(user_id):
    """Проверяет, включена ли цензура для участника"""
    return user_id in censored_users

# =====================================================
# СИСТЕМА БАНОВ
# =====================================================

banned_users = {}  # {peer_id: {user_id: {"reason": "причина", "banned_by": "кто", "time": timestamp}}}

def load_bans():
    """Загружает баны из файла"""
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
    """Сохраняет баны в файл"""
    with open(config.BANS_FILE, "w", encoding="utf-8") as f:
        json.dump(banned_users, f, ensure_ascii=False, indent=2)

def ban_user(peer_id, user_id, reason="", banned_by=None):
    """Банит пользователя (исключает из беседы)"""
    try:
        # Исключаем из чата
        chat_id = peer_id - 2000000000
        vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
        
        # Сохраняем информацию о бане
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
    """Проверяет, забанен ли пользователь (но бот не может это проверить, так как его нет в чате)"""
    if peer_id in banned_users and user_id in banned_users[peer_id]:
        return True
    return False

# =====================================================
# СИСТЕМА МУТА (удаление сообщений)
# =====================================================

muted_users = {}  # {peer_id: {user_id: until_timestamp}}

def mute_user(peer_id, user_id, duration_minutes=0):
    """Заглушить пользователя"""
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
    """Снять мут с пользователя"""
    if peer_id in muted_users and user_id in muted_users[peer_id]:
        del muted_users[peer_id][user_id]
        return True
    return False

def is_user_muted(peer_id, user_id):
    """Проверяет, замьючен ли пользователь"""
    if peer_id in muted_users and user_id in muted_users[peer_id]:
        until = muted_users[peer_id][user_id]
        if until == float('inf') or time.time() < until:
            return True
        else:
            # Срок истёк, удаляем запись
            del muted_users[peer_id][user_id]
    return False

def get_user_id_from_mention_or_reply(text, msg, peer_id):
    """Извлекает ID пользователя из упоминания или ответа"""
    
    # Способ 1: ответ на сообщение
    reply_msg = msg.get("reply_message")
    if reply_msg:
        return reply_msg.get("from_id")
    
    # Способ 2: упоминание [id123|Имя]
    mention_match = re.search(r'\[id(\d+)\|', text)
    if mention_match:
        return int(mention_match.group(1))
    
    # Способ 3: ссылка vk.com/id123
    link_match = re.search(r'vk\.com/id(\d+)', text)
    if link_match:
        return int(link_match.group(1))
    
    return None
    
# =====================================================
# ЗАГРУЗКА МАТОВ
# =====================================================

def load_bad_words():
    if os.path.exists(config.BAD_WORDS_FILE):
        with open(config.BAD_WORDS_FILE, "r", encoding="utf-8") as f:
            words = [
                line.strip().lower()
                for line in f
                if line.strip()
            ]
            if words:
                return words
    return ["хуй", "пизда", "блять", "сука"]

def save_bad_words(words):
    with open(config.BAD_WORDS_FILE, "w", encoding="utf-8") as f:
        for word in words:
            f.write(word + "\n")

BAD_WORDS = load_bad_words()
print(f"Загружено матов: {len(BAD_WORDS)}")

# =====================================================
# СИСТЕМА РАНГОВ (1 - басота, 2 - шестерка, 3 - постоянный)
# =====================================================

user_ranks = {}  # {user_id: rank}

def load_ranks():
    """Загружает ранги из файла"""
    global user_ranks
    if os.path.exists(config.RANKS_FILE):
        try:
            with open(config.RANKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Преобразуем ключи в int
            fixed = {}
            for k, v in data.items():
                try:
                    fixed[int(k)] = v
                except:
                    fixed[k] = v
            user_ranks = fixed
            print(f"📊 Загружено рангов: {len(user_ranks)}")
        except Exception as e:
            print(f"❌ Ошибка загрузки рангов: {e}")
            user_ranks = {}
    else:
        print(f"📭 Файл {config.RANKS_FILE} не найден")
        user_ranks = {}
        save_ranks()

def save_ranks():
    """Сохраняет ранги в файл"""
    global user_ranks
    try:
        with open(config.RANKS_FILE, "w", encoding="utf-8") as f:
            json.dump(user_ranks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения рангов: {e}")

def get_user_rank(user_id):
    """Возвращает ранг пользователя: 3, 2, 1 или 0"""
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
    """Проверяет, может ли пользователь выполнить команду"""
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
            "!дис", "!стопдис"
        ]
        for bc in basota_commands:
            if command.startswith(bc):
                return True
        return False
    
    return False
# =====================================================
# ФРАЗЫ ДЛЯ ТЕМУТИНГА
# =====================================================

def load_phrases():
    phrases = []
    if os.path.exists(config.PHRASES_FILE):
        with open(config.PHRASES_FILE, "r", encoding="utf-8") as f:
            phrases = [line.strip() for line in f if line.strip()]
    if not phrases:
        phrases = [
            "Я лох",
            "Я ничего не понимаю в этой жизни",
            "Извините, я тупой",
            "У меня IQ комнатной температуры",
            "Я согласен с тем, что я даун",
            "Мам, забери меня отсюда",
            "Кто я? Зачем я здесь?",
            "Я бот, а вы даже не заметили",
            "Сосите, я вас всех переиграл",
            "Кек"
        ]
        save_phrases(phrases)
    return phrases

def save_phrases(phrases):
    with open(config.PHRASES_FILE, "w", encoding="utf-8") as f:
        for phrase in phrases:
            f.write(phrase + "\n")

TROLL_PHRASES = load_phrases()
print(f"📝 Загружено фраз для троллинга: {len(TROLL_PHRASES)}")

# =====================================================
# СИСТЕМА ТЕМУТИНГА
# =====================================================

trolled_users = {}  # {peer_id: [target_id1, target_id2, ...]

def start_troll(peer_id, target_id, replied_cmid=None):
    """Начинает темутить пользователя (добавляет в список)"""
    if peer_id not in trolled_users:
        trolled_users[peer_id] = []
    
    if target_id not in trolled_users[peer_id]:
        trolled_users[peer_id].append(target_id)
        user_name = get_user_name(target_id)
        send_message(peer_id, f"✅ {user_name} терь на темуте")
    
    if replied_cmid:
        try:
            delete_message(peer_id, replied_cmid)
        except:
            pass

def stop_troll(peer_id, target_id=None):
    """Останавливает темутинг для пользователя или всех"""
    if peer_id not in trolled_users:
        return False
    
    if target_id:
        # Удаляем конкретного пользователя
        if target_id in trolled_users[peer_id]:
            trolled_users[peer_id].remove(target_id)
            user_name = get_user_name(target_id)
            send_message(peer_id, f"✅ {user_name} может базарить")
            
            # Если список стал пустым — удаляем ключ
            if not trolled_users[peer_id]:
                del trolled_users[peer_id]
            return True
    else:
        # Удаляем всех
        del trolled_users[peer_id]
        send_message(peer_id, f"✅ Темутинг отключен для всех")
        return True
    
    return False

def is_user_trolled(peer_id, user_id):
    """Проверяет, нужно ли темутить пользователя"""
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

# =====================================================
# СИСТЕМА РЕАКЦИЙ
# =====================================================

user_reaction = {}

REACTION_IDS = {
    "лайк": 1,
    "каки": 5,
    "край": 7
}

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
    user_reaction[peer_id] = {"target_id": target_id, "reaction": reaction_type}
    user_name = get_user_name(target_id)
    reaction_emoji = get_reaction_emoji(reaction_type)
    send_message(peer_id, f"Терь буду ставить {reaction_emoji} под каждым сообщением {user_name}")

def stop_reaction(peer_id):
    if peer_id in user_reaction:
        user_name = get_user_name(user_reaction[peer_id]["target_id"])
        del user_reaction[peer_id]
        send_message(peer_id, f"✅ Больше не ставлю реакции {user_name}")
        return True
    return False

def is_user_has_reaction(peer_id, user_id):
    if peer_id in user_reaction:
        return user_reaction[peer_id]["target_id"] == user_id
    return False

def get_user_reaction(peer_id):
    if peer_id in user_reaction:
        return user_reaction[peer_id]["reaction"]
    return None
    
# =====================================================
# СИСТЕМА ПРОМТОВ
# =====================================================
print(f"🔍 Проверка config: {hasattr(config, 'DEFAULT_OBOSNUY_PROMPT')}")

def load_prompts():
    default_prompts = {"alo": config.DEFAULT_ALO_PROMPT, "sudi": config.DEFAULT_SUDI_PROMPT, "obosnuy": config.DEFAULT_OBOSNUY_PROMPT}
    if os.path.exists(config.PROMPTS_FILE):
        with open(config.PROMPTS_FILE, "r", encoding="utf-8") as f:
            try:
                prompts = json.load(f)
                for key in default_prompts:
                    if key not in prompts:
                        prompts[key] = default_prompts[key]
                return prompts
            except:
                return default_prompts
    return default_prompts

def save_prompts(prompts):
    with open(config.PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)

PROMPTS = load_prompts()

def get_prompt(command):
    return PROMPTS.get(command, PROMPTS.get("alo", "Ты помощник."))

def set_prompt(command, new_prompt):
    PROMPTS[command] = new_prompt
    save_prompts(PROMPTS)
    return True

# =====================================================
# DEEPSEEK ЧЕРЕЗ OPENROUTER
# =====================================================

def ask_deepseek(question, prompt_type="alo"):
    try:
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        system_prompt = get_prompt(prompt_type)
        data = {
            "model": "google/gemini-3.1-flash-lite-preview",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
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

# =====================================================
# VK INIT
# =====================================================

vk_session = vk_api.VkApi(token=config.GROUP_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, config.GROUP_ID)
BOT_ID = -config.GROUP_ID

# =====================================================
# ХРАНИЛИЩЕ СООБЩЕНИЙ ДЛЯ АНАЛИЗА
# =====================================================

message_history = deque(maxlen=config.MESSAGE_HISTORY_MAXLEN)

# =====================================================
# ИМЯ ПОЛЬЗОВАТЕЛЯ
# =====================================================

user_name_cache = {}
# Кэш для списка админов
admins_cache = {}
ADMINS_CACHE_TTL = 300 #5 minut

def get_user_name(user_id):
    current_time = time.time()
    if user_id in user_name_cache:
        name, cache_time = user_name_cache[user_id]
        if current_time - cache_time < config.CACHE_TIME:
            return name
    
    try:
        user = vk.users.get(user_ids=user_id)[0]
        name = f"{user['first_name']} {user['last_name']}"
        user_name_cache[user_id] = (name, current_time)
        return name
    except:
        return "Unknown"

# =====================================================
# ОТПРАВКА СООБЩЕНИЯ
# =====================================================

def send_message(peer_id, text, attachment=None, reply_to=None):
    params = {
        "peer_id": peer_id,
        "message": text,
        "random_id": random.randint(1, 999999999)
    }
    if attachment:
        params["attachment"] = attachment
    if reply_to:
        try:
            forward = {
                "peer_id": peer_id,
                "conversation_message_ids": [reply_to],
                "is_reply": True
            }
            params["forward"] = json.dumps(forward, ensure_ascii=False)
        except:
            pass
    return vk.messages.send(**params)

# =====================================================
# УДАЛЕНИЕ СООБЩЕНИЯ
# =====================================================

def delete_message(peer_id, cmid):
    try:
        vk.messages.delete(peer_id=peer_id, cmids=[cmid], delete_for_all=1)
        print(f"Удалено сообщение cmid={cmid}")
    except Exception as e:
        print(f"Ошибка удаления: {e}")

# =====================================================
# ПРОВЕРКА НА МАТ
# =====================================================

def contains_bad_words(text):
    if not text:
        return False
    text = text.lower()
    for word in BAD_WORDS:
        if word in text:
            return True
    return False

# =====================================================
# ОБРАБОТКА ВЛОЖЕНИЙ
# =====================================================

def build_attachment_string(attachments):
    result = []
    for att in attachments:
        try:
            att_type = att["type"]
            obj = att[att_type]
            owner_id = obj.get("owner_id")
            media_id = obj.get("id")
            if owner_id is None or media_id is None:
                continue
            attachment = f"{att_type}{owner_id}_{media_id}"
            access_key = obj.get("access_key")
            if access_key:
                attachment += f"_{access_key}"
            result.append(attachment)
        except:
            pass
    return ",".join(result)

# =====================================================
# АНАЛИЗ ЧАТА
# =====================================================

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
            "model": "google/gemini-3.1-flash-lite-preview",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
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

# =====================================================
# ОСНОВНОЙ ОБРАБОТЧИК
# =====================================================

def handle_message(msg):
    global message_history
    
    peer_id = msg.get("peer_id")
    from_id = msg.get("from_id")
    
    if peer_id < 2000000000 or from_id == BOT_ID:
        return
    
    text = msg.get("text", "")
    cmid = msg.get("conversation_message_id")
    
    print(f"\n==============================\nСообщение: {text}")
    
    # ==========================================
    # ПРОВЕРКА НА МУТ (удаляем все сообщения)
    # ==========================================
    if is_user_muted(peer_id, from_id):
        delete_message(peer_id, cmid)
        print(f"🔇 Удалено сообщение от замьюченного {get_user_name(from_id)}")
        return
    
    # ==========================================
    # ПРОВЕРКА НА РЕАКЦИИ
    # ==========================================
    if is_user_has_reaction(peer_id, from_id):
        if not text.startswith("!"):
            add_reaction(peer_id, cmid, get_user_reaction(peer_id))
    
    # ==========================================
    # ПРОВЕРКА НА ТЕМУТИНГ
    # ==========================================
    if is_user_trolled(peer_id, from_id):
        print(f"{from_id} терь на темуте")
        
        user_name = get_user_name(from_id)
        fake_message = get_random_phrase()
        bot_text = f"{user_name}: {fake_message}"
        
        message_history.append({
            "user_id": from_id,
            "user_name": user_name,
            "text": fake_message,
            "time": time.time()
        })
        
        attachment_string = build_attachment_string(msg.get("attachments", []))
        reply_to = msg.get("reply_message", {}).get("conversation_message_id") if msg.get("reply_message") else None
        
        try:
            send_message(peer_id, bot_text, attachment_string, reply_to)
            print(f"✅ Отправлена фейковая фраза: {fake_message}")
        except Exception as e:
            print(f"Ошибка отправки фейка: {e}")
        
        try:
            delete_message(peer_id, cmid)
            print(f"🗑 Реальное сообщение удалено")
        except Exception as e:
            print(f"Ошибка удаления: {e}")
        return
    
    # ==========================================
    # СОХРАНЯЕМ СООБЩЕНИЕ В ИСТОРИЮ
    # ==========================================
    if text and not text.startswith("!"):
        message_history.append({
            "user_id": from_id,
            "user_name": get_user_name(from_id),
            "text": text,
            "time": time.time()
        })
        print(f"💾 Сохранено в историю. Всего: {len(message_history)}")
        
    # ==========================================
    # ТРИГГЕРЫ НА ФРАЗЫ (доступны всем)
    # ==========================================
    
    text_lower = text.lower()
    
    if text_lower in ["кто админы", "кто админ", "а судьи кто", "админы", "админ"]:
        current_time = time.time()
        
        if peer_id in admins_cache:
            cached_data, cache_time = admins_cache[peer_id]
            if current_time - cache_time < ADMINS_CACHE_TTL:
                if cached_data:
                    send_message(peer_id, "\n".join(cached_data))
                else:
                    send_message(peer_id, "Нет админов, первым буш?")
                return
        
        # Собираем всех админов
        sixers = []
        basota = []
        owner = None
        specials = []
        
        try:
            members = vk.messages.getConversationMembers(peer_id=peer_id)
            for member in members['items']:
                member_id = member['member_id']
                if member_id > 0:
                    rank = get_user_rank(member_id)
                    user_name = get_user_name(member_id)
                    
                    # Проверяем, есть ли особая роль
                    if member_id in config.SPECIAL_ROLES:
                        special_role = config.SPECIAL_ROLES[member_id]
                        specials.append(f"{special_role} {user_name}")
                    elif rank == 3:
                        owner = user_name
                    elif rank == 2:
                        sixers.append(user_name)
                    elif rank == 1:
                        basota.append(user_name)
        except Exception as e:
            print(f"Ошибка получения участников: {e}")
            send_message(peer_id, "❌ Не могу получить список админов, сори")
            return
        
        # Формируем ответ
        final_result = []
        
        if owner:
            final_result.append(f"👑 Пахан: {owner}")
        if specials:
            final_result.extend(specials)
        if sixers:
            final_result.append(f"⭐ Шестёрки: {', '.join(sixers)}")
        if basota:
            final_result.append(f"💩 Басота: {', '.join(basota)}")
        
        if not final_result:
            final_result = ["Нет админов, первым буш??"]
        
        admins_cache[peer_id] = (final_result, current_time)
        send_message(peer_id, "\n".join(final_result))
        return
        
    # ==========================================
    # ПУБЛИЧНЫЕ КОМАНДЫ (доступны всем)
    # ==========================================
    
    # !цензура - включить цензуру для себя
    if text.lower() == "!цензура":
        if is_user_censored(from_id):
            send_message(peer_id, f"⚠️ {get_user_name(from_id)}, ты уже на карандаше")
        else:
            add_censored_user(from_id)
            send_message(peer_id, f"{get_user_name(from_id)}, можешь базарить смело")
        return
    
    # !откл - отключить цензуру для себя
    if text.lower() == "!откл":
        if not is_user_censored(from_id):
            send_message(peer_id, f"⚠️ {get_user_name(from_id)}, я тя и так не слушаю")
        else:
            remove_censored_user(from_id)
            send_message(peer_id, f"{get_user_name(from_id)}, зря, щя обиженные хуисосы тебе страйков накинут")
        return
    
    # !бот - статистика бота
    if text.lower() == "!бот":
        # Время работы (используем уже импортированный time)
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
        
        # Пинг до ВК
        vk_ping = "..."
        try:
            start = time.time()
            vk.account.getInfo()
            vk_ping = int((time.time() - start) * 1000)
        except:
            vk_ping = "❌"
        
        # Пинг до OpenRouter
        or_ping = "..."
        try:
            start = time.time()
            requests.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"}, timeout=5)
            or_ping = int((time.time() - start) * 1000)
        except:
            or_ping = "❌"
        
        stats_text = f"""⏱ Время работы: {uptime_str}
📡 VK API: {vk_ping} мс
🌐 OpenRouter: {or_ping} мс
📚 Матюков: {len(BAD_WORDS)}"""
        
        send_message(peer_id, stats_text)
        return
    
    # ==========================================
    # КОМАНДЫ АДМИНОВ (с проверкой рангов)
    # ==========================================
    #print(f"🔍 ДИАГНОСТИКА: from_id={from_id}, rank={get_user_rank(from_id)}") // разкомментить если понадобится ид
    if get_user_rank(from_id) >= 1:
        
        # ==========================================
        # КОМАНДА БАНА !нах
        # ==========================================
        
        if text.lower().startswith("!нах"):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав! Токо шестёрки и пахан!")
                return
            
            # Парсим причину (всё после команды)
            reason_text = text[4:].strip()
            
            # Получаем ID из ответа или упоминания
            target_id = get_user_id_from_mention_or_reply(reason_text, msg, peer_id)
            
            # Формируем причину
            reason = ""
            if target_id:
                # Убираем упоминание из текста причины
                clean_reason = re.sub(r'\[id\d+\|[^\]]+\]\s*', '', reason_text).strip()
                if clean_reason:
                    reason = clean_reason
            else:
                # Если нет упоминания, вся строка — это причина (ищем ID отдельно)
                target_id = get_user_id_from_mention_or_reply("", msg, peer_id)
                if not target_id:
                    send_message(peer_id, "❌ Использование:\n!нах (ответом на сообщение)\n!нах @username причина\n!нах причина [id123|Имя]")
                    return
                reason = reason_text
            
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя забанить бота! ебанулся!!")
                return
            
            if get_user_rank(target_id) >= get_user_rank(from_id):
                send_message(peer_id, "❌ Нельзя забанить админа! ахуел!!!")
                return
            
            admin_name = get_user_name(from_id)
            user_name = get_user_name(target_id)
            
            # Баним
            if ban_user(peer_id, target_id, reason, admin_name):
                if reason:
                    send_message(peer_id, f"{user_name} вылетел(а) нахуй из чата по команде {admin_name}\n📝 Причина: {reason}")
                else:
                    send_message(peer_id, f"{user_name} вылетел(а) нахуй из чата по команде {admin_name}")
                
                # Удаляем сообщение с командой, если это ответ
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    delete_message(peer_id, reply_msg.get("conversation_message_id"))
            else:
                send_message(peer_id, "⚠️ Не удалось забанить, сори. У меня точно админка?")
            return
            
        # ==========================================
        # КОМАНДА РАЗБАНА !разбан
        # ==========================================
        
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
                send_message(peer_id, f"✅ {user_name} разбанен(а)!\n📝 Был забанен(а) по причине: {reason}\n👑 Разбанен(а) администратором: {admin_name}")
            else:
                send_message(peer_id, f"✅ {user_name} разбанен(а)!\n👑 Разбанен(а) администратором: {admin_name}")
            
            reply_msg = msg.get("reply_message")
            if reply_msg:
                delete_message(peer_id, reply_msg.get("conversation_message_id"))
            return
        
        # ==========================================
        # КОМАНДЫ МУТА
        # ==========================================
        
        # !мут - замутить (навсегда или на N минут)
        if text.lower().startswith("!мут"):
            if get_user_rank(from_id) < 2:
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            # Парсим аргументы (например, "!мут 5" или "!мут")
            rest = text[4:].strip()
            parts = rest.split()
            duration = 0  # по умолчанию навсегда
            
            if parts and parts[0].isdigit():
                duration = int(parts[0])
                # Убираем число из строки
                search_text = ' '.join(parts[1:])
            else:
                search_text = rest
            
            # Получаем ID пользователя
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
                
                # Удаляем сообщение с командой, если это ответ
                reply_msg = msg.get("reply_message")
                if reply_msg:
                    delete_message(peer_id, reply_msg.get("conversation_message_id"))
            return
        
        # !базарь - снять мут
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
                send_message(peer_id, f"🔊 {get_user_name(target_id)} можеш базарить")
            else:
                send_message(peer_id, "⚠️ Он не в муте")
            return
            
        # ==========================================
        # КОМАНДА СПИСОК ЗАМЬЮЧЕННЫХ !муты
        # ==========================================
        
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
                    continue  # срок истёк, пропускаем
                
                result.append(f"🔇 {user_name} — {time_left}")
            
            if result:
                # Добавляем заголовок
                result_text = "📋 Список хулиганов:\n" + "\n".join(result)
                send_message(peer_id, result_text)
            else:
                send_message(peer_id, "Никто не хулиганил")
            return
       
                # !обоснуй - анализ картинки
        if text.lower().startswith("!обоснуй"):
            # Басота не может использовать
            if get_user_rank(from_id) == 1:
                send_message(peer_id, "⚠️ У тя недостаточно прав для этой команды, соплячок")
                return
            
            attachments = msg.get("attachments", [])
            if not attachments:
                send_message(peer_id, "❌ Прикрепи картинку к сообщению!")
                return
            
            # Ищем первую картинку
            image_url = None
            for att in attachments:
                if att.get("type") == "photo":
                    photo = att.get("photo", {})
                    sizes = photo.get("sizes", [])
                    if sizes:
                        # Берём самую большую картинку
                        best = max(sizes, key=lambda x: x.get("width", 0) * x.get("height", 0))
                        image_url = best.get("url")
                    break
            
            if not image_url:
                send_message(peer_id, "❌ Не удалось получить ссылку на картинку")
                return
            
            send_message(peer_id, "🤔 Анализирую картинку, падажжи...")
            
            def analyze():
                result = analyze_image_with_gemini(image_url)
                if len(result) > 3500:
                    result = result[:3500] + "..."
                send_message(peer_id, f"💬 {result}")
            
            threading.Thread(target=analyze, daemon=True).start()
            return
        # !короновать 1/2 - выдать ранг (только для создателя)
        if text.lower().startswith("!короновать "):
            if from_id != config.OWNER_ID:
                send_message(peer_id, "⚠️ Только пахан может короновать!")
                return
            
            parts = text[12:].strip().split()
            if len(parts) < 1:
                send_message(peer_id, "⚠️ Использование: !короновать [1|2] (ответом на сообщение)")
                return
            
            try:
                new_rank = int(parts[0])
            except:
                send_message(peer_id, "⚠️ Ранг должен быть 1 или 2")
                return
            
            if new_rank not in [1, 2]:
                send_message(peer_id, "⚠️ Ранг должен быть 1 (басота) или 2 (шестерка)")
                return
            
            reply_msg = msg.get("reply_message")
            if not reply_msg:
                send_message(peer_id, "❌ Команда должна быть ответом на сообщение!")
                return
            
            target_id = reply_msg.get("from_id")
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя давать ранги боту! ебанулся!!")
                return
            
            if target_id == config.OWNER_ID:
                send_message(peer_id, "❌ Нельзя пахану ранг менять!!")
                return
            
            rank_names = {1: "басота", 2: "шестерка"}
            
            if set_user_rank(target_id, new_rank):
                send_message(peer_id, f"✅ {get_user_name(target_id)} теперь {rank_names[new_rank]}!")
            else:
                send_message(peer_id, "❌ Не удалось выдать ранг")
            return
        
        # !снять - снять ранг (только для создателя)
        if text.lower() == "!снять":
            if from_id != config.OWNER_ID:
                send_message(peer_id, "⚠️ Только пахан может снимать ранги!")
                return
            
            reply_msg = msg.get("reply_message")
            if not reply_msg:
                send_message(peer_id, "❌ Команда !снять должна быть ответом на сообщение!")
                return
            
            target_id = reply_msg.get("from_id")
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
            if new_word and new_word not in BAD_WORDS:
                BAD_WORDS.append(new_word)
                save_bad_words(BAD_WORDS)
                send_message(peer_id, f"✅ Слово '{new_word}' добавлено")
            elif new_word in BAD_WORDS:
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
            if del_word in BAD_WORDS:
                BAD_WORDS.remove(del_word)
                save_bad_words(BAD_WORDS)
                send_message(peer_id, f"✅ Слово '{del_word}' удалено")
            elif del_word:
                send_message(peer_id, f"⚠️ Слова '{del_word}' нет")
            else:
                send_message(peer_id, f"⚠️ Некорректное слово")
            return
        
        # ==========================================
        # КОМАНДЫ ТЕМУТИНГА (с поддержкой ответа и упоминания)
        # ==========================================
        
        # !натемут - начать темутить
        if text.lower().startswith("!натемут"):
            if not can_use_command(from_id, "!натемут"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            # Парсим аргументы
            search_text = text[9:].strip()
            
            # Получаем ID пользователя (из ответа или упоминания)
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
            
            # Запускаем темутинг
            if peer_id not in trolled_users:
                trolled_users[peer_id] = []
            
            if target_id not in trolled_users[peer_id]:
                trolled_users[peer_id].append(target_id)
                user_name = get_user_name(target_id)
                send_message(peer_id, f"✅ {user_name} терь на темуте")
            else:
                send_message(peer_id, f"⚠️ {get_user_name(target_id)} уже на темуте")
            
            # Удаляем сообщение с командой, если это ответ
            reply_msg = msg.get("reply_message")
            if reply_msg:
                delete_message(peer_id, reply_msg.get("conversation_message_id"))
            return
        
        # !хватит - остановить темутинг для конкретного
        if text.lower().startswith("!хватит"):
            if not can_use_command(from_id, "!хватит"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            # Парсим аргументы
            search_text = text[7:].strip()
            
            # Получаем ID пользователя (из ответа или упоминания)
            target_id = get_user_id_from_mention_or_reply(search_text, msg, peer_id)
            
            if not target_id:
                send_message(peer_id, "❌ Использование:\n!хватит (ответом на сообщение)\n!хватит @username\n!хватит [id123|Имя]")
                return
            
            if peer_id in trolled_users and target_id in trolled_users[peer_id]:
                trolled_users[peer_id].remove(target_id)
                user_name = get_user_name(target_id)
                send_message(peer_id, f"✅ {user_name} может базарить")
                
                # Если список стал пустым — удаляем ключ
                if not trolled_users[peer_id]:
                    del trolled_users[peer_id]
            else:
                send_message(peer_id, f"⚠️ {get_user_name(target_id)} не на темуте")
            return
        
        # !аннул - остановить темутинг для всех
        if text.lower() == "!аннул":
            if not can_use_command(from_id, "!аннул"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            
            if peer_id in trolled_users:
                del trolled_users[peer_id]
                send_message(peer_id, "✅ Темутинг остановлен для всех")
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
                    send_message(peer_id, f"✅ Фраза добавлена: \"{new_phrase}\"")
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
                    send_message(peer_id, f"✅ Фраза удалена: \"{old_phrase}\"")
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
        
        # ==========================================
        # КОМАНДЫ РЕАКЦИЙ
        # ==========================================
        
        # !дис
        if text.lower().startswith("!дис "):
            if not can_use_command(from_id, "!дис"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            parts = text[5:].strip().split()
            if len(parts) < 1:
                send_message(peer_id, "⚠️ Использование: !дис [лайк|каки|край] (ответом на сообщение)")
                return
            
            reaction_type = parts[0].lower()
            if reaction_type not in config.REACTIONS_LIST:
                send_message(peer_id, f"⚠️ Нет такой реакции! Доступные: лайк, каки, край")
                return
            
            reply_msg = msg.get("reply_message")
            if not reply_msg:
                send_message(peer_id, "❌ Команда !дис должна быть ответом на сообщение!")
                return
            
            target_id = reply_msg.get("from_id")
            if target_id == BOT_ID:
                send_message(peer_id, "❌ Нельзя ставить реакции на бота! в себя приди!!")
                return
            
            start_reaction(peer_id, target_id, reaction_type)
            delete_message(peer_id, reply_msg.get("conversation_message_id"))
            return
        
        # !стопдис
        if text.lower() == "!стопдис":
            if not can_use_command(from_id, "!стопдис"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            if stop_reaction(peer_id):
                send_message(peer_id, "✅ Реакции отключены")
            else:
                send_message(peer_id, "❌ Ни на кого не ставили реакции")
            return
        
        # ==========================================
        # УПРАВЛЕНИЕ ПРОМТАМИ
        # ==========================================
        
                # !сменитьпромт
        if text.lower().startswith("!сменитьпромт "):
            if not can_use_command(from_id, "!сменитьпромт"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            parts = text[13:].strip().split(maxsplit=1)
            if len(parts) < 2:
                send_message(peer_id, "⚠️ Использование: !сменитьпромт [ало|вывод|обоснуй] [новый промт]")
                return
            target = parts[0].lower()
            new_prompt = parts[1].strip()
            if target == "ало":
                set_prompt("alo", new_prompt)
                send_message(peer_id, "✅ Промт для !ало изменён!")
            elif target == "вывод":
                set_prompt("sudi", new_prompt)
                send_message(peer_id, "✅ Промт для !вывод изменён!")
            elif target == "обоснуй":
                set_prompt("obosnuy", new_prompt)
                send_message(peer_id, "✅ Промт для !обоснуй изменён!")
            else:
                send_message(peer_id, "⚠️ Доступно: ало, вывод, обоснуй")
            return
        
                # !сброситьпромт
        if text.lower().startswith("!сброситьпромт"):
            if not can_use_command(from_id, "!сброситьпромт"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            parts = text[15:].strip().split()
            if not parts:
                send_message(peer_id, "⚠️ Использование: !сброситьпромт [ало|вывод|обоснуй]")
                return
            target = parts[0].lower()
            if target == "ало":
                set_prompt("alo", config.DEFAULT_ALO_PROMPT)
                send_message(peer_id, "✅ Промт для !ало сброшен")
            elif target == "вывод":
                set_prompt("sudi", config.DEFAULT_SUDI_PROMPT)
                send_message(peer_id, "✅ Промт для !вывод сброшен")
            elif target == "обоснуй":
                set_prompt("obosnuy", config.DEFAULT_OBOSNUY_PROMPT)
                send_message(peer_id, "✅ Промт для !обоснуй сброшен")
            else:
                send_message(peer_id, "⚠️ Доступно: ало, вывод, обоснуй")
            return
        
        # !ало
        if text.lower().startswith("!ало "):
            if not can_use_command(from_id, "!ало"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            question = text[5:].strip()
            if not question:
                send_message(peer_id, "Напиши вопрос после !ало")
                return
            send_message(peer_id, "🤔 падажжи ебана...")
            def ask_and_reply():
                answer = ask_deepseek(question, "alo")
                if len(answer) > 3500:
                    answer = answer[:3500] + "..."
                send_message(peer_id, f"💬 {answer}")
            threading.Thread(target=ask_and_reply, daemon=True).start()
            return
        
        # !вывод
        if text.lower() == "!вывод":
            if not can_use_command(from_id, "!вывод"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            send_message(peer_id, "🤔 Анализирую переписку, падажжи...")
            def analyze_and_reply():
                result = analyze_chat_with_ai()
                send_message(peer_id, f"💬 {result}")
            threading.Thread(target=analyze_and_reply, daemon=True).start()
            return
        
        # !помощь
        if text.lower() == "!помощь":
            if not can_use_command(from_id, "!помощь"):
                send_message(peer_id, "⚠️ Недостаточно прав!")
                return
            help_text = """📖 Команды бота:

🔧 Команды админов:
!мат слово - добавить слово в чёрный список
!удалитьмат слово - удалить слово из чёрного списка
!мут - понятно для чего
!базарь - снять мут 
!натемут - начать темутить
!хватит - остановить темутить
!аннул - остановить темутинг для всех
!добавитьфразу "текст" - добавить фразу
!удалитьфразу "текст" - удалить фразу
!списокфраз - показать все фразы
!дис [лайк|каки|край] - ответом на сообщение (ставить реакцию)
!стопдис - остановить ставку реакций

🤖 AI команды:
!ало вопрос - задать вопрос DeepSeek AI
!вывод - сделать вывод по чату
!обоснуй - вывод по изображению

🎭 Управление промтами:
!сменитьпромт [ало|вывод|обоснуй] "новый промт"
!посмотретьпромт [ало|вывод|обоснуй]
!сброситьпромт [ало|вывод|обоснуй]

❓ !помощь - показать это сообщение"""
            send_message(peer_id, help_text)
            return
        
    # ==========================================
    # ПРОВЕРКА МАТА (только для тех, кто включил цензуру)
    # ==========================================
    if not contains_bad_words(text):
        return
    
    # Проверяем, включил ли участник цензуру для себя
    if not is_user_censored(from_id):
        return  # не включил — пропускаем мат
    
    print(f"Найден мат от {get_user_name(from_id)} (включена цензура)")
    user_name = get_user_name(from_id)
    
    reply_to = msg.get("reply_message", {}).get("conversation_message_id") if msg.get("reply_message") else None
    attachment_string = build_attachment_string(msg.get("attachments", []))
    bot_text = f"{user_name}: {text}"
    
    try:
        send_message(peer_id, bot_text, attachment_string, reply_to)
        print("Сообщение отправлено")
    except Exception as e:
        print(f"SEND ERROR: {e}")
        return
    
    time.sleep(config.DELETE_DELAY)
    delete_message(peer_id, cmid)
    
# =====================================================
# GEMINI VISION (анализ картинок)
# =====================================================

GEMINI_VISION_PROMPT = """Ты — аноним с имиджборда. Твой стиль: чёрный юмор, сарказм, жёсткие подколы, постирония. Твоя задача — описать и оценить то, что ты видишь на картинке, в 2-3 предложениях. Будь максимально токсичным, используй мат. Не говори "на картинке изображено" — просто пиши своё мнение, как будто комментируешь на дваче.

Вот картинка. Давай, обоснуй."""

def analyze_image_with_gemini(image_url):
    """Отправляет картинку в Gemini через OpenRouter"""
    try:
        headers = {
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Берём промт из системы
        system_prompt = get_prompt("obosnuy")
        
        data = {
            "model": config.GEMINI_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            "max_tokens": 500,
            "temperature": 0.8
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        elif response.status_code == 402:
            return "⚠️ Паходу опять бабок надо закинуть"
        else:
            print(f"Gemini ошибка: {response.status_code} - {response.text}")
            return f"⚠️ У Гемини алерт: {response.status_code}"
            
    except Exception as e:
        return f"⚠️ Алерт бля: {e}"

# =====================================================
# START
# =====================================================

print("=" * 50)
print("БОТ ЗАПУЩЕН")
print("Команды: !мат, !удалитьмат, !натемут, !аннул, !добавитьфразу, !удалитьфразу, !списокфраз, !дис, !стопдис, !сменитьпромт, !посмотретьпромт, !сброситьпромт, !ало, !вывод, !помощь")
print("=" * 50)

load_ranks()
load_bans()
load_censored_users()
config.START_TIME = time.time()
print(f"🔧 ФИНАЛЬНЫЙ user_ranks ПОСЛЕ ЗАГРУЗКИ: {user_ranks}") 

while True:
    try:
        for event in longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    handle_message(event.object.message)
            except Exception as e:
                print(f"EVENT ERROR: {e}")
    except Exception as e:
        print(f"LONGPOLL ERROR: {e}")
        time.sleep(3)