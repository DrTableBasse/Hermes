import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

host = "192.168.10.62"
user = "ubuntu"
password = "Soldat21*/!!"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=password, timeout=15)

sftp = client.open_sftp()

# Upload the modified auth_middleware.py
local_path = r"C:\Users\nuezs\Documents\Informatique\Github\Hermes\web-api\middleware\auth_middleware.py"
remote_path = "/home/ubuntu/Hermes-v2/web-api/middleware/auth_middleware.py"
sftp.put(local_path, remote_path)
print("Fichier auth_middleware.py copie sur le serveur")
sftp.close()

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out + err

# Rebuild web-api (no-cache needed for Python file changes without rebuild? Let's just restart)
print("Redemarrage web-api...")
rc, out = run("cd Hermes-v2 && docker compose restart web-api 2>&1", timeout=30)
print(out)
print("exit:", rc)

import time
time.sleep(5)

print("Status:")
rc, out = run("cd Hermes-v2 && docker compose ps web-api 2>&1")
print(out)

print("\nREADY - Essaie de creer un ticket maintenant, puis je lirai les logs")
client.close()
