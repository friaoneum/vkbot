# vk_utils.py - Вспомогательные функции для работы с VK
import vk_api
import random
import time
import json
import re
import config

# =====================================================
# ПОДКЛЮЧЕНИЕ К VK
# =====================================================

vk_session = vk_api.VkApi(token=config.GROUP_TOKEN)
vk = vk_session.get_api()
BOT_ID = -config.GROUP_ID

# =====================================================
# КЭШ ИМЁН
# =====================================================

user_name_cache = {}

def get_user_name(user_id, mention=True):
    """
    Возвращает имя пользователя
    mention=True: возвращает кликабельное упоминание [id123|Имя]
    mention=False: возвращает просто имя (текстом)
    """
    current_time = time.time()
    
    if user_id in user_name_cache:
        name, cache_time = user_name_cache[user_id]
        if current_time - cache_time < config.CACHE_TIME:
            if mention:
                return f"[id{user_id}|{name}]"
            return name
    
    try:
        user = vk.users.get(user_ids=user_id)[0]
        name = f"{user['first_name']} {user['last_name']}"
        user_name_cache[user_id] = (name, current_time)
        
        if mention:
            return f"[id{user_id}|{name}]"
        return name
    except:
        if mention:
            return f"[id{user_id}|Unknown]"
        return "Unknown"

# =====================================================
# ОТПРАВКА СООБЩЕНИЯ
# =====================================================

def send_message(peer_id, text, attachment=None, reply_to=None, disable_mentions=False, keyboard=None):
    params = {
        "peer_id": peer_id,
        "message": text,
        "random_id": random.randint(1, 999999999)
    }
    if attachment:
        params["attachment"] = attachment
    if reply_to:
        forward = {
            "peer_id": peer_id,
            "conversation_message_ids": [reply_to],
            "is_reply": True
        }
        params["forward"] = json.dumps(forward, ensure_ascii=False)
    if disable_mentions:
        params["disable_mentions"] = 1
    if keyboard:
        params["keyboard"] = keyboard  # уже строка JSON
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
# ПОЛУЧЕНИЕ ID ИЗ УПОМИНАНИЯ ИЛИ ОТВЕТА
# =====================================================

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
# ОБРАБОТКА ВЛОЖЕНИЙ
# =====================================================

def build_attachment_string(attachments):
    result = []
    for att in attachments:
        try:
            att_type = att["type"]
            obj = att[att_type]
            
            if att_type == "video":
                owner_id = obj.get("owner_id")
                media_id = obj.get("id")
                access_key = obj.get("access_key", "")
                if access_key:
                    result.append(f"video{owner_id}_{media_id}_{access_key}")
                else:
                    result.append(f"video{owner_id}_{media_id}")
            
            elif att_type == "doc":
                owner_id = obj.get("owner_id")
                doc_id = obj.get("id")
                access_key = obj.get("access_key", "")
                title = obj.get("title", "").lower()
                
                video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.3gp', '.mpeg']
                if any(ext in title or ext == extension for extension in video_extensions):
                    if access_key:
                        result.append(f"doc{owner_id}_{doc_id}_{access_key}")
                    else:
                        result.append(f"doc{owner_id}_{doc_id}")
                else:
                    if access_key:
                        result.append(f"doc{owner_id}_{doc_id}_{access_key}")
                    else:
                        result.append(f"doc{owner_id}_{doc_id}")
            
            elif att_type == "photo":
                owner_id = obj.get("owner_id")
                photo_id = obj.get("id")
                access_key = obj.get("access_key", "")
                if access_key:
                    result.append(f"photo{owner_id}_{photo_id}_{access_key}")
                else:
                    result.append(f"photo{owner_id}_{photo_id}")
            
            elif att_type == "link":
                url = obj.get("url", "")
                video_sites = ["youtube", "youtu.be", "vk.com/video", "rutube", "dzen.ru/video"]
                if any(site in url.lower() for site in video_sites):
                    result.append(f"link{url}")
                    
        except Exception as e:
            print(f"Ошибка обработки вложения {att_type}: {e}")
            
    return ",".join(result)

def build_keyboard(rows, one_time=False, inline=False):
    """
    Создаёт клавиатуру VK.
    rows: список рядов, каждый ряд – список кнопок.
          Кнопка = (label, command) или (label, command, color).
          color: "primary", "positive", "negative", "secondary".
    one_time: скрыть после нажатия
    inline: True – встроенная (прикреплена к сообщению), False – обычная
    """
    keyboard = {
        "one_time": one_time,
        "inline": inline,
        "buttons": []
    }
    for row in rows:
        buttons_row = []
        for item in row:
            if isinstance(item, tuple):
                if len(item) == 3:
                    label, command, color = item
                else:
                    label, command = item
                    color = "primary"
            else:
                label = item
                command = item
                color = "primary"
            buttons_row.append({
                "action": {
                    "type": "text",
                    "label": label,
                    "payload": json.dumps({"command": command}, ensure_ascii=False)
                },
                "color": color
            })
        keyboard["buttons"].append(buttons_row)
    return json.dumps(keyboard, ensure_ascii=False)