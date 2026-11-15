# moderation.py - Система фильтрации матов
import os
import config

BAD_WORDS = []

def get_bad_words():
    """Возвращает текущий список матов"""
    return BAD_WORDS

def set_bad_words(words):
    """Устанавливает список матов"""
    global BAD_WORDS
    BAD_WORDS = words
    save_bad_words(words)

def load_bad_words():
    global BAD_WORDS
    if os.path.exists(config.BAD_WORDS_FILE):
        try:
            with open(config.BAD_WORDS_FILE, "r", encoding="utf-8") as f:
                words = [line.strip().lower() for line in f if line.strip()]
                if words:
                    BAD_WORDS = words
                    return
        except Exception as e:
            print(f"❌ Ошибка загрузки матов: {e}")
    
    # Если файла нет или он пустой
    BAD_WORDS = ["хуй", "пизда", "блять", "сука"]
    save_bad_words(BAD_WORDS)

def save_bad_words(words):
    global BAD_WORDS
    BAD_WORDS = words
    with open(config.BAD_WORDS_FILE, "w", encoding="utf-8") as f:
        for word in words:
            f.write(word + "\n")

def contains_bad_words(text):
    if not text:
        return False
    text = text.lower()
    for word in BAD_WORDS:
        if word in text:
            return True
    return False