import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import google.generativeai as genai
from database import init_db, save_signal, update_result, add_feedback, get_user_history, get_user_winrate, get_global_feedback

# Load env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Init Gemini
genai.configure(api_key=GEMINI_API_KEY)
vision_model = genai.GenerativeModel('gemini-1.5-flash')

# Init DB
init_db()

# Logging
logging.basicConfig(level=logging.INFO)

# ==================== PROMPT PER MODE ====================
def get_prompt(mode):
    mode_names = {
        'scalp': 'Scalping 15 menit',
        'intraday': 'Intraday 1 jam',
        'swing': 'Swing 4 jam'
    }
    
    return f"""
Kamu adalah trader pro XAUUSD dengan spesialisasi {mode_names[mode]}.

ATURAN:
1. Hanya trade searah tren.
2. Jangan paksakan entry kalau tidak ada setup A+.
3. Gunakan pending order (buy/sell stop/limit).
4. Minimal RR 1:2.
5. Jika ada setup, berikan:
   - Entry price
   - Stop Loss
   - Take Profit
   - RR ratio
   - Alasan singkat (1-2 kalimat)

6. Jika tidak ada setup, jawab: "TIDAK ADA SETUP VALID"

Analisis chart ini untuk sinyal {mode_names[mode]}.
Gunakan bahasa Indonesia yang tegas dan profesional.
"""
