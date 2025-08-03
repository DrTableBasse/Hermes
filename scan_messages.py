#!/usr/bin/env python3
"""
Script de lancement pour le scan des messages Discord
"""

import asyncio
import sys
import os

# Ajouter le répertoire scripts au path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

async def main():
    print("🚀 Lancement du scan des messages Discord...")
    print("⚠️  Ce processus peut prendre plusieurs minutes selon le nombre de messages")
    print("📊 Les catégories suivantes seront exclues:")
    print("   - 777116825250168852")
    print("   - 777139814599491584") 
    print("   - 989815462755962890")
    print()
    
    try:
        from message_stats_scanner import MessageStatsScanner
        scanner = MessageStatsScanner()
        await scanner.run_scan()
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        print("Assurez-vous que le fichier scripts/message_stats_scanner.py existe")
    except Exception as e:
        print(f"❌ Erreur lors du scan: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 