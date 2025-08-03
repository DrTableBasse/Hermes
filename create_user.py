#!/usr/bin/env python3
"""
Script pour créer l'utilisateur hermes_bot dans PostgreSQL
Utilise Docker pour se connecter à la base de données
"""

import subprocess
import sys

def run_docker_command(command, description):
    """Exécute une commande Docker et affiche le résultat"""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - Succès")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} - Échec")
            print(f"Erreur: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - Exception: {e}")
        return False

def main():
    print("🚀 Création de l'utilisateur hermes_bot dans PostgreSQL")
    print("=" * 60)
    
    # Vérifier que le conteneur PostgreSQL est en cours d'exécution
    if not run_docker_command("sudo docker ps --filter name=saucisseland-postgres --format '{{.Status}}'", "Vérification du conteneur PostgreSQL"):
        print("❌ Le conteneur PostgreSQL n'est pas en cours d'exécution")
        print("💡 Démarrez-le avec: sudo docker compose up -d db")
        return
    
    # Script SQL pour créer l'utilisateur
    create_user_sql = """
    -- Créer l'utilisateur hermes_bot s'il n'existe pas
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'hermes_bot') THEN
            CREATE USER hermes_bot WITH PASSWORD 'bot_password_2024';
        END IF;
    END
    $$;
    
    -- Accorder les permissions
    GRANT ALL PRIVILEGES ON DATABASE saucisseland TO hermes_bot;
    GRANT ALL ON SCHEMA public TO hermes_bot;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hermes_bot;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO hermes_bot;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO hermes_bot;
    """
    
    # Écrire le script SQL dans un fichier temporaire
    with open("create_hermes_bot.sql", "w") as f:
        f.write(create_user_sql)
    
    # Exécuter le script SQL dans le conteneur PostgreSQL
    docker_command = f"sudo docker exec -i saucisseland-postgres psql -U postgres -d saucisseland -f - < create_hermes_bot.sql"
    
    if run_docker_command(docker_command, "Création de l'utilisateur hermes_bot"):
        print("✅ Utilisateur hermes_bot créé avec succès")
    else:
        print("❌ Échec de la création de l'utilisateur hermes_bot")
        return
    
    # Tester la connexion avec hermes_bot
    test_sql = "SELECT version();"
    test_command = f"echo '{test_sql}' | sudo docker exec -i saucisseland-postgres psql -U hermes_bot -d saucisseland"
    
    if run_docker_command(test_command, "Test de connexion avec hermes_bot"):
        print("\n🎉 Configuration PostgreSQL terminée avec succès!")
        print("📝 L'utilisateur hermes_bot est maintenant configuré")
        print("💡 Vous pouvez maintenant démarrer le bot avec: python3 main.py")
    else:
        print("\n❌ Échec du test de connexion")
        print("💡 Vérifiez les logs ci-dessus pour plus de détails")
    
    # Nettoyer le fichier temporaire
    import os
    os.remove("create_hermes_bot.sql")

if __name__ == "__main__":
    main() 