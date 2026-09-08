# Analyse technique de Strucnode

> Analyse réalisée sur `strucnode.py` — 4 691 lignes, 245 Ko, fichier unique.
> Les références de la forme `strucnode.py:1234` pointent la ligne concernée.

---

## 1. État des lieux

| Indicateur | Valeur |
|---|---|
| Fichiers Python | **1** (`strucnode.py`) |
| Lignes | 4 691 |
| Classes | 9 (dont 3 « God classes » de 650 à 1 540 lignes) |
| Clés de traduction | 252 |
| `except Exception` génériques | 80 |
| `except:` nus | 7 |
| `import` en milieu de fonction | 27 |
| `print()` de debug | 13 |
| Tests | **0** |
| Workflow CI | **0** |

Répartition du code :

| Lignes | Zone |
|---:|---|
| 1 537 | `NodeEditorTab` |
| 836 | `FileExplorer` (fenêtre principale + onglet Explorateur) |
| 741 | Lecteur vidéo + visionneuses plein écran + visionneuse 360° |
| 654 | `OrganizeTab` |
| 275 | Couche de traduction (`_STRINGS`) |
| 175 | `Node` (rendu canvas) |
| 151 | Types de nodes + moteur de champs |
| 106 | Métadonnées / médias |
| 92 | Construction d'arbre + opérations |
| 55 | Thème / constantes |

Le code est loin d'être mauvais : le moteur nodal est élégant, la visionneuse 360°
est vectorisée avec NumPy, les traitements longs sont bien passés en thread avec
`after(0, ...)` pour revenir sur le thread Tk. Les problèmes sont **structurels**,
pas algorithmiques.

---

## 2. Problème n°1 — Le monolithe

### 2.1 Pourquoi c'est bloquant

Ce n'est pas qu'une question de confort de lecture :

- **Impossible de tester.** La logique métier (résolution des champs, construction
  d'arbre, planification des opérations) est pure et parfaitement testable — mais
  elle est dans le même fichier que Tkinter. Importer une fonction = importer tout
  le module = créer une racine Tk. D'où 0 test.
- **Le contexte se perd.** `_show_preview` (nodal, ligne 3027) et `_load_structure`
  (organize, ligne 3436) font presque la même chose, avec deux barres de progression
  différentes et deux fois le même texte codé en dur. C'est le symptôme direct de
  « je ne retrouve plus ce que j'ai déjà écrit ».
- **Le code mort passe inaperçu.** 5 méthodes (~95 lignes, `strucnode.py:4520-4612`)
  sont mortes et personne ne l'a vu — détail en §4.1.
- **Tout collisionne.** Un changement dans la palette touche le même fichier qu'un
  changement dans le lecteur vidéo : impossible de relire un diff proprement.

### 2.2 Architecture cible proposée

```text
strucnode/
├── __main__.py              # python -m strucnode
├── app.py                   # StrucnodeApp(tk.Tk) : assemblage, onglets, barre langue
├── config.py                # chemins (presets, cache, settings), persistance
├── theme.py                 # couleurs, polices, styles ttk
│
├── i18n/
│   ├── __init__.py          # t(), set_locale(), bind(), notify()
│   └── locales/
│       ├── en.json
│       └── fr.json
│
├── core/                    # ZÉRO import Tkinter → 100 % testable
│   ├── model.py             # dataclass FileEntry (remplace les dicts)
│   ├── categories.py        # EXT_CATEGORIES, get_category, fmt_size
│   ├── scanner.py           # parcours disque, annulable, avec progression
│   ├── metadata.py          # EXIF unifié + cache (fusionne les 2 implémentations)
│   ├── fields.py            # registre des champs (id, clé i18n, resolver)
│   ├── tree.py              # build_tree, flatten_to_operations, sanitize_component
│   ├── planner.py           # plan d'opérations, détection de collisions
│   ├── executor.py          # exécution copy/move + journal
│   └── dedupe.py            # comparaisons méta / octet à octet
│
├── media/
│   ├── images.py            # miniatures, RAW, détection 360°
│   ├── video.py             # VideoPlayer (ffmpeg / cv2 / audio)
│   └── system.py            # open_file (xdg-open / start / open)
│
└── ui/
    ├── widgets.py           # Card, CategoryBar, Section, ScrollFrame, mixins
    ├── explorer_tab.py
    ├── organize_tab.py
    ├── viewers.py           # plein écran image / vidéo / 360°
    └── nodes/
        ├── node.py          # rendu canvas d'un node
        ├── editor_tab.py    # canvas, drag & drop, câbles
        ├── palette.py
        └── presets.py       # (dé)sérialisation JSON versionnée
```

Aucun fichier ne dépasserait ~400 lignes, sauf `ui/nodes/editor_tab.py` (~600 après
extraction de la palette et des presets).

### 2.3 Ordre de découpage recommandé

L'ordre compte : chaque étape doit laisser l'application fonctionnelle.

1. **`theme.py` + `core/categories.py`** — constantes pures, zéro risque, permet de
   valider la mécanique de packaging.
2. **`i18n/`** — voir §3, c'est ce qui débloque la correction du bug de langue.
3. **`core/`** — déplacer `read_exif`, `_get_exif_datetime`, `get_file_field`,
   `build_tree_from_chain_extended`, `flatten_tree_to_operations`,
   `_files_equal_*`. **Écrire les tests à ce moment-là**, pendant que le
   comportement de référence est encore observable.
4. **`media/`** — `VideoPlayer` et les visionneuses, gros bloc mais très autonome.
5. **`ui/`** — en dernier, un onglet à la fois.

Point d'attention : `NODE_TYPES` est aujourd'hui une **variable globale reconstruite
à chaque changement de langue** (`strucnode.py:1236`, `3877`, `1892`). Il faut la
transformer en registre de champs immuable, où le label n'est pas une chaîne mais
une **clé i18n** résolue à l'affichage. C'est la condition pour que le découpage ne
recrée pas des cycles d'import.

---

## 3. Problème n°2 — La traduction

### 3.1 Le mécanisme actuel et pourquoi il fuit

Le texte est injecté dans le widget **au moment de sa construction** :

```python
self._lbl_summary = tk.Label(self.left, text=_("resume"), ...)
```

Il n'existe ensuite aucun lien entre le widget et sa clé. Pour retraduire,
`_set_language` (`strucnode.py:3876-3971`) parcourt **une liste écrite à la main** de
noms d'attributs :

```python
for attr, key in [("_lbl_summary", "resume"), ("_lbl_by_cat", "by_category"), ...]:
    w = getattr(self, attr, None)
    if w:
        try: w.config(text=_(key))
        except Exception: pass
```

Trois conséquences mécaniques :

1. **Tout widget oublié dans la liste n'est jamais traduit.** Et rien ne le signale :
   les `except Exception: pass` avalent l'erreur.
2. **Tout widget reconstruit après le changement de langue repart en dur.** Exemple :
   `_setup_file_tree_cols` (`strucnode.py:4305`) réécrit les en-têtes en français
   (`"Nom"`, `"Taille"`, `"Modifie le"`) à **chaque** clic sur une catégorie. Vous
   passez en anglais, vous cliquez sur « Images » → les colonnes repassent en
   français.
3. **Le texte dynamique est comparé à des chaînes traduites.** Pour savoir s'il faut
   retraduire un libellé, le code compare son contenu actuel à une liste de
   traductions attendues :

```python
if cur_st in ("Ready — choose a folder to begin",
              "Prêt — choisissez un dossier pour commencer", ...):
```

   (`strucnode.py:3894-3903`, `3143-3157`, `3808-3813`, `3849-3855`). Dès que le
   libellé contient une donnée (un nombre de fichiers, un chemin), la comparaison
   échoue et le texte reste figé dans l'ancienne langue.

### 3.2 Ce qui ne change pas de langue — liste exhaustive

| Élément | Ligne | Nature |
|---|---|---|
| En-têtes du tableau de fichiers | `4305-4310` | Écrits en dur en FR, réécrits à chaque changement de catégorie |
| Panneau Métadonnées : clés `Nom`, `Taille`, `Modifié`, `Type`, `360°`, `Format` | `4676-4678` | En dur en FR |
| Valeurs EXIF : `Focale`, `Marque`, `Appareil`, `Ouverture`, `Exposition` | `385-421` | Clés de données **et** libellés affichés, en FR |
| Libellés des filtres EXIF (`ISO :`, `Focale :`, `Appareil :`, `Ouv. :`) | `4337` | En dur en FR |
| Valeurs des combos de filtre (`Toutes`, `Tous`) | `4326`, `4341`, `4350`, `4508-4509` | En dur en FR — **et cause d'un bug fonctionnel, voir §4.2** |
| Noms de catégories dans les barres et le tableau d'extensions | `4471`, `4660` | `cat.capitalize()` → toujours en anglais technique |
| Statut « Demarrage de l'analyse... » | `4406` | En dur en FR, sans accent |
| Statut après analyse (« X fichiers, Y dossiers… ») | `4437` | Jamais retraduit après coup |
| `(sans extension)` | `4416` | En dur en FR, devient un nom de dossier |
| Progression nodale « ⏳ Calcul de la structure… » | `3066`, `3072` | En dur en FR |
| Progression Organiser « ⏳ Calcul… » / « ⏳ Recalcul… » | `3459`, `3544` | En dur en FR |
| « Aucun node utilisable. » | `3062` | En dur en FR |
| « L'éditeur nodal n'est pas encore initialisé… » | `3440` | En dur en FR |
| « Aucune structure définie dans l'éditeur nodal… » | `3445-3446` | En dur en FR |
| Suffixe de renommage `-doublon` | `3746` | En dur en FR, écrit sur le disque |
| Unités de taille `o / Ko / Mo / Go / To` | `358-364` | Toujours en FR (`o` au lieu de `B`) |
| Titre de la fenêtre au démarrage | `3860` | `"Strucnode - Statistiques & Organisation Nodale"` en dur |
| Libellés des nodes déjà posés sur le canvas | `1379`, `3046` | Figés dans la langue de création, sauvegardés tels quels dans les presets |
| Tranches de taille (`< 100 Ko`, `1 Mo - 10 Mo`) | `1314-1320` | En dur en FR, deviennent des noms de dossiers |

Par ailleurs, **11 clés de traduction sont définies mais jamais utilisées** —
`computing_progress`, `ops_computing`, `video_error`, `folder_not_found`,
`no_files_nodal`, `no_structure2`, `dest_folder_lbl`, `ext_filter`, `mode_label`,
`reset_btn`, `sect_mode`. Ce sont exactement les endroits où une chaîne en dur a été
écrite à la place. La traduction avait été prévue, elle n'a pas été branchée.

### 3.3 Architecture i18n proposée

**Fichier `i18n/locales/fr.json`** (et `en.json`) — les 252 clés sortent du `.py` :

```json
{
  "explorer.summary": "Résumé",
  "explorer.columns.name": "Nom",
  "organize.progress": "⏳ Calcul… {done} / {total} fichiers ({pct} %)"
}
```

**Module `i18n/__init__.py`** — trois primitives :

```python
def t(key, **kw) -> str          # traduit, formate, log si la clé manque
def set_locale(lang) -> None     # change la locale et notifie
def bind(widget, key, **kw)      # lie DÉFINITIVEMENT un widget à une clé
```

`bind()` est le cœur de la correction : au lieu d'injecter du texte, on enregistre le
couple (widget, clé) dans un registre faible. `set_locale()` parcourt le registre et
réapplique. **Un widget lié est traduit pour toujours, sans liste à maintenir.**

```python
# avant
self._lbl_summary = tk.Label(self.left, text=_("resume"))

# après
self._lbl_summary = i18n.bind(tk.Label(self.left), "explorer.summary")
```

Pour ce qui n'est pas un simple `text=` (colonnes de Treeview, onglets, titres de
fenêtre), un `i18n.on_change(callback)` permet d'enregistrer une fonction de
rafraîchissement au lieu d'un widget.

**Trois règles à graver**, qui suppriment toute la fragilité actuelle :

1. **Une chaîne traduite ne doit jamais servir de donnée ni d'identifiant.** Les
   sentinelles des combos deviennent une constante (`ALL = "__all__"`) affichée via
   une table de correspondance. Les clés EXIF deviennent `focal_length`, `make`,
   `model`… et sont traduites uniquement à l'affichage.
2. **Jamais de comparaison à une chaîne traduite.** Le « texte est-il encore le
   placeholder ? » se remplace par un état explicite (`self._struct_state = "empty"`).
3. **Le texte dynamique se stocke sous forme (clé, paramètres)**, pas sous forme de
   chaîne finale. Un statut se recalcule par `t(self._status_key, **self._status_args)`.

**Deux tests de non-régression** (rapides à écrire, ils verrouillent tout) :

- toute clé présente dans `en.json` existe dans `fr.json` et réciproquement, avec les
  mêmes champs de format ;
- toute clé appelée dans le code (scan AST des appels `t("…")`) existe dans les deux
  fichiers.

---

## 4. Bugs identifiés

### 4.1 Code mort — ~95 lignes jamais exécutées

`strucnode.py:4520-4612`. Cinq méthodes se réfèrent à des attributs qui n'existent
pas :

| Code | Attribut réel |
|---|---|
| `self.summaryframe` | `self.summary_frame` |
| `self.catsframe` | `self.cat_frame` |
| `self.statusvar` | `self.status_var` |
| `self.summarycarddata` | `self._summary_card_data` |
| `self.card(...)` / `self.catbar(...)` | `self._card(...)` / `self._cat_bar(...)` |

Chaque méthode commence par `if not hasattr(self, 'summaryframe'): return` → elle
sort immédiatement, en silence. Et `_refresh_dynamic_texts_after_locale`, qui devait
justement retraduire les cartes de résumé, les barres de catégories et le statut
après un changement de langue, **n'est appelée nulle part**. C'est très probablement
un correctif du bug de traduction écrit puis jamais branché — il faut le rebrancher
avec les bons noms d'attributs.

### 4.2 En anglais, la liste de fichiers d'une catégorie image est vide

Le bug le plus visible, et il est actif **par défaut** puisque la locale initiale est
`en` (`strucnode.py:34`).

- `_add_exif_filters` (`4339`) initialise les combos EXIF à `_("filter_all2")`,
  soit **`"All"`** en anglais.
- `_apply_file_filter` (`4630`) teste la sentinelle en dur :

```python
if any(v != "Tous" and f.get("meta", {}).get(k, "") != v for k, v in exif_f.items()):
    continue
```

`"All" != "Tous"` → vrai, et aucun fichier n'a un ISO valant `"All"` → **tous les
fichiers sont écartés**. En anglais, cliquer sur la catégorie « Images » affiche une
liste vide.

Le même défaut touche le filtre d'extension (`ext_q != "Toutes"`, ligne `4629`) : il
se déclenche dès qu'on repasse en anglais puis qu'on touche à un filtre.

Correctif : sentinelles internes (`ALL = "__all__"`) découplées de l'affichage.

### 4.3 `NameError` dans trois gestionnaires d'erreur

`strucnode.py:733`, `1063`, `1142` :

```python
except Exception as ex:
    self.after(0, lambda: messagebox.showerror(_("error"), str(ex)))
```

En Python 3, `ex` est **supprimé à la sortie du bloc `except`**. Le `lambda` le
capture par nom et s'exécute plus tard, via `after(0, ...)` : à ce moment `ex`
n'existe plus → `NameError` dans la boucle Tk. Résultat : quand l'ouverture d'une
vidéo, d'une image plein écran ou d'un panorama 360° échoue, **aucun message
d'erreur ne s'affiche**, l'utilisateur voit juste une fenêtre vide.

Correctif : `lambda e=ex: ...` (capture par valeur).

### 4.4 Les fichiers non résolus sont copiés dans un dossier nommé `?`

`get_file_field` retourne `"?"` quand un champ n'est pas résolvable
(`strucnode.py:1339`). `_refresh_ops` (`3576`) calcule bien `ok_ops` en excluant ces
opérations… **et ne s'en sert jamais**. `_run` (`3617`) exécute `self._ops`, qui
contient tout.

Conséquence : les fichiers listés dans l'onglet « Non appariés » sont quand même
copiés, dans un dossier littéralement nommé `?`. Sous Windows, `?` est un caractère
interdit → chaque opération échoue et remonte dans le compteur d'erreurs.

Correctif : n'exécuter que `ok_ops`, ou proposer explicitement un dossier de repli
(`_Non_apparies/`).

### 4.5 Les stratégies « comparer » écrasent quand les fichiers diffèrent

`_do_run`, `strucnode.py:3729-3737` :

```python
elif collision_action == "compare_meta":
    if _files_equal_meta(src, dst):
        done += 1; continue
# ... si différents : on tombe dans shutil.copy2(src, dst) → écrasement
```

Si les fichiers sont identiques, on saute — correct. S'ils sont **différents**, il
n'y a pas de `else` : le code continue et écrase la destination. C'est l'inverse de
ce qu'on attend d'un mode « comparer » : deux photos différentes portant le même nom
(cas très courant avec les compteurs d'appareils photo qui rebouclent à `IMG_9999`)
→ **perte de données silencieuse**.

Correctif : si différents → renommer automatiquement (comme le mode `rename`).

### 4.6 Collisions entre deux sources non détectées

`_run` (`3624`) ne détecte que les collisions avec des fichiers **déjà présents** sur
le disque :

```python
collisions = [(src, dst) for src, dst in self._ops if os.path.exists(dst)]
```

Si deux fichiers sources différents produisent la **même** destination — deux
`IMG_0042.jpg` venant de deux dossiers, rangés dans le même `2024/05/` — aucune
collision n'est détectée à la planification, et la seconde copie écrase la première
pendant l'exécution. En mode `move`, l'original est perdu.

Correctif : détecter les doublons de destination dans `self._ops` lui-même
(`Counter` sur les `dst`) et les traiter comme des collisions.

### 4.7 Noms de dossiers non assainis

Les noms de dossiers viennent de valeurs EXIF (`Canon EOS 5D Mark II`), de noms de
fichiers ou de texte libre saisi dans un node « Liant ». Rien n'est filtré
(`strucnode.py:1548-1565`) :

- un modèle d'appareil contenant `/` crée une arborescence non voulue ;
- `\ : * ? " < > |` font échouer l'opération sous Windows ;
- un espace ou un point final est silencieusement supprimé par Windows ;
- un Liant contenant `../..` **sort du dossier de destination** — le plan affiché à
  l'utilisateur ne correspond alors plus à ce qui est écrit sur le disque.

Correctif : une fonction `sanitize_component(name)` dans `core/tree.py`, appliquée
systématiquement, plus une assertion finale que chaque `dst` reste bien sous la racine
de destination (`os.path.commonpath`).

### 4.8 Divers

| Sujet | Ligne | Détail |
|---|---|---|
| Traversée de chemin sur les presets | `2194` | `_preset_path` concatène le nom saisi sans filtrage : un preset nommé `../x` écrit hors du dossier de presets |
| Cache EXIF non borné | `1238` | `_exif_cache` grandit sans limite et est indexé sur le seul chemin : jamais invalidé si le fichier change |
| Logique EXIF dupliquée | `370` / `1240` | `read_exif` et `_get_exif_datetime` réimplémentent chacune leur parsing |
| `Image.open` sans fermeture | `402`, `452`, `1268` | Descripteurs de fichiers laissés ouverts ; utiliser `with` |
| Pas de vérification destination ⊂ source | `3615` | Copier un dossier dans lui-même produit une récursion |
| Dossier de presets mal nommé | `2180` | `~/.file_explorer_presets` — vestige d'un ancien nom, à migrer vers `~/.strucnode/presets` |
| Preset JSON sans numéro de version | `2231` | Aucune migration possible si le format évolue |
| `print()` de debug en production | 13 occurrences | À remplacer par le module `logging` |

---

## 5. Améliorations proposées

### 5.1 Performance

| Point | Situation | Proposition |
|---|---|---|
| Parcours disque | `os.walk` + un `os.stat` par fichier (`4413`) | `os.scandir`, qui fournit déjà `stat` via `DirEntry` — gain typique ×2 à ×3 |
| Analyse non annulable | `_do_scan` (`4410`) va jusqu'au bout | Drapeau d'annulation, comme dans `_do_run` qui le fait déjà bien |
| Lecture EXIF | Séquentielle, un thread (`4513`) | `ThreadPoolExecutor` — la lecture EXIF est dominée par les E/S, gain ×4 à ×8 |
| Remplissage du tableau | Insertion de toutes les lignes une à une (`4643`) | Pagination ou insertion par lots ; au-delà de ~20 000 fichiers l'interface se fige |
| Palette | `refresh_palette` (`1918`) évalue **tous** les champs sur **tous** les fichiers, EXIF compris | Échantillonner (500 fichiers) pour les compteurs indicatifs, calculer en entier à la demande |
| Panorama 360° | `np.array(pano)` reconstruit à chaque image (`1160`) | Mettre le tableau NumPy en cache à côté de l'objet PIL |
| Aperçus | Aucun cache de miniatures | Cache LRU disque dans `~/.strucnode/cache`, indexé sur `(chemin, mtime, taille)` |

### 5.2 Robustesse et sûreté des données

C'est le point le plus important : **Strucnode déplace les photos de l'utilisateur**.
Une erreur ici n'est pas un bug d'affichage, c'est une perte de souvenirs.

1. **Journal d'opérations.** Écrire chaque `(src, dst, mode, horodatage)` réussi dans
   un JSON sous `~/.strucnode/journal/`. Cela donne gratuitement un **annuler** pour
   le mode `move`, qui n'existe pas aujourd'hui.
2. **Vérification de l'espace disponible** avant exécution (`shutil.disk_usage`) —
   sinon on découvre le disque plein au fichier 8 000 sur 12 000.
3. **Assainissement + garde anti-traversée** sur tous les noms de dossiers (§4.7).
4. **Détection des collisions internes au plan** (§4.6).
5. **Refus explicite** d'une destination située à l'intérieur de la source.
6. **Résumé pré-exécution** enrichi : nombre d'opérations, volume total, collisions,
   non appariés, espace requis vs disponible.
7. **`shutil.copy2` → `copyfile` + `copystat`** avec écriture dans un fichier
   temporaire puis renommage atomique, pour ne pas laisser de fichier tronqué si
   l'application est fermée en cours de copie.

### 5.3 Qualité et outillage

1. **Tests.** Une fois `core/` extrait, les cibles prioritaires sont :
   `get_file_field` (chaque champ), `build_tree_from_chain_extended`,
   `flatten_tree_to_operations`, `sanitize_component`, la détection de collisions,
   `_files_equal_*`, et les deux tests i18n de §3.3. Environ 40 tests couvrent
   l'essentiel du risque — sans jamais lancer Tkinter.
2. **Lint.** `ruff` avec les règles `E, F, B, UP, SIM`. Il détecte à lui seul les
   `NameError` de §4.3, les variables inutilisées de §4.1/§4.4 et les `except:` nus.
3. **CI.** Un workflow GitHub Actions (ruff + pytest sur 3.10/3.11/3.12) —
   le dépôt a des modèles d'issue et de PR mais aucune vérification automatique.
4. **`logging` à la place de `print`**, avec un niveau réglable par variable
   d'environnement.
5. **Imports en tête de module.** Les 27 imports en milieu de fonction masquent les
   dépendances réelles ; ne garder ce motif que pour les dépendances optionnelles
   (`cv2`, `rawpy`, `sounddevice`), et de préférence via un module
   `media/optional.py` qui centralise les tests de disponibilité.
6. **`dataclass FileEntry`** à la place des dictionnaires `{"path": …, "name": …}`
   passés partout : l'autocomplétion et `mypy` deviennent utiles, et les clés
   `"_mtime"` / `"_exif_dt"` injectées à la volée dans le dict (`1289`) disparaissent.

### 5.4 Expérience utilisateur

- **Mémoriser les préférences** (langue, dernier dossier, dernière destination, mode
  copie/déplacement) dans `~/.strucnode/settings.json`. Aujourd'hui la langue revient
  à l'anglais à chaque lancement.
- **Annuler l'analyse** en cours (le bouton existe pour les opérations, pas pour
  l'analyse).
- **Annuler / Rétablir dans l'éditeur nodal** — supprimer un node par erreur oblige à
  tout refaire.
- **Détection de la langue système** au premier lancement.
- **Raccourcis clavier** : `Ctrl+O` choisir un dossier, `F5` analyser, `Suppr`
  supprimer un node, `Ctrl+S` enregistrer le preset.
- **Unités de taille localisées** (`o/Ko/Mo` en FR, `B/KB/MB` en EN).
- **Message d'aide sur les non appariés** : expliquer *pourquoi* un fichier n'est pas
  apparié (pas d'EXIF, extension exclue…) plutôt qu'afficher `?`.

### 5.5 Distribution

- Point d'entrée `gui_scripts` dans `pyproject.toml` → commande `strucnode`.
- `packages = ["strucnode"]` à la place de `py-modules = ["strucnode"]` après le
  découpage.
- Version en source unique (`strucnode/__init__.py:__version__`, lue par
  `pyproject.toml`).
- `requirements.txt` liste toutes les dépendances optionnelles comme si elles étaient
  requises — le README les dit pourtant optionnelles. Le rendre cohérent avec les
  `optional-dependencies` du `pyproject.toml`.
- Recette PyInstaller pour livrer un binaire Windows — c'est le format attendu par
  le public visé (photographes), qui n'installera pas Python.

---

## 6. Feuille de route proposée

### Étape 1 — Correctifs immédiats (~1 journée, sans refonte)

Aucun découpage requis, valeur immédiate :

1. Filtres cassés en anglais (§4.2) — c'est le bug le plus visible.
2. Les trois `NameError` (§4.3) — correction d'une ligne chacun.
3. Ne plus exécuter les opérations non appariées (§4.4).
4. Le mode « comparer » ne doit plus écraser (§4.5).
5. Assainissement des noms de dossiers (§4.7).
6. Rebrancher ou supprimer le code mort (§4.1).

### Étape 2 — Extraction de l'i18n (~1 journée)

7. `i18n/` + `en.json` / `fr.json`, mécanisme `bind()`.
8. Reprendre les ~20 chaînes en dur listées en §3.2.
9. Les deux tests de cohérence des clés.

Après cette étape, cliquer sur 🇬🇧 / 🇫🇷 change réellement toute l'interface.

### Étape 3 — Extraction du cœur (~2 à 3 journées)

10. `core/` sans aucun import Tkinter.
11. Suite de tests sur `core/`.
12. `ruff` + workflow CI.

### Étape 4 — Découpage de l'interface (~2 à 3 journées)

13. `media/`, puis `ui/` un onglet à la fois.
14. `app.py` + `__main__.py`, mise à jour du `pyproject.toml`.

### Étape 5 — Sûreté des données et confort (continu)

15. Journal d'opérations + annulation.
16. Collisions internes au plan, vérification d'espace disque.
17. Préférences persistées, annuler/rétablir dans l'éditeur nodal, caches.

---

## 7. Synthèse

Le projet est sain sur le fond. Les trois axes, par ordre de rentabilité :

1. **Six correctifs ciblés** règlent des bugs réellement visibles, dont un qui vide la
   liste de fichiers en anglais et un qui peut écraser des photos.
2. **L'i18n par liaison widget → clé** supprime la cause structurelle du problème de
   changement de langue, au lieu d'allonger indéfiniment une liste à maintenir à la
   main.
3. **L'extraction d'un `core/` sans Tkinter** est ce qui rend le projet testable — et
   donc ce qui rend toutes les évolutions suivantes sûres, y compris celles qui
   touchent au déplacement de fichiers.


---

## 8. État d'avancement

Le découpage a été réalisé. Cette section fait le lien entre le diagnostic
ci-dessus et ce qui est effectivement dans le dépôt, y compris ce qui reste.

### Fait

| § | Sujet | Où |
|---|---|---|
| 2.2 | Découpage en paquet `strucnode/` | `app.py`, `config.py`, `theme.py`, `core/`, `media/`, `ui/`, `i18n/` |
| 2.2 | `core/` sans aucun import Tkinter | vérifié par `tests/test_imports.py` et par l'absence d'import `tkinter` dans `core/` |
| 3.3 | Traductions hors du code | `strucnode/i18n/locales/{en,fr}.json` |
| 3.3 | Liaison widget → clé (`tr`, `tr_var`, `set_raw`) | `strucnode/i18n/__init__.py` |
| 3.2 | Les ~20 chaînes en dur reprises | en-têtes de colonnes, panneau métadonnées, filtres EXIF, statuts, suffixe de renommage, unités de taille, tranches de taille |
| 3.3 | Tests de cohérence des catalogues | `tests/test_i18n.py` |
| 4.1 | Code mort supprimé, logique de rafraîchissement rebranchée | `ExplorerTab._render_summary` / `_render_categories`, `StrucnodeApp._render_scan_status` |
| 4.2 | Filtres cassés en anglais | sentinelle par index de combo (`ALL_INDEX`), `ExplorerTab._selected_filter` |
| 4.3 | `NameError` dans les gestionnaires d'erreur | capture par valeur (`lambda e=exc:`) dans `media/video.py` et `ui/viewers.py` |
| 4.4 | Fichiers non appariés copiés dans `?` | `core/planner.build_plan` les sort de `operations` |
| 4.5 | Mode « comparer » qui écrasait | `core/executor._resolve_collision` renomme au lieu d'écraser |
| 4.6 | Collisions entre deux sources | `Plan.internal_collisions` |
| 4.7 | Noms de dossiers non assainis | `core/tree.sanitize_component`, appliqué à chaque composant |
| 4.8 | Traversée sur les noms de presets | `PresetStore.path_for` assainit le nom |
| 4.8 | Cache EXIF non borné | LRU de 20 000 entrées, clé `(chemin, mtime, taille)` |
| 4.8 | Logique EXIF dupliquée | une seule analyse dans `core/metadata.read_metadata` |
| 4.8 | `Image.open` sans fermeture | `with Image.open(...)` |
| 4.8 | Destination dans la source | `planner.destination_is_inside` |
| 4.8 | Preset sans version | `SCHEMA_VERSION` dans `PresetStore` |
| 4.8 | Dossier de presets mal nommé | `~/.strucnode/presets`, avec migration de l'ancien dossier |
| 4.8 | `print()` de debug | remplacés par `logging` |
| 5.1 | Lecture EXIF parallèle | `ThreadPoolExecutor` dans `ExplorerTab._load_exif_bg` |
| 5.2 | Journal d'opérations | `~/.strucnode/journal/`, écrit par `core/executor` |
| 5.2 | Vérification d'espace disque | `planner.free_space`, contrôlée avant exécution |
| 5.2 | Copie atomique | fichier temporaire puis `os.replace` |
| 5.2 | Résumé pré-exécution enrichi | `OrganizeTab._confirm_run` |
| 5.3 | Tests | 384 tests, sans écran |
| 5.3 | Lint + CI | `ruff` configuré, workflow sur Python 3.10 à 3.13 |
| 5.4 | Préférences persistées | `~/.strucnode/settings.json` (langue, dernier dossier, destination) |
| 5.4 | Détection de la langue système | `config.detect_locale`, au premier lancement |
| 5.4 | Unités de taille localisées | clé `size_units` |
| 5.5 | Point d'entrée + packaging | `strucnode` (gui-scripts), `python -m strucnode`, `packages` corrigé |
| 5.5 | `requirements.txt` cohérent | dépendances optionnelles commentées, `[media]` dans le `pyproject.toml` |

Le fichier `strucnode.py` à la racine ne contient plus que le lanceur, pour que
la commande documentée dans le README continue de fonctionner.

### Reste à faire

Volontairement laissé de côté, par ordre de valeur :

1. **`dataclass FileEntry`** (§5.3). Les fichiers indexés circulent toujours
   comme des dictionnaires. Les remplacer touche presque tous les modules UI ;
   c'est un changement à faire seul, avec les tests actuels comme filet.
2. **Annulation de l'analyse depuis l'interface** (§5.1). Le mécanisme est en
   place (`scanner.scan` accepte un `threading.Event`, et fermer la fenêtre
   l'active), mais il n'y a pas encore de bouton d'arrêt à côté de la barre de
   progression.
3. **Annuler / rétablir dans l'éditeur nodal** (§5.4).
4. **Annulation d'un déplacement à partir du journal** (§5.2). Le journal est
   écrit, l'action « annuler » qui le relit n'existe pas encore.
5. **Pagination du tableau de fichiers** (§5.1). Au-delà d'environ 20 000
   fichiers l'insertion ligne par ligne fige encore l'interface.
6. **Cache de miniatures sur disque** (§5.1).
7. **Raccourcis clavier** (§5.4).
8. **Recette PyInstaller** (§5.5).

### Vérification

Le conteneur utilisé pour ce travail n'a ni Tkinter ni Pillow : **l'application
n'y a jamais été lancée**. Le premier essai sur une vraie machine a d'ailleurs
révélé un crash au démarrage — `ExplorerTab._build_ui()` lisait
`self._video_player` avant que `__init__` ne l'affecte.

Le filet de sécurité a été refait en conséquence. Le stub Tkinter de
`tests/tk_stub.py` était trop permissif : il répondait à *n'importe quel*
attribut par un objet factice, ce qui masquait exactement ce genre d'erreur. Il
est maintenant strict — un attribut commençant par `_` qui n'a pas été affecté
lève `AttributeError`, comme le ferait le vrai Tk — et `tests/test_construction.py`
**construit réellement** chaque vue (les trois onglets, la fenêtre principale, les
visionneuses plein écran) au lieu de se contenter de les importer. Le test a été
validé en réintroduisant le bug : il échoue avec le message exact remonté par
l'utilisateur.

Ce qui est vérifié aujourd'hui : `ruff` sans avertissement, **408 tests** verts,
la construction de chaque vue, un aller-retour complet éditeur nodal → plan →
exécution sur de vrais fichiers temporaires, et le changement de langue appliqué
à toutes les vues construites.

Ce qui ne l'est pas et demande encore un œil humain : le rendu visuel, le
glisser-déposer de la palette (les événements souris ne sont pas simulés), la
lecture vidéo et la visionneuse 360° avec de vrais médias.
