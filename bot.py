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
"""# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Scalping (15m)", callback_data="mode_scalp")],
        [InlineKeyboardButton("📈 Intraday (1H)", callback_data="mode_intraday")],
        [InlineKeyboardButton("📉 Swing (4H)", callback_data="mode_swing")],
        [InlineKeyboardButton("📋 History Saya", callback_data="history")],
        [InlineKeyboardButton("⭐ Feedback Global", callback_data="feedback_global")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🤖 *Bot Sinyal XAUUSD Pro*\n\n"
        "Pilih mode trading:\n"
        "• Scalping → M15 (cepat)\n"
        "• Intraday → 1H (medium)\n"
        "• Swing → 4H (longer)\n\n"
        "Kirim screenshot chart XAUUSD setelah pilih mode.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("mode_"):
        mode = query.data.replace("mode_", "")
        context.user_data['mode'] = mode
        await query.edit_message_text(
            f"✅ Mode *{mode.upper()}* dipilih.\n\n"
            "Sekarang kirim *screenshot chart XAUUSD* (timeframe sesuai mode).",
            parse_mode="Markdown"
        )
    
    elif query.data == "history":
        user_id = query.from_user.id
        history = get_user_history(user_id)
        winrate = get_user_winrate(user_id)
        
        if not history:
            await query.edit_message_text("📭 Belum ada sinyal untuk user ini.")
            return
        
        text = f"📋 *History Sinyal ({len(history)} total)*\n"
        text += f"🏆 *Winrate: {winrate}%*\n\n"
        for h in history[:10]:
            mode, entry, sl, tp, rr, result, date, fb = h
            status = "✅" if result == "win" else "❌" if result == "loss" else "⏳"
            text += f"{status} {mode.upper()} | Entry {entry} | RR {rr} | {date[:10]}\n"
        if len(history) > 10:
            text += f"\n... dan {len(history)-10} sinyal lainnya."
        await query.edit_message_text(text, parse_mode="Markdown")
    
    elif query.data == "feedback_global":
        feedbacks = get_global_feedback()
        if not feedbacks:
            await query.edit_message_text("⭐ Belum ada feedback dari user lain.")
            return
        text = "⭐ *Feedback Global (5 bintang)*\n\n"
        for fb in feedbacks[:10]:
            score, comment, user = fb
            stars = "⭐" * (score or 0)
            comment_text = f" - {comment}" if comment else ""
            text += f"{stars} dari @{user or 'anon'}{comment_text}\n"
        await query.edit_message_text(text, parse_mode="Markdown")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'mode' not in context.user_data:
        await update.message.reply_text("⚠️ Pilih mode dulu! Ketik /start")
        return
    
    mode = context.user_data['mode']
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_url = file.file_path
    
    await update.message.reply_text(f"🔄 Menganalisis {mode.upper()}...")
    
    try:
        # Download gambar
        import requests
        img_data = requests.get(file_url).content
        
        # Kirim ke Gemini
        prompt = get_prompt(mode)
        response = vision_model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": img_data}
        ])
        
        analysis = response.text
        
        # Parse sinyal jika ada
        if "TIDAK ADA" not in analysis.upper():
            # Ekstrak angka (sederhana)
            import re
            entry_match = re.search(r'Entry[: ]*([0-9.]+)', analysis)
            sl_match = re.search(r'SL[: ]*([0-9.]+)', analysis)
            tp_match = re.search(r'TP[: ]*([0-9.]+)', analysis)
            rr_match = re.search(r'RR[: ]*([0-9.]+)', analysis)
            
            if entry_match and sl_match and tp_match:
                entry = float(entry_match.group(1))
                sl = float(sl_match.group(1))
                tp = float(tp_match.group(1))
                rr = float(rr_match.group(1)) if rr_match else 0
                
                # Simpan ke DB
                save_signal(
                    update.effective_user.id,
                    update.effective_user.username,
                    mode, entry, sl, tp, rr
                )
                
                # Tombol feedback & update result
                keyboard = [
                    [InlineKeyboardButton("✅ Win", callback_data=f"result_win_{mode}"),
                     InlineKeyboardButton("❌ Loss", callback_data=f"result_loss_{mode}")],
                    [InlineKeyboardButton("⭐ Beri Rating (1-5)", callback_data=f"rate_{mode}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"📊 *Sinyal {mode.upper()}*\n\n{analysis}\n\n"
                    "📌 Jangan lupa update hasil trade dan beri rating!",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(analysis)
        else:
            await update.message.reply_text(
                f"📉 *{mode.upper()}*\n\n{analysis}\n\n💬 *{random_quote()}*",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("❌ Gagal analisis. Coba ulangi.")

def random_quote():
    quotes = [
        "🏆 Disiplin hari ini = profit besok.",
        "🧘 Trader terbaik adalah yang tahu kapan tidak trading.",
        "📉 Lebih baik kehilangan peluang daripada kehilangan modal.",
        "🔥 Sabar adalah edge terbesar trader ritel.",
        "🚀 Uang datang dari menunggu, bukan memaksa.",
        "💎 Konsistensi > akurasi.",
        "🧠 Risk management adalah segalanya.",
    ]
    import random
    return random.choice(quotes)

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    port = int(os.environ.get("PORT", 8443))
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
