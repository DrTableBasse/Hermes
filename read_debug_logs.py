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

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out + err

rc, out = run("cd Hermes-v2 && docker compose logs web-api --tail=60 2>&1")
for line in out.splitlines():
    if "DEBUG" in line or "WARNING" in line or "401" in line or "POST" in line or "tickets" in line.lower():
        print(line)

client.close()
