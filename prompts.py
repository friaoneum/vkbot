# prompts.py - Система управления промтами
import os
import json
import config

PROMPTS = {}

def load_prompts():
    global PROMPTS
    default_prompts = {
        "alo": config.DEFAULT_ALO_PROMPT,
        "sudi": config.DEFAULT_SUDI_PROMPT,
        "obosnuy": config.DEFAULT_OBOSNUY_PROMPT,
        "slysh": config.DEFAULT_SLYSH_PROMPT
    }
    if os.path.exists(config.PROMPTS_FILE):
        with open(config.PROMPTS_FILE, "r", encoding="utf-8") as f:
            try:
                prompts = json.load(f)
                for key in default_prompts:
                    if key not in prompts:
                        prompts[key] = default_prompts[key]
                PROMPTS = prompts
                return
            except:
                PROMPTS = default_prompts
    else:
        PROMPTS = default_prompts
    save_prompts(PROMPTS)

def save_prompts(prompts):
    with open(config.PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)

def get_prompt(command):
    return PROMPTS.get(command, PROMPTS.get("alo", "Ты помощник."))

def set_prompt(command, new_prompt):
    PROMPTS[command] = new_prompt
    save_prompts(PROMPTS)
    return True