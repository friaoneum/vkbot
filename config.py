# config.py - Конфигурация бота
# =====================================================
# Время запуска бота (будет установлено в main.py)
import os

# =====================================================
# ПУТИ К ФАЙЛАМ
# =====================================================
DATA_DIR = "data"  # папка для хранения данных

# Файлы для хранения данных (теперь внутри DATA_DIR)
ACCESS_FILE = os.path.join(DATA_DIR, "access.json")
BANS_FILE = os.path.join(DATA_DIR, "bans.json")
RANKS_FILE = os.path.join(DATA_DIR, "ranks.json")
CENSORED_USERS_FILE = os.path.join(DATA_DIR, "censored_users.json")
BAD_WORDS_FILE = os.path.join(DATA_DIR, "bad_words.txt")
PHRASES_FILE = os.path.join(DATA_DIR, "troll_phrases.txt")
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")
MODELS_FILE = os.path.join(DATA_DIR, "models.json")
LINKS_ENABLED_FILE = os.path.join(DATA_DIR, "links_enabled.json")
ANTISPAM_ENABLED_FILE = os.path.join(DATA_DIR, "antispam_enabled.json")
INACTIVITY_FILE = os.path.join(DATA_DIR, "inactivity.json")

GREETING_ENABLED_FILE = os.path.join(DATA_DIR, "greeting_enabled.json")
GREETING_TEXT_FILE = os.path.join(DATA_DIR, "greeting_text.txt")
RULES_ENABLED_FILE = os.path.join(DATA_DIR, "rules_enabled.json")
RULES_TEXT_FILE = os.path.join(DATA_DIR, "rules_text.txt")
SLYSH_ENABLED_FILE = os.path.join(DATA_DIR, "slysh_enabled.json")
NICKNAMES_ENABLED_FILE = os.path.join(DATA_DIR, "nicknames_enabled.json")
NICKNAMES_FILE = os.path.join(DATA_DIR, "nicknames.json")
AGITATION_FILE = os.path.join(DATA_DIR, "agitation.json")
FORCED_CENSORED_USERS_FILE = os.path.join(DATA_DIR, "forced_censored_users.json")

START_TIME = None

GROUP_TOKEN = os.getenv("GROUP_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

GEMINI_VISION_MODEL = "google/gemini-2.5-flash"

GROUP_ID = 240211941 #237768763 #239895595 #240211941

# Ваш ID (постоянный админ)
OWNER_ID = 200000675743 ##1107340870 Low

# =====================================================
# НАСТРОЙКИ БОТА
# =====================================================
MESSAGE_HISTORY_MAXLEN = 200
CACHE_TIME = 300
DELETE_DELAY = 0.1
ADMINS_CACHE_TTL = 60  
INACTIVITY_DAYS = 30  # через сколько дней кикать

REACTIONS_LIST = ["лайк", "каки", "край"]

# =====================================================
# НАСТРОЙКИ АНТИСПАМА (повторы + флуд)
# =====================================================
ANTISPAM_REPEAT_COUNT = 5      # сколько одинаковых сообщений подряд
ANTISPAM_REPEAT_WINDOW = 30    # окно в секундах (проверяем только за это время)
ANTISPAM_MUTE_DURATION = 10    # минут мута за спам

# ПАРАМЕТРЫ ДЛЯ ФЛУДА (частота)
ANTISPAM_FLOOD_COUNT = 5       # максимум сообщений за окно
ANTISPAM_FLOOD_WINDOW = 5      # окно в секундах (например, 5 сообщений за 5 секунд)

# =====================================================
# МОДЕЛИ ПО УМОЛЧАНИЮ
# =====================================================
DEFAULT_MODELS = {
    "alo": "google/gemini-3.1-flash-lite",
    "sudi": "google/gemini-3.1-flash-lite",
    "obosnuy": "google/gemini-2.5-flash",
    "slysh": "google/gemini-3.1-flash-lite"
}

# =====================================================
# ПРОМТЫ
# =====================================================
DEFAULT_ALO_PROMPT = """Ты — конченый фрик. Твой стиль: чёрный юмор, цинизм, сарказм, постирония, переход на личности, мат и унижение.
Не будь вежливым — будь максимально токсичным. Твоя цель интеллектуальное и словесное доминирование.
Твоя задача обоссать заданый тебе вопрос и участника, который тебе его задал, но ответь на вопрос обязательно. """

DEFAULT_SUDI_PROMPT = """Ты — конченый фрик. Твой стиль: чёрный юмор, цинизм, сарказм, постирония, переход на личности, мат и унижение. 
Ты презираешь серьёзность, пафос и интеллектуальные потуги участников. Твоя цель интеллектуальное и словесное доминирование.
Твоя задача — проанализировать диалог ниже и выдать ЕДКИЙ, ЖЁСТКИЙ, ОСКОРБИТЕЛЬНЫЙ ВЫВОД (3-5 предложений). 
Не пиши общие фразы — бей прямо по участникам, по их текстам. Просто пиши своё мнение."""

DEFAULT_OBOSNUY_PROMPT = """Ты — конченый фрик. Твой стиль: чёрный юмор, цинизм, сарказм, постирония, переход на личности, мат и унижение. 
Твоя задача — описать и оценить то, что ты видишь на картинке, в 2-3 предложениях. Будь максимально токсичным, язвительным и оскорбительным.
Твоя цель интеллектуальное и словесное доминирование. Используй мат, чёрный юмор, сравнения с животными и т.д. 
Просто пиши своё мнение."""

DEFAULT_SLYSH_PROMPT = """Ты — конченый фрик, который ненавидит всех и вся. Твой стиль: чёрный юмор, цинизм, сарказм, постирония, переход на личности, мат и унижение.
Ответь в своем стиле, но сохраняя контекст диалога, не выпадай из темы. Твоя цель интеллектуальное и словесное доминирование.
 Пиши в продолжение диалога как участник чата, пиши исключительно от своего имени, не пытайся писать от чужого. """

# =====================================================
# ПРИВЕТСТВИЯ И ПРАВИЛА
# =====================================================
DEFAULT_GREETING = "{mention}, терь в чате"

DEFAULT_RULES = """📜 Правила чата:

1. Идите нахуй
2. Скидывайте сиськи админу
3. Не флудить
4. Слушаться администрацию
5. Выебите мне кто нибудь пожацлустаь"""

# =====================================================
# ОСОБЫЕ РОЛИ
# =====================================================
SPECIAL_ROLES = {
    #754827736: "💋 Тёлка админа:",
    # Добавляйте других: 123456789: "🎭 Какая-то роль",
}