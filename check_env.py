import paramiko
import sys
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

print("=== .env vars pertinents ===")
rc, out = run("grep NEXT_PUBLIC Hermes-v2/.env; grep BOT_API Hermes-v2/.env")
print(out)

print("\n=== web-api logs recents (erreurs auth) ===")
rc, out = run("cd Hermes-v2 && docker compose logs web-api --tail=100 2>&1")
# filter lines with 401 or error
for line in out.splitlines():
    if "401" in line or "ERROR" in line or "WARNING" in line or "session" in line.lower():
        print(line)

print("\n=== Test appel POST tickets depuis le serveur ===")
rc, out = run(
    "curl -s -o /dev/null -w '%{http_code}' -X POST "
    "http://localhost:3000/api/proxy/tickets "
    "-H 'Content-Type: application/json' "
    "-d '{\"title\": \"test\"}'"
)
print("HTTP status (no cookie):", out)

client.close()
