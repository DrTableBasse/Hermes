"""État d'exécution partagé du processus bot."""
from datetime import datetime, timezone

# Horodatage de démarrage du processus (import de ce module ≈ lancement du bot).
STARTED_AT: datetime = datetime.now(timezone.utc)
