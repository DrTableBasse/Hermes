import paramiko
import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

host = "192.168.10.62"
user = "ubuntu"
password = "Soldat21*/!!"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, password=password, timeout=15)

sftp = client.open_sftp()
local_path = r"C:\Users\nuezs\Documents\Informatique\Github\Hermes\web-api\middleware\auth_middleware.py"
remote_path = "/home/ubuntu/auth_middleware_fix.py"
sftp.put(local_path, remote_path)
sftp.close()
print("Fichier uploade")

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out + err

rc, out = run("docker cp /home/ubuntu/auth_middleware_fix.py hermes-v2-web-api-1:/app/middleware/auth_middleware.py 2>&1")
print("docker cp:", out.strip(), "exit:", rc)

rc, out = run("cd Hermes-v2 && docker compose restart web-api 2>&1", timeout=30)
print(out[-300:].strip())

time.sleep(8)

rc, out = run("cd Hermes-v2 && docker compose ps web-api 2>&1")
print(out)
print("Essaie de creer un ticket !")

client.close()
