# Synchronisation des Membres Discord dans la Base de Données

## 📋 Vue d'ensemble

Ce système permet de synchroniser tous les membres Discord dans la base de données PostgreSQL partagée entre le bot Hermes et le site web Saucisse-Land. Cela résout le problème de la limite de 1000 membres de l'API Discord pour la recherche d'utilisateurs.

## 🗄️ Modifications de la Base de Données

### Migration SQL

Un script de migration a été créé : `migrations/add_nickname_to_user_voice_data.sql`

Pour l'appliquer :
```bash
psql -U hermes_bot -d saucisseland -f migrations/add_nickname_to_user_voice_data.sql
```

### Changements

- **Colonne `nickname`** ajoutée à la table `user_voice_data`
  - Stocke le pseudo Discord sur le serveur (nickname)
  - NULL si identique au username
  - Type: VARCHAR(255)

- **Index créés** pour améliorer les performances :
  - `idx_user_voice_username` sur `username`
  - `idx_user_voice_nickname` sur `nickname`

## 🤖 Modifications du Bot Hermes

### 1. Synchronisation Automatique

- **Au démarrage** : Tous les membres du serveur sont synchronisés automatiquement
- **Événements Discord** :
  - `on_member_join` : Synchronise les nouveaux membres
  - `on_member_update` : Met à jour les membres quand leur pseudo change

### 2. Commande de Synchronisation Manuelle

- **Commande** : `/sync-members`
- **Description** : Synchronise tous les membres du serveur dans la base de données
- **Utilisation** : Utile pour forcer une resynchronisation complète

### 3. Méthodes Ajoutées

Dans `VoiceDataManager` :
- `sync_member(user_id, username, nickname)` : Synchronise un membre
- `find_user_by_username_or_nickname(search_term)` : Recherche un utilisateur

## 🌐 Modifications du Site Web

### Backend (FastAPI)

- **Méthode modifiée** : `DiscordService.find_user_by_username()`
  - Utilise maintenant la base de données au lieu de l'API Discord
  - Recherche par `username` ou `nickname`
  - Priorité aux correspondances exactes
  - Fallback vers l'API Discord en cas d'erreur BDD

### Avantages

✅ Pas de limite de 1000 membres  
✅ Recherche plus rapide (index SQL)  
✅ Fonctionne même si l'API Discord est indisponible  
✅ Recherche par username ou nickname  

## 🧪 Tests

Un script de test est disponible : `test_sync.py`

Pour l'exécuter :
```bash
python test_sync.py
```

## 📝 Notes Importantes

1. **Première synchronisation** : La synchronisation initiale peut prendre du temps selon le nombre de membres
2. **Mise à jour en temps réel** : Les changements de pseudo sont détectés automatiquement
3. **Performance** : Les index SQL garantissent des recherches rapides même avec beaucoup de membres

## 🔧 Dépannage

### Si la synchronisation ne fonctionne pas

1. Vérifier que la migration SQL a été appliquée
2. Vérifier les permissions de la base de données
3. Vérifier les logs du bot pour les erreurs
4. Utiliser `/sync-members` pour forcer une resynchronisation

### Si la recherche ne trouve pas d'utilisateurs

1. Vérifier que les membres ont été synchronisés
2. Vérifier que la recherche utilise bien la base de données (logs backend)
3. Vérifier les index SQL sont créés

