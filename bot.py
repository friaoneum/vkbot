# bot.py - Главный файл запуска
import time
from moderation import load_bad_words
from prompts import load_prompts
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from vk_utils import vk_session
from commands import (
    handle_message,
    load_ranks,
    load_bans,
    load_censored_users,
    load_forced_censored_users,
    load_models,
    load_slysh_state,
    load_greeting_state,
    load_greeting_text,
    load_rules_state,
    load_rules_text,
    load_nicknames_state,
    load_nicknames,
    load_agitation_state,
    load_access,
    load_links_state,
    load_antispam_state,
    load_inactivity_data
)
import config

# =====================================================
# ЗАГРУЗКА ВСЕХ ДАННЫХ
# =====================================================
print("=" * 50)
print("🔄 ЗАГРУЗКА ДАННЫХ...")
print("=" * 50)

load_ranks()
load_bans()
load_censored_users()
load_forced_censored_users()
load_models()
load_slysh_state()
load_greeting_state()
load_greeting_text()
load_rules_state()
load_rules_text()
load_nicknames_state()
load_nicknames()
load_agitation_state()
load_access()
load_links_state()
load_antispam_state()
load_inactivity_data()
load_bad_words()
load_prompts()

config.START_TIME = time.time()

print("=" * 50)
print("✅ БОТ ЗАПУЩЕН")
print("=" * 50)

# =====================================================
# ОСНОВНОЙ ЦИКЛ
# =====================================================
longpoll = VkBotLongPoll(vk_session, config.GROUP_ID)

while True:
    try:
        for event in longpoll.listen():
            try:
                if event.type == VkBotEventType.MESSAGE_NEW:
                    handle_message(event.object.message)
                
                elif event.type == VkBotEventType.GROUP_JOIN:
                    user_id = event.object.user_id
                    peer_id = event.object.peer_id
                    if peer_id and peer_id > 2000000000:
                        from commands import is_user_banned, get_user_name, greeting_enabled, get_greeting, send_message
                        if is_user_banned(peer_id, user_id):
                            try:
                                chat_id = peer_id - 2000000000
                                vk_session.get_api().messages.removeChatUser(chat_id=chat_id, user_id=user_id)
                                print(f"🚫 Забаненный {get_user_name(user_id)} кикнут")
                            except Exception as e:
                                print(f"❌ Ошибка кика забаненного: {e}")
                            continue
                        
                        if greeting_enabled:
                            user_name = get_user_name(user_id)
                            from commands import get_greeting
                            welcome_msg = get_greeting(user_id, user_name)
                            send_message(peer_id, welcome_msg)
                            
            except Exception as e:
                print(f"EVENT ERROR: {e}")
    except Exception as e:
        print(f"LONGPOLL ERROR: {e}")
        time.sleep(3)