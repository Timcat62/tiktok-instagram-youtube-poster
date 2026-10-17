# 🎬 Social Poster

Publie **une vidéo** sur **YouTube (Shorts)**, **Instagram (Reels)** et **TikTok** en une fois, avec **la même description, les mêmes hashtags et la même cover**.

![Aperçu](docs/screenshot.png)

- 📥 Glisse-dépose une vidéo **verticale ou horizontale** (MP4, MOV, WEBM, MKV…).
- 🖼️ Choisis la **cover parmi les frames de la vidéo** (curseur, image par image, ou bande d'aperçus).
- 📱 Les vidéos **horizontales sont converties en 9:16** pour être publiées comme **Shorts** sur YouTube (fond flouté, bandes noires ou recadrage), avec option pour appliquer aussi ce format à Instagram et TikTok.
- ✅ **Coche ou décoche** les réseaux : publie sur un, deux ou trois. Un réseau non configuré est simplement grisé.
- 🔒 Tout tourne **sur ton ordinateur**. Tes jetons de connexion restent dans le dossier `data/` (jamais envoyé sur GitHub).

---

## ⚠️ À savoir avant de commencer

Chaque réseau impose de créer une **« app développeur »** (gratuite) à ton nom. Ça prend 10 à 20 minutes par réseau, une seule fois. Il y a quelques limites imposées par les plateformes, pas par l'outil :

| Réseau | Limite |
|---|---|
| **YouTube** | Les projets Google **non audités** publient les vidéos en **privé** (verrouillées). Pour publier en public, il faut demander l'[audit de l'API YouTube](https://support.google.com/youtube/contact/yt_api_form) (gratuit, quelques jours ou semaines). Quota par défaut : quelques vidéos par jour. |
| **Instagram** | Le compte doit être **professionnel** (Créateur ou Entreprise) et **lié à une Page Facebook**. Max 100 publications par 24 h via l'API. La connexion dure **60 jours**, ensuite il suffit de cliquer sur « Reconnecter ». |
| **TikTok** | Tant que ton app TikTok **n'est pas auditée**, ton compte TikTok doit être **en privé** et les vidéos sont publiées en **« Moi uniquement »**. Après l'audit, tu choisis librement la visibilité. Alternative sans audit : le mode **« Brouillon »**, qui envoie la vidéo dans ta boîte TikTok pour que tu la publies depuis l'app. |

Autres règles des plateformes :
- **Shorts YouTube** : 3 minutes maximum. Au-delà, la vidéo est publiée comme une vidéo classique.
- **Reels Instagram** : entre 3 secondes et 15 minutes, légende de 2 200 caractères et 30 hashtags maximum.

---

## Installation

1. Installe **Python 3.10 ou plus récent** : <https://www.python.org/downloads/> (sous Windows, coche **« Add python.exe to PATH »**).
2. Télécharge ce projet : bouton vert **Code → Download ZIP**, puis décompresse-le. Tu peux aussi utiliser `git clone https://github.com/Timcat62/tiktok-instagram-youtube-poster.git`.
3. Lance l'application :
   - **Windows** : double-clique sur `run.bat`
   - **macOS / Linux** : `./run.sh` dans un terminal

La première fois, les dépendances s'installent automatiquement (ffmpeg est inclus, rien d'autre à installer). Ensuite l'interface s'ouvre dans ton navigateur sur <http://localhost:8765>.

> Garde la fenêtre noire (le terminal) ouverte pendant que tu utilises l'application.

---

## Configuration des comptes

Tout se fait dans l'onglet **Comptes** de l'application. Tu n'as besoin de configurer **que les réseaux que tu utilises**.

### YouTube

1. Va sur [Google Cloud Console](https://console.cloud.google.com/) et crée un projet (par exemple « Social Poster »).
2. **API et services → Bibliothèque** : cherche **YouTube Data API v3** et clique sur **Activer**.
3. **API et services → Écran de consentement OAuth** :
   - Type d'utilisateur : **Externe**.
   - Renseigne le nom de l'app et ton e-mail.
   - Dans **Audience** (ou « Utilisateurs test »), ajoute ton adresse Gmail.
   - Clique sur **Publier l'application** (passage en *Production*). Sinon Google déconnecte l'app **tous les 7 jours**. Pas besoin de faire valider l'app : Google affichera juste un avertissement « Application non validée ». Clique alors sur *Paramètres avancés → Accéder à …*.
4. **API et services → Identifiants → Créer des identifiants → ID client OAuth** :
   - Type d'application : **Application de bureau**.
   - Télécharge le fichier JSON.
5. Dans l'app : **Importer client_secret.json**, puis **Connecter ma chaîne**. Une page Google s'ouvre : connecte-toi et accepte.
6. *(Optionnel, pour publier en public)* Demande l'[audit de l'API YouTube](https://support.google.com/youtube/contact/yt_api_form).

> **Miniatures personnalisées** : ta chaîne doit être validée par téléphone (<https://www.youtube.com/verify>). Sans ça, la vidéo est quand même publiée, mais sans la cover choisie. Sur les Shorts, YouTube peut aussi afficher sa propre frame dans le fil Shorts.

### Instagram

**Prérequis** : un compte Instagram **Professionnel** (Paramètres → Type de compte → Créateur ou Entreprise), **lié à une Page Facebook** (depuis la Page : Paramètres → Comptes liés → Instagram).

1. Va sur [Meta for Developers](https://developers.facebook.com/apps/) et clique sur **Créer une app**.
   - Cas d'utilisation : **Autre**, puis type **Entreprise** (selon l'interface, le cas d'utilisation peut s'appeler « Gérer les messages et le contenu sur Instagram »).
2. Dans le tableau de bord de l'app, ajoute les produits :
   - **Instagram**, en choisissant **« API setup with Facebook login »** (et non « Instagram login »).
   - **Facebook Login** (ou « Facebook Login for Business »).
3. **Facebook Login → Paramètres → URI de redirection OAuth valides** : ajoute
   `http://localhost:8765/auth/instagram/callback`
   *(en mode développement, Meta autorise souvent `localhost` automatiquement)*
4. **Paramètres de l'app → Général** : copie l'**App ID** et l'**App Secret** dans l'application, puis clique sur **Enregistrer**.
5. Clique sur **Connecter avec Facebook**. Autorise **ta Page** et **ton compte Instagram** quand Facebook le demande.

Ton app peut rester en **mode Développement** : tu peux publier sur ton propre compte, puisque tu es administrateur de l'app.

**Plan B** : si la connexion par redirection pose problème, ouvre le [Graph API Explorer](https://developers.facebook.com/tools/explorer/), sélectionne ton app et génère un *User Token* avec les permissions `instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management`. Colle-le ensuite dans « Plan B » : il est converti automatiquement en jeton de 60 jours.

### TikTok

1. Va sur [TikTok for Developers](https://developers.tiktok.com/apps/), connecte-toi et clique sur **Create app** (une « organisation » ou un compte individuel suffit).
2. Plateforme : coche **Desktop**.
3. Ajoute les produits :
   - **Login Kit** : dans *Redirect URI → Desktop*, ajoute `http://localhost:8765/auth/tiktok/callback/` (avec le `/` final).
   - **Content Posting API** : active **Direct Post**.
4. Scopes : `user.info.basic`, `video.publish`, `video.upload`.
5. Pour tester **sans attendre l'audit** : onglet **Sandbox** → crée un sandbox → ajoute ton compte TikTok dans **Target users**. Utilise ensuite le *Client key* et le *Client secret* **du sandbox**.
6. Passe ton compte TikTok **en privé** (app TikTok → Paramètres → Confidentialité → Compte privé) tant que l'app n'est pas auditée.
7. Dans l'application : renseigne **Client key** et **Client secret**, clique sur **Enregistrer**, puis sur **Connecter TikTok**.

Pour publier en public : soumets ton app à l'audit (*Submit for review*) depuis le portail TikTok. Les vidéos de démonstration demandées peuvent être des captures de cet outil. Une fois l'app validée, remplace les clés du sandbox par celles de production.

---

## Utilisation

1. **Publier** → glisse ta vidéo.
2. Choisis la **cover** avec le curseur, les flèches ◀ ▶ (ou ← → au clavier) ou les vignettes.
3. Si la vidéo est horizontale, choisis le rendu du Short (aperçu en direct).
4. Écris le **titre** (YouTube uniquement), la **description** et les **hashtags** (avec ou sans `#`, séparés par des espaces). La légende finale est `description + hashtags`, identique sur les trois réseaux.
5. Coche les réseaux voulus et clique sur **Publier**. Chaque réseau avance de son côté : si l'un échoue, les autres continuent.

Le brouillon (titre, description, hashtags) et tes choix (réseaux cochés, visibilité…) sont mémorisés dans ton navigateur.

## Comment ça marche

| | YouTube | Instagram | TikTok |
|---|---|---|---|
| API | YouTube Data API v3 (`videos.insert`) | Graph API (Reels, envoi « resumable ») | Content Posting API (Direct Post ou Inbox) |
| Cover | Frame extraite puis envoyée comme miniature (`thumbnails.set`) | `thumb_offset` (position de la frame en ms) | `video_cover_timestamp_ms` |
| Vidéo horizontale | Convertie en 1080×1920 → Short | Telle quelle (ou 9:16 si l'option est cochée) | Telle quelle (ou 9:16 si l'option est cochée) |
| Hashtags | Dans la description + en tags | Dans la légende | Dans la légende |

Si un fichier n'est pas compatible avec Instagram (codec, 4K, plus de 60 i/s, conteneur MKV/WEBM…), il est ré-encodé automatiquement en MP4 H.264. Les vidéos importées sont supprimées automatiquement après 7 jours (`data/uploads`).

## Dépannage

- **« Python est introuvable »** : réinstalle Python en cochant *Add to PATH*.
- **Le port 8765 est déjà utilisé** : change le port avec la variable `PORT`, par exemple `set PORT=8800` puis `run.bat`. Les URI de redirection Instagram/TikTok doivent alors utiliser ce même port.
- **YouTube : « access_denied »** : ton adresse n'est pas dans les utilisateurs test, ou l'app n'est pas publiée.
- **YouTube : vidéo « privée (verrouillée) »** : c'est la limite des projets non audités (voir plus haut).
- **Instagram : « Aucun compte Instagram professionnel trouvé »** : le compte n'est pas pro, n'est pas lié à une Page, ou la Page n'a pas été cochée pendant la connexion. Reconnecte-toi et coche tout.
- **TikTok : `unaudited_client_can_only_post_to_private_accounts`** : passe ton compte TikTok en privé, ou utilise le mode Brouillon.
- **TikTok : redirect_uri invalide** : vérifie l'URI exacte, `/` final compris.

## Adapter le projet

```
app.py              Serveur web local (Flask) + routes
poster/video.py     ffmpeg : analyse, frames, conversion 9:16
poster/youtube.py   Connexion + publication YouTube
poster/instagram.py Connexion + publication Instagram
poster/tiktok.py    Connexion + publication TikTok
poster/jobs.py      Publication en parallèle avec suivi de progression
static/             Interface (HTML/CSS/JS sans framework)
data/               Tes réglages et jetons (créé au lancement, ignoré par git)
```

Pour ajouter un réseau : crée `poster/<reseau>.py` avec `status()` et `publish(...)`, puis branche-le dans `jobs.py`, `app.py` et `static/`.

Les contributions sont les bienvenues (issues et pull requests).

## Licence

[MIT](LICENSE) : libre d'utilisation, de modification et de redistribution.
