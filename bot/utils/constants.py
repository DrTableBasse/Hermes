import os

LOG_CHANNEL_NAME       = "all-logs"
VOICE_LOG_CHANNEL_NAME = "logs-vocal"

COG_DIRECTORIES = ('fun', 'moderation', 'system', 'gamification', 'utilities')


def cogs_names() -> list[str]:
    result = []
    base = os.path.join(os.path.dirname(__file__), '..', 'cogs')
    for directory in COG_DIRECTORIES:
        path = os.path.join(base, directory)
        if not os.path.isdir(path):
            continue
        for filename in sorted(os.listdir(path)):
            if filename.endswith('.py') and filename != '__init__.py':
                result.append(f'cogs.{directory}.{filename[:-3]}')
    return result


def get_env_var(name: str, required: bool = True) -> str | None:
    value = os.getenv(name)
    if required and not value:
        raise ValueError(f"Variable d'environnement '{name}' manquante")
    return value
