from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_ip(request: Request) -> str:
    """IP réelle du visiteur.

    web-api n'est joignable que par le proxy Next.js (réseau Docker interne) ;
    sans ce relais, tous les visiteurs partageraient l'IP du conteneur `web`
    et donc un seul compteur. Le proxy écrase `X-Client-IP` avec l'IP qu'il a
    lui-même déterminée, la valeur envoyée par le navigateur n'arrive jamais ici.
    """
    ip = request.headers.get("x-client-ip", "").strip()
    return ip or get_remote_address(request)


# Limite par défaut sur toutes les routes ; les routes sensibles ajoutent la leur.
limiter = Limiter(key_func=client_ip, default_limits=["120/minute"])
