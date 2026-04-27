"""
Script de test pour vérifier la synchronisation des membres Discord
"""
import asyncio
import os
from dotenv import load_dotenv
from utils.database import voice_manager, db_manager

load_dotenv()

async def test_sync():
    """Test de la synchronisation d'un membre"""
    try:
        # Initialiser la base de données
        await db_manager.initialize()
        print("✅ Base de données initialisée")
        
        # Test de synchronisation d'un membre fictif
        test_user_id = 123456789012345678
        test_username = "test_user"
        test_nickname = "Test Nickname"
        
        result = await voice_manager.sync_member(test_user_id, test_username, test_nickname)
        if result:
            print(f"✅ Membre synchronisé: {test_username} ({test_user_id})")
        else:
            print(f"❌ Échec de la synchronisation")
        
        # Test de recherche
        found = await voice_manager.find_user_by_username_or_nickname("test_user")
        if found:
            print(f"✅ Utilisateur trouvé: {found}")
        else:
            print("❌ Utilisateur non trouvé")
        
        # Test de recherche par nickname
        found = await voice_manager.find_user_by_username_or_nickname("Test Nickname")
        if found:
            print(f"✅ Utilisateur trouvé par nickname: {found}")
        else:
            print("❌ Utilisateur non trouvé par nickname")
        
        # Nettoyer le test
        async with db_manager.get_connection() as conn:
            await conn.execute("DELETE FROM user_voice_data WHERE user_id = $1", test_user_id)
            print("🧹 Données de test supprimées")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sync())

