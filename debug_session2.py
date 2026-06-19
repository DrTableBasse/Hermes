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

# Schema exact de la table session
print("=== Schema table session ===")
rc, out = run(
    'cd Hermes-v2 && docker compose exec -T db psql -U hermes -d hermes -c '
    r'"\\d session" 2>&1'
)
print(out)

# Check toutes les colonnes de la session valide
print("=== Session valide complete ===")
rc, out = run(
    'cd Hermes-v2 && docker compose exec -T db psql -U hermes -d hermes -c '
    '"SELECT * FROM session WHERE \\"expiresAt\\" > NOW();" 2>&1'
)
print(out)

# Ajouter du debug dans auth_middleware pour voir le token recu
print("=== Ajout debug logging dans auth_middleware ===")
debug_code = '''import logging
logger = logging.getLogger(__name__)

async def get_current_user(
    session_token: Optional[str] = Cookie(None, alias="better-auth.session_token"),
) -> dict:
    logger.warning("TOKEN RECU: %r", session_token[:20] if session_token else None)
    if not session_token:
        raise HTTPException(status_code=401, detail="Non authentifié")
    user = await _fetch_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")
    return user
'''
print(debug_code)

client.close()
