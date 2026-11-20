# Refonte du site SaucisseLand (web-v2) — document de conception

Date : 2026-11-20 · Statut : à valider

## 1. Intention

Le site actuel (`web/`, Next.js 14) est jugé « pas fifou » : look sombre générique, pas d'identité, pas de
composants partagés. Le propriétaire veut une **vitrine gaming premium** qui donne envie de rejoindre le
Discord **SaucisseLand / les Généraux Saucisses** : communauté multi-gaming, chill, safe place, humour
décalé dans les détails. Il veut aussi une **stack à jour** (Next 16, React 19, Tailwind 4, next-intl 4).

Maquette de référence validée, section par section, avec le propriétaire :
https://claude.ai/artifact/Aa2fWfJSQVrdJaBgZ9D6ip (source : `saucisseland-vitrine.html`, à copier dans
`docs/superpowers/specs/assets/` au démarrage du chantier). Cadres Figma « Hero D · Fusion A + C » et
« 02 · La caserne en direct » dans le fichier Figma `aByuYyYfsCkTYJsNO0GK0U`.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- Nouvelle identité appliquée à **tout** le site (vitrine + pages existantes + admin).
- Accueil court fait d'aperçus ; le détail vit sur des pages dédiées.
- Données réelles partout où elles existent ; sections branchées sur Hermes (bot) pour le direct.
- Code propre : design system (tokens + composants), une seule couche d'accès API, types stricts.
- Stack à jour, sans faille connue.

**Non-objectifs**
- Thème clair (abandonné : sombre uniquement).
- Réseau social (fil, MP, amis) : le site reste une vitrine + espace membre.
- Réécrire le bot ou web-api au-delà des endpoints nécessaires.

**Anti-objectifs (échec même si ça « marche »)**
- Look « généré par IA » : mêmes cartes partout, dégradé violet générique, emoji comme icônes de section.
- Les mêmes éléments répétés entre l'accueil et les pages (le propriétaire l'a explicitement rejeté).
- Chiffres présentés comme réels alors qu'ils sont fictifs.
- Casser le site en production pendant les travaux.

## 3. Contraintes

- Stack Docker existante (`compose.yml`) : db PostgreSQL 15, bot (API interne :8001 non publiée,
  métriques :9101), web-api (interne :8000), web (:3000). Déploiement : push `main` puis
  `git pull && docker compose up -d --build` sur `ubuntu@192.168.10.62:~/Hermes-v2`.
- web-api reste interne ; tout passe par le proxy Next.js `/api/proxy/[...path]` (qui pose `X-Client-IP`).
- Authentification **better-auth** (Discord OAuth2), sessions dans PostgreSQL, validées par web-api.
  Les deux sites (ancien et v2) partagent la même base et le même schéma better-auth.
- Les identifiants Discord (snowflakes) dépassent la précision des nombres JavaScript : **ils doivent
  transiter en chaînes** dans toutes les réponses JSON consommées par web-v2.
- Animations : respect de `prefers-reduced-motion` ; accessibilité AA.
- Logo et mascotte : **non inventés** ; emplacement réservé, logo fourni plus tard par le propriétaire.
- Visuels des jeux : **visuels officiels** souhaités ; droits à vérifier ; emplacements stylés en attendant.

## 4. Approches envisagées

| Approche | Pour | Contre |
|---|---|---|
| **1. Nouveau `web-v2/` sur la stack à jour, portage page par page, bascule à la fin** (retenue) | Aucun travail fait deux fois ; code propre dès le départ ; l'ancien site reste en ligne | Deux sites coexistent quelques semaines |
| 2. Monter l'ancien site de version puis refaire le design | Chaque étape déployable | On adapte à Tailwind 4 du code destiné à disparaître |
| 3. Refaire le design sur la stack actuelle puis monter de version | Résultat visible le plus vite | Tout le nouveau code migré une seconde fois |

Le propriétaire a délégué le choix ; l'approche 1 est retenue.

## 5. Décisions (prises avec le propriétaire)

### 5.1 Identité visuelle
- Sombre uniquement. Fond anthracite bleuté **en un seul dégradé continu sur toute la page** (pas de
  coupure de couleur entre sections), halos violet/cyan, touches orange, particules discrètes, grille
  légère, sol en grille en perspective sous le hero.
- Couleurs (tokens) : fond `#0C0E1A`, panneaux `#13162A`/`#171A2E`, violet `#9B6BFF`→`#6E5BFF`,
  cyan `#3FE0F0`, bleu `#4D7CFF`, orange `#FF8A3D`, vert `#3BD16F`, texte `#EDEBFA`, atténué `#9A97B8`.
- Typographie : **Bricolage Grotesque** (titres, 700/800) + **Instrument Sans** (texte).
- Cartes sombres épurées ; effet verre réservé aux éléments clés (barre de navigation, fenêtres Discord).
- Menu : barre flottante translucide floutée — logo à gauche, liens au centre, bouton « Rejoindre Discord ».
- Humour : dans les textes, grades charcutiers, easter eggs (curseur saucisse sur le bouton principal,
  saucisse sur la barre d'XP), console d'Hermes aux logs absurdes, ton d'Hermes **pince-sans-rire**.

### 5.2 Grades (affichés partout où un niveau apparaît)
Recrue Cocktail → Caporal Chipolata → Sergent Merguez → Lieutenant Toulouse → Colonel Saucisson →
Général Saucisse. Seuils de niveau : voir §8 (recalibrés sur la distribution réelle).

### 5.3 Pages et navigation
Menu : Accueil, Jeux (ancre), Progression, Hermes, Galerie. Pied de page : + L'état-major, Règlement,
Mentions légales, Contacter le staff. Espace connecté : Profil, Quêtes, Tickets, Admin (selon rôle).

**Accueil (ordre validé), uniquement des aperçus :**
1. Hero « fusion A + C » : titre « Bienvenue à SaucisseLand », accroche militaire (« Garde-à-vous,
   recrue… »), 2 boutons, chips de grades, compteurs ; à droite pile de 3 fenêtres Discord (vocal
   « Cantine des Généraux », salon #général avec message d'Hermes, carte profil) + satellites reliés.
2. La caserne en direct : 4 cartes (membres, en ligne + courbe 24 h, en vocal + avatars, messages du
   jour) + fil d'activité.
3. Nos jeux : jeu de la semaine en vedette + **bandeau défilant en continu** (pause au survol) des 7 jeux
   (War Dogs, Dead by Daylight, League of Legends, Warframe, Overwatch, Fortnite, Minecraft), bouton
   « Trouver des joueurs ».
4. Prochains events : event vedette avec **compte à rebours**, organisateur + grade, inscrits/places,
   récompense XP, bouton « Je viens » (ouvre l'event Discord) ; liste des suivants.
5. Aperçu progression : **frise des 6 grades** (pas de classement ici).
6. Aperçu Hermes : démonstration de la commande `/rang` dans une fenêtre Discord (pas de console ici).
7. Aperçu galerie : les 3 moments de la semaine (pas de bandeau ici).
8. Appel final « Rejoins les Généraux Saucisses » (**accueil uniquement**) + pied de page en colonnes.

**Pages dédiées :**
- `/progression` : fiche de personnage RPG (échelle des grades, fiche d'exemple « toi dans 3 semaines »
  clairement marquée, quêtes de la semaine, vitrine de succès par rareté) + classement réel.
- `/hermes` : tableau de bord (statut en ligne, temps de réponse, disponibilité 30 j, commandes servies),
  rapport du jour avec mini-graphiques, **console de logs absurdes**, grille des commandes commentées.
- `/galerie` : deux bandeaux défilants en sens inverse, clic = aperçu agrandi, Échap pour fermer.
- `/etat-major` : cartes du staff (avatar, rôle, grade militaire, phrase perso, jeux, bouton
  « Contacter via un ticket »).
- Pages existantes portées et restylées : classement, profil public `/u/[id]`, profil, quêtes,
  articles + éditeur, comparaison, top semaine, tickets, admin (découpé en sous-composants).

### 5.4 Sources de données
| Donnée | Source |
|---|---|
| XP, niveaux, séries, quêtes, succès, classements, invitations, articles | Tables existantes via web-api |
| Chiffres en direct (membres, en ligne, en vocal, messages du jour, courbe 24 h) | **Nouveau** : endpoint du bot (lecture guild), exposé par web-api avec cache court et budget de temps ; si le bot ne répond pas, la section affiche les dernières valeurs connues ou se masque |
| Events | **Nouveau** : événements programmés Discord (guild scheduled events) lus par le bot ; récompense XP et grade de l'organisateur calculés côté web-api |
| Galerie | **Nouvelle table** `gallery_items` ; les membres postent dans `#galerie`, un membre du staff valide par réaction, Hermes enregistre (image téléchargée dans le volume média partagé, ou URL de clip) |
| État-major | **Nouveau** : membres portant les rôles staff (lus par le bot) + textes (grade, phrase, jeux) éditables dans l'admin (nouvelle table `staff_profiles`) |
| Statut et stats d'Hermes | **Nouveau** : endpoint du bot (latence, disponibilité, commandes servies, XP distribuée du jour, succès, tickets, rappels de bump) |
| Logs absurdes de la console | Liste statique côté site (humour, assumé comme tel) |
| Fiche « toi dans 3 semaines » | Données d'exemple marquées « Exemple » |

### 5.5 Stack web-v2
Next.js 16 (App Router, `output: 'standalone'`), React 19, Tailwind CSS 4 (tokens en variables CSS),
composants shadcn/ui compatibles Tailwind 4, next-intl 4 (français par défaut ; anglais conservé si
le coût reste faible, sinon français seul — au choix du constructeur après mesure), better-auth 1.7,
icônes lucide. Animations en CSS, bibliothèque d'animation seulement si un besoin le justifie.

### 5.6 Transition
- `web-v2` ajouté à `compose.yml` comme service séparé, publié sur un port de test (ex. 3002) le temps
  du chantier ; même base, même web-api, même schéma better-auth.
- Bascule : `web-v2` reprend le port 3000 et l'URL de production, `web/` est supprimé.
- Chaque étape est commitée et déployée sur le port de test ; la bascule fait l'objet d'une validation
  explicite du propriétaire.

## 6. Ce qui reste au constructeur
Découpage des composants, structure des dossiers, choix exacts des requêtes et des index, stratégie de
cache des endpoints du bot, détails responsive (règle : même page simplifiée sur mobile — fenêtres
empilées, bandeaux défilants conservés, animations allégées), tests (aucun n'existe aujourd'hui :
ajouter au minimum des tests des endpoints nouveaux et du calcul des grades).

## 7. Hors périmètre (chantiers suivants)
File d'actions site → bot (outbox + LISTEN/NOTIFY), notifications en direct, tickets bidirectionnels,
découpage des grosses routes web-api, nettoyage des logiques d'achievements dupliquées.

## 8. Réponses après relecture

### Décidé par le propriétaire
- **Seuils des grades** (calés sur la distribution réelle : médiane niveau 3, 99e centile niveau 44,
  maximum 90) : Recrue Cocktail 1-2 · Caporal Chipolata 3-7 · Sergent Merguez 8-14 ·
  Lieutenant Toulouse 15-24 · Colonel Saucisson 25-44 · Général Saucisse 45+.
  Source de vérité : **table `grades` (level_min, nom, couleur)**, lue par web-api et par le bot.
  Aucun rôle Discord de niveau n'existe aujourd'hui (`XP_LEVEL_ROLES` vide) : les grades sont
  d'abord un affichage site + bot (`/rang`) ; les rôles Discord par grade sont hors périmètre.
- **Events** : affichage seul. Source = événements programmés Discord ; « inscrits » = nombre
  d'intéressés Discord (`user_count`) ; « Je viens » = lien vers l'event Discord ; la récompense XP
  est un texte lu dans la description de l'event (convention `XP: 200`), non attribuée automatiquement.
  L'attribution automatique d'XP de présence est un chantier ultérieur.
- **État-major** : membres portant le rôle d'administration (`ADMIN_ROLE_NAME`) ou le rôle de
  modération. Chaque membre du staff édite sa propre phrase et ses jeux ; l'admin édite tout.
- **Domaine** : le site a un domaine public, volontairement non exposé pendant le chantier. web-v2
  n'a ni domaine ni sous-domaine : il tourne uniquement sur le réseau local
  (`http://192.168.10.62:3002`), avec sa propre URL de redirection Discord OAuth
  (`http://192.168.10.62:3002/api/auth/callback/discord`) ajoutée par le propriétaire. Le domaine
  n'intervient qu'à la bascule, où web-v2 reprend la configuration actuelle du port 3000.

### Choix du constructeur (validés ici, modifiables)
- **better-auth** : ancien et nouveau site sont tous deux en 1.7.27 (montée faite le 2026-11-20),
  aucun risque de schéma divergent pendant la transition.
- **Galerie** : salon configuré par variable d'environnement `GALLERY_CHANNEL_ID` ; validation par la
  réaction ✅ d'un membre du staff ; images jpg/png/webp/gif ≤ 10 Mo (mêmes contrôles que
  `web-api/routes/media.py` : magic bytes, nom UUID) ; clips acceptés en lien YouTube, Twitch ou
  Medal ; retrait ou masquage depuis l'admin, et automatiquement si le message Discord est supprimé.
- **Direct** : table `guild_stats_snapshots` alimentée par le bot toutes les 5 minutes (membres,
  en ligne, en vocal, messages), conservée 30 jours ; la courbe 24 h et le « messages du jour » en
  découlent. Disponibilité d'Hermes : enregistrement des battements dès maintenant ; tant que
  30 jours ne sont pas écoulés, la page affiche « depuis le JJ/MM » au lieu d'un chiffre inventé.
- **Contacter via un ticket** : ouvre le formulaire de ticket existant pré-rempli avec la catégorie
  « Contact staff » et le pseudo du membre visé.
- **Langue** : français seul au lancement, structure next-intl conservée pour ajouter l'anglais plus tard.
- **Visuels officiels des jeux** : non bloquants pour la bascule ; emplacements stylés en attendant.
- **Identifiants Discord en chaînes** : corrigé dans web-api pour toutes les routes consommées par web-v2.
