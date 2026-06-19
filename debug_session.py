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

# 1. Check sessions in DB
print("=== Sessions actives en DB ===")
rc, out = run(
    'cd Hermes-v2 && docker compose exec -T db psql -U hermes -d hermes -c '
    '"SELECT id, token, \\"expiresAt\\" FROM session ORDER BY \\"expiresAt\\" DESC LIMIT 5;" 2>&1'
)
print(out)

# 2. Add debug logging to auth middleware temporarily
print("=== Auth middleware actuel ===")
rc, out = run("cat Hermes-v2/web-api/middleware/auth_middleware.py")
print(out)

# 3. Check if other client-side POST endpoints that require auth exist and work
# Try to find if any other endpoint is called client-side with auth
print("=== Recherche d'autres POST avec auth dans les logs ===")
rc, out = run("cd Hermes-v2 && docker compose logs web-api --tail=200 2>&1")
for line in out.splitlines():
    if "POST" in line or "401" in line or "403" in line:
        print(line)

client.close()
