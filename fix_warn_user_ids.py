"""
Script pour corriger les IDs utilisateur incorrects dans les warns.

Ce script permet de corriger les warns qui ont été enregistrés avec un mauvais user_id.
"""
import asyncio
import os
from dotenv import load_dotenv
from utils.database import DatabaseManager, WarnManager

load_dotenv()

async def fix_warn_user_ids():
    """Corrige les IDs utilisateur dans les warns."""
    print("=" * 60)
    print("CORRECTION DES IDs UTILISATEUR DANS LES WARNS")
    print("=" * 60)
    
    # Configuration
    OLD_USER_ID = 279205522970902530  # ID incorrect
    NEW_USER_ID = 279205522970902528  # ID correct (Dr.TableBasse)
    
    print(f"\nAncien ID (incorrect): {OLD_USER_ID}")
    print(f"Nouvel ID (correct): {NEW_USER_ID}")
    print(f"\n[ATTENTION] Cette operation va modifier les warns dans la base de donnees.")
    
    # Accepter --yes pour exécution automatique
    import sys
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv
    
    if not auto_confirm:
        # Demander confirmation
        try:
            confirmation = input("\nVoulez-vous continuer ? (oui/non): ").strip().lower()
            if confirmation not in ['oui', 'o', 'yes', 'y']:
                print("[ERREUR] Operation annulee.")
                return
        except EOFError:
            print("\n[INFO] Mode non-interactif detecte. Utilisez --yes pour executer automatiquement.")
            print("[ERREUR] Operation annulee.")
            return
    else:
        print("\n[INFO] Mode automatique active (--yes)")
    
    try:
        # Initialiser la base de données
        db_manager = DatabaseManager()
        await db_manager.initialize()
        warn_manager = WarnManager(db_manager)
        
        print("\n[INFO] Verification des warns avant correction...")
        
        # Vérifier les warns avec l'ancien ID
        old_warns = await warn_manager.get_user_warns(OLD_USER_ID)
        old_count = await warn_manager.get_warn_count(OLD_USER_ID)
        
        print(f"  Warns avec l'ancien ID ({OLD_USER_ID}): {old_count}")
        if old_warns:
            print(f"  Détails:")
            for warn in old_warns[:5]:  # Afficher les 5 premiers
                print(f"    - Warn #{warn.get('id')}: {warn.get('reason', 'N/A')}")
        
        # Vérifier les warns avec le nouvel ID
        new_warns = await warn_manager.get_user_warns(NEW_USER_ID)
        new_count = await warn_manager.get_warn_count(NEW_USER_ID)
        
        print(f"\n  Warns avec le nouvel ID ({NEW_USER_ID}): {new_count}")
        if new_warns:
            print(f"  Détails:")
            for warn in new_warns[:5]:  # Afficher les 5 premiers
                print(f"    - Warn #{warn.get('id')}: {warn.get('reason', 'N/A')}")
        
        if old_count == 0:
            print("\n[INFO] Aucun warn a corriger avec l'ancien ID.")
            return
        
        # Corriger les IDs
        print(f"\n[INFO] Correction des warns...")
        fixed_count = await warn_manager.fix_user_id_in_warns(OLD_USER_ID, NEW_USER_ID)
        
        print(f"[SUCCES] {fixed_count} warn(s) corrige(s)")
        
        # Vérifier après correction
        print("\n[INFO] Verification apres correction...")
        new_warns_after = await warn_manager.get_user_warns(NEW_USER_ID)
        new_count_after = await warn_manager.get_warn_count(NEW_USER_ID)
        
        print(f"  Warns avec le nouvel ID ({NEW_USER_ID}): {new_count_after}")
        if new_warns_after:
            print(f"  Détails:")
            for warn in new_warns_after[:5]:  # Afficher les 5 premiers
                print(f"    - Warn #{warn.get('id')}: {warn.get('reason', 'N/A')}")
        
        old_warns_after = await warn_manager.get_user_warns(OLD_USER_ID)
        old_count_after = await warn_manager.get_warn_count(OLD_USER_ID)
        
        print(f"\n  Warns avec l'ancien ID ({OLD_USER_ID}): {old_count_after}")
        
        if old_count_after == 0 and new_count_after == old_count:
            print("\n[SUCCES] Correction reussie ! Tous les warns ont ete transferes.")
        else:
            print(f"\n[ATTENTION] {old_count_after} warn(s) restent avec l'ancien ID.")
        
        # Fermer la connexion
        await db_manager.close()
        
        print("\n" + "=" * 60)
        print("FIN DE LA CORRECTION")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERREUR] Erreur lors de la correction: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_warn_user_ids())

