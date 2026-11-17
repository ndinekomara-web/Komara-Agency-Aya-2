# Aya — Komara Agency

Assistante conversationnelle de Komara Agency, en application web autonome.
Plus de Telegram : Aya tourne comme un serveur web et s'installe sur ordinateur
et sur téléphone, comme une application classique (PWA).

## Ce que fait Aya

- Répond aux questions sur les services, les tarifs et les délais, en français,
  anglais et arabe, à partir de `knowledge_base/`.
- Reconnaît les salutations et les adieux, et bloque les tentatives
  d'extraction de prompt.
- Guide le client dans un parcours de devis (service, budget, confirmation).
- Garde l'historique de chaque conversation dans une base locale SQLite.

## Installation sur ordinateur

```bash
git clone https://github.com/ndinekomara-web/Komara-Agency-Aya-2.git
cd Komara-Agency-Aya-2
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Ouvrez ensuite `http://localhost:8000`.

## Installation sur téléphone (et sur ordinateur) comme une application

L'application est une PWA : elle s'installe depuis le navigateur, sans store.

1. Mettez Aya en ligne, ou lancez-la sur un ordinateur du même réseau.
2. Ouvrez l'adresse dans le navigateur du téléphone : `http://IP-DU-PC:8000`.
3. **Android / Chrome** : menu ⋮ → « Installer l'application ».
4. **iPhone / Safari** : bouton Partager → « Sur l'écran d'accueil ».
5. **Ordinateur / Chrome ou Edge** : icône d'installation dans la barre d'adresse.

Aya s'ouvre alors en plein écran, avec son icône, comme ChatGPT.

> Une PWA exige HTTPS pour s'installer proprement en dehors de `localhost`.
> En production, mettez Aya derrière un domaine avec certificat (Railway,
> Render, ou un reverse proxy Caddy/Nginx sur votre serveur).

## Déploiement

### Docker (recommandé sur un VPS)

```bash
cp .env.example .env
docker compose up -d --build
```

Aya écoute sur le port 8000. Les conversations sont conservées dans `./data`.

### Railway / Render

- Start command : `uvicorn app:app --host 0.0.0.0 --port $PORT`
  (déjà dans le `Procfile`).
- Ajoutez un volume monté sur `/app/data` pour garder l'historique.

## Configuration

Toutes les options passent par des variables d'environnement (voir `.env.example`).

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `PORT` | Port d'écoute | `8000` |
| `DEFAULT_LANGUAGE` | Langue de départ | `fr` |
| `APP_ACCESS_TOKEN` | Mot de passe protégeant la conversation | vide (public) |
| `RAG_BACKEND` | `auto`, `keyword` ou `embed` | `auto` |
| `MEMORY_DIR` | Dossier de la base SQLite | `./data` |
| `GOOGLE_SHEETS_ID` | Journal Sheets (facultatif) | vide |

### Deux moteurs de recherche

- **Mots-clés** (défaut) : aucune dépendance lourde, démarrage instantané.
- **Embeddings** : `pip install -r requirements-embeddings.txt`, puis
  `RAG_BACKEND=embed`. Meilleure compréhension, mais télécharge un modèle
  d'environ 120 Mo au premier lancement.

En mode `auto`, Aya utilise les embeddings s'ils sont installés et bascule
sinon sur les mots-clés : l'application ne tombe jamais en panne à cause
d'une dépendance manquante.

## Enrichir les connaissances

Les réponses viennent de fichiers Markdown versionnés, un dossier par langue :

```
knowledge_base/
├── fr/   (services.md, tarifs.md, faq.md)
├── en/
└── ar/
```

Ajoutez ou modifiez un fichier, puis redémarrez l'application. Les titres
`##` délimitent les sections ; un titre clair améliore nettement la recherche.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

## Structure

| Fichier | Rôle |
| --- | --- |
| `app.py` | Serveur web FastAPI et API de conversation |
| `web/` | Interface (HTML, CSS, JS), manifeste et service worker PWA |
| `message_router.py` | Enchaînement des traitements d'un message |
| `rag_engine.py` | Recherche dans la base de connaissances |
| `logical_steps.py` | Parcours de devis |
| `chat_store.py` | Historique SQLite des conversations |
| `memory_sheets.py` | Journal Google Sheets (facultatif) |

## Licence

© Komara Agency. Tous droits réservés.
