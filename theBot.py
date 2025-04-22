date = '22 April 2025'
author = 'Kömen | Enes Bekdemir'

import requests
from bs4 import BeautifulSoup as bs
import time
### python-telegram-bot==13.15
from telegram import Bot, Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, JobQueue
from telegram.error import TelegramError, Unauthorized, BadRequest, TimedOut, NetworkError
from dotenv import load_dotenv
import os
import logging
import sqlite3
import threading
import urllib3
import pandas as pd

load_dotenv()
os.environ['PYTHONIOENCODING'] = 'utf-8'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db_path = 'yadyok.db'
db_lock = threading.Lock()

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive'
}

# --- Disable InsecureRequestWarning ---
try:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    logger.info("Disabled InsecureRequestWarning from urllib3.")
except Exception as e:
    logger.warning(f"Could not disable InsecureRequestWarning: {e}")



def init_db():
    with db_lock:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            # Table for subscribers
            c.execute('''CREATE TABLE IF NOT EXISTS chat_ids (
                            id INTEGER PRIMARY KEY,
                            main_announcements BOOLEAN DEFAULT 1,
                            yadyok_announcements BOOLEAN DEFAULT 1,
                            mis_announcements BOOLEAN DEFAULT 1
                            )''')
            # Table for announcements
            c.execute('''CREATE TABLE IF NOT EXISTS main_announcements (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            announcement TEXT UNIQUE NOT NULL
                            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS yadyok_announcements (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            announcement TEXT UNIQUE NOT NULL
                            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS mis_announcements (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            announcement TEXT UNIQUE NOT NULL
                            )''')
            conn.commit()
    logger.info("Database initialized.")

def save_chat_id(chat_id) -> bool:
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute("INSERT OR IGNORE INTO chat_ids (id) VALUES (?)", (chat_id,))
                conn.commit()
                logger.info(f"Attempted to save chat ID {chat_id}.")
                return True
        except sqlite3.Error as e:
            logger.error(f"Database error saving chat ID {chat_id}: {e}")
            return False

def delete_chat_id(chat_id) -> bool:
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM chat_ids WHERE id = ?", (chat_id,))
                conn.commit()
                if conn.total_changes > 0:
                    logger.info(f"Chat ID {chat_id} deleted.")
                    return True
                else:
                    logger.warning(f"Chat ID {chat_id} not found for deletion.")
                    return False
        except sqlite3.Error as e:
            logger.error(f"Database error deleting chat ID {chat_id}: {e}")
            return False

def get_chat_ids():
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT id, main_announcements, yadyok_announcements, mis_announcements FROM chat_ids")
                df = pd.DataFrame(c.fetchall(), columns=['id', 'main_announcements', 'yadyok_announcements', 'mis_announcements'])
                return df
        except sqlite3.Error as e:
            logger.error(f"Database error getting chat IDs: {e}")
            return pd.DataFrame()

def get_user_subscriptions(chat_id) -> dict:
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT main_announcements, yadyok_announcements, mis_announcements FROM chat_ids WHERE id = ?", (chat_id,))
                row = c.fetchone()
                if row:
                    return {
                        'main_announcements': row[0],
                        'yadyok_announcements': row[1],
                        'mis_announcements': row[2]
                    }
                else:
                    logger.warning(f"Chat ID {chat_id} not found for subscription check.")
                    return {}
        except sqlite3.Error as e:
            logger.error(f"Database error getting user subscriptions for chat ID {chat_id}: {e}")
            return {}

def subscribe(chat_id, announcement_type) -> bool:
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute(f"UPDATE chat_ids SET {announcement_type} = 1 WHERE id = ?", (chat_id,))
                conn.commit()
                if conn.total_changes > 0:
                    logger.info(f"Chat ID {chat_id} subscribed to {announcement_type}.")
                    return True
                else:
                    logger.warning(f"Chat ID {chat_id} not found for subscription.")
                    return False
        except sqlite3.Error as e:
            logger.error(f"Database error subscribing chat ID {chat_id}: {e}")
            return False

def unsubscribe(chat_id, announcement_type) -> bool:
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute(f"UPDATE chat_ids SET {announcement_type} = 0 WHERE id = ?", (chat_id,))
                conn.commit()
                if conn.total_changes > 0:
                    logger.info(f"Chat ID {chat_id} unsubscribed from {announcement_type}.")
                    return True
                else:
                    logger.warning(f"Chat ID {chat_id} not found for unsubscription.")
                    return False
        except sqlite3.Error as e:
            logger.error(f"Database error unsubscribing chat ID {chat_id}: {e}")
            return False

### --- Database Functions ---
def get_announcements_from_db(table='yadyok') -> set[str]:
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute(f"SELECT announcement FROM {table}_announcements")
                return {row[0].strip() for row in c.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"Database error getting {table.upper()} announcements: {e}")
            return set()

def save_announcements(ordered_announcements: list[str], table='yadyok_announcements'):
    if not ordered_announcements:
        return
    saved_count = 0
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                ordered_announcements.reverse()
                for announcement_text in ordered_announcements:
                    c.execute(f"INSERT OR IGNORE INTO {table}_announcements (announcement) VALUES (?)", (announcement_text.strip(),))
                    if c.rowcount > 0: # Check if a row was actually inserted
                        saved_count += 1
                conn.commit()
                if saved_count > 0:
                    logger.info(f"Saved {saved_count} new {table} announcements to DB sequentially.")
        except sqlite3.Error as e:
            logger.error(f"Database error saving {table} announcements: {e}")


# --- Scraping Functions ---
def fetch_announcements_MAIN() -> list[str]:
    url = 'https://bogazici.edu.tr/tr-TR/Content/Duyurular/Duyurular'
    announcements = []
    try:
        response = session.get(url, headers=headers, verify=False, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8' 
        soup = bs(response.text, 'html.parser')
        items = soup.find_all('a', class_='urltoGO')
        
        announcements = [item.get_text(strip=True) for item in items if item.get_text(strip=True)]
        
        logger.info(f"Fetched {len(announcements)} MAIN announcements from {url} in order.")
        return announcements
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching MAIN announcements from {url}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch MAIN announcements: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing MAIN announcements HTML: {e}")
        return []

def fetch_announcements_YADYOK() -> list[str]:
    url = 'https://yadyok.bogazici.edu.tr/tr/duyurular'
    announcements = []
    try:
        response = session.get(url, headers=headers, verify=False, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = bs(response.text, 'html.parser')
        items = soup.find_all('span', class_='field-content')

        announcements = [item.get_text(strip=True) for item in items if item.get_text(strip=True)]
        
        logger.info(f"Fetched {len(announcements)} YADYOK announcements from {url} in order.")
        return announcements
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching YADYOK announcements from {url}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch YADYOK announcements: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing YADYOK announcements HTML: {e}")
        return []

def fetch_announcements_MIS() -> list[str]:
    url = 'https://mis.bogazici.edu.tr/tr/latest-news'
    announcements = []
    try:
        response = session.get(url, headers=headers, verify=False, timeout=20)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = bs(response.text, 'html.parser')
        
        td_tags = soup.find_all("td", class_="views-field views-field-title")
        items = [td.find("a") for td in td_tags if td.find("a")]

        announcements = [item.get_text(strip=True) for item in items if item.get_text(strip=True)]
        
        logger.info(f"Fetched {len(announcements)} MIS announcements from {url} in order.")
        return announcements
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error fetching MIS announcements from {url}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch MIS announcements: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing MIS announcements HTML: {e}")
        return []




# --- Command Handlers ---
def status(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    logger.info(f"/status command received from {user_name} ({chat_id})")
    subscriptions = get_user_subscriptions(chat_id)
    if subscriptions:
        status_message = (
            f"Abonelik durumun:\n"
            f"Ana sayfa duyurularına {'abonesin, abonelikten çıkmak için' if subscriptions['main_announcements'] else 'abone değilsin, abone olmak için'}: \n{'/unsubscribe_main' if subscriptions['main_announcements'] else '/subscribe_main'}\n"
            f"YADYOK duyurularına {'abonesin, abonelikten çıkmak için' if subscriptions['yadyok_announcements'] else 'abone değilsin, abone olmak için'}: \n{'/unsubscribe_yadyok' if subscriptions['yadyok_announcements'] else '/subscribe_yadyok'}\n"
            f"MIS duyurularına {'abonesin, abonelikten çıkmak için' if subscriptions['mis_announcements'] else 'abone değilsin, abone olmak için'}: \n{'/unsubscribe_mis' if subscriptions['mis_announcements'] else '/subscribe_mis'}\n"
            f"Duyuru bildirimlerini tamamen kapatmak için /stop komutunu kullanabilirsin.\n"
            f"/latest, /start"
            f"\n\n-Kömen")
        update.message.reply_text(status_message)
    else:
        update.message.reply_text("Seni bulamadım. Lütfen /start komutunu kullanarak kaydolmayı dene.")


def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    logger.info(f"/start command received from {user_name} ({chat_id})")
    if save_chat_id(chat_id):
        update.message.reply_text(
            f"Merhaba {user_name}! 👋\n"
            f"Benim görevim yeni bir duyuru olduğunda sana haber vermek.\n"
            f"Son duyuruları görmek için /latest komutunu kullanabilirsin.\n"
            f"Duyuru bildirimlerini tamamen kapatmak için /stop komutunu kullanabilirsin."
            f"\nAbonelik durumunu görmek için /status komutunu kullanabilirsin."
            f"\n\n-Kömen"
        )
    else:
        update.message.reply_text(
            "Merhaba! Seni kaydederken bir sorun oluştu. Lütfen daha sonra tekrar dene veya yönetici ile iletişime geç."
        )

def fetch_latest_announcements(update: Update, context: CallbackContext, table, limit):
    rows = []
    with db_lock:
        try:
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                c.execute(f"SELECT announcement FROM {table} ORDER BY id DESC LIMIT ?", (limit,))
                rows = c.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Database error getting latest {table.upper()} announcements: {e}")
            update.message.reply_text("Duyuruları getirirken bir veritabanı hatası oluştu. 😟")
            return 
    if rows:
        def escape_md(text):
            escape_chars = r'_*[]()~`>#+-=|{}.!'
            # Need to escape the escape character itself
            return ''.join(f'\\{char}' if char in escape_chars else char for char in text)
        announcements_text = [f"\\- {escape_md(row[0].strip())}" for row in rows]
        response = "\n".join(announcements_text)
        
        table_message = {'main_announcements': 'Ana sayfadaki', 'yadyok_announcements': "YADYOK duyurularındaki", 'mis_announcements': 'MIS duyurularındaki'}
        update.message.reply_text(
            f"*{table_message[table]} son {len(rows)} duyuru:*\n\n{response}", # Clarified order in message
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        update.message.reply_text(f"Veritabanında kayıtlı {table if not table == 'main' else 'ana sayfa'} duyurusu bulunamadı. Belki de henüz hiç duyuru yayınlanmadı? 🤔")

def latest(update: Update, context: CallbackContext):
    logger.info(f"/latest command received from {update.effective_chat.id}")
    limit = 5
    types = get_user_subscriptions(update.effective_chat.id)
    for typ in types:
        if types[typ] == 1:
            fetch_latest_announcements(update, context, typ, limit)

def stop(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    logger.info(f"/stop command received from {user_name} ({chat_id})")
    if delete_chat_id(chat_id):
        update.message.reply_text("YADYOK duyuru bildirimlerin kapatıldı. Tekrar başlatmak istersen /start komutunu kullanabilirsin. Görüşmek üzere! 👋")
    else:
        update.message.reply_text("Bildirimlerini kapatırken bir sorun oluştu veya zaten abone değildin.")

def subscribe_to_main(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if subscribe(chat_id, 'main_announcements'):
        update.message.reply_text("Ana sayfa duyurularına abone oldun!")
    else:
        update.message.reply_text("Ana sayfa duyurularına abone olurken bir sorun oluştu.")

def unsubscribe_from_main(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if unsubscribe(chat_id, 'main_announcements'):
        update.message.reply_text("Ana sayfa duyurularından çıkış yaptın.")
    else:
        update.message.reply_text("Ana sayfa duyurularından çıkış yaparken bir sorun oluştu.")

def subscribe_to_yadyok(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if subscribe(chat_id, 'yadyok_announcements'):
        update.message.reply_text("YADYOK duyurularına abone oldun!")
    else:
        update.message.reply_text("YADYOK duyurularına abone olurken bir sorun oluştu.")

def unsubscribe_from_yadyok(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if unsubscribe(chat_id, 'yadyok_announcements'):
        update.message.reply_text("YADYOK duyurularından çıkış yaptın.")
    else:
        update.message.reply_text("YADYOK duyurularından çıkış yaparken bir sorun oluştu.")

def subscribe_to_mis(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if subscribe(chat_id, 'mis_announcements'):
        update.message.reply_text("MIS duyurularına abone oldun!")
    else:
        update.message.reply_text("MIS duyurularına abone olurken bir sorun oluştu.")

def unsubscribe_from_mis(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if unsubscribe(chat_id, 'mis_announcements'):
        update.message.reply_text("MIS duyurularından çıkış yaptın.")
    else:
        update.message.reply_text("MIS duyurularından çıkış yaparken bir sorun oluştu.")




def notify_users(bot: Bot, ordered_new_announcements: list[str], chat_ids: list, typ):
    if not ordered_new_announcements or not chat_ids:
        return

    def escape_md(text):
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

    # Format using the received order
    escaped_announcements = [f"\\- {escape_md(ann.strip())}" for ann in ordered_new_announcements]
    
    text = f"*Yeni {typ.upper() if not typ == 'main' else 'Ana Sayfa'} Duyuruları:*\n\n" + "\n".join(escaped_announcements) # Added "(Sırasıyla)"

    sent_count = 0
    failed_ids = []
    unauthorized_ids = [] # Keep track specifically for deletion after loop

    for chat_id in chat_ids:
        try:
            bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
            sent_count += 1
            logger.debug(f"Sent notification to {chat_id}")
            time.sleep(0.1) # Small delay to avoid hitting rate limits
        except Unauthorized:
            logger.warning(f"Bot unauthorized for chat ID {chat_id}. Marking for removal.")
            unauthorized_ids.append(chat_id) # Mark for removal later
            failed_ids.append(chat_id)
        except BadRequest as e:
            logger.error(f"Failed to send to {chat_id}: BadRequest - {e}")
            if "chat not found" in str(e).lower():
                logger.warning(f"Chat {chat_id} not found. Marking for removal.")
                unauthorized_ids.append(chat_id) # Mark for removal later
            failed_ids.append(chat_id)
        except (TimedOut, NetworkError) as e:
            logger.warning(f"Network/Timeout error sending to {chat_id}: {e}. Will retry next cycle.")
            # Don't remove on temporary errors
            failed_ids.append(chat_id)
        except TelegramError as e:
            logger.error(f"Telegram error sending to {chat_id}: {e}")
            failed_ids.append(chat_id)
        except Exception as e:
            logger.error(f"Unexpected error sending message to {chat_id}: {e}")
            failed_ids.append(chat_id)

    logger.info(f"Notifications sent attempt complete. Success: {sent_count}/{len(chat_ids)}. Failures: {len(failed_ids)}")

    # Remove unauthorized/not found users after the loop
    if unauthorized_ids:
        logger.info(f"Removing {len(unauthorized_ids)} users due to Unauthorized/BadRequest errors.")
        for chat_id in unauthorized_ids:
            delete_chat_id(chat_id)

def compare_current_and_existing(current_set: set[str], existing_set: set[str], bot, typ) -> list[str]:
    new_announcements_ordered = []
    for ann in current_set:
        stripped_ann = ann.strip()
        if stripped_ann and stripped_ann not in existing_set:
            new_announcements_ordered.append(stripped_ann)

    if new_announcements_ordered:
        logger.info(f"Found {len(new_announcements_ordered)} new {typ.upper()} announcement(s) in order.")
        # Log the new announcements found (optional, good for debugging)
        # for i, ann in enumerate(new_announcements_ordered):
        #    logger.debug(f"  New {i+1}: {ann}")

        chat_ids = get_chat_ids()
        chat_ids = chat_ids[chat_ids[typ + '_announcements'] == 1]['id'].tolist()
        if chat_ids:
            logger.info(f"Notifying {len(chat_ids)} users about {typ.upper()}...")
            notify_users(bot, new_announcements_ordered, chat_ids, typ)
        else:
            logger.info(f"No users subscribed for {typ.upper()} notifications.")

        save_announcements(new_announcements_ordered, table=typ)
    else:
        logger.info(f"No new {typ.upper()} announcements found.")
    logger.info(f"Finished job: check_announcements_job for {typ.upper()}")
    

def check_announcements_job(context: CallbackContext):
    logger.info("Running job: check_announcements_job")
    bot = context.bot

    current_YADYOK = fetch_announcements_YADYOK()
    existing_announcements_set_YADYOK = get_announcements_from_db(table='yadyok')
    compare_current_and_existing(current_YADYOK, existing_announcements_set_YADYOK, bot, 'yadyok')
    
    current_MIS = fetch_announcements_MIS()
    existing_announcements_set_MIS = get_announcements_from_db(table='mis')
    compare_current_and_existing(current_MIS, existing_announcements_set_MIS, bot, 'mis')
    
    current_MAIN = fetch_announcements_MAIN()
    existing_announcements_set_MAIN = get_announcements_from_db(table='main')
    compare_current_and_existing(current_MAIN, existing_announcements_set_MAIN, bot, 'main')

    logger.info("Finished job: check_announcements_job")



# --- Main Function ---
def main():
    init_db()

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    job_queue = updater.job_queue

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("status", status))
    dispatcher.add_handler(CommandHandler("latest", latest))
    dispatcher.add_handler(CommandHandler("stop", stop))
    
    dispatcher.add_handler(CommandHandler("subscribe_main", subscribe_to_main))
    dispatcher.add_handler(CommandHandler("unsubscribe_main", unsubscribe_from_main))
    dispatcher.add_handler(CommandHandler("subscribe_yadyok", subscribe_to_yadyok))
    dispatcher.add_handler(CommandHandler("unsubscribe_yadyok", unsubscribe_from_yadyok))
    dispatcher.add_handler(CommandHandler("subscribe_mis", subscribe_to_mis))
    dispatcher.add_handler(CommandHandler("unsubscribe_mis", unsubscribe_from_mis))
    
    
    logger.info("Command handlers registered.")

    job_queue.run_repeating(
        check_announcements_job,
        interval=3600, # Check every hour
        # interval=60, # DEBUG: Check every minute
        first=10,
        name="check_announcements"
    )
    logger.info("Scheduled announcement check job (every hour).")

    logger.info("Starting bot polling...")
    updater.start_polling()
    logger.info("Bot started successfully.")
    updater.idle()
    logger.info("Bot stopped.")

if __name__ == '__main__':
    main()