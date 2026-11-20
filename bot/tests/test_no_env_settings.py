"""Les réglages du registre se lisent en base (utils.settings), jamais dans l'environnement."""
import os
import re
import sys

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BOT_DIR)

from utils.settings_registry import SETTINGS  # noqa: E402

# Seuls ces fichiers lisent les anciens noms : l'amorçage depuis .env et le registre lui-même.
_ALLOWED = {
    os.path.join("utils", "settings.py"),
    os.path.join("utils", "settings_registry.py"),
}
# Tout littéral égal à un ancien nom : couvre getenv('X') comme les noms passés à un
# assistant (ex. _get_channel_id('ADMIN_LOG_CHANNEL_ID')) avant d'atteindre getenv.
_ENV_READ = re.compile(r"""['"]([A-Z][A-Z0-9_]+)['"]""")


def _offenders() -> list[str]:
    registry_env = {d.env for d in SETTINGS.values() if d.env}
    found = []
    for root, dirs, files in os.walk(BOT_DIR):
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, BOT_DIR)
            if rel in _ALLOWED:
                continue
            with open(path, encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    for var in _ENV_READ.findall(line):
                        if var in registry_env:
                            found.append(f"{rel}:{lineno} {var}")
    return found


def test_no_registry_env_read_in_code():
    offenders = _offenders()
    assert not offenders, "Lectures d'environnement à migrer vers utils.settings :\n" + "\n".join(offenders)
