from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_ip(request: Request) -> str:
    """IP réelle du visiteur.

    web-api n'est joignable que depuis le réseau Docker interne ; sans ce relais,
    tous les visiteurs partageraient l'IP du conteneur `web` et donc un seul
    compteur. `X-Client-IP` est posé d'autorité dans le conteneur `web` par
    `web/runtime/client-ip.cjs`, avant Next, sur chaque requête entrante (IP de
    la socket, ou en-tête `TRUSTED_IP_HEADER` du proxy de confiance) : la valeur
    envoyée par le navigateur est écrasée, y compris sur le rewrite `/media/*`.
    """
    ip = request.headers.get("x-client-ip", "").strip()
    return ip or get_remote_address(request)


# Limite par défaut sur toutes les routes ; les routes sensibles ajoutent la leur.
limiter = Limiter(key_func=client_ip, default_limits=["120/minute"])
