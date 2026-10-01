import os
import sqlite3
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

DB = "bookings.db"
TIMES = ["10:00", "11:00", "12:00", "14:00", "15:00"]
OWNER_ID = os.environ.get("OWNER_ID")

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS bookings ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER, day TEXT, time TEXT)"
        )

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Termin buchen", callback_data="book")],
        [InlineKeyboardButton("Meine Termine", callback_data="my")],
        [InlineKeyboardButton("Termin absagen", callback_data="cancel")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hallo! Was möchten Sie tun?", reply_markup=main_menu())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "book":
        days = [date.today() + timedelta(days=i) for i in range(1, 6)]
        keyboard = [
            [InlineKeyboardButton(d.strftime("%d.%m."), callback_data=f"day:{d.isoformat()}")]
            for d in days
        ]
        await query.edit_message_text("Wählen Sie einen Tag:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("day:"):
        day = data.split(":", 1)[1]
        with sqlite3.connect(DB) as conn:
            taken = {r[0] for r in conn.execute("SELECT time FROM bookings WHERE day = ?", (day,))}
        free = [t for t in TIMES if t not in taken]
        if not free:
            await query.edit_message_text(f"Am {day} ist alles belegt.", reply_markup=main_menu())
            return
        keyboard = [[InlineKeyboardButton(t, callback_data=f"time:{day}:{t}")] for t in free]
        await query.edit_message_text(f"Freie Zeiten am {day}:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("time:"):
        _, day, t = data.split(":", 2)
        with sqlite3.connect(DB) as conn:
            busy = conn.execute(
                "SELECT 1 FROM bookings WHERE day = ? AND time = ?", (day, t)
            ).fetchone()
            if not busy:
                conn.execute(
                    "INSERT INTO bookings (user_id, day, time) VALUES (?, ?, ?)",
                    (user_id, day, t),
                )
        if busy:
            await query.edit_message_text("Dieser Termin ist leider schon vergeben.", reply_markup=main_menu())
            return
        await query.edit_message_text(f"Gebucht: {day} um {t} Uhr.", reply_markup=main_menu())
        if OWNER_ID:
            name = query.from_user.full_name
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"Neue Buchung: {name}, {day} um {t} Uhr",
            )

    elif data == "my":
        with sqlite3.connect(DB) as conn:
            rows = conn.execute(
                "SELECT day, time FROM bookings WHERE user_id = ? ORDER BY day, time",
                (user_id,),
            ).fetchall()
        text = "\n".join(f"{d} um {t} Uhr" for d, t in rows) or "Keine Termine."
        await query.edit_message_text(text, reply_markup=main_menu())

    elif data == "cancel":
        with sqlite3.connect(DB) as conn:
            rows = conn.execute(
                "SELECT id, day, time FROM bookings WHERE user_id = ? ORDER BY day, time",
                (user_id,),
            ).fetchall()
        if not rows:
            await query.edit_message_text("Keine Termine.", reply_markup=main_menu())
            return
        keyboard = [
            [InlineKeyboardButton(f"{d} {t}", callback_data=f"del:{i}")] for i, d, t in rows
        ]
        await query.edit_message_text("Welchen Termin absagen?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del:"):
        booking_id = int(data.split(":", 1)[1])
        with sqlite3.connect(DB) as conn:
            conn.execute(
                "DELETE FROM bookings WHERE id = ? AND user_id = ?", (booking_id, user_id)
            )
        await query.edit_message_text("Termin abgesagt.", reply_markup=main_menu())

init_db()
app = Application.builder().token(os.environ["BOT_TOKEN"]).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.run_polling()