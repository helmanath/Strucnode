"""
Strucnode
==========

Desktop Tkinter application for file analysis, metadata inspection, media preview,
and node-based file organization.

Main responsibilities
---------------------
- Scan a folder tree and compute file statistics.
- Preview images, RAW files, videos, and 360° panoramas.
- Extract useful metadata such as EXIF dates and camera information.
- Build destination folder structures visually with a node editor.
- Simulate and execute copy/move operations toward a target folder.

Notes for maintainers
---------------------
This script currently centralizes UI code, media helpers, metadata extraction,
and organization logic in one file. It works well for a standalone release, but a
future refactor could split it into modules such as `media.py`, `metadata.py`,
`node_editor.py`, and `organizer.py`.
"""

import os, math, threading, datetime, subprocess, sys, time, traceback

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try:
    from PIL import Image as _pil_img_ref
    _pil_img_ref.MAX_IMAGE_PIXELS = None
except ImportError:
    pass

_LOCALE = "en"

# =============================================================================
# Localization layer
# Stores all translatable UI strings and the helpers used to switch language.
# =============================================================================
_STRINGS = {
    "choose_folder":      {"en":"Choose Folder",                           "fr":"Choisir un dossier"},
    "analyze":            {"en":"Analyze",                                 "fr":"Analyser"},
    "no_folder":          {"en":"No folder selected",                      "fr":"Aucun dossier sélectionné"},
    "tab_explorer":       {"en":"  📂 Explorer  ",                         "fr":"  📂 Explorateur  "},
    "tab_nodal":          {"en":"  🔗 Node Editor  ",                      "fr":"  🔗 Éditeur Nodal  "},
    "tab_organize":       {"en":"  📁 Organize  ",                         "fr":"  📁 Organiser  "},
    "available_after":    {"en":"Available after indexing",                "fr":"Disponible après indexation"},
    "resume":             {"en":"SUMMARY",                                 "fr":"RÉSUMÉ"},
    "by_category":        {"en":"BY CATEGORY",                             "fr":"PAR CATÉGORIE"},
    "click_filter":       {"en":"Click to filter",                         "fr":"Clic pour filtrer"},
    "detail_ext":         {"en":"DETAIL BY EXTENSION",                     "fr":"DÉTAIL PAR EXTENSION"},
    "files_select":       {"en":"FILES — select a category or extension",  "fr":"FICHIERS — sélectionner une catégorie ou extension"},
    "preview":            {"en":"PREVIEW",                                 "fr":"APERÇU"},
    "metadata":           {"en":"METADATA",                                "fr":"MÉTADONNÉES"},
    "click_enlarge":      {"en":"Click to enlarge",                        "fr":"Cliquer pour agrandir"},
    "filter_name":        {"en":"Name",                                    "fr":"Nom"},
    "filter_ext":         {"en":"Extension",                               "fr":"Extension"},
    "reset":              {"en":"Reset",                                   "fr":"Réinitialiser"},
    "select_file":        {"en":"Select file",                             "fr":"Sélectionner fichier"},
    "decoding_raw":       {"en":"Decoding RAW...",                         "fr":"Décodage RAW..."},
    "no_metadata":        {"en":"No metadata",                             "fr":"Aucune métadonnée"},
    "indexing":           {"en":"Indexing",                                "fr":"Indexation en cours"},
    "rawpy_required":     {"en":"rawpy required (install rawpy exifread)", "fr":"rawpy requis (install rawpy exifread)"},
    "opencv_required":    {"en":"opencv-python required",                  "fr":"opencv-python requis"},
    "reading_exif":       {"en":"Reading EXIF",                            "fr":"Lecture EXIF"},
    "node_editor_title":  {"en":"🔗 NODE EDITOR",                         "fr":"🔗 ÉDITEUR NODAL"},
    "node_editor_hint":   {"en":"port=chain_attr  Ctrl+click=multi-select","fr":"port=chain_attr  Ctrl+clic=multi-sélection"},
    "pal_legend_chain":    {"en":"\u25b6  Port chain = folder level",       "fr":"\u25b6  Port chain = niveau de dossier"},
    "pal_legend_meta":     {"en":"Dbl-click META = separator",              "fr":"Dbl-clic META = s\u00e9parateur"},
    "pal_legend_folder":   {"en":"Dbl-click FOLDER = rename",              "fr":"Dbl-clic DOSSIER = renommer"},
    "pal_legend_multisel": {"en":"Ctrl+click = multi-sel.",                "fr":"Ctrl+clic = multi-sel."},
    "pal_legend_cut":      {"en":"Click on wire = cut",                    "fr":"Clic sur fil = couper"},
    "clear_all":          {"en":"🗑 Clear all",                            "fr":"🗑 Tout effacer"},
    "reset_view":         {"en":"↺ Reset view",                            "fr":"↺ Réinitialiser vue"},
    "new_preset":         {"en":"＋ New",                                  "fr":"＋ Nouveau"},
    "save_preset":        {"en":"💾 Save",                                 "fr":"💾 Sauvegarder"},
    "palette":            {"en":"PALETTE",                                 "fr":"PALETTE"},
    "how_to_build":       {"en":"HOW TO BUILD",                            "fr":"COMMENT CONSTRUIRE"},
    "how_to_build_txt":   {"en":"1. Drag META nodes\n2. Connect left\u2192right (each node = 1 folder level)\n3. Dbl-click a node \u2192 set suffix separator",
                           "fr":"1. Glissez des nodes META\n2. Connectez-les gauche\u2192droite (chaque node = 1 niveau)\n3. Dbl-clic sur un node \u2192 régler le séparateur suffixe"},
    "drag_nodes_hint":    {"en":"Drag nodes from the palette to build your structure","fr":"Glissez des nodes depuis la palette pour construire votre structure"},
    "preview_structure":  {"en":"STRUCTURE PREVIEW",                       "fr":"APERÇU STRUCTURE"},
    "click_preview":      {"en":"⊙ Preview structure",                     "fr":"⊙ Aperçu structure"},
    "col_count":          {"en":"Count",                                   "fr":"Nb"},
    "structure_label":    {"en":"STRUCTURE",                               "fr":"STRUCTURE"},
    "folder_node":        {"en":"📁 Folder",                               "fr":"📁 Dossier"},
    "connector_label":    {"en":"CONNECTOR (fixed text)",                  "fr":"LIANT (texte fixe)"},
    "arguments_label":    {"en":"ARGUMENTS (metadata)",                    "fr":"ARGUMENTS (métadonnées)"},
    "no_files_indexed":   {"en":"No files indexed",                        "fr":"Aucun fichier indexé"},
    "files_indexed":      {"en":"{n:,} files indexed",                     "fr":"{n:,} fichiers indexés"},
    "computing_n":        {"en":"Computing {n:,} files",                   "fr":"Calcul {n:,} fichiers"},
    "view_reset":         {"en":"View reset \u2014 Zoom 100%",              "fr":"Vue réinitialisée \u2014 Zoom 100%"},
    "preset_name_lbl":    {"en":"Preset name",                             "fr":"Nom du préset"},
    "overwrite_lbl":      {"en":"Overwrite existing",                      "fr":"Écraser un existant"},
    "err_empty_name":     {"en":"Name cannot be empty.",                   "fr":"Le nom ne peut pas être vide."},
    "err_bad_chars":      {"en":"Forbidden chars: ? / : * \" < > |",      "fr":"Caractères interdits : ? / : * \" < > |"},
    "cancel":             {"en":"Cancel",                                  "fr":"Annuler"},
    "ok":                 {"en":"OK",                                      "fr":"OK"},
    "folder_name_lbl":    {"en":"Folder name",                             "fr":"Nom du dossier"},
    "connector_text":     {"en":"Connector text",                          "fr":"Texte du liant"},
    "presets_lbl":        {"en":"Presets",                                 "fr":"Prérèglages"},
    "custom_lbl":         {"en":"Custom",                                  "fr":"Personnalisé"},
    "chain_click":        {"en":"Click \u00ab Preview structure \u00bb.",   "fr":"Cliquez sur \u00ab Aperçu structure \u00bb."},
    "chain_computing":    {"en":"Computing\u2026\n{n:,} files analyzed",   "fr":"Calcul\u2026\n{n:,} fichiers analysés"},
    "chain_result":       {"en":"Chain: {label}\n{n:,} files analyzed",    "fr":"Chaîne : {label}\n{n:,} fichiers analysés"},
    "chain_error":        {"en":"Error: {msg}",                            "fr":"Erreur : {msg}"},
    "no_files_nodal":     {"en":"No files indexed. Do a scan in the Explorer tab first.","fr":"Aucun fichier indexé. Faites d'abord une analyse dans l'onglet Explorateur."},
    "organize_title":     {"en":"📁 ORGANIZE FILES",                       "fr":"📁 ORGANISER LES FICHIERS"},
    "organize_hint":      {"en":"Apply the node editor structure to a destination folder.","fr":"Appliquez la structure de l'éditeur nodal à un dossier de destination."},
    "no_structure":       {"en":"No structure defined. Go to Node Editor \u2192 click \u00ab Preview structure \u00bb.",
                           "fr":"Aucune structure définie. Allez dans Éditeur Nodal \u2192 cliquez sur \u00ab Aperçu structure \u00bb."},
    "no_structure2":      {"en":"No structure defined in the node editor.", "fr":"Aucune structure définie dans l'éditeur nodal."},
    "load_structure":     {"en":"\u27f3 Load structure from node editor",   "fr":"\u27f3 Charger la structure depuis l'éditeur nodal"},
    "load_ext_hint":      {"en":"Load a structure to see available extensions.","fr":"Chargez une structure pour voir les extensions disponibles."},
    "check_all":          {"en":"All",                                     "fr":"Tout"},
    "check_none":         {"en":"None",                                    "fr":"Aucun"},
    "browse":             {"en":"Browse\u2026",                             "fr":"Parcourir\u2026"},
    "apply_structure":    {"en":"\u25b6  Apply structure",                  "fr":"\u25b6  Appliquer la structure"},
    "ops_preview":        {"en":"OPERATIONS PREVIEW",                      "fr":"PRÉVISUALISATION DES OPÉRATIONS"},
    "tab_all_ops":        {"en":"All operations ",                         "fr":"Toutes les opérations "},
    "tab_unmatched":      {"en":"Unmatched ",                              "fr":"Sans correspondance "},
    "col_src":            {"en":"Source file",                             "fr":"Fichier source"},
    "col_dst":            {"en":"Destination",                             "fr":"Destination"},
    "col_file":           {"en":"File",                                    "fr":"Fichier"},
    "col_reason":         {"en":"Destination (missing field)",             "fr":"Destination (champ manquant)"},
    "start_status":       {"en":"Load a structure from the node editor to begin.","fr":"Chargez une structure depuis l'éditeur nodal pour commencer."},
    "zero_files":         {"en":"0 files",                                 "fr":"0 fichiers"},
    "dup_section":        {"en":"DUPLICATE MANAGEMENT",                    "fr":"GESTION DES DOUBLONS"},
    "duplicates_q":       {"en":"What do you want to do with these files?","fr":"Que souhaitez-vous faire pour ces fichiers ?"},
    "dup_ignore":         {"en":"Ignore duplicates",                       "fr":"Ignorer les doublons"},
    "dup_replace":        {"en":"Replace",                                 "fr":"Remplacer"},
    "dup_rename":         {"en":"Rename (-copy)",                          "fr":"Renommer (-doublon)"},
    "cancelling":         {"en":"Cancelling\u2026",                        "fr":"Annulation en cours\u2026"},
    "error":              {"en":"Error",                                   "fr":"Erreur"},
    "apercu_title":       {"en":"Preview",                                 "fr":"Aperçu"},
    "structure_info":     {"en":"Structure: {label}",                      "fr":"Structure : {label}"},
    "nodal_structure":    {"en":"NODAL STRUCTURE",                         "fr":"STRUCTURE NODAL"},
    "copy_mode":          {"en":"Copy",                                    "fr":"Copie"},
    "move_mode":          {"en":"Move",                                    "fr":"Déplacement"},
    "dest_folder_lbl":    {"en":"Destination folder:",                     "fr":"Dossier de destination :"},
    "ext_filter":         {"en":"Filter by extension",                     "fr":"Filtre par extension"},
    "mode_label":         {"en":"Mode:",                                   "fr":"Mode :"},
    "node_dbl_rename":    {"en":"double-click to rename",                  "fr":"double-clic pour renommer"},
    "node_dbl_edit":      {"en":"double-click to edit",                    "fr":"double-clic pour modifier"},
    "node_parent_hint":   {"en":"parent / name / output",                  "fr":"parent / nom / sortie"},
    "node_fixed_val":     {"en":"fixed value: {v}",                        "fr":"valeur fixe : {v}"},
    "node_field":         {"en":"field: {f}",                              "fr":"champ : {f}"},
    "node_sep":           {"en":"sep.: {s}",                               "fr":"sépar. : {s}"},
    "node_sep_none":      {"en":"(none)",                                  "fr":"(aucun)"},
    "node_default_folder":{"en":"Folder",                                  "fr":"Dossier"},
    "dup_ask":            {"en":"Ask each time",                           "fr":"Demander à chaque fois"},
    "dup_skip":           {"en":"Skip duplicates",                         "fr":"Ignorer les doublons"},
    "dup_replace_auto":   {"en":"Replace automatically",                   "fr":"Remplacer automatiquement"},
    "dup_rename_auto":    {"en":"Rename (-copy)",                          "fr":"Renommer (-doublon)"},
    "dup_meta":           {"en":"Meta+size (skip if identical)",           "fr":"Méta+taille (ignorer si identique)"},
    "dup_full_cmp":       {"en":"Bit-for-bit (skip if identical)",         "fr":"Bit-à-bit complet (ignorer si identique)"},
    "sect_dest":          {"en":"DESTINATION FOLDER",                      "fr":"DOSSIER DE DESTINATION"},
    "sect_mode":          {"en":"COPY / MOVE",                             "fr":"COPIE / DÉPLACEMENT"},
    "sect_ext":           {"en":"FILTER BY EXTENSION",                     "fr":"FILTRER PAR EXTENSION"},
    "viewer_hint":        {"en":"Scroll=zoom  Drag=pan  Esc=close",        "fr":"Scroll=zoom  Glisser=pan  Echap=fermer"},
    "canvas_empty":       {"en":"Empty canvas \u2014 drag nodes from the palette","fr":"Canvas vide \u2014 ajoutez des nodes depuis la palette"},
    "node_nom":           {"en":"NAME",                                    "fr":"NOM"},
    "node_count_status":  {"en":"{n} nodes  {f} folder(s)  {m} meta  \u2022  ","fr":"{n} nodes  {f} dossier(s)  {m} méta  \u2022  "},
    "node_conn_status":   {"en":"{nc} connection(s){sel}",                 "fr":"{nc} connexion(s){sel}"},
    "preview_ready":      {"en":"Preview ready \u2014 {n:,} files  |  {label}","fr":"Aperçu prêt \u2014 {n:,} fichiers  |  {label}"},
    "computing_progress": {"en":"\u23f3 Computing\u2026 {d:,}/{t:,} files ({p}%)","fr":"\u23f3 Calcul\u2026 {d:,}/{t:,} fichiers ({p}%)"},
    "err_compute":        {"en":"\u274c Compute error: {msg}",              "fr":"\u274c Erreur calcul : {msg}"},
    "connector_btn":      {"en":"\U0001f517 Connector (e.g. -, _, ' ')",   "fr":"\U0001f517 Liant (ex. -, _, ' ')"},
    "connector_canvas":   {"en":"\U0001f517 Connector: {v}",               "fr":"\U0001f517 Liant : {v}"},
    "connector_ex":       {"en":"E.g. -, _, ' ', '/', 'photos', etc.",    "fr":"Ex. -, _, ' ', '/', 'photos', etc."},
    "connector_preview":  {"en":"Preview: {ex}{sep}",                     "fr":"Aperçu : {ex}{sep}"},
    "apply_btn":          {"en":"Apply",                                   "fr":"Appliquer"},
    "dlg_save_error":     {"en":"Save error",                              "fr":"Erreur sauvegarde"},
    "dlg_not_found":      {"en":"Not found",                               "fr":"Introuvable"},
    "dlg_load_error":     {"en":"Load error",                              "fr":"Erreur chargement"},
    "dlg_delete":         {"en":"Delete",                                  "fr":"Supprimer"},
    "dlg_delete_error":   {"en":"Delete error",                            "fr":"Erreur suppression"},
    "dlg_invalid_conn":   {"en":"Invalid connection",                      "fr":"Connexion invalide"},
    "dlg_confirm":        {"en":"Confirm",                                 "fr":"Confirmer"},
    "dlg_cancelled":      {"en":"Cancelled",                               "fr":"Annulé"},
    "dlg_done":           {"en":"Done",                                    "fr":"Terminé"},
    "dlg_warning":        {"en":"Warning",                                 "fr":"Attention"},
    "dlg_choose_dest":    {"en":"Choose destination folder",               "fr":"Choisir le dossier de destination"},
    "dlg_preset_err":     {"en":"Preset error: {e}",                       "fr":"Erreur préset : {e}"},
    "dlg_file_missing":   {"en":"File not found:\n{path}\nCheck the presets folder.","fr":"Fichier introuvable :\n{path}\nVérifiez le dossier des presets."},
    "dlg_file_missing2":  {"en":"File not found:\n{path}",                 "fr":"Fichier introuvable :\n{path}"},
    "dlg_folder_missing": {"en":"Folder not found:\n{folder}",             "fr":"Dossier introuvable :\n{folder}"},
    "status_ready":       {"en":"Ready \u2014 choose a folder to begin",   "fr":"Prêt \u2014 choisissez un dossier pour commencer"},
    "status_files":       {"en":"{f:,} files  |  {size}",                  "fr":"{f:,} fichiers  |  {size}"},
    "status_scan":        {"en":"{files:,} files  {dirs:,} subfolders  {size}","fr":"{files:,} fichiers  {dirs:,} sous-dossiers  {size}"},
    "status_errors":      {"en":"  {n} error(s)",                          "fr":"  {n} erreur(s)"},
    "ops_recalc":         {"en":"Recalculating for {n:,} files",           "fr":"Recalcul pour {n:,} fichiers"},
    "ops_selected":       {"en":"{n:,}/{t:,} files selected  {e} ext.",    "fr":"{n:,}/{t:,} fichiers sélectionnés  {e} extensions"},
    "ops_progress":       {"en":"{done}/{total} files processed",          "fr":"{done}/{total} fichiers traités"},
    "ops_errors":         {"en":"{n} error(s)",                            "fr":"{n} erreur(s)"},
    "ops_count":          {"en":"{n:,} files",                             "fr":"{n:,} fichiers"},
    "ops_unmatched":      {"en":"{n} unmatched",                           "fr":"{n} sans corresp."},
    "ops_unmatched_tab":  {"en":"Unmatched {n} ",                          "fr":"Sans correspondance {n} "},
    "ops_collision":      {"en":"{n} files already exist at destination.", "fr":"{n} fichiers existent déjà à la destination."},
    "ops_confirm":        {"en":"Do you want to {verb} {n:,} files?",      "fr":"Voulez-vous {verb} {n:,} fichiers ?"},
    "ops_cancelled":      {"en":"Operation cancelled after {done} files {verb}.","fr":"Opération annulée après {done} fichiers {verb}."},
    "ops_cancelled_err":  {"en":"{n} error(s) before stop.",               "fr":"{n} erreur(s) avant l'arrêt."},
    "ops_status_cancel":  {"en":"Cancelled: {done} files {verb}",          "fr":"Annulé : {done} fichiers {verb}"},
    "ops_done_msg":       {"en":"{done} files {verb} successfully.",       "fr":"{done} fichiers {verb} avec succès."},
    "ops_done_err":       {"en":"{n} error(s):\n{details}",                "fr":"{n} erreur(s) :\n{details}"},
    "ops_status_done":    {"en":"Done: {done} files {verb}",               "fr":"Terminé : {done} fichiers {verb}"},
    "ops_computing":      {"en":"\u23f3 Computing\u2026 {d:,}/{t:,} files","fr":"\u23f3 Calcul\u2026 {d:,}/{t:,} fichiers"},
    "files_section":      {"en":"FILES  {label}",                          "fr":"FICHIERS  {label}"},
    "files_count":        {"en":"{n:,}/{t:,} files",                       "fr":"{n:,}/{t:,} fichiers"},
    "need_folder":        {"en":"Please choose a folder first.",           "fr":"Veuillez d'abord choisir un dossier."},
    "folder_not_found":   {"en":"Folder not found: {f}",                   "fr":"Dossier introuvable : {f}"},
    "filter_all":         {"en":"All",                                     "fr":"Toutes"},
    "filter_all2":        {"en":"All",                                     "fr":"Tous"},
    "app_title":          {"en":"Strucnode",                           "fr":"Strucnode"},
    "window_title":       {"en":"Strucnode \u2014 Statistics & Nodal Organisation","fr":"Strucnode \u2014 Statistiques & Organisation Nodale"},
    "pal_sect_exif":      {"en":"EXIF DATE (PHOTO) \U0001f4f8",            "fr":"DATE EXIF (PHOTO) \U0001f4f8"},
    "pal_sect_created":   {"en":"CREATION DATE",                           "fr":"DATE CRÉATION"},
    "pal_sect_modif":     {"en":"MODIFIED DATE",                           "fr":"DATE MODIFICATION"},
    "pal_sect_file":      {"en":"FILE",                                    "fr":"FICHIER"},
    "nt_annee_creation":  {"en":"Year (created)",                          "fr":"Année création"},
    "nt_mois_creation":   {"en":"Month (created)",                         "fr":"Mois création"},
    "nt_jour_creation":   {"en":"Day (created)",                           "fr":"Jour création"},
    "nt_annee_modif":     {"en":"Year (modified)",                         "fr":"Année modif"},
    "nt_mois_modif":      {"en":"Month (modified)",                        "fr":"Mois modif"},
    "nt_jour_modif":      {"en":"Day (modified)",                          "fr":"Jour modif"},
    "nt_extension":       {"en":"Extension",                               "fr":"Extension"},
    "nt_categorie":       {"en":"Category",                                "fr":"Catégorie"},
    "nt_taille":          {"en":"Size range",                              "fr":"Taille"},
    "nt_premiere_lettre": {"en":"First letter",                            "fr":"1ère lettre"},
    "nt_exif_annee":      {"en":"Year (EXIF photo)",                       "fr":"Année photo (EXIF)"},
    "nt_exif_mois":       {"en":"Month (EXIF photo)",                      "fr":"Mois photo (EXIF)"},
    "nt_exif_jour":       {"en":"Day (EXIF photo)",                        "fr":"Jour photo (EXIF)"},
    "nt_exif_date_full":  {"en":"Full date (EXIF)",                        "fr":"Date complète (EXIF)"},
    "nt_nom_fichier":     {"en":"Filename (no ext)",                       "fr":"Nom du fichier (sans ext)"},
    "card_files":         {"en":"Files",                                   "fr":"Fichiers"},
    "card_subfolders":    {"en":"Subfolders",                              "fr":"Sous-dossiers"},
    "card_total_size":    {"en":"Total size",                              "fr":"Taille totale"},
    "card_extensions":    {"en":"Extensions",                              "fr":"Extensions"},
    "col_extension":      {"en":"Extension",                               "fr":"Extension"},
    "col_category":       {"en":"Category",                                "fr":"Catégorie"},
    "col_files":          {"en":"Files",                                   "fr":"Fichiers"},
    "col_total_size":     {"en":"Total size",                              "fr":"Taille totale"},
    "col_percent":        {"en":"%",                                       "fr":"%"},
    "col_name":           {"en":"Name",                                    "fr":"Nom"},
    "col_size":           {"en":"Size",                                    "fr":"Taille"},
    "col_date":           {"en":"Modified",                                "fr":"Modifié le"},
    "col_focal":          {"en":"Focal",                                   "fr":"Focale"},
    "col_device":         {"en":"Device",                                  "fr":"Appareil"},
    "col_brand":          {"en":"Brand",                                   "fr":"Marque"},
    "col_aperture":       {"en":"Aperture",                                "fr":"Ouverture"},
    "col_exposure":       {"en":"Exposure",                                "fr":"Exposition"},
    "op_section":         {"en":"OPERATION",                               "fr":"OPÉRATION"},
    "summary_section":    {"en":"SUMMARY",                                 "fr":"RÉSUMÉ"},
    "sect_mode_copy":     {"en":"\U0001f4cb  Copy  (originals are kept)",  "fr":"\U0001f4cb  Copier  (les originaux sont conservés)"},
    "sect_mode_move":     {"en":"\u2702\ufe0f   Move  (originals are deleted)","fr":"\u2702\ufe0f   Déplacer  (les originaux sont supprimés)"},
    "verb_copy":          {"en":"copy",                                    "fr":"copier"},
    "verb_move":          {"en":"move",                                    "fr":"déplacer"},
    "verb_copied":        {"en":"copied",                                  "fr":"copiés"},
    "verb_moved":         {"en":"moved",                                   "fr":"déplacés"},
    "collision_title":    {"en":"Files already exist at destination",      "fr":"Fichiers déjà présents à destination"},
    "warn_move":          {"en":"\n\u26a0\ufe0f  Originals will be DELETED.","fr":"\n\u26a0\ufe0f  Les originaux seront SUPPRIMÉS."},
    "node_sel_status":    {"en":"  |  {n} selected \u2014 Del to delete",  "fr":"  |  {n} sélectionné(s) \u2014 Suppr pour effacer"},
    "close_btn":          {"en":"\u2715 Close",                            "fr":"\u2715 Fermer"},
    "reset_btn":          {"en":"\u21ba Reset",                            "fr":"\u21ba Reset"},
    "loading":            {"en":"Loading\u2026",                           "fr":"Chargement\u2026"},
    "video_hint":         {"en":"Space: pause  \u2022  Esc: close",        "fr":"Espace : pause  \u2022  Echap : fermer"},
    "video_error":        {"en":"Error:\n{msg}",                           "fr":"Erreur :\n{msg}"},
    "node_badge_folder":  {"en":"FOLDER",                                 "fr":"DOSSIER"},
    "node_badge_liant":   {"en":"CONNECTOR",                              "fr":"LIANT"},
    "node_badge_arg":     {"en":"ARG",                                    "fr":"ARG"},
    "rename_folder_title":{"en":"Rename folder",                           "fr":"Renommer le dossier"},
    "edit_liant_title":   {"en":"Edit connector",                          "fr":"Modifier le liant"},
    "no_preset":          {"en":"No preset",                                 "fr":"Aucun préset"},
    "select_preset":      {"en":"\u2014 select \u2014",                         "fr":"\u2014 s\u00e9lectionner \u2014"},
    "save_preset_title":  {"en":"Save preset",                                "fr":"Sauvegarder le pr\u00e9set"},
    "load_preset_title":  {"en":"Load a preset",                              "fr":"Charger un pr\u00e9set"},
    "delete_preset_confirm": {"en":"Delete preset \u00ab{name}\u00bb?",         "fr":"Supprimer le pr\u00e9set \u00ab {name} \u00bb ?"},
    "current_preset":     {"en":"the current preset",                         "fr":"le preset courant"},
    "save_before_new":    {"en":"Save changes to {label} before creating a new preset?", "fr":"Sauvegarder les modifications de {label} avant de cr\u00e9er un nouveau preset ?"},
    "save_before_load":   {"en":"Save changes to {label} before loading \u00ab{name}\u00bb?", "fr":"Sauvegarder les modifications de {label} avant de charger \u00ab {name} \u00bb ?"},
    "separator_title":    {"en":"Node separator",                              "fr":"S\u00e9parateur de ce node"},
    "separator_hint":     {"en":"The separator is added AFTER this node\u2019s value\nto form the parent folder name.\n\nExample: EXIF Year = \u00ab2026\u00bb + Connector \u00ab-\u00bb + Month \u00ab04\u00bb\n  \u2192 folder \u00ab2026-04\u00bb", "fr":"Le s\u00e9parateur est ajout\u00e9 APR\u00c8S la valeur de ce node\npour former le nom du dossier parent.\n\nExemple : Ann\u00e9e EXIF = \u00ab 2026 \u00bb + Liant \u00ab - \u00bb + Mois \u00ab 04 \u00bb\n  \u2192 dossier \u00ab 2026-04 \u00bb"},
    "wrong_port_msg":     {"en":"Connect an Argument or Connector to the \u25bc NAME port of the folder,\nnot to the \u25c4 input port.", "fr":"Reliez un Argument ou Liant au port \u25bc NOM du dossier,\nnon au port \u25c4 entr\u00e9e."},
    "no_nodes_canvas":    {"en":"No nodes on the canvas.",                    "fr":"Aucun node sur le canvas."},
    "no_files_preview":   {"en":"No files indexed.\nPlease do a scan in the Explorer tab first.", "fr":"Aucun fichier index\u00e9.\nEffectuez d\u2019abord une analyse dans l\u2019onglet Explorateur."},
    "summary_template":   {"en":"Operations: {n:,}\nMode: {mode}\nDestination: {dest}", "fr":"Op\u00e9rations : {n:,}\nMode : {mode}\nDestination : {dest}"},
    "dest_undefined":     {"en":"(undefined)",                                "fr":"(non d\u00e9fini)"},
    "dest_label":         {"en":"to:\n{dest}",                               "fr":"vers :\n{dest}"},
    "n_errors_status":    {"en":"  —  {n} error(s)",                          "fr":"  —  {n} erreur(s)"},
    "n_others":           {"en":"\n... and {n} more.",                        "fr":"\n... et {n} autres."},
    "sep_none":           {"en":"None",                                       "fr":"Aucun"},
    "sep_dash":           {"en":"Dash -",                                     "fr":"Tiret -"},
    "sep_space":          {"en":"Space",                                      "fr":"Espace"},
    "sep_dot":            {"en":"Dot .",                                      "fr":"Point ."},
}


def _(key, **kwargs):
    """Return the UI string for *key* in the current locale, with optional format args."""
    entry = _STRINGS.get(key, {})
    s = entry.get(_LOCALE, entry.get("en", key))
    return s.format(**kwargs) if kwargs else s

def set_locale(lang: str):
    """Switch the active locale ('en' or 'fr').
    After calling this, call root.refresh_locale() to update dynamic StringVars."""
    global _LOCALE
    _LOCALE = lang if lang in ("en", "fr") else "en"

from collections import defaultdict
from pathlib import Path

BG       = "#1c1b19"
SURFACE  = "#201f1d"
SURFACE2 = "#2d2c2a"
BORDER   = "#393836"
TEXT     = "#cdccca"
MUTED    = "#797876"
PRIMARY  = "#4f98a3"
PRIMARY_H= "#227f8b"
SUCCESS  = "#6daa45"
ORANGE   = "#fdab43"
PURPLE   = "#a86fdf"

EXTENSION_COLORS = {

    "images":"#fdab43","videos":"#dd6974","audio":"#6daa45",
    "code":"#4f98a3","docs":"#a86fdf","data":"#5591c7",
    "archives":"#bb653b","other":"#797876",
}
EXT_CATEGORIES = {

    "images":{".jpg",".jpeg",".png",".gif",".bmp",".webp",".svg",".ico",".tiff",".heic",
              ".raw",".cr2",".nef",".arw",".dng",".orf",".rw2",".pef",".srw",".x3f"},
    "videos":{".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm",".m4v"},
    "audio":{".mp3",".wav",".flac",".aac",".ogg",".wma",".m4a"},
    "code":{".py",".js",".ts",".html",".css",".java",".c",".cpp",".h",".go",".rs",
            ".php",".rb",".sh",".json",".xml",".yaml",".yml",".toml"},
    "docs":{".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",".txt",".md",".odt",".rtf"},
    "data":{".csv",".sql",".db",".sqlite",".parquet",".feather"},
    "archives":{".zip",".tar",".gz",".bz2",".7z",".rar",".xz"},
}
IMAGE_EXTS = {".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff",".heic"}

RAW_EXTS   = {".arw",".raw",".cr2",".nef",".dng",".orf",".rw2",".pef",".srw",".x3f"}
VIDEO_EXTS = {".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm",".m4v"}
PREVIEW_W  = 280
PREVIEW_H  = 210

def get_category(ext):
    """Map a file extension to the coarse category used by the explorer and organizer."""

    ext = ext.lower()
    for cat, exts in EXT_CATEGORIES.items():
        if ext in exts: return cat
    return "other"

def fmt_size(n):
    """Format a file size in bytes into a short human-readable value."""

    for unit in ("o","Ko","Mo","Go","To"):
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} Po"

# =============================================================================
# Metadata and preview helpers
# Utility functions for EXIF extraction, RAW previews, and OS-level file opening.
# =============================================================================
def read_exif(filepath):
    """Extract a reduced set of EXIF fields from image and RAW files using available libraries."""

    meta = {}
    ext = Path(filepath).suffix.lower()
    if ext not in IMAGE_EXTS and ext not in RAW_EXTS:
        return meta
# RAW files often need a different metadata path and thumbnail strategy than standard images.
    if ext in RAW_EXTS:
        try:
            import exifread
            with open(filepath, "rb") as f:
                tags = exifread.process_file(f, stop_tag="UNDEF", details=False)
            def gt(k):
                v = tags.get(k); return str(v).strip() if v else None
            if iso := gt("EXIF ISOSpeedRatings"): meta["ISO"] = iso
            if fl := gt("EXIF FocalLength"):
                try:
                    n,d = map(int, str(fl).split("/")); meta["Focale"] = f"{n//d} mm"
                except: meta["Focale"] = fl
            if mk := gt("Image Make"): meta["Marque"] = mk
            if mo := gt("Image Model"): meta["Appareil"] = mo
            if et := gt("EXIF ExposureTime"): meta["Exposition"] = et + " s"
            if fn := gt("EXIF FNumber"):
                try:
                    n,d = map(int, str(fn).split("/")); meta["Ouverture"] = f"f/{n/d:.1f}"
                except: meta["Ouverture"] = fn
            if dt := gt("EXIF DateTimeOriginal"): meta["Date"] = dt
            return meta
        except ImportError: pass
        except Exception as _e: print(f"[READ_EXIF][exifread] {filepath!r}: {_e}")
    try:
        from PIL import Image, ExifTags
        img = Image.open(filepath)
        exif_data = getattr(img, "_getexif", lambda: None)()
        if exif_data:
            for tag_id, val in exif_data.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag == "ISOSpeedRatings": meta["ISO"] = str(val)
                elif tag == "FocalLength":
                    try: meta["Focale"] = f"{round(val[0]/val[1])} mm"
                    except: meta["Focale"] = str(val)
                elif tag == "Make": meta["Marque"] = str(val).strip()
                elif tag == "Model": meta["Appareil"] = str(val).strip()
                elif tag == "ExposureTime":
                    try: meta["Exposition"] = f"1/{int(val[1]/val[0])} s"
                    except: meta["Exposition"] = str(val)
                elif tag == "FNumber":
                    try: meta["Ouverture"] = f"f/{val[0]/val[1]:.1f}"
                    except: meta["Ouverture"] = str(val)
                elif tag == "DateTime": meta["Date"] = str(val)
    except Exception as _e: print(f"[READ_EXIF][Pillow] {filepath!r}: {_e}")
    return meta

def open_raw_thumbnail(filepath):
    """Build a preview image for a RAW photo using rawpy, Pillow, or dcraw fallback strategies."""

    try:
        import rawpy
        with rawpy.imread(filepath) as raw:
            thumb = raw.extract_thumb()
            if thumb.format.name in ("JPEG","PNG"):
                from PIL import Image; import io
                return Image.open(io.BytesIO(thumb.data))
            rgb = raw.postprocess(use_camera_wb=True, half_size=True)
            from PIL import Image; return Image.fromarray(rgb)
    except ImportError: pass
    except Exception: pass
    try:
        from PIL import Image; img = Image.open(filepath); img.thumbnail((1920,1920)); return img
    except Exception: pass
    try:
        r = subprocess.run(["dcraw","-e","-c",filepath], capture_output=True, timeout=15)
        if r.returncode == 0:
            from PIL import Image; import io; return Image.open(io.BytesIO(r.stdout))
    except Exception: pass
    return None

def is_360_image(filepath):
    """Return True when an image looks like an equirectangular panorama based on ratio or XMP hints."""

    try:
        from PIL import Image
        img = Image.open(filepath); w,h = img.size
        if 1.9 <= (w/h if h else 0) <= 2.1: return True
        xmp = str(img.info.get("xmp","") or img.info.get("XML:com.adobe.xmp",""))
        if "equirectangular" in xmp.lower() or "ProjectionType" in xmp: return True
    except Exception: pass
    return False

def open_file(path, parent=None):
    """Open a file with the operating system default application."""

    try:
        if sys.platform == "win32": os.startfile(str(Path(path)))
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else:
            for p in ("xdg-open",):
                try: subprocess.Popen([p, path]); return
                except FileNotFoundError: continue
    except Exception as ex:
        if parent: messagebox.showerror(_("error"), str(ex), parent=parent)
# =============================================================================
# Video and fullscreen viewers
# Playback helpers and specialized viewers for media-rich previews.
# =============================================================================
class VideoPlayer:
    """Low-level embedded video player used by preview canvases and fullscreen playback windows."""

    # Internal state groups playback state, decoding backends, audio buffers, and canvas sizing.
    def __init__(self, canvas, w, h):
        self.canvas = canvas; self.w = w; self.h = h
        self._cap = None
        self._playing = False
        self._muted = False
        self._volume = 1.0
        self._thread = None
        self._tk_img = None
        self._fps = 25.0
        self._frame_idx = 0
        self._total_frames = 0
        self._lock = threading.Lock()
        self._on_state_change = None
        self._audio_frames = None
        self._frame_queue  = None  # initialized in play()
        self._audio_pos = 0
        self._audio_sr = 44100
        self._audio_stream = None
        self._has_audio = False
        self._ffmpeg_proc        = None
        self._ffmpeg_first_frame = None
        self._use_ffmpeg         = False
        self._src_path           = None
        self._out_w              = w
        self._out_h              = h

    def _fire_state(self, playing):
        """Calls _on_state_change safely from any thread."""
        cb = self._on_state_change
        if not cb: return
        try:
            self.canvas.after(0, lambda: cb(playing) if self._on_state_change else None)
        except Exception:
            pass

    # Loading is asynchronous so heavy video probing does not freeze the Tkinter event loop.
    def load(self, path, on_state_change=None):
        self.stop()
        self._on_state_change = on_state_change
        threading.Thread(target=self._do_load, args=(path,), daemon=True).start()

    # Playback starts two loops: a decoding thread and a Tk-side display loop.
    def play(self):
        if not self._cap and not self._use_ffmpeg: return
        import queue as _q
        self._frame_queue = _q.Queue(maxsize=2)
        self._playing = True
        self._fire_state(True)
        threading.Thread(target=self._play_loop, daemon=True).start()
        self._tick()  # Start the display loop in the Tkinter thread
        if self._has_audio and not self._muted:
            self._start_audio()

    # Tkinter UI updates must stay on the main thread, so frames are consumed here from a queue.
    def _tick(self):
        """Display loop on the Tkinter thread: consumes _frame_queue."""
        if not self._playing:
            return
        try:
            img = self._frame_queue.get_nowait()
            self._put_frame(img)
        except Exception:
            pass  # Queue is empty during this cycle
        delay_ms = max(8, int(1000.0 / min(self._fps or 25.0, 60.0)))
        try:
            self.canvas.after(delay_ms, self._tick)
        except Exception:
            pass  # Canvas was destroyed

    def pause(self):
        self._playing = False
        self._stop_audio()
        self._fire_state(False)

    def toggle(self):
        if self._playing: self.pause()
        else: self.play()

    def stop(self):
        self._playing = False
        self._stop_audio()
        with self._lock:
            if self._cap: self._cap.release(); self._cap = None
        self._close_ffmpeg()
        self._use_ffmpeg   = False
        self._audio_frames = None; self._has_audio = False

    # Seeking reopens the FFmpeg pipe when needed because rawvideo pipes are forward-only.
    def seek(self, ratio):
        target = int(ratio * self._total_frames)
# FFmpeg streams cannot seek backwards cheaply, so the pipe is recreated at the target position.
        if self._use_ffmpeg and self._src_path:
            was_playing = self._playing
            self._playing = False
            time.sleep(0.05)
            self._frame_idx = target
            self._open_ffmpeg(self._src_path, self._out_w, self._out_h, start_frame=target)
            if was_playing:
                self._playing = True
                import queue as _q
                self._frame_queue = _q.Queue(maxsize=2)
                threading.Thread(target=self._play_loop, daemon=True).start()
                try: self.canvas.after(0, self._tick)
                except Exception: pass
            else:
                self._show_single_frame()
        else:
            with self._lock:
                if self._cap: self._cap.set(1, target); self._frame_idx = target
            if not self._playing: self._show_single_frame()
        if self._has_audio and self._audio_frames is not None:
            self._audio_pos = int(ratio * len(self._audio_frames))

    def set_muted(self, muted):
        self._muted = muted
        if muted: self._stop_audio()
        elif self._playing and self._has_audio: self._start_audio()

    def set_volume(self, vol):
        self._volume = max(0.0, min(1.0, float(vol)))

    @property
    def is_playing(self): return self._playing

    @property
    def progress(self):
        return (self._frame_idx / self._total_frames) if self._total_frames else 0.0

    @property
    def time_str(self):
        fps = self._fps or 25
        def fmt(s): return f"{int(s)//60}:{int(s)%60:02d}"
        return f"{fmt(self._frame_idx/fps)} / {fmt(self._total_frames/fps)}"

    # Prefer ffprobe for accurate metadata, then fall back to OpenCV when FFmpeg tools are unavailable.
    def _probe_video(self, path):
        """Returns (fps, total_frames, vw, vh) using ffprobe or cv2."""
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-select_streams", "v:0", path],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                import json as _json
                info = _json.loads(r.stdout)
                st   = info["streams"][0]
                vw   = int(st.get("width", 0))
                vh   = int(st.get("height", 0))
                nb   = int(st.get("nb_frames", 0) or 0)
                fr   = st.get("r_frame_rate", "25/1")
                try:
                    n, d = fr.split("/"); fps = float(n) / float(d)
                except Exception:
                    fps = 25.0
                return fps, nb, vw, vh
        except Exception:
            pass
        try:
            import cv2
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                fps   = cap.get(5) or 25.0
                total = int(cap.get(7))
                vw    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                vh    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                return fps, total, vw, vh
        except Exception:
            pass
        return 25.0, 0, self.w, self.h

    # FFmpeg is used as the fast path for resizing and decoding large or complex videos.
    def _open_ffmpeg(self, path, out_w, out_h, start_frame=0):
        """Opens a resized FFmpeg pipe. Returns True on success."""
        self._close_ffmpeg()
        try:
            seek_args = []
            if start_frame > 0 and self._fps:
                t = start_frame / self._fps
                seek_args = ["-ss", f"{t:.3f}"]
            cmd = [
                "ffmpeg",
                "-hwaccel", "auto",
                *seek_args,
                "-i", path,
                "-vf", f"scale={out_w}:{out_h}",
                "-pix_fmt", "rgb24",
                "-f", "rawvideo",
                "-an",
                "-loglevel", "quiet",
                "pipe:1"
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL,
                                    bufsize=out_w * out_h * 3 * 8)
            frame_bytes = out_w * out_h * 3
            import queue as _tq
            q = _tq.Queue()
            def _read():
                try: q.put(proc.stdout.read(frame_bytes))
                except Exception: q.put(b"")
            t = threading.Thread(target=_read, daemon=True); t.start()
            try:
                test = q.get(timeout=10)  # 10s max to start
            except _tq.Empty:
                test = b""
            if len(test) == frame_bytes:
                self._ffmpeg_proc        = proc
                self._ffmpeg_first_frame = test
                return True
            proc.kill(); proc.wait()
        except FileNotFoundError:
            pass  # FFmpeg not installed -> OpenCV fallback
        except Exception:
            pass
        return False

    def _close_ffmpeg(self):
        p = self._ffmpeg_proc
        self._ffmpeg_proc        = None
        self._ffmpeg_first_frame = None
        if p:
            try: p.kill(); p.wait(timeout=2)
            except Exception: pass

    # Backend selection happens here: FFmpeg first, OpenCV fallback second.
    def _do_load(self, path):
        self._src_path = path
        fps, total, vw, vh = self._probe_video(path)
        scale  = min(self.w / max(vw, 1), self.h / max(vh, 1))
        out_w  = max(2, int(vw * scale) & ~1)
        out_h  = max(2, int(vh * scale) & ~1)
        self._fps          = fps
        self._total_frames = total
        self._frame_idx    = 0
        self._out_w        = out_w
        self._out_h        = out_h
        if self._open_ffmpeg(path, out_w, out_h):
            self._use_ffmpeg = True
            with self._lock:
                self._cap = None
        else:
            self._use_ffmpeg = False
            try:
                import cv2
                cap = cv2.VideoCapture(path)
                if not cap.isOpened():
                    raise RuntimeError("Unable to open the video")
                with self._lock:
                    self._cap = cap
            except ImportError:
                self.canvas.after(0, self._show_no_cv2); return
            except Exception as ex:
                self.canvas.after(0, lambda: self._show_error(str(ex))); return

        self._show_single_frame()
        threading.Thread(target=self._load_audio, args=(path,), daemon=True).start()

    def _raw_to_tk(self, raw_bytes, w, h):
        from PIL import Image, ImageTk
        import numpy as np
        arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, w, 3))
        return ImageTk.PhotoImage(Image.fromarray(arr))

    def _show_single_frame(self):
        if self._use_ffmpeg:
            raw = self._ffmpeg_first_frame
            if raw:
                img = self._raw_to_tk(raw, self._out_w, self._out_h)
                try: self.canvas.after(0, self._put_frame, img)
                except Exception: pass
            return
        import cv2
        with self._lock:
            if not self._cap: return
            ret, frame = self._cap.read()
            if ret:
                self._frame_idx = int(self._cap.get(1))
                img = self._cv2_to_tk(frame)
                try: self.canvas.after(0, self._put_frame, img)
                except Exception: pass

    # Decoding is intentionally decoupled from drawing to keep UI responsiveness stable.
    def _play_loop(self):
        """Decoding thread: fills self._frame_queue at the source FPS rate."""
        src_fps   = self._fps or 25.0
        src_delay = 1.0 / src_fps
        t_start   = time.monotonic()
        frames_read = 0

        if self._use_ffmpeg:
            proc       = self._ffmpeg_proc
            frame_size = self._out_w * self._out_h * 3
            out_w, out_h = self._out_w, self._out_h
            first = self._ffmpeg_first_frame
            if first:
                img = self._raw_to_tk(first, out_w, out_h)
                try: self._frame_queue.put(img, timeout=0.5)
                except Exception: pass
                frames_read += 1

            while self._playing:
                raw = proc.stdout.read(frame_size)
                if len(raw) < frame_size:
                    self._playing = False
                    self._stop_audio()
                    self._fire_state(False)
                    break
                frames_read    += 1
                self._frame_idx = frames_read
                img = self._raw_to_tk(raw, out_w, out_h)
                try:
                    self._frame_queue.put(img, timeout=0.5)
                except Exception:
                    pass
                next_t  = t_start + frames_read * src_delay
                sleep_t = next_t - time.monotonic()
                if sleep_t > 0.001:
                    time.sleep(sleep_t)
        else:
            import cv2
            RENDER_MAX  = 60.0
            step        = max(1, round(src_fps / RENDER_MAX))

            while self._playing:
                with self._lock:
                    if not self._cap:
                        break
                    display_frame = None
                    for _ in range(step):
                        ret, frame = self._cap.read()
                        if not ret:
                            self._cap.set(1, 0)
                            self._frame_idx = 0
                            self._audio_pos = 0
                            self._playing   = False
                            self._stop_audio()
                            self._fire_state(False)
                            break
                        frames_read    += 1
                        self._frame_idx = int(self._cap.get(1))
                        display_frame   = frame
                    if display_frame is None:
                        break

                img = self._cv2_to_tk(display_frame)
                try:
                    self._frame_queue.put(img, timeout=0.5)
                except Exception:
                    pass
                next_t  = t_start + frames_read * src_delay
                sleep_t = next_t - time.monotonic()
                if sleep_t > 0.001:
                    time.sleep(sleep_t)

    def _cv2_to_tk(self, frame):
        import cv2
        from PIL import Image, ImageTk
        fh, fw = frame.shape[:2]
        scale = min(self.w / fw, self.h / fh)
        nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
        if nw != fw or nh != fh:
            frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return ImageTk.PhotoImage(Image.fromarray(rgb))

    def _put_frame(self, tk_img):
        try:
            self._tk_img = tk_img
            self.canvas.delete("video_frame")
            tw = tk_img.width(); th = tk_img.height()
            self.canvas.create_image((self.w-tw)//2, (self.h-th)//2,
                                      anchor="nw", image=tk_img, tags="video_frame")
        except Exception:
            pass  # Canvas was destroyed (fenêtre fermée pendant la lecture)

    # Audio extraction also uses a layered fallback strategy: MoviePy first, FFmpeg pipe second.
    def _load_audio(self, path):
        try:
            import numpy as np
            try:
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(path)
                if clip.audio is None: clip.close(); return
                sr = 44100
                arr = clip.audio.to_soundarray(fps=sr, nbytes=2); clip.close()
                if arr.ndim == 1: arr = np.column_stack([arr, arr])
                arr = np.clip(arr, -1.0, 1.0)
                self._audio_frames = (arr * 32767).astype(np.int16)
                self._audio_sr = sr; self._has_audio = True; return
            except ImportError: pass
            except Exception: pass
            cmd = ["ffmpeg","-i",path,"-vn","-acodec","pcm_s16le",
                   "-ar","44100","-ac","2","-f","s16le","pipe:1","-loglevel","quiet"]
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            if r.returncode == 0 and r.stdout:
                data = np.frombuffer(r.stdout, dtype=np.int16)
                if data.size % 2: data = data[:-1]
                self._audio_frames = data.reshape(-1, 2)
                self._audio_sr = 44100; self._has_audio = True
        except Exception: pass

    # Audio playback is optional and should fail silently when dependencies are missing.
    def _start_audio(self):
        if not self._has_audio or self._muted or self._audio_frames is None: return
        self._stop_audio()
        try:
            import sounddevice as sd, numpy as np
            frames = self._audio_frames; sr = self._audio_sr; player = self
            def callback(outdata, frame_count, time_info, status):
                pos = player._audio_pos; end = pos + frame_count
                chunk = frames[pos:end]
                if len(chunk) < frame_count:
                    pad = np.zeros((frame_count - len(chunk), 2), dtype=np.int16)
                    chunk = np.vstack([chunk, pad]) if len(chunk) else pad
                player._audio_pos = end
                vol = player._volume
                out = (chunk.astype(np.float32) * vol).astype(np.int16)
                outdata[:] = out.reshape(outdata.shape)
            self._audio_stream = sd.RawOutputStream(
                samplerate=sr, channels=2, dtype="int16",
                blocksize=2048, callback=callback)
            self._audio_stream.start()
        except ImportError: pass
        except Exception: pass

    def _stop_audio(self):
        try:
            if self._audio_stream:
                self._audio_stream.stop(); self._audio_stream.close()
                self._audio_stream = None
        except Exception: pass

    def _show_no_cv2(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0,0,self.w,self.h, fill="#1a0a0c", outline="")
        self.canvas.create_text(self.w//2, self.h//2-20, text="🎬", fill="#dd6974", font=("Segoe UI",36))
        self.canvas.create_text(self.w//2, self.h//2+20,
            text=_("opencv_required"), fill=MUTED, font=("Segoe UI",8), justify="center")

    def _show_error(self, msg):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0,0,self.w,self.h, fill="#1a0a0c", outline="")
        self.canvas.create_text(self.w//2, self.h//2, text=f"Erreur :\n{msg}",
            fill="#dd6974", font=("Segoe UI",8), justify="center", width=self.w-20)
class FullscreenVideoPlayer(tk.Toplevel):
    """Fullscreen window that wraps `VideoPlayer` with transport and audio controls."""

    def __init__(self, parent, filepath):
        super().__init__(parent)
        self.title(Path(filepath).name)
        self.configure(bg="black"); self.attributes("-fullscreen", True)
        self._seek_var = tk.DoubleVar(value=0.0); self._muted = False

        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        bar = tk.Frame(self, bg="#0e0e0e"); bar.pack(side="bottom", fill="x")
        s = ttk.Style(self)
        s.configure("FS.Horizontal.TScale", background="#0e0e0e",
                    troughcolor="#393836", sliderlength=14, sliderrelief="flat")
        ttk.Scale(bar, from_=0, to=1, orient="horizontal", variable=self._seek_var,
                  command=self._on_seek, style="FS.Horizontal.TScale").pack(fill="x", padx=12, pady=(6,2))
        btn_row = tk.Frame(bar, bg="#0e0e0e"); btn_row.pack(fill="x", padx=12, pady=(0,8))
        self._play_btn = tk.Button(btn_row, text="\u23f8", fg=SUCCESS, bg="#0e0e0e",
            relief="flat", font=("Segoe UI",13,"bold"), width=3,
            cursor="hand2", activebackground="#0e0e0e", command=self._toggle_play)
        self._play_btn.pack(side="left", padx=(0,8))
        self._time_lbl = tk.Label(btn_row, text="0:00 / 0:00", bg="#0e0e0e", fg=MUTED, font=("Segoe UI",10))
        self._time_lbl.pack(side="left", padx=(0,16))
        self._mute_btn = tk.Button(btn_row, text="\U0001f50a", fg=TEXT, bg="#0e0e0e", relief="flat",
            font=("Segoe UI",12), cursor="hand2",
            activebackground="#0e0e0e", command=self._toggle_mute)
        self._mute_btn.pack(side="left")
        self._vol_var = tk.DoubleVar(value=1.0)
        ttk.Scale(btn_row, from_=0, to=1, orient="horizontal", variable=self._vol_var,
                  command=self._on_volume, style="FS.Horizontal.TScale", length=90).pack(side="left", padx=(4,16))
        tk.Button(btn_row, text=_("close_btn"), bg="#3a2020", fg="#dd6974", relief="flat",
            font=("Segoe UI",10), padx=12, pady=2, cursor="hand2",
            command=self._close).pack(side="right")
        tk.Label(btn_row, text=_("video_hint"),
            bg="#0e0e0e", fg=MUTED, font=("Segoe UI",8)).pack(side="right", padx=12)

        self.bind("<Escape>", lambda e: self._close())
        self.bind("<space>", lambda e: self._toggle_play())
        self.canvas.bind("<Escape>", lambda e: self._close())
        self.canvas.bind("<space>", lambda e: self._toggle_play())
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set())
        self.canvas.focus_set()  # make sure the canvas has focus on startup

        self.update_idletasks()
        cw = self.winfo_screenwidth(); ch = self.winfo_screenheight() - 80
        self._player = VideoPlayer(self.canvas, cw, ch)
        self._player.load(filepath, on_state_change=self._on_state)
        self.after(700, self._auto_play)
        self._update_bar()

    def _auto_play(self):
        try:
            if not self.winfo_exists(): return
            self._player.play()
            self._play_btn.config(text="\u23f8", fg=SUCCESS)
        except Exception:
            pass

    def _on_state(self, playing):
        try:
            if not self.winfo_exists(): return
            self._play_btn.config(text="\u23f8" if playing else "\u25b6", fg=SUCCESS if playing else "#dd6974")
        except Exception:
            pass

    def _toggle_play(self): self._player.toggle()
    def _on_seek(self, val): self._player.seek(float(val))

    def _toggle_mute(self):
        self._muted = not self._muted
        self._player.set_muted(self._muted)
        self._mute_btn.config(text="\U0001f507" if self._muted else "\U0001f50a",
                              fg="#dd6974" if self._muted else TEXT)

    def _on_volume(self, val):
        v = float(val); self._player.set_volume(v)
        if v == 0: self._muted=True; self._mute_btn.config(text="\U0001f507",fg="#dd6974")
        elif self._muted:
            self._muted=False; self._player.set_muted(False); self._mute_btn.config(text="\U0001f50a",fg=TEXT)

    def _update_bar(self):
        try:
            if not self.winfo_exists(): return
            self._seek_var.set(self._player.progress)
            self._time_lbl.config(text=self._player.time_str)
            self.after(150, self._update_bar)
        except Exception:
            pass

    def _close(self):
        self._player.stop(); self.destroy()
class FullscreenViewer(tk.Toplevel):
    """Fullscreen still-image viewer with zoom, pan, rotation, and mirroring tools."""

    def __init__(self, parent, filepath):
        super().__init__(parent)
        self.title(Path(filepath).name); self.configure(bg="black"); self.attributes("-fullscreen", True)
        self.filepath = filepath
        self._zoom=1.0; self._offset=[0,0]; self._drag_start=None
        self._orig=None; self._rotation=0; self._flip_h=False; self._flip_v=False; self._tk_img=None
        self._is_raw = Path(filepath).suffix.lower() in RAW_EXTS
        self._build_ui()
        threading.Thread(target=self._load_image, daemon=True).start()

    def _build_ui(self):
        bar=tk.Frame(self,bg="#111110",pady=8,padx=10); bar.pack(side="bottom",fill="x")
        self.canvas=tk.Canvas(self,bg="black",highlightthickness=0); self.canvas.pack(fill="both",expand=True)
        bc=dict(bg=SURFACE2,fg=TEXT,relief="flat",font=("Segoe UI",10),padx=10,pady=4,cursor="hand2",activebackground=BORDER,activeforeground=TEXT)
        def sep(): tk.Label(bar,text="|",bg="#111110",fg=BORDER,font=("Segoe UI",12)).pack(side="left",padx=3)
        tk.Button(bar,text=_("close_btn"),bg="#3a2020",fg="#dd6974",relief="flat",font=("Segoe UI",10),padx=12,pady=4,cursor="hand2",command=self.destroy).pack(side="right",padx=(6,0))
        tk.Label(bar,text=_("viewer_hint"),bg="#111110",fg=MUTED,font=("Segoe UI",8)).pack(side="right",padx=12)
        self._rot_lbl=tk.Label(bar,text="0\u00b0",bg="#111110",fg=ORANGE,font=("Segoe UI",11,"bold"),width=8); self._rot_lbl.pack(side="left",padx=(0,8))
        tk.Button(bar,text="\u21ba 90\u00b0",**bc,command=lambda:self._rotate(-90)).pack(side="left",padx=2)
        tk.Button(bar,text="\u21bb 90\u00b0",**bc,command=lambda:self._rotate(90)).pack(side="left",padx=2)
        tk.Button(bar,text="\u21d5 180\u00b0",**bc,command=lambda:self._rotate(180)).pack(side="left",padx=2)
        sep()
        tk.Button(bar,text="\u21d4 H",**bc,command=self._flip_horizontal).pack(side="left",padx=2)
        tk.Button(bar,text="\u21d5 V",**bc,command=self._flip_vertical).pack(side="left",padx=2)
        sep()
        tk.Button(bar,text="\u21ba Reset",bg=SURFACE2,fg=ORANGE,relief="flat",font=("Segoe UI",10),padx=10,pady=4,cursor="hand2",activebackground=BORDER,command=self._reset).pack(side="left",padx=2)
        if self._is_raw: tk.Label(bar,text="RAW",bg=ORANGE,fg="#1c1b19",font=("Segoe UI",8,"bold"),padx=6,pady=2).pack(side="left",padx=6)
        self.bind("<Escape>",lambda e:self.destroy())
        self.canvas.bind("<ButtonPress-1>",self._drag_start_cb)
        self.canvas.bind("<B1-Motion>",self._drag_move_cb)
        self.canvas.bind("<ButtonRelease-1>",self._drag_end_cb)
        self.canvas.bind("<MouseWheel>",lambda e:self._zoom_step(1.1 if e.delta>0 else 0.9))

    # RAW files need a separate loading path because Pillow alone cannot decode many camera formats.
    def _load_image(self):
        try:
            if self._is_raw:
                img = open_raw_thumbnail(self.filepath)
                if img is None: raise RuntimeError("Impossible de decoder ce fichier RAW.\nInstallez : pip install rawpy exifread")
            else:
                from PIL import Image; img = Image.open(self.filepath)
            self._orig = img; self.after(0, self._fit_and_draw)
        except Exception as ex: self.after(0, lambda: messagebox.showerror(_("error"), str(ex), parent=self))

    # Transformations are applied on a copy to preserve the original image as the single source of truth.
    def _get_transformed(self):
        from PIL import Image
        img = self._orig.copy()
        if self._flip_h: img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if self._flip_v: img = img.transpose(Image.FLIP_TOP_BOTTOM)
        if self._rotation: img = img.rotate(-self._rotation, expand=True)
        return img

    def _fit_and_draw(self):
        if not self._orig: return
        self.update_idletasks()
        cw,ch = self.canvas.winfo_width(),self.canvas.winfo_height()
        img = self._get_transformed()
        self._zoom=min(cw/img.width,ch/img.height); self._offset=[0,0]; self._draw()

    # Rendering is recomputed on every zoom, pan, rotation, or flip event for simplicity and correctness.
    def _draw(self):
        if not self._orig: return
        from PIL import Image, ImageTk
        self.update_idletasks()
        cw,ch = self.canvas.winfo_width(),self.canvas.winfo_height()
        img = self._get_transformed()
        nw,nh = max(1,int(img.width*self._zoom)),max(1,int(img.height*self._zoom))
        self._tk_img = ImageTk.PhotoImage(img.resize((nw,nh),Image.LANCZOS))
        self.canvas.delete("all"); self.canvas.create_image(cw//2+self._offset[0],ch//2+self._offset[1],anchor="center",image=self._tk_img)

    def _rotate(self,d): self._rotation=(self._rotation+d)%360; self._rot_lbl.config(text=f"{self._rotation}\u00b0"); self._fit_and_draw()
    def _flip_horizontal(self): self._flip_h=not self._flip_h; self._draw()
    def _flip_vertical(self): self._flip_v=not self._flip_v; self._draw()
    def _reset(self): self._rotation=0; self._flip_h=False; self._flip_v=False; self._rot_lbl.config(text="0\u00b0"); self._offset=[0,0]; self._fit_and_draw()
    def _zoom_step(self,f): self._zoom=max(0.05,min(self._zoom*f,20)); self._draw()
    def _drag_start_cb(self,e): self._drag_start=(e.x,e.y)
    def _drag_move_cb(self,e):
        if self._drag_start:
            self._offset[0]+=e.x-self._drag_start[0]; self._offset[1]+=e.y-self._drag_start[1]
            self._drag_start=(e.x,e.y); self._draw()
    def _drag_end_cb(self,e): self._drag_start=None
class Viewer360(tk.Toplevel):
    """Fullscreen 360° panorama viewer rendered from an equirectangular source image."""

    FOV=90; SPEED=0.3
    def __init__(self,parent,filepath):
        super().__init__(parent); self.title(f"360\u00b0 \u2014 {Path(filepath).name}")
        self.configure(bg="black"); self.attributes("-fullscreen",True)
        self.filepath=filepath; self._yaw=0.0; self._pitch=0.0; self._fov=self.FOV; self._roll=0
        self._drag_start=None; self._pano=None; self._tk_img=None; self._rendering=False; self._pending=False
        bar=tk.Frame(self,bg="#111110",pady=7,padx=8); bar.pack(side="bottom",fill="x")
        self.canvas=tk.Canvas(self,bg="black",highlightthickness=0); self.canvas.pack(fill="both",expand=True)
        bc=dict(bg=SURFACE2,fg=TEXT,relief="flat",font=("Segoe UI",10),padx=9,pady=3,cursor="hand2",activebackground=BORDER,activeforeground=TEXT)
        def sep(): tk.Label(bar,text="|",bg="#111110",fg=BORDER,font=("Segoe UI",12)).pack(side="left",padx=3)
        tk.Label(bar,text="\U0001f310 360\u00b0",bg="#111110",fg=ORANGE,font=("Segoe UI",10,"bold")).pack(side="left",padx=(0,6)); sep()
        tk.Button(bar,text="\u21ba \u221290\u00b0",**bc,command=lambda:self._add_roll(-90)).pack(side="left",padx=2)
        tk.Button(bar,text="\u21bb +90\u00b0",**bc,command=lambda:self._add_roll(90)).pack(side="left",padx=2)
        self._roll_lbl=tk.Label(bar,text="0\u00b0",bg="#111110",fg=ORANGE,font=("Segoe UI",10,"bold"),width=5); self._roll_lbl.pack(side="left",padx=(2,4)); sep()
        tk.Button(bar,text="\u2b06",**bc,command=lambda:self._set_pitch(85)).pack(side="left",padx=2)
        tk.Button(bar,text="\u27a1",**bc,command=lambda:self._set_pitch(0)).pack(side="left",padx=2)
        tk.Button(bar,text="\u2b07",**bc,command=lambda:self._set_pitch(-85)).pack(side="left",padx=2); sep()
        tk.Button(bar,text="\u21ba Reset",bg=SURFACE2,fg=ORANGE,relief="flat",font=("Segoe UI",10),padx=9,pady=3,cursor="hand2",activebackground=BORDER,command=self._reset_view).pack(side="left",padx=2); sep()
        tk.Button(bar,text=_("close_btn"),bg="#3a2020",fg="#dd6974",relief="flat",font=("Segoe UI",10),padx=12,pady=3,cursor="hand2",command=self.destroy).pack(side="right",padx=(6,0))
        self._info_lbl=tk.Label(bar,text=_("loading"),bg="#111110",fg=MUTED,font=("Segoe UI",8)); self._info_lbl.pack(side="right",padx=8)
        self.bind("<Escape>",lambda e:self.destroy())
        self.bind("<Left>",lambda e:self._add_yaw(-15)); self.bind("<Right>",lambda e:self._add_yaw(15))
        self.bind("<Up>",lambda e:self._add_pitch(10)); self.bind("<Down>",lambda e:self._add_pitch(-10))
        self.canvas.bind("<ButtonPress-1>",lambda e:setattr(self,"_drag_start",(e.x,e.y)))
        self.canvas.bind("<B1-Motion>",self._drag_move)
        self.canvas.bind("<ButtonRelease-1>",lambda e:setattr(self,"_drag_start",None))
        self.canvas.bind("<MouseWheel>",self._scroll)
        self.canvas.bind("<Configure>",lambda e:self._request_render())
        threading.Thread(target=self._load,daemon=True).start()

    def _load(self):
        try:
            from PIL import Image
            img=Image.open(self.filepath).convert("RGB")
            if img.width>4096: img=img.resize((4096,2048),Image.LANCZOS)
            self._pano=img; self.after(0,self._request_render)
        except Exception as ex: self.after(0,lambda:messagebox.showerror(_("error"),str(ex),parent=self))

    # Rendering is throttled through a pending flag so repeated user input does not spawn unlimited threads.
    def _request_render(self):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        if not self._rendering: self._pending=False; self._rendering=True; threading.Thread(target=self._render,daemon=True).start()
        else: self._pending=True

    # The panorama is sampled by projecting screen rays into spherical coordinates and remapping them into the source image.
    def _render(self):
        if not self._pano: self._rendering=False; return
        try:
            from PIL import Image; import numpy as np
            self.update_idletasks(); cw,ch=self.canvas.winfo_width(),self.canvas.winfo_height()
            if cw<2 or ch<2: self._rendering=False; return
            rw=min(cw,1280); rh=int(rw*ch/cw); pano=self._pano; pw,ph=pano.size; pa=np.array(pano)
            fov=math.radians(self._fov); yaw=math.radians(self._yaw); pit=math.radians(max(-85,min(85,self._pitch)))
            xs=np.linspace(-1,1,rw); ys=np.linspace(1,-1,rh); xg,yg=np.meshgrid(xs,ys)
            f=1.0/math.tan(fov/2); asp=rw/rh; dx=xg*asp; dy=yg; dz=np.full_like(dx,f)
            if self._roll!=0:
                rl=math.radians(self._roll); cr,sr=math.cos(rl),math.sin(rl); dx,dy=dx*cr-dy*sr,dx*sr+dy*cr
            cp,sp=math.cos(pit),math.sin(pit); dy2=dy*cp-dz*sp; dz2=dy*sp+dz*cp
            cy2,sy2=math.cos(yaw),math.sin(yaw); dx3=dx*cy2+dz2*sy2; dz3=-dx*sy2+dz2*cy2; dy3=dy2
            nm=np.sqrt(dx3**2+dy3**2+dz3**2); dx3/=nm; dy3/=nm; dz3/=nm
            lon=np.arctan2(dx3,dz3); lat=np.arcsin(np.clip(dy3,-1,1))
            u=((lon/(2*math.pi))+0.5)%1.0; v=(lat/math.pi)+0.5
            px=np.clip((u*pw).astype(int),0,pw-1); py_=np.clip((v*ph).astype(int),0,ph-1)
            out=Image.fromarray(pa[py_,px].astype("uint8"),"RGB")
            if rw!=cw or rh!=ch: out=out.resize((cw,ch),Image.NEAREST)
            try:
                if self.winfo_exists():
                    self.after(0,lambda i=out:self._show(i))
                else:
                    self._rendering=False
            except Exception:
                self._rendering=False
        except Exception as _e:
            print(f"[VIEWER360][render] {traceback.format_exc()}")
            self._rendering=False

    def _show(self,img):
        from PIL import ImageTk
        try:
            if not self.winfo_exists(): self._rendering=False; return
            if not self.canvas.winfo_exists(): self._rendering=False; return
        except Exception: self._rendering=False; return
        self._tk_img=ImageTk.PhotoImage(img); self.canvas.delete("all")
        self.canvas.create_image(0,0,anchor="nw",image=self._tk_img)
        self._info_lbl.config(text=f"Yaw:{self._yaw:.0f}\u00b0 Pitch:{self._pitch:.0f}\u00b0 Roll:{self._roll}\u00b0 FOV:{self._fov}\u00b0")
        self._rendering=False
        if self._pending: self._request_render()

    # Mouse drag updates yaw and pitch only; actual drawing stays delegated to the render request pipeline.
    def _drag_move(self,event):
        if self._drag_start:
            self._yaw=(self._yaw-(event.x-self._drag_start[0])*self.SPEED)%360
            self._pitch=max(-85,min(85,self._pitch-(event.y-self._drag_start[1])*self.SPEED))
            self._drag_start=(event.x,event.y); self._request_render()

    def _scroll(self,e): self._fov_step(-5 if e.delta>0 else 5)
    def _fov_step(self,d): self._fov=max(20,min(130,self._fov+d)); self._request_render()
    def _add_yaw(self,d): self._yaw=(self._yaw+d)%360; self._request_render()
    def _add_pitch(self,d): self._pitch=max(-85,min(85,self._pitch+d)); self._request_render()
    def _set_pitch(self,v): self._pitch=v; self._request_render()
    def _add_roll(self,d): self._roll=(self._roll+d)%360; self._roll_lbl.config(text=f"{self._roll}\u00b0"); self._request_render()
    def _reset_view(self): self._yaw=0.0; self._pitch=0.0; self._fov=self.FOV; self._roll=0; self._roll_lbl.config(text="0\u00b0"); self._request_render()



# =============================================================================
# Node-editor metadata model
# Helpers that convert file attributes into node fields and tree structures.
# =============================================================================
def _build_node_types() -> dict:
    """Build NODE_TYPES labels in the current locale — call after set_locale()."""
    return {
        "annee_creation":  {"label":_("nt_annee_creation"),  "color":"#4f98a3","field":"year_ctime"},
        "mois_creation":   {"label":_("nt_mois_creation"),   "color":"#4f98a3","field":"month_ctime"},
        "jour_creation":   {"label":_("nt_jour_creation"),   "color":"#4f98a3","field":"day_ctime"},
        "annee_modif":     {"label":_("nt_annee_modif"),     "color":"#fdab43","field":"year_mtime"},
        "mois_modif":      {"label":_("nt_mois_modif"),      "color":"#fdab43","field":"month_mtime"},
        "jour_modif":      {"label":_("nt_jour_modif"),      "color":"#fdab43","field":"day_mtime"},
        "extension":       {"label":_("nt_extension"),       "color":"#a86fdf","field":"ext"},
        "categorie":       {"label":_("nt_categorie"),       "color":"#a86fdf","field":"category"},
        "taille":          {"label":_("nt_taille"),          "color":"#6daa45","field":"size_range"},
        "premiere_lettre": {"label":_("nt_premiere_lettre"), "color":"#dd6974","field":"first_letter"},
        "exif_annee":      {"label":_("nt_exif_annee"),      "color":"#5591c7","field":"exif_year"},
        "exif_mois":       {"label":_("nt_exif_mois"),       "color":"#5591c7","field":"exif_month"},
        "exif_jour":       {"label":_("nt_exif_jour"),       "color":"#5591c7","field":"exif_day"},
        "exif_date_full":  {"label":_("nt_exif_date_full"),  "color":"#5591c7","field":"exif_date_full"},
        "nom_fichier":     {"label":_("nt_nom_fichier"),     "color":"#dd6974","field":"filename_noext"},
    }

NODE_TYPES = _build_node_types()
_exif_cache: dict = {}

def _get_exif_datetime(filepath):

    """Returns a datetime from the photo EXIF data, or None if unavailable.
    Priority: DateTimeOriginal > DateTimeDigitized > DateTime.
    Compatible with JPEG, HEIC, RAW (via exifread), and others through Pillow."""
    if filepath in _exif_cache:
        return _exif_cache[filepath]
    dt = None
    ext = Path(filepath).suffix.lower()
    if ext not in IMAGE_EXTS and ext not in RAW_EXTS:
        _exif_cache[filepath] = None
        return None
    try:
        import exifread, io as _io
        with open(filepath, "rb") as f:
            tags = exifread.process_file(f, stop_tag="UNDEF", details=False, debug=False)
        for tag in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
            v = tags.get(tag)
            if v:
                try:
                    dt = datetime.datetime.strptime(str(v).strip(), "%Y:%m:%d %H:%M:%S")
                    break
                except ValueError:
                    pass
    except Exception as _e:
        print(f"[EXIF][exifread] {filepath!r}: {_e}")
    if dt is None and ext in IMAGE_EXTS:
        try:
            from PIL import Image, ExifTags
            img = Image.open(filepath)
            exif_data = getattr(img, "_getexif", lambda: None)()
            if exif_data:
                for tag_id, val in exif_data.items():
                    tag = ExifTags.TAGS.get(tag_id, "")
                    if tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime") and val:
                        try:
                            dt = datetime.datetime.strptime(str(val).strip(), "%Y:%m:%d %H:%M:%S")
                            break
                        except ValueError:
                            pass
        except Exception as _e:
            print(f"[EXIF][Pillow] {filepath!r}: {_e}")
    _exif_cache[filepath] = dt
    return dt


def get_file_field(file_info, field):
    """Resolve a derived metadata field used by the organization engine for one indexed file."""

    path = file_info["path"]
    if "_mtime" not in file_info:
        try:
            st = os.stat(path)
            try:
                file_info["_mtime"] = datetime.datetime.fromtimestamp(st.st_mtime)
            except (OSError, OverflowError, ValueError):
                file_info["_mtime"] = datetime.datetime.now()
            try:
                file_info["_ctime"] = datetime.datetime.fromtimestamp(st.st_ctime)
            except (OSError, OverflowError, ValueError):
                file_info["_ctime"] = datetime.datetime.now()
        except OSError:
            file_info["_mtime"] = file_info["_ctime"] = datetime.datetime.now()
    mtime = file_info["_mtime"]
    ctime = file_info["_ctime"]
    if field == "year_ctime":   return str(ctime.year)
    if field == "month_ctime":  return f"{ctime.month:02d}"
    if field == "day_ctime":    return f"{ctime.day:02d}"
    if field == "year_mtime":   return str(mtime.year)
    if field == "month_mtime":  return f"{mtime.month:02d}"
    if field == "day_mtime":    return f"{mtime.day:02d}"
    if field == "ext":          return file_info["ext"].lstrip(".").upper() or "SANS_EXT"
    if field == "category":     return get_category(file_info["ext"]).capitalize()
    if field == "size_range":
        s = file_info["size_bytes"]
        if s < 100*1024:       return "< 100 Ko"
        elif s < 1024*1024:    return "100 Ko - 1 Mo"
        elif s < 10*1024*1024: return "1 Mo - 10 Mo"
        elif s < 100*1024*1024:return "10 Mo - 100 Mo"
        else:                  return "> 100 Mo"
    if field == "first_letter":
        n = file_info["name"]
        return n[0].upper() if n else "#"
    if field == "filename_noext":
        return Path(file_info["name"]).stem
    if field in ("exif_year", "exif_month", "exif_day", "exif_date_full"):
        if "_exif_dt" not in file_info:
            _ext = file_info.get("ext", "").lower()
            if _ext in IMAGE_EXTS or _ext in RAW_EXTS:
                file_info["_exif_dt"] = _get_exif_datetime(file_info["path"])
            else:
                file_info["_exif_dt"] = None
        exif_dt = file_info["_exif_dt"]
# Missing EXIF dates are replaced by filesystem modification time so the structure builder still produces deterministic folders.
        fallback = exif_dt if exif_dt is not None else mtime
        if field == "exif_year":      return str(fallback.year)
        if field == "exif_month":     return f"{fallback.month:02d}"
        if field == "exif_day":       return f"{fallback.day:02d}"
        if field == "exif_date_full": return fallback.strftime("%Y-%m-%d")
    return "?"

def build_tree_from_chain(file_list, fields):
    """Recursively group files according to a list of metadata fields."""

    if not fields:
        return {"(racine)": file_list}
    tree = {}
    for f in file_list:
        key = get_file_field(f, fields[0])
        if key not in tree:
            tree[key] = []
        tree[key].append(f)
    if len(fields) == 1:
        return tree
    result = {}
    for key, sub_files in tree.items():
        result[key] = build_tree_from_chain(sub_files, fields[1:])
    return result

COLOR_ARGUMENT = "#4f98a3"
COLOR_LIANT    = "#a86fdf"
COLOR_FOLDER   = "#fdab43"


# =============================================================================
# Node editor visual model
# Canvas node rendering, ports, hit testing, and selection state.
# =============================================================================
class Node:
    """Visual graph node used by the node editor canvas."""

    NW, NH = 200, 90
    PORT_R = 7

    def __init__(self, canvas, node_id, node_family, type_key, x, y, label_override=None):
        self.canvas      = canvas
        self.id          = node_id
        self.node_family = node_family   # "argument" | "liant" | "folder"
        self.type_key    = type_key      # clé NODE_TYPES pour "argument", None sinon
        self.x, self.y   = x, y
        if node_family == "argument":
            self._label = label_override or (NODE_TYPES[type_key]["label"] if type_key else "Argument")
            self._label_is_default = not bool(label_override)
        elif node_family == "liant":
            self._label = label_override or "-"
            self._label_is_default = False
        else:
            default_folder = _("node_default_folder")
            self._label = label_override if label_override else default_folder
            self._label_is_default = not bool(label_override)
        self.separator  = ""
        self.canvas_ids = []
        self._selected  = False
        self.draw()

    @property
    def color(self):
        if self.node_family == "folder":  return COLOR_FOLDER
        if self.node_family == "liant":   return COLOR_LIANT
        return NODE_TYPES[self.type_key]["color"]

    @property
    def label(self): return self._label

    @label.setter
    def label(self, v):
        self._label = v
        self.draw()

    @property
    def field(self):
        if self.node_family == "argument":
            return NODE_TYPES[self.type_key]["field"]
        return None

    # Redrawing the full node keeps rendering logic simple and avoids tracking many incremental canvas updates.
    def draw(self):
        for cid in self.canvas_ids:
            self.canvas.delete(cid)
        self.canvas_ids.clear()
        x, y, w, h = self.x, self.y, self.NW, self.NH
        c        = self.color
        bw       = 3 if self._selected else 2
        out      = TEXT if self._selected else c
        sel_fill = "#252320" if self._selected else SURFACE2

        shadow  = self.canvas.create_rectangle(x+4, y+4, x+w+4, y+h+4,
                      fill="#0d0c0b", outline="", tags=f"node_{self.id}")
        body    = self.canvas.create_rectangle(x, y, x+w, y+h,
                      fill=sel_fill, outline=out, width=bw, tags=f"node_{self.id}")
        header  = self.canvas.create_rectangle(x+bw, y+bw, x+w-bw, y+25,
                      fill=c, outline="", tags=f"node_{self.id}")

        if self.node_family == "folder":
            icon = "📁"; badge = _("node_badge_folder"); bcol = COLOR_FOLDER
        elif self.node_family == "liant":
            icon = "🔗"; badge = _("node_badge_liant");  bcol = COLOR_LIANT
        else:
            icon = "📌"; badge = _("node_badge_arg");    bcol = COLOR_ARGUMENT
        if self.node_family == "folder":
            if getattr(self, "_label_is_default", False):
                display_label = _("node_default_folder")
            else:
                display_label = self._label  # nom personnalisé par l'utilisateur
        elif self.node_family in ("argument", "liant") and self.type_key in NODE_TYPES:
            display_label = NODE_TYPES[self.type_key].get("label", self._label)
        else:
            display_label = self._label
        title = self.canvas.create_text(x + w//2, y + 14,
                    text=f"{icon}  {display_label}",
                    fill="#0f1a1c", font=("Segoe UI", 8, "bold"),
                    tags=f"node_{self.id}")

        if self.node_family == "folder":
            sub_text  = _("node_dbl_rename")
            hint_text = _("node_parent_hint")
        elif self.node_family == "liant":
            sub_text  = _("node_fixed_val", v=self._label)
            hint_text = _("node_dbl_edit")
        else:
            sep_disp  = f'"{self.separator}"' if self.separator else _("node_sep_none")
            sub_text  = _("node_field", f=NODE_TYPES[self.type_key]['field'])
            hint_text = _("node_sep", s=sep_disp)

        sub_t  = self.canvas.create_text(x + w//2, y + 48,
                     text=sub_text, fill=MUTED, font=("Segoe UI", 7),
                     tags=f"node_{self.id}")
        hint_t = self.canvas.create_text(x + w//2, y + 63,
                     text=hint_text, fill=c, font=("Segoe UI", 6, "bold"),
                     tags=f"node_{self.id}")
        del_b  = self.canvas.create_text(x + w - 10, y + 14,
                     text="✕", fill="#0f1a1c", font=("Segoe UI", 8, "bold"),
                     tags=(f"node_{self.id}", f"del_{self.id}"))
        badge_t = self.canvas.create_text(x + 8, y + h - 10,
                     text=badge, fill=bcol,
                     font=("Segoe UI", 6, "bold"), anchor="w",
                     tags=f"node_{self.id}")

        port_in  = self.canvas.create_oval(
            x - self.PORT_R, y + h//2 - self.PORT_R,
            x + self.PORT_R, y + h//2 + self.PORT_R,
            fill=SURFACE, outline=c, width=2,
            tags=(f"node_{self.id}", f"port_in_{self.id}"))
        port_out = self.canvas.create_oval(
            x + w - self.PORT_R, y + h//2 - self.PORT_R,
            x + w + self.PORT_R, y + h//2 + self.PORT_R,
            fill=c, outline=c,
            tags=(f"node_{self.id}", f"port_out_{self.id}"))

        self.canvas_ids = [cid for cid in
            [shadow, body, header, title, sub_t, hint_t, del_b, badge_t, port_in, port_out]
            if cid is not None]

        if self.node_family == "folder":
            port_name_in = self.canvas.create_polygon(
                x + w//2 - 8, y + h,
                x + w//2 + 8, y + h,
                x + w//2,     y + h + 13,
                fill=SURFACE2, outline=COLOR_LIANT, width=2,
                tags=(f"node_{self.id}", f"port_name_in_{self.id}"))
            lbl_nom = self.canvas.create_text(x + w//2, y + h + 22,
                text=_("node_nom"), fill=COLOR_LIANT, font=("Segoe UI", 6, "bold"),
                tags=f"node_{self.id}")
            self.canvas_ids += [port_name_in, lbl_nom]

    def set_selected(self, sel):
        self._selected = sel
        self.draw()

    def port_in_pos(self):      return (self.x,           self.y + self.NH // 2)
    def port_out_pos(self):     return (self.x + self.NW, self.y + self.NH // 2)
    def port_name_in_pos(self): return (self.x + self.NW // 2, self.y + self.NH + 13)

    def move(self, dx, dy):
        self.x += dx; self.y += dy
        for cid in self.canvas_ids:
            self.canvas.move(cid, dx, dy)

    # Hit testing includes the additional folder-name port area exposed by folder nodes.
    def hit_test(self, mx, my):
        extra = 25 if self.node_family == "folder" else 0
        return self.x <= mx <= self.x + self.NW and self.y <= my <= self.y + self.NH + extra

    def hit_delete(self, mx, my):
        dx, dy = self.x + self.NW - 10, self.y + 14
        return abs(mx - dx) < 10 and abs(my - dy) < 10

    def hit_port_out(self, mx, my):
        px, py = self.port_out_pos()
        return abs(mx - px) < 14 and abs(my - py) < 14

    def hit_port_in(self, mx, my):
        px, py = self.port_in_pos()
        return abs(mx - px) < 14 and abs(my - py) < 14

    def hit_port_name_in(self, mx, my):
        if self.node_family != "folder": return False
        px, py = self.port_name_in_pos()
        return abs(mx - px) < 16 and abs(my - py) < 16
def _decode_field_token(token):

    """Décode un token "field::separator" → (field_name, separator)."""
    if "::" in token and not token.startswith("__"):
        field_name, sep = token.split("::", 1)
        return field_name, sep
    return token, ""


def _resolve_folder_name(file_info, name_tokens):

    """
    Calcule le nom d'un dossier pour un fichier donné à partir d'une liste de tokens.
    Chaque token :
      "arg::field_name::sep"  → valeur dynamique du champ + séparateur
      "lit::texte_fixe"       → texte littéral (liant)
    """
    parts = []
    for tok in name_tokens:
        if tok.startswith("arg::"):
            rest = tok[5:]
            field_name, sep = _decode_field_token(rest)
            val = get_file_field(file_info, field_name)
            parts.append(val + sep)
        elif tok.startswith("lit::"):
            parts.append(tok[5:])
    return "".join(parts).strip()

def build_tree_from_chain_extended(file_list, fields, _progress_cb=None, _level=0):
    """
    Construit l'arbre de structure.
    Supporte :
      - "field_name::sep"         → argument (valeur dynamique) + séparateur
      - "__folder_dyn__||tok|..."  → dossier dont le nom est calculé par une chaîne
                                      de tokens arg:: et lit::
      - "__folder__NomFixe"        → dossier fixe (sans chaîne de nom)
    """
    if not fields:
        return {"(racine)": file_list}
    field = fields[0]
    rest  = fields[1:]

    if field.startswith("__folder__"):
        folder_name = field[len("__folder__"):]
        sub = build_tree_from_chain_extended(file_list, rest)
        return {folder_name: sub}

    if field.startswith("__folder_dyn__||"):
        spec        = field[len("__folder_dyn__||"):]
        name_tokens = spec.split("|") if spec else []
        tree = {}
        total = len(file_list)
        for i, f in enumerate(file_list):
            key = _resolve_folder_name(f, name_tokens) or "Dossier"
            tree.setdefault(key, []).append(f)
            if _level == 0 and _progress_cb and (i % 50 == 0 or i == total - 1):
                _progress_cb(i + 1, total)
        if not rest:
            return tree
        return {k: build_tree_from_chain_extended(v, rest, _level=_level+1)
                for k, v in tree.items()}

    field_name, sep = _decode_field_token(field)
    tree = {}
    total = len(file_list)
    for i, f in enumerate(file_list):
        try:
            raw = get_file_field(f, field_name)
        except Exception as _e:
            print(f"[BUILD_TREE] get_file_field erreur sur {f.get('path','?')!r} field={field_name!r}: {_e}")
            raw = "?"
        key = raw + sep if sep else raw
        tree.setdefault(key, []).append(f)
        if _level == 0 and _progress_cb and (i % 50 == 0 or i == total - 1):
            _progress_cb(i + 1, total)
    if not rest:
        return tree
    return {k: build_tree_from_chain_extended(v, rest, _level=_level+1)
            for k, v in tree.items()}

def flatten_tree_to_operations(tree, base_path, current_path=""):
    """Parcourt l'arbre et retourne une liste de (src_path, dst_path)."""
    ops = []
    if isinstance(tree, list):
        for fi in tree:
            dst_dir = os.path.join(base_path, current_path) if current_path else base_path
            ops.append((fi["path"], os.path.join(dst_dir, fi["name"])))
    else:
        for key, val in tree.items():
            sub = os.path.join(current_path, key) if current_path else key
            ops.extend(flatten_tree_to_operations(val, base_path, sub))
    return ops
# =============================================================================
# Node editor tab
# Main interactive workspace for creating structures, previews, and presets.
# =============================================================================
class NodeEditorTab(tk.Frame):
    """Main node-editor workspace responsible for structure design, presets, and previews."""

    def __init__(self, parent, get_files_cb):
        super().__init__(parent, bg=BG)
        self._get_files      = get_files_cb
        self._nodes          = {}
        self._connections    = []
        self._next_id        = 0
        self._drag_node      = None
        self._drag_offset    = (0, 0)
        self._selected_nodes = set()
        self._rubber_start   = None   # (x, y) départ du rubber-band
        self._rubber_rect    = None   # canvas id du rect de sélection
        self._wire_src       = None   # (nid, port_type)  port_type = "chain"|"attr"
        self._wire_tmp       = None
        self._pan_start       = None
        self._shift_pan_start = None
        self._canvas_zoom     = 1.0
        self._rename_win     = None
        self._last_tree      = None
        self._last_labels    = []
        self._uv_cache       = {}
        self._preset_dirty = False
        self._preset_name_var = None  # sera créé dans _build_ui
        self._build_ui()
        self.after(200, self._load_last_preset)
    def _build_ui(self):
        tb = tk.Frame(self, bg=SURFACE, pady=6, padx=10)
        tb.pack(fill="x")
        self._lbl_title = tk.Label(tb, text=_("node_editor_title"), bg=SURFACE, fg=PRIMARY,
                 font=("Segoe UI", 9, "bold"))
        self._lbl_title.pack(side="left")
        self._lbl_hint = tk.Label(tb,
            text=_("node_editor_hint"),
            bg=SURFACE, fg=MUTED, font=("Segoe UI", 7))
        self._lbl_hint.pack(side="left", padx=(8,0))
        self._btn_clear = tk.Button(tb, text=_("clear_all"), bg=SURFACE2, fg=MUTED,
                  relief="flat", font=("Segoe UI", 9), padx=8, pady=3,
                  cursor="hand2", command=self._clear_all)
        self._btn_clear.pack(side="right", padx=(6,0))
        self._btn_preview = tk.Button(tb, text=_("click_preview"), bg=PRIMARY, fg="#0f3638",
                  activebackground=PRIMARY_H, activeforeground="#0f3638",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3,
                  cursor="hand2", command=self._show_preview)
        self._btn_preview.pack(side="right", padx=(6,0))
        self._btn_reset_view = tk.Button(tb, text=_("reset_view"), bg=SURFACE2, fg=MUTED,
                  relief="flat", font=("Segoe UI", 9), padx=8, pady=3,
                  cursor="hand2", command=self._reset_view)
        self._btn_reset_view.pack(side="right", padx=(0,6))
        tk.Frame(tb, bg=BORDER, width=1).pack(side="right", fill="y", pady=4, padx=6)
        self._preset_name_var = tk.StringVar(value=_("no_files_indexed"))
        self._preset_dirty = False
        pbar = tk.Frame(tb, bg=SURFACE)
        pbar.pack(side="right", fill="y")

        def pbtn(text, fg, cmd, padx_in=8, bold=False):
            """Crée un bouton preset uniforme dans pbar."""
            f = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
            return tk.Button(pbar, text=text, bg=SURFACE2, fg=fg,
                             relief="flat", font=f,
                             padx=padx_in, pady=0,
                             cursor="hand2", command=cmd)
        self._btn_new_preset = tk.Button(pbar, text=_("new_preset"), bg=SURFACE2, fg=SUCCESS,
                  relief="flat", font=("Segoe UI", 9),
                  padx=8, pady=0, cursor="hand2",
                  command=self._new_preset)
        self._btn_new_preset.pack(side="left", padx=(0, 6), fill="y")

        self._preset_del_btn = tk.Button(pbar, text="🗑", bg=SURFACE2, fg=MUTED,
                  relief="flat", font=("Segoe UI", 9),
                  padx=8, pady=0, cursor="hand2",
                  command=self._delete_current_preset)
        self._preset_del_btn.pack(side="left", padx=(0, 2), fill="y")

        self._btn_save_preset = tk.Button(pbar, text=_("save_preset"), bg=SURFACE2, fg=TEXT,
                  relief="flat", font=("Segoe UI", 9),
                  padx=8, pady=0, cursor="hand2",
                  command=self._save_preset)
        self._btn_save_preset.pack(side="left", padx=(0, 6), fill="y")

        style_cb = ttk.Style()
        style_cb.configure("Preset.TCombobox",
            fieldbackground=SURFACE2, background=SURFACE2,
            foreground=TEXT, selectbackground=SURFACE2,
            selectforeground=TEXT, arrowcolor=PRIMARY,
            borderwidth=0, relief="flat")
        style_cb.map("Preset.TCombobox",
            fieldbackground=[(("readonly",), SURFACE2)],
            foreground=[(("readonly",), TEXT)])
        self._preset_combo_var = tk.StringVar(value="—")
        self._preset_combo = ttk.Combobox(
            pbar, textvariable=self._preset_combo_var,
            state="readonly", width=18,
            style="Preset.TCombobox",
            font=("Segoe UI", 9))
        self._preset_combo.pack(side="left", padx=(0, 4), fill="y")
        self._preset_combo.bind("<<ComboboxSelected>>", self._on_preset_combo_select)

        self._preset_dirty_lbl = tk.Label(pbar, text="", bg=SURFACE,
            fg=ORANGE, font=("Segoe UI", 10, "bold"), width=1)
        self._preset_dirty_lbl.pack(side="left", fill="y")

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)
        pal_outer = tk.Frame(main, bg=SURFACE, width=205)
        pal_outer.pack(side="left", fill="y")
        pal_outer.pack_propagate(False)
        self._lbl_palette = tk.Label(pal_outer, text=_("palette"), bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), pady=8)
        self._lbl_palette.pack(fill="x", padx=10)
        tk.Frame(pal_outer, bg=BORDER, height=1).pack(fill="x")

        _pc = tk.Canvas(pal_outer, bg=SURFACE, highlightthickness=0, bd=0)
        _pvsb = ttk.Scrollbar(pal_outer, orient="vertical", command=_pc.yview,
                              style="Dark.Vertical.TScrollbar")
        _pc.pack(side="left", fill="both", expand=True)
        _pc.configure(yscrollcommand=self._pal_yscroll_cb)

        pal = tk.Frame(_pc, bg=SURFACE)
        _pw = _pc.create_window((0,0), window=pal, anchor="nw")

        def _pal_update_scroll(e=None):
            _pc.configure(scrollregion=_pc.bbox("all"))
            content_h = pal.winfo_reqheight()
            canvas_h  = _pc.winfo_height()
            if content_h > canvas_h + 2:
                if not _pvsb.winfo_ismapped():
                    _pvsb.pack(side="right", fill="y", before=_pc)
            else:
                if _pvsb.winfo_ismapped():
                    _pvsb.pack_forget()
                    _pc.yview_moveto(0)

        pal.bind("<Configure>", _pal_update_scroll)
        _pc.bind("<Configure>", lambda e: (_pc.itemconfig(_pw, width=e.width),
                                            _pal_update_scroll()))

        def _pscroll(e): _pc.yview_scroll(int(-1*(e.delta/120)), "units")
        _pc.bind("<MouseWheel>", _pscroll)
        pal.bind("<MouseWheel>", _pscroll)

        self._pal_canvas    = _pc
        self._pal_scrollbar = _pvsb
        self._pal_scroll_fn = _pscroll
        self._pal_update_scroll = _pal_update_scroll
        pf = tk.Frame(pal, bg=SURFACE)
        pf.pack(fill="x", padx=8, pady=(8,4))
        self._lbl_how_to_build = tk.Label(pf, text=_("how_to_build"), bg=SURFACE, fg=PRIMARY,
                 font=("Segoe UI", 7, "bold"))
        self._lbl_how_to_build.pack(anchor="w", pady=(0,4))
        self._lbl_how_to_build_txt = tk.Label(pf,
            text=_("how_to_build_txt"),
            bg=SURFACE, fg=MUTED, font=("Segoe UI", 7),
            justify="left", wraplength=185)
        self._lbl_how_to_build_txt.pack(anchor="w", pady=(0,4))
        tk.Frame(pf, bg=BORDER, height=1).pack(fill="x")
        self._pal_meta_frame = tk.Frame(pal, bg=SURFACE)
        self._pal_meta_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self._build_palette_meta()
        self._pal_info = tk.Label(pal, text="", bg=SURFACE, fg=MUTED,
                                  font=("Segoe UI", 7), justify="center", pady=6)
        self._pal_info.pack(fill="x", padx=6)
        leg = tk.Frame(pal, bg=SURFACE)
        leg.pack(fill="x", padx=8, pady=(0,8))
        tk.Frame(leg, bg=BORDER, height=1).pack(fill="x", pady=4)
        self._pal_legend_items = []
        for key, col in [("pal_legend_chain", TEXT),
                          ("pal_legend_meta",  PRIMARY),
                          ("pal_legend_folder", ORANGE),
                          ("pal_legend_multisel", MUTED),
                          ("pal_legend_cut",   MUTED)]:
            lbl = tk.Label(leg, text=_(key), bg=SURFACE, fg=col,
                     font=("Segoe UI", 7))
            lbl.pack(anchor="w")
            self._pal_legend_items.append((lbl, key))
        cf = tk.Frame(main, bg=BG)
        cf.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(cf, bg="#171614", highlightthickness=0, cursor="crosshair")
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda e: self._draw_grid())
        self._bind_canvas_events()
        self._hint = self._lbl_drag_hint = tk.Label(cf,
            text=_("drag_nodes_hint"),
            bg="#171614", fg=MUTED, font=("Segoe UI", 10))
        self._hint.place(relx=0.5, rely=0.5, anchor="center")
        pv = tk.Frame(main, bg=SURFACE, width=285)
        pv.pack(side="right", fill="y")
        pv.pack_propagate(False)
        self._lbl_preview_struct = tk.Label(pv, text=_("preview_structure"), bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), pady=8)
        self._lbl_preview_struct.pack(fill="x", padx=8)
        tk.Frame(pv, bg=BORDER, height=1).pack(fill="x")
        self._chain_lbl = tk.Label(pv,
            text=_("chain_click"),
            bg=SURFACE, fg=MUTED, font=("Segoe UI", 8),
            justify="center", pady=10, wraplength=265)
        self._chain_lbl.pack(fill="x", padx=6)
        tf = tk.Frame(pv, bg=SURFACE)
        tf.pack(fill="both", expand=True)
        self._prev_tree = ttk.Treeview(tf, show="tree headings",
                                       style="Custom.Treeview", selectmode="none")
        self._prev_tree["columns"] = ("count",)
        self._prev_tree.heading("#0",    text=_("folder_node"))
        self._prev_tree.heading("count", text=_("col_count"))
        self._prev_tree.column("#0",    width=195)
        self._prev_tree.column("count", width=60, anchor="center")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self._prev_tree.yview, style="Dark.Vertical.TScrollbar")
        self._prev_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._prev_tree.pack(fill="both", expand=True)

        self._status = tk.StringVar(value=_("canvas_empty"))
        tk.Label(self, textvariable=self._status, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8), anchor="w", padx=10, pady=4).pack(fill="x", side="bottom")
        self._nodal_prog_var = tk.IntVar(value=0)
        self._nodal_prog_frame = tk.Frame(self, bg=SURFACE, height=4)
        self._nodal_prog_frame.pack(fill="x", side="bottom")
        self._nodal_prog_frame.pack_propagate(False)
        self._nodal_prog_inner = tk.Frame(self._nodal_prog_frame, bg=PRIMARY, height=4)
        self._nodal_prog_inner.place(x=0, y=0, relwidth=0.0, height=4)
        self._nodal_prog_var.trace_add("write", self._update_nodal_prog_bar)
    def _pal_yscroll_cb(self, first, last):
        """Callback yscrollcommand : transmet à la scrollbar et la masque si inutile."""
        if hasattr(self, "_pal_scrollbar"):
            self._pal_scrollbar.set(first, last)

    def _bind_pal_scroll(self, w):
        if hasattr(self, "_pal_scroll_fn"):
            w.bind("<MouseWheel>", self._pal_scroll_fn)
        for c in w.winfo_children():
            self._bind_pal_scroll(c)

    def _build_palette_meta(self):
        for w in self._pal_meta_frame.winfo_children():
            w.destroy()
        tk.Label(self._pal_meta_frame, text=_("structure_label"), bg=SURFACE, fg=COLOR_FOLDER,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(4,2))
        btn_f = tk.Button(self._pal_meta_frame, text=_("folder_node"),
            bg=SURFACE2, fg=COLOR_FOLDER, relief="flat", font=("Segoe UI", 8),
            padx=6, pady=3, cursor="hand2", anchor="w",
            activebackground=BORDER, activeforeground=COLOR_FOLDER,
            command=self._add_folder_node)
        btn_f.pack(fill="x", pady=1)
        self._bind_palette_dnd_folder(btn_f)
        tk.Label(self._pal_meta_frame, text=_("connector_label"), bg=SURFACE, fg=COLOR_LIANT,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(6,2))
        btn_l = tk.Button(self._pal_meta_frame,
            text=_("connector_btn"),
            bg=SURFACE2, fg=COLOR_LIANT, relief="flat", font=("Segoe UI", 8),
            padx=6, pady=3, cursor="hand2", anchor="w",
            activebackground=BORDER, activeforeground=COLOR_LIANT,
            command=self._add_liant_node)
        btn_l.pack(fill="x", pady=1)
        self._bind_palette_dnd_liant(btn_l)
        tk.Label(self._pal_meta_frame, text=_("arguments_label"), bg=SURFACE, fg=COLOR_ARGUMENT,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(6,2))
        global NODE_TYPES
        NODE_TYPES = _build_node_types()
        sections = [
            (_("pal_sect_exif"),    ["exif_annee","exif_mois","exif_jour","exif_date_full"]),
            (_("pal_sect_created"), ["annee_creation","mois_creation","jour_creation"]),
            (_("pal_sect_modif"),   ["annee_modif","mois_modif","jour_modif"]),
            (_("pal_sect_file"),    ["nom_fichier","extension","categorie","taille","premiere_lettre"]),
        ]
        for section_title, keys in sections:
            tk.Label(self._pal_meta_frame, text=section_title.upper(), bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 6, "bold"), pady=2).pack(anchor="w", fill="x")
            for k in keys:
                info  = NODE_TYPES[k]
                badge = f"  ({self._uv_cache[k]})" if k in self._uv_cache else ""
                btn   = tk.Button(self._pal_meta_frame,
                                  text=f"📌  {info['label']}{badge}",
                                  bg=SURFACE2, fg=info["color"],
                                  relief="flat", font=("Segoe UI", 8), padx=6, pady=3,
                                  cursor="hand2", anchor="w",
                                  activebackground=BORDER, activeforeground=info["color"],
                                  command=lambda key=k: self._add_argument_node(key))
                btn.pack(fill="x", pady=1)
                self._bind_palette_dnd(btn, k)
        self._bind_pal_scroll(self._pal_meta_frame)
        if hasattr(self, '_pal_update_scroll'): self._pal_update_scroll()

    def refresh_palette(self):
        files = self._get_files()
        if not files:
            self._build_palette_meta()
            self._pal_info.config(text=_("no_files_indexed"))
            return
        self._pal_info.config(text=_("computing_n", n=len(files)))
        self._build_palette_meta()
        def _compute():
            try:
                cache = {}
                for k in NODE_TYPES:
                    try:
                        cache[k] = len(set(get_file_field(f, NODE_TYPES[k]["field"]) for f in files))
                    except Exception as _e:
                        print(f"[PALETTE] Erreur champ {k!r}: {_e}")
                        cache[k] = 0
                self.after(0, lambda: self._apply_uv_cache(cache, len(files)))
            except Exception as _e:
                print(f"[PALETTE][ERREUR] {traceback.format_exc()}")
        threading.Thread(target=_compute, daemon=True).start()

    def _bind_palette_dnd(self, btn, type_key):
        """Permet de drag un bouton argument de palette vers le canvas."""
        _state = {"dragging": False, "ghost": None}

        def on_press(e):
            _state["dragging"] = False; _state["ghost"] = None

        def on_motion(e):
            abs_x = btn.winfo_rootx() + e.x
            abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            on_canvas = 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height()
            if not _state["dragging"]:
                _state["dragging"] = True; btn.config(cursor="fleur")
            if on_canvas:
                self._canvas.config(cursor="fleur")
                info = NODE_TYPES[type_key]
                if _state["ghost"] is None:
                    _state["ghost"] = self._canvas.create_rectangle(
                        cx, cy, cx + Node.NW, cy + Node.NH,
                        outline=info["color"], fill="#1c1b19", width=2, dash=(6,3), tags="pal_ghost")
                    _state["ghost_lbl"] = self._canvas.create_text(
                        cx + Node.NW//2, cy + Node.NH//2,
                        text=f"📌  {info['label']}", fill=info["color"],
                        font=("Segoe UI", 8), tags="pal_ghost")
                else:
                    self._canvas.coords(_state["ghost"], cx, cy, cx+Node.NW, cy+Node.NH)
                    self._canvas.coords(_state["ghost_lbl"], cx+Node.NW//2, cy+Node.NH//2)
            else:
                self._canvas.config(cursor="crosshair")
                if _state["ghost"] is not None:
                    self._canvas.delete("pal_ghost"); _state["ghost"] = None

        def on_release(e):
            btn.config(cursor="hand2"); self._canvas.config(cursor="crosshair")
            self._canvas.delete("pal_ghost"); _state["ghost"] = None
            if not _state["dragging"]: return
            _state["dragging"] = False
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            if 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height():
                if self._hint: self._hint.place_forget()
                nid = self._next_id; self._next_id += 1
                drop_x = max(10, cx - Node.NW//2); drop_y = max(10, cy - Node.NH//2)
                self._nodes[nid] = Node(self._canvas, nid, "argument", type_key, drop_x, drop_y)
                self._update_status()

        btn.bind("<ButtonPress-1>",   on_press,   add="+")
        btn.bind("<B1-Motion>",       on_motion)
        btn.bind("<ButtonRelease-1>", on_release, add="+")

    def _bind_palette_dnd_folder(self, btn):
        """Drag & drop pour créer un node folder."""
        _state = {"dragging": False, "ghost": None}

        def on_press(e):
            _state["dragging"] = False; _state["ghost"] = None

        def on_motion(e):
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            on_canvas = 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height()
            if not _state["dragging"]:
                _state["dragging"] = True; btn.config(cursor="fleur")
            if on_canvas:
                self._canvas.config(cursor="fleur")
                if _state["ghost"] is None:
                    _state["ghost"] = self._canvas.create_rectangle(
                        cx, cy, cx+Node.NW, cy+Node.NH,
                        outline=COLOR_FOLDER, fill="#1c1b19", width=2, dash=(6,3), tags="pal_ghost")
                    _state["ghost_lbl"] = self._canvas.create_text(
                        cx+Node.NW//2, cy+Node.NH//2,
                        text=_("folder_node"), fill=COLOR_FOLDER,
                        font=("Segoe UI", 8), tags="pal_ghost")
                else:
                    self._canvas.coords(_state["ghost"], cx, cy, cx+Node.NW, cy+Node.NH)
                    self._canvas.coords(_state["ghost_lbl"], cx+Node.NW//2, cy+Node.NH//2)
            else:
                self._canvas.config(cursor="crosshair")
                if _state["ghost"] is not None:
                    self._canvas.delete("pal_ghost"); _state["ghost"] = None

        def on_release(e):
            btn.config(cursor="hand2"); self._canvas.config(cursor="crosshair")
            self._canvas.delete("pal_ghost"); _state["ghost"] = None
            if not _state["dragging"]: return
            _state["dragging"] = False
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            if 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height():
                if self._hint: self._hint.place_forget()
                nid = self._next_id; self._next_id += 1
                drop_x = max(10, cx - Node.NW//2); drop_y = max(10, cy - Node.NH//2)
                self._nodes[nid] = Node(self._canvas, nid, "folder", None, drop_x, drop_y)
                self._update_status()

        btn.bind("<ButtonPress-1>",   on_press,   add="+")
        btn.bind("<B1-Motion>",       on_motion)
        btn.bind("<ButtonRelease-1>", on_release, add="+")

    def _bind_palette_dnd_liant(self, btn):
        """Drag & drop pour créer un node liant."""
        _state = {"dragging": False, "ghost": None}

        def on_press(e):
            _state["dragging"] = False; _state["ghost"] = None

        def on_motion(e):
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            on_canvas = 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height()
            if not _state["dragging"]:
                _state["dragging"] = True; btn.config(cursor="fleur")
            if on_canvas:
                self._canvas.config(cursor="fleur")
                if _state["ghost"] is None:
                    _state["ghost"] = self._canvas.create_rectangle(
                        cx, cy, cx+Node.NW, cy+Node.NH,
                        outline=COLOR_LIANT, fill="#1c1b19", width=2, dash=(6,3), tags="pal_ghost")
                    _state["ghost_lbl"] = self._canvas.create_text(
                        cx+Node.NW//2, cy+Node.NH//2,
                        text=_("connector_canvas"), fill=COLOR_LIANT,
                        font=("Segoe UI", 8), tags="pal_ghost")
                else:
                    self._canvas.coords(_state["ghost"], cx, cy, cx+Node.NW, cy+Node.NH)
                    self._canvas.coords(_state["ghost_lbl"], cx+Node.NW//2, cy+Node.NH//2)
            else:
                self._canvas.config(cursor="crosshair")
                if _state["ghost"] is not None:
                    self._canvas.delete("pal_ghost"); _state["ghost"] = None

        def on_release(e):
            btn.config(cursor="hand2"); self._canvas.config(cursor="crosshair")
            self._canvas.delete("pal_ghost"); _state["ghost"] = None
            if not _state["dragging"]: return
            _state["dragging"] = False
            abs_x = btn.winfo_rootx() + e.x; abs_y = btn.winfo_rooty() + e.y
            cx = abs_x - self._canvas.winfo_rootx()
            cy = abs_y - self._canvas.winfo_rooty()
            if 0 <= cx <= self._canvas.winfo_width() and 0 <= cy <= self._canvas.winfo_height():
                if self._hint: self._hint.place_forget()
                nid = self._next_id; self._next_id += 1
                drop_x = max(10, cx - Node.NW//2); drop_y = max(10, cy - Node.NH//2)
                self._nodes[nid] = Node(self._canvas, nid, "liant", None, drop_x, drop_y)
                self._update_status()

        btn.bind("<ButtonPress-1>",   on_press,   add="+")
        btn.bind("<B1-Motion>",       on_motion)
        btn.bind("<ButtonRelease-1>", on_release, add="+")

    def _apply_uv_cache(self, cache, n):
        self._uv_cache = cache
        self._build_palette_meta()
        self._pal_info.config(text=_("files_indexed", n=n))
        if hasattr(self, '_pal_update_scroll'): self._pal_update_scroll()

    def _draw_grid(self):
        self._canvas.delete("grid")
        self.update_idletasks()
        w = self._canvas.winfo_width()  or 1200
        h = self._canvas.winfo_height() or 800
        for x in range(0, w, 40): self._canvas.create_line(x, 0, x, h, fill="#1e1d1b", tags="grid")
        for y in range(0, h, 40): self._canvas.create_line(0, y, w, y, fill="#1e1d1b", tags="grid")
        self._canvas.tag_lower("grid")

    def _reset_view(self):
        self._canvas_zoom = 1.0
        Node.NW = 200
        Node.NH = 90
        for n in self._nodes.values(): n.draw()
        self._redraw_wires()
        self._draw_grid()
        self._status.set(_("view_reset"))
    def _next_pos(self):
        base_x, base_y = 120, 120
        offset = len(self._nodes) * 30
        return base_x + offset, base_y + offset

    def _add_folder_node(self, name=None):
        if self._hint: self._hint.place_forget()
        x, y = self._next_pos()
        nid = self._next_id; self._next_id += 1
        self._nodes[nid] = Node(self._canvas, nid, "folder", None, x, y,
                                label_override=name or None)
        self._update_status()

    def _add_argument_node(self, type_key):
        if self._hint: self._hint.place_forget()
        x, y = self._next_pos()
        nid = self._next_id; self._next_id += 1
        self._nodes[nid] = Node(self._canvas, nid, "argument", type_key, x, y)
        self._update_status()

    def _add_liant_node(self, label=None):
        if self._hint: self._hint.place_forget()
        x, y = self._next_pos()
        nid = self._next_id; self._next_id += 1
        self._nodes[nid] = Node(self._canvas, nid, "liant", None, x, y,
                                label_override=label or "-")
        self._update_status()
    def _delete_node(self, nid):
        if nid not in self._nodes: return
        for cid in self._nodes[nid].canvas_ids:
            self._canvas.delete(cid)
        del self._nodes[nid]
        to_remove = [c for c in self._connections if c["src"] == nid or c["dst"] == nid]
        for c in to_remove:
            self._canvas.delete(c.get("cid"))
# Node deletion must also remove all related graph connections to keep the canvas state coherent.
        self._connections = [c for c in self._connections if c["src"] != nid and c["dst"] != nid]
        self._selected_nodes.discard(nid)
        if self._selected_node_primary == nid:
            self._selected_node_primary = None
        self._update_status()
        cur = self._preset_name_var.get() if hasattr(self, '_preset_name_var') else ''
        if cur and cur != _("no_preset") and not self._preset_dirty:
            self._mark_dirty()

    @property
    def _selected_node_primary(self):
        return getattr(self, "_sel_primary", None)
    @_selected_node_primary.setter
    def _selected_node_primary(self, v):
        self._sel_primary = v

    def _delete_selected(self):
        for nid in list(self._selected_nodes):
            self._delete_node(nid)
        self._selected_nodes.clear()
        self._update_status()
    _PRESETS_DIR = None  # répertoire de stockage des presets

    def _get_presets_dir(self):
        """Retourne (et crée si besoin) le folder de presets."""
        import os
        d = os.path.normpath(os.path.join(os.path.expanduser("~"), ".file_explorer_presets"))
        os.makedirs(d, exist_ok=True)
        return d

    def _list_presets(self):
        """Retourne les noms de presets disponibles (sans .json), normalisés NFC."""
        import os, unicodedata
        d = self._get_presets_dir()
        names = []
        for f in os.listdir(d):
            if f.endswith(".json") and not f.startswith("_"):
                names.append(unicodedata.normalize("NFC", f[:-5]))
        return sorted(names)

    def _preset_path(self, name):
        """Retourne le chemin normalisé vers le file .json d'un preset."""
        import os
        return os.path.normpath(os.path.join(self._get_presets_dir(), name + ".json"))

    def _get_last_preset_name(self):
        import os
        cfg = os.path.join(self._get_presets_dir(), "_last.txt")
        try:
            if os.path.exists(cfg):
                with open(cfg, "r", encoding="utf-8") as f:
                    return f.read().strip()
        except Exception:
            pass
        return None

    def _set_last_preset_name(self, name):
        import os
        cfg = os.path.join(self._get_presets_dir(), "_last.txt")
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                f.write(name)
        except Exception:
            pass
    def _mark_dirty(self):
        """Le canvas a été modified depuis le dernier loading/save."""
        self._preset_dirty = True
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="✦")

    def _mark_clean(self, name):
        """Le preset vient d'être sauvegardé ou chargé : état propre."""
        self._preset_dirty = False
        self._preset_name_var.set(name)
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="")
        self._refresh_preset_combo()
    def _preset_data(self):
        return {
            "nodes": [
                {"id": nid, "family": n.node_family, "type_key": n.type_key,
                 "label": n.label, "x": n.x, "y": n.y, "separator": n.separator}
                for nid, n in self._nodes.items()
            ],
            "connections": [
                {"src": c["src"], "dst": c["dst"], "ctype": c["ctype"]}
                for c in self._connections
            ],
            "next_id": self._next_id
        }

    def _apply_preset_data(self, data):
        """Reconstruit le canvas depuis un dict — NE déclenche PAS _mark_dirty."""
        self._canvas.delete("all")
        self._nodes.clear()
        self._connections.clear()
        self._selected_nodes.clear()
        self._draw_grid()
        for nd in data.get("nodes", []):
            nid = nd["id"]
            n = Node(self._canvas, nid, nd["family"],
                     nd.get("type_key") or nd.get("typekey"),
                     nd["x"], nd["y"], label_override=nd.get("label"))
            n.separator = nd.get("separator", "")
            n.draw()
            self._nodes[nid] = n
        for cd in data.get("connections", []):
            if cd["src"] in self._nodes and cd["dst"] in self._nodes:
                self._connections.append({"src": cd["src"], "dst": cd["dst"],
                                          "ctype": cd["ctype"], "cid": None})
        self._next_id = data.get("next_id",
            max((nd["id"] for nd in data.get("nodes", [])), default=0) + 1)
        self._redraw_wires()
        if self._hint:
            self._hint.place_forget()
            self._hint = None
        self._update_status()
    def _save_preset(self):
        import json, os
        cur_name = self._preset_name_var.get().strip()
        is_new = (not cur_name or cur_name == _("no_preset"))

        if not is_new:
            try:
                with open(self._preset_path(cur_name), "w", encoding="utf-8") as f:
                    json.dump(self._preset_data(), f, ensure_ascii=False, indent=2)
                self._set_last_preset_name(cur_name)
                self._mark_clean(cur_name)
            except Exception as e:
                from tkinter import messagebox as _mb
                _mb.showerror(_("dlg_save_error"), str(e), parent=self)
            return
        win = tk.Toplevel(self)
        win.title(_("save_preset_title"))
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=_("preset_name_lbl"), bg=BG, fg=TEXT,
                 font=("Segoe UI", 10)).pack(padx=20, pady=(16,4), anchor="w")
        var = tk.StringVar(value="")
        entry = tk.Entry(win, textvariable=var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat",
                         font=("Segoe UI", 11), width=28)
        entry.pack(padx=20, ipady=6, fill="x")
        entry.select_range(0, "end")
        entry.focus_set()

        presets = self._list_presets()
        if presets:
            tk.Label(win, text=_("overwrite_lbl"), bg=BG, fg=MUTED,
                     font=("Segoe UI", 8)).pack(padx=20, pady=(8,2), anchor="w")
            lb_frame = tk.Frame(win, bg=SURFACE2)
            lb_frame.pack(padx=20, fill="x")
            lb = tk.Listbox(lb_frame, bg=SURFACE2, fg=TEXT,
                            selectbackground=PRIMARY_H, selectforeground="#0f3638",
                            relief="flat", font=("Segoe UI", 9),
                            height=min(5, len(presets)), activestyle="none")
            for p in presets:
                lb.insert("end", p)
            lb.pack(fill="x")
            lb.bind("<<ListboxSelect>>",
                lambda e: var.set(lb.get(lb.curselection()[0])) if lb.curselection() else None)

        err_lbl = tk.Label(win, text="", bg=BG, fg="#dd6974", font=("Segoe UI", 8))
        err_lbl.pack(padx=20, anchor="w")
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(padx=20, pady=(4,16), fill="x")

        def do_save():
            name = var.get().strip()
            if not name:
                err_lbl.config(text=_("err_empty_name"))
                return
            if any(c in set(r'/\:*?"<>|') for c in name):
                err_lbl.config(text=_("err_bad_chars"))
                return
            try:
                with open(self._preset_path(name), "w", encoding="utf-8") as f:
                    json.dump(self._preset_data(), f, ensure_ascii=False, indent=2)
                self._set_last_preset_name(name)
                self._mark_clean(name)
                win.destroy()
            except Exception as e:
                err_lbl.config(text=_("dlg_preset_err", e=e))

        entry.bind("<Return>", lambda e: do_save())
        tk.Button(btn_row, text=_("cancel"), bg=SURFACE2, fg=MUTED, relief="flat",
                  font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2",
                  command=win.destroy).pack(side="right", padx=(6,0))
        tk.Button(btn_row, text=_("save_preset"), bg=PRIMARY, fg="#0f3638", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=4, cursor="hand2",
                  command=do_save).pack(side="right")
        win.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width()//2 - win.winfo_width()//2
        py = self.winfo_rooty() + self.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{px}+{py}")
    def _refresh_preset_combo(self):
        """Resynchronise la combobox avec l'état réel (files + preset chargé).
        combo_var contient TOUJOURS le nom brut sans étoile.
        L'étoile est gérée par _preset_dirty_lbl."""
        if not hasattr(self, "_preset_combo"):
            return
        presets = self._list_presets()
        if presets:
            self._preset_combo["values"] = presets
            self._preset_combo.config(state="readonly")
        else:
            self._preset_combo["values"] = []
            self._preset_combo.config(state="disabled")
            self._preset_combo_var.set(_("no_preset"))
            if hasattr(self, "_preset_dirty_lbl"):
                self._preset_dirty_lbl.config(text="")
            return
        cur = self._preset_name_var.get().strip()
        if cur and cur != _("no_preset") and cur in presets:
            self._preset_combo_var.set(cur)
        else:
            self._preset_combo_var.set(_("select_preset"))
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="✦" if self._preset_dirty else "")

    def _on_preset_combo_select(self, event=None):
        """Charge le preset sélectionné dans la combobox."""
        import json
        name = self._preset_combo_var.get().strip()
        if not name or name.startswith("—") or name == _("no_preset"):
            return
        if self._preset_dirty:
            from tkinter import messagebox as _mb
            cur = self._preset_name_var.get().strip()
            label = f'"{cur}"' if cur and cur != _("no_preset") else _("current_preset")
            rep = _mb.askyesnocancel(
                _("load_preset_title"),
                _("save_before_load", label=label, name=name),
                parent=self)
            if rep is None:
                self._refresh_preset_combo()
                return
            if rep:
                self._save_preset()
        path = self._preset_path(name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_preset_data(data)
            self._set_last_preset_name(name)
            self._mark_clean(name)
        except FileNotFoundError:
            from tkinter import messagebox as _mb
            _mb.showerror(_("dlg_not_found"),
                _("dlg_file_missing", path=path),
                parent=self)
            self._refresh_preset_combo()
        except Exception as e:
            from tkinter import messagebox as _mb
            _mb.showerror(_("dlg_load_error"), str(e), parent=self)
            self._refresh_preset_combo()
    def _delete_current_preset(self):
        """Supprime le preset actuellement chargé (ou sélectionné dans la combo)."""
        import os
        name = self._preset_name_var.get().strip()
        if not name or name == _("no_preset"):
            name = self._preset_combo_var.get().strip()
        if not name or name.startswith("—") or name == _("no_preset"):
            return
        from tkinter import messagebox as _mb
        if not _mb.askyesno(_("dlg_delete"),
                _("delete_preset_confirm", name=name), parent=self):
            return
        path = self._preset_path(name)
        if not os.path.exists(path):
            _mb.showerror(_("dlg_not_found"),
                _("dlg_file_missing2", path=path), parent=self)
            self._refresh_preset_combo()
            return
        try:
            os.remove(path)
        except Exception as e:
            _mb.showerror(_("dlg_delete_error"), str(e), parent=self)
            return
        if self._preset_name_var.get().strip() == name:
            self._preset_dirty = False
            self._preset_name_var.set(_("no_preset"))
            self._set_last_preset_name("")
            if hasattr(self, "_preset_dirty_lbl"):
                self._preset_dirty_lbl.config(text="")
        self._refresh_preset_combo()
    def _load_last_preset(self):
        import json
        name = self._get_last_preset_name()
        if not name:
            self._refresh_preset_combo()
            return
        path = self._preset_path(name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_preset_data(data)
            self._mark_clean(name)
        except Exception:
            self._refresh_preset_combo()
    def _new_preset(self):
        """Réinitialise le canvas pour créer un nouveau preset."""
        if self._preset_dirty:
            from tkinter import messagebox as _mb
            cur = self._preset_name_var.get().strip()
            label = f'"{cur}"' if cur and cur != _("no_preset") else _("current_preset")
            rep = _mb.askyesnocancel(
                _("new_preset"),
                _("save_before_new", label=label),
                parent=self)
            if rep is None:
                return
            if rep:
                self._save_preset()
        self._canvas.delete("all")
        self._nodes.clear()
        self._connections.clear()
        self._selected_nodes.clear()
        self._next_id = 1
        self._draw_grid()
        self._redraw_wires()
        self._preset_dirty = False
        self._preset_name_var.set(_("no_preset"))
        if hasattr(self, "_preset_dirty_lbl"):
            self._preset_dirty_lbl.config(text="")
        self._refresh_preset_combo()
        self._update_status()

    def _clear_all(self):
        self._canvas.delete("all"); self._nodes.clear(); self._connections.clear()
        self._selected_nodes.clear(); self._wire_src = None; self._wire_tmp = None
        self._rubber_rect = None
        self._draw_grid()
        if self._hint: self._hint.place(relx=0.5, rely=0.5, anchor="center")
        self._prev_tree.delete(*self._prev_tree.get_children())
        self._chain_lbl.config(text=_("chain_click"))
        self._last_tree = None; self._update_status()
    def _redraw_wires(self):
        for c in self._connections:
            self._canvas.delete(c.get("cid"))
        for c in self._connections:
            c["cid"] = self._draw_wire_conn(c)
        self._canvas.tag_lower("grid")


    def _draw_wire_conn(self, conn):
        sn = self._nodes.get(conn["src"]); dn = self._nodes.get(conn["dst"])
        if not sn or not dn: return None
        ct = conn["ctype"]
        if ct == "name_in":
            x1, y1 = sn.port_out_pos(); x2, y2 = dn.port_name_in_pos()
            col = COLOR_LIANT
        else:  # "chain"
            x1, y1 = sn.port_out_pos(); x2, y2 = dn.port_in_pos()
            col = sn.color
        cx = (x1 + x2) / 2
        cid = self._canvas.create_line(x1, y1, cx, y1, cx, y2, x2, y2,
            fill=col, width=2, smooth=True, splinesteps=32, tags="wire")
        self._canvas.tag_bind(cid, "<ButtonPress-1>",
            lambda e, c=conn: self._cut_wire(c))
        self._canvas.tag_bind(cid, "<Enter>",
            lambda e, cid2=cid: self._canvas.itemconfig(cid2, width=4, fill="#ff4444"))
        self._canvas.tag_bind(cid, "<Leave>",
            lambda e, cid2=cid, col2=col: self._canvas.itemconfig(cid2, width=2, fill=col2))
        return cid


    def _cut_wire(self, conn):
        self._canvas.delete(conn.get("cid"))
        self._connections = [c for c in self._connections
                             if not (c["src"] == conn["src"] and c["dst"] == conn["dst"]
                                     and c["ctype"] == conn["ctype"])]
        self._update_status()
    def _bind_canvas_events(self):
        c = self._canvas
        c.bind("<ButtonPress-1>",          self._on_press)
        c.bind("<B1-Motion>",              self._on_drag)
        c.bind("<ButtonRelease-1>",         self._on_release)
        c.bind("<ButtonPress-3>",          self._on_pan_start)
        c.bind("<B3-Motion>",              self._on_pan)
        c.bind("<ButtonRelease-3>",         lambda e: setattr(self, "_pan_start", None))
        c.bind("<ButtonPress-2>",          self._on_pan_start)
        c.bind("<B2-Motion>",              self._on_pan)
        c.bind("<ButtonRelease-2>",         lambda e: setattr(self, "_pan_start", None))
        c.bind("<Shift-ButtonPress-1>",    self._on_shift_pan_start)
        c.bind("<Shift-B1-Motion>",        self._on_shift_pan)
        c.bind("<Shift-ButtonRelease-1>",  self._on_shift_pan_end)
        c.bind("<MouseWheel>",             self._on_canvas_wheel)
        c.bind("<Button-4>",               lambda e: self._canvas_zoom_step(e, 1.1))
        c.bind("<Button-5>",               lambda e: self._canvas_zoom_step(e, 0.9))
        c.bind("<Double-Button-1>",         self._on_double_click)
        c.bind("<Delete>",                 lambda e: self._delete_selected())
        c.bind("<BackSpace>",              lambda e: self._delete_selected())
        c.bind("<FocusIn>",                lambda e: None)
        c.config(takefocus=True)
        c.bind("<ButtonPress-1>",          self._on_press, add="+")

    def _find_node_at(self, mx, my):
        for nid, n in reversed(list(self._nodes.items())):
            if n.hit_test(mx, my): return nid
        return None

    def _on_press(self, event):
        mx, my = event.x, event.y
        ctrl   = (event.state & 0x0004) != 0
        self._canvas.focus_set()
        for nid, n in self._nodes.items():
            if n.hit_port_name_in(mx, my):
                self._wire_src = (nid, "name_in"); return
        for nid, n in self._nodes.items():
            if n.hit_port_out(mx, my):
                self._wire_src = (nid, "chain"); return
        for nid, n in list(self._nodes.items()):
            if n.hit_delete(mx, my):
                self._delete_node(nid); return

        nid = self._find_node_at(mx, my)

        if nid is not None:
            if ctrl:
                if nid in self._selected_nodes:
                    self._selected_nodes.discard(nid)
                    self._nodes[nid].set_selected(False)
                else:
                    self._selected_nodes.add(nid)
                    self._nodes[nid].set_selected(True)
            else:
                if nid not in self._selected_nodes:
                    for sid in self._selected_nodes:
                        if sid in self._nodes: self._nodes[sid].set_selected(False)
                    self._selected_nodes = {nid}
                    self._nodes[nid].set_selected(True)
            self._drag_node   = nid
            self._drag_offset = (mx - self._nodes[nid].x, my - self._nodes[nid].y)
            for sid in self._selected_nodes:
                if sid in self._nodes:
                    for cid in self._nodes[sid].canvas_ids:
                        self._canvas.tag_raise(cid)
        else:
            if not ctrl:
                for sid in self._selected_nodes:
                    if sid in self._nodes: self._nodes[sid].set_selected(False)
                self._selected_nodes.clear()
            self._rubber_start = (mx, my)


    def _on_drag(self, event):
        mx, my = event.x, event.y
        if self._wire_src is not None:
            if self._wire_tmp: self._canvas.delete(self._wire_tmp)
            src_nid, ptype = self._wire_src
            sn = self._nodes.get(src_nid)
            if sn:
                if ptype == "chain":
                    x1, y1 = sn.port_out_pos(); col = sn.color
                else:
                    x1, y1 = sn.port_out_pos()  # compat; col = ORANGE
                cx = (x1 + mx) / 2
                self._wire_tmp = self._canvas.create_line(
                    x1, y1, cx, y1, cx, my, mx, my,
                    fill=col, width=2, dash=(6,3), smooth=True,
                    splinesteps=32, tags="wire_tmp")
            return
        if self._rubber_start is not None and self._drag_node is None:
            if self._rubber_rect: self._canvas.delete(self._rubber_rect)
            rx, ry = self._rubber_start
            self._rubber_rect = self._canvas.create_rectangle(
                rx, ry, mx, my,
                outline=PRIMARY, fill=PRIMARY, stipple="gray25", tags="rubber")
            return
        if self._drag_node is not None and self._drag_node in self._nodes:
            dn = self._nodes[self._drag_node]
            base_dx = mx - self._drag_offset[0] - dn.x
            base_dy = my - self._drag_offset[1] - dn.y
            for sid in self._selected_nodes:
                if sid in self._nodes:
                    self._nodes[sid].move(base_dx, base_dy)
            self._redraw_wires()

    def _on_release(self, event):
        mx, my = event.x, event.y

        if self._wire_src is not None:
            src_nid, ptype = self._wire_src
            src_n = self._nodes.get(src_nid)
            for nid, n in self._nodes.items():
                if nid == src_nid: continue

                if ptype == "chain":
                    if n.hit_port_in(mx, my):
                        if src_n and src_n.node_family in ("argument", "liant") and n.node_family == "folder":
                            from tkinter import messagebox as _mb
                            _mb.showwarning(_("dlg_invalid_conn"),
                                _("wrong_port_msg"), parent=self)
                            break
                        conn = {"src": src_nid, "dst": nid, "ctype": "chain", "cid": None}
                        if not any(c["src"] == src_nid and c["dst"] == nid and c["ctype"] == "chain"
                                   for c in self._connections):
                            self._connections.append(conn)
                        self._redraw_wires(); break
                    elif n.hit_port_name_in(mx, my):
                        if not src_n or src_n.node_family not in ("argument", "liant"):
                            from tkinter import messagebox as _mb
                            _mb.showwarning(_("dlg_invalid_conn"),
                                "Seuls les nodes Argument et Liant peuvent\nse connecter au port ▼ NOM d'un dossier.", parent=self)
                            break
                        conn = {"src": src_nid, "dst": nid, "ctype": "name_in", "cid": None}
                        if not any(c["ctype"] == "name_in" and c["dst"] == nid
                                   for c in self._connections):
                            self._connections.append(conn)
                        self._redraw_wires(); break

                elif ptype == "name_in":
                    if n.hit_port_out(mx, my):
                        if n.node_family not in ("argument", "liant"):
                            break
                        conn = {"src": nid, "dst": src_nid, "ctype": "name_in", "cid": None}
                        if not any(c["ctype"] == "name_in" and c["dst"] == src_nid
                                   for c in self._connections):
                            self._connections.append(conn)
                        self._redraw_wires(); break

            if self._wire_tmp:
                self._canvas.delete(self._wire_tmp); self._wire_tmp = None
            self._wire_src = None

        if self._rubber_rect:
            self._canvas.delete(self._rubber_rect); self._rubber_rect = None
        if self._rubber_start is not None:
            rx0, ry0 = self._rubber_start; rx1, ry1 = mx, my
            x0, x1 = min(rx0, rx1), max(rx0, rx1)
            y0, y1 = min(ry0, ry1), max(ry0, ry1)
            for nid, n in self._nodes.items():
                cx, cy = n.x + n.NW // 2, n.y + n.NH // 2
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    self._selected_nodes.add(nid)
                    n.set_selected(True)
            self._rubber_start = None

        self._drag_node = None
        self._update_status()
        cur = self._preset_name_var.get() if hasattr(self, "_preset_name_var") else ""
        if cur and cur != _("no_preset") and not self._preset_dirty:
            self._mark_dirty()


    def _on_pan_start(self, event): self._pan_start = (event.x, event.y)

    def _on_pan(self, event):
        if self._pan_start:
            dx = event.x - self._pan_start[0]; dy = event.y - self._pan_start[1]
            self._pan_start = (event.x, event.y)
            for n in self._nodes.values(): n.move(dx, dy)
            self._redraw_wires()

    def _on_shift_pan_start(self, event):
        self._shift_pan_start = (event.x, event.y)
        self._canvas.config(cursor="fleur")

    def _on_shift_pan(self, event):
        if self._shift_pan_start:
            dx = event.x - self._shift_pan_start[0]
            dy = event.y - self._shift_pan_start[1]
            self._shift_pan_start = (event.x, event.y)
            for n in self._nodes.values(): n.move(dx, dy)
            self._redraw_wires()

    def _on_shift_pan_end(self, event):
        self._shift_pan_start = None
        self._canvas.config(cursor="crosshair")

    def _on_canvas_wheel(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self._canvas_zoom_step(event, factor)

    def _canvas_zoom_step(self, event, factor):
        MIN_ZOOM, MAX_ZOOM = 0.2, 4.0
        new_zoom = max(MIN_ZOOM, min(self._canvas_zoom * factor, MAX_ZOOM))
        if new_zoom == self._canvas_zoom:
            return
        real_factor = new_zoom / self._canvas_zoom
        self._canvas_zoom = new_zoom
        cx, cy = event.x, event.y
        for n in self._nodes.values():
            new_x = cx + (n.x - cx) * real_factor
            new_y = cy + (n.y - cy) * real_factor
            n.move(new_x - n.x, new_y - n.y)
        Node.NW = max(100, min(300, int(200 * self._canvas_zoom)))
        Node.NH = max(45,  min(160, int(90  * self._canvas_zoom)))
        for n in self._nodes.values():
            n.draw()
        self._redraw_wires()
        self._draw_grid()
        self._status.set(f"Zoom : {int(self._canvas_zoom * 100)} %")

    def _on_double_click(self, event):
        nid = self._find_node_at(event.x, event.y)
        if nid is None: return
        n = self._nodes[nid]
        if n.node_family == "folder":
            self._open_rename_dialog(nid)
        elif n.node_family == "liant":
            self._open_liant_dialog(nid)
        elif n.node_family == "argument":
            self._open_separator_dialog(nid)

    def _open_rename_dialog(self, nid):
        if self._rename_win and self._rename_win.winfo_exists():
            self._rename_win.destroy()
        n = self._nodes[nid]
        win = tk.Toplevel(self); self._rename_win = win
        win.title(_("rename_folder_title")); win.configure(bg=SURFACE)
        win.resizable(False, False); win.geometry("320x120"); win.transient(self)
        tk.Label(win, text=_("folder_name_lbl"), bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 10)).pack(padx=20, pady=(16,4), anchor="w")
        var = tk.StringVar(value=n.label)
        entry = tk.Entry(win, textvariable=var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        entry.pack(fill="x", padx=20, ipady=6); entry.select_range(0, "end"); entry.focus_set()
        def confirm(*_):
            v = var.get().strip()
            if v:
                self._mark_dirty()
                n.label = v
                n._label_is_default = False  # l'utilisateur a personnalisé le nom
            win.destroy()
        entry.bind("<Return>", confirm)
        tk.Button(win, text=_("ok"), bg=PRIMARY, fg="#0f3638", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=20, pady=4,
                  cursor="hand2", command=confirm).pack(pady=10)

    def _open_liant_dialog(self, nid):
        """Popup pour éditer le texte libre d'un node Liant."""
        if self._rename_win and self._rename_win.winfo_exists():
            self._rename_win.destroy()
        n = self._nodes[nid]
        win = tk.Toplevel(self); self._rename_win = win
        win.title(_("edit_liant_title")); win.configure(bg=SURFACE)
        win.resizable(False, False); win.geometry("340x160"); win.transient(self)
        tk.Label(win, text=_("connector_text"), bg=SURFACE, fg=COLOR_LIANT,
                 font=("Segoe UI", 10, "bold")).pack(padx=20, pady=(16,2), anchor="w")
        tk.Label(win, text=_("connector_ex"),
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).pack(padx=20, anchor="w")
        presets_frame = tk.Frame(win, bg=SURFACE); presets_frame.pack(padx=20, pady=4, anchor="w")
        var = tk.StringVar(value=n.label)
        for lbl, val in [("-","-"),("_","_"),(" "," "),(".",".")]:
            tk.Button(presets_frame, text=repr(lbl), bg=SURFACE2, fg=COLOR_LIANT,
                      relief="flat", font=("Segoe UI", 8), padx=8, pady=2, cursor="hand2",
                      command=lambda v=val: var.set(v)).pack(side="left", padx=2)
        entry = tk.Entry(win, textvariable=var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 13))
        entry.pack(fill="x", padx=20, ipady=6)
        entry.select_range(0, "end"); entry.focus_set()
        def confirm(*_):
            v = var.get()
            self._mark_dirty(); n.label = v if v else "-"
            win.destroy()
        entry.bind("<Return>", confirm)
        tk.Button(win, text=_("ok"), bg=COLOR_LIANT, fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=20, pady=4,
                  cursor="hand2", command=confirm).pack(pady=8)

    def _open_separator_dialog(self, nid):
        """Popup de configuration du séparateur pour un node Argument."""
        if self._rename_win and self._rename_win.winfo_exists():
            self._rename_win.destroy()
        n = self._nodes[nid]
        win = tk.Toplevel(self); self._rename_win = win
        win.title(_("separator_title")); win.configure(bg=BG)
        win.resizable(False, False); win.transient(self)

        tk.Label(win, text=f"📌  {n.label}", bg=BG, fg=n.color,
                 font=("Segoe UI", 11, "bold"), pady=10, padx=16).pack(anchor="w")
        tk.Label(win,
            text=_("separator_hint"),
            bg=BG, fg=MUTED, font=("Segoe UI", 8), justify="left", padx=16).pack(anchor="w")
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", pady=6)

        sep_var = tk.StringVar(value=n.separator)
        presets = [(_("sep_none"), ""), (_("sep_dash"), "-"), ("Underscore _", "_"),
                   (_("sep_space"), " "), (_("sep_dot"), ".")]
        tk.Label(win, text=_("presets_lbl"), bg=BG, fg=TEXT,
                 font=("Segoe UI", 9, "bold"), padx=16).pack(anchor="w")
        btn_row = tk.Frame(win, bg=BG); btn_row.pack(fill="x", padx=16, pady=4)
        for lbl, val in presets:
            tk.Button(btn_row, text=lbl, bg=SURFACE2, fg=TEXT, relief="flat",
                      font=("Segoe UI", 8), padx=8, pady=4, cursor="hand2",
                      command=lambda v=val: sep_var.set(v)).pack(side="left", padx=2)

        tk.Label(win, text=_("custom_lbl"), bg=BG, fg=TEXT,
                 font=("Segoe UI", 9), padx=16).pack(anchor="w", pady=(8,2))
        ent_row = tk.Frame(win, bg=BG); ent_row.pack(fill="x", padx=16, pady=(0,8))
        entry = tk.Entry(ent_row, textvariable=sep_var, bg=SURFACE2, fg=TEXT,
                         insertbackground=TEXT, relief="flat",
                         font=("Segoe UI", 12), width=8)
        entry.pack(side="left", ipady=5)

        prev_frame = tk.Frame(win, bg=SURFACE, pady=6); prev_frame.pack(fill="x")
        prev_lbl = tk.Label(prev_frame, text="", bg=SURFACE, fg=PRIMARY,
                            font=("Segoe UI", 9, "bold"), padx=16)
        prev_lbl.pack(anchor="w")
        _examples = {
            "exif_annee":"2026", "exif_mois":"04", "exif_jour":"26",
            "exif_date_full":"2026-04-26", "annee_creation":"2026", "mois_creation":"04",
            "jour_creation":"26", "annee_modif":"2026", "mois_modif":"04", "jour_modif":"26",
            "nom_fichier":"DSC_0042", "extension":"JPG", "categorie":"Images", "taille":"1 Mo - 10 Mo",
        }
        def update_prev(*_):
            sep = sep_var.get()
            ex  = _examples.get(n.field, "valeur")
            prev_lbl.config(text=_("connector_preview", ex=ex, sep=sep))
        sep_var.trace_add("write", update_prev); update_prev()

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", pady=4)
        btn_f = tk.Frame(win, bg=BG); btn_f.pack(fill="x", padx=16, pady=(4,12))
        def apply():
            self._mark_dirty(); n.separator = sep_var.get()
            n.draw(); self._redraw_wires(); win.destroy()
        tk.Button(btn_f, text=_("cancel"), bg=SURFACE2, fg=MUTED, relief="flat",
                  font=("Segoe UI", 9), padx=10, pady=5, cursor="hand2",
                  command=win.destroy).pack(side="right", padx=(6,0))
        tk.Button(btn_f, text=_("apply_btn"), bg=PRIMARY, fg="#0f3638", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=5, cursor="hand2",
                  command=apply).pack(side="right")
        win.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width()//2 - win.winfo_width()//2
        py = self.winfo_rooty() + self.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{px}+{py}")
    def _update_status(self):
        folders  = sum(1 for n in self._nodes.values() if n.node_family == "folder")
        metadata = sum(1 for n in self._nodes.values() if n.node_family == "argument")
        nc       = len(self._connections)
        nsel     = len(self._selected_nodes)
        sel_txt  = _("node_sel_status", n=nsel) if nsel else ""
        self._status.set(
            _("node_count_status", n=len(self._nodes), f=folders, m=metadata)
            + _("node_conn_status", nc=nc, sel=sel_txt))
    def _resolve_chain(self):
        """Retourne la liste ordonnée des nids dans la chaîne principale.
        Exclut les nodes argument/liant qui font partie d'une chaîne de nom (port NOM)."""
        if not self._nodes: return []
        name_chain_nodes = set()
        direct_name_srcs = set(c["src"] for c in self._connections if c["ctype"] == "name_in"
                               and c["src"] in self._nodes)
        arg_liant_chain = [c for c in self._connections if c["ctype"] == "chain"
                           and c["src"] in self._nodes and c["dst"] in self._nodes
                           and self._nodes[c["src"]].node_family in ("argument", "liant")
                           and self._nodes[c["dst"]].node_family in ("argument", "liant")]
        al_in_e = {nid: [] for nid in self._nodes}
        for c in arg_liant_chain:
            al_in_e[c["dst"]].append(c["src"])

        def collect_name_chain(nid):
            if nid in name_chain_nodes: return
            if nid not in self._nodes: return
            if self._nodes[nid].node_family not in ("argument", "liant"): return
            name_chain_nodes.add(nid)
            for src in al_in_e.get(nid, []):
                collect_name_chain(src)

        for s in direct_name_srcs:
            collect_name_chain(s)
        chain_conns = [c for c in self._connections if c["ctype"] == "chain"
                       and c["src"] in self._nodes and c["dst"] in self._nodes
                       and c["src"] not in name_chain_nodes
                       and c["dst"] not in name_chain_nodes]

        out_e = {nid: [] for nid in self._nodes}
        in_e  = {nid: [] for nid in self._nodes}
        for c in chain_conns:
            out_e[c["src"]].append(c["dst"])
            in_e[c["dst"]].append(c["src"])
        valid_nodes = [nid for nid in self._nodes if nid not in name_chain_nodes]
        if not valid_nodes: return []

        roots = [nid for nid in valid_nodes if not in_e[nid]]
        if not roots: roots = [valid_nodes[0]]

        visited = []
        def walk(nid):
            if nid in visited or nid in name_chain_nodes: return
            visited.append(nid)
            for dst in out_e.get(nid, []):
                walk(dst)
        for r in roots:
            walk(r)
        return visited


    def _get_name_chain_for_folder(self, folder_nid):
        """
        Retourne la liste ORDONNÉE des nids argument/liant connectés au port NOM
        du dossier donné, en suivant la chaîne chain entre ces nodes.
        """
        name_in_srcs = [c["src"] for c in self._connections
                        if c["ctype"] == "name_in" and c["dst"] == folder_nid
                        and c["src"] in self._nodes]
        if not name_in_srcs: return []
        chain_conns = [c for c in self._connections if c["ctype"] == "chain"
                       and c["src"] in self._nodes and c["dst"] in self._nodes
                       and self._nodes[c["src"]].node_family in ("argument","liant")
                       and self._nodes[c["dst"]].node_family in ("argument","liant")]
        out_e = {nid: [] for nid in self._nodes}
        in_e  = {nid: [] for nid in self._nodes}
        for c in chain_conns:
            out_e[c["src"]].append(c["dst"]); in_e[c["dst"]].append(c["src"])
        all_in_chain = set()
        def collect_back(nid):
            if nid in all_in_chain: return
            if nid not in self._nodes: return
            if self._nodes[nid].node_family not in ("argument","liant"): return
            all_in_chain.add(nid)
            for src in in_e.get(nid, []): collect_back(src)
        for s in name_in_srcs: collect_back(s)
        roots = [n for n in all_in_chain if not any(s in all_in_chain for s in in_e.get(n, []))]
        if not roots: roots = list(name_in_srcs[:1])
        chain = []
        def walk_fwd(nid):
            if nid not in all_in_chain or nid in chain: return
            chain.append(nid)
            for dst in out_e.get(nid, []):
                if dst in all_in_chain: walk_fwd(dst)
        for r in roots: walk_fwd(r)
        return chain

    def get_structure(self):
        """Expose l'arbre résolu pour l'tab Organiser."""
        files = self._get_files()
        if not files: return None
        return self.get_structure_for_files(files)

    def get_structure_for_files(self, files, progress_cb=None):
        """Construit l'arbre pour une liste de files donnée."""
        if not files: return None
        chain = self._resolve_chain()
        if not chain: return None
        fields = []; labels = []
        for nid in chain:
            n = self._nodes[nid]
            if n.node_family == "argument":
                token = f"{n.field}::{n.separator}"
                fields.append(token)
                sep_hint = f" [{n.separator!r}]" if n.separator else ""
                labels.append(n.label + sep_hint)
            elif n.node_family == "folder":
                name_chain = self._get_name_chain_for_folder(nid)
                if name_chain:
                    tokens = []
                    for a in name_chain:
                        an = self._nodes[a]
                        if an.node_family == "argument":
                            tokens.append(f"arg::{an.field}::{an.separator}")
                        elif an.node_family == "liant":
                            tokens.append(f"lit::{an.label}")
                    fields.append("__folder_dyn__||" + "|".join(tokens))
                else:
                    fields.append(f"__folder__{n.label}")
                labels.append(f"📁 {n.label}")
        if not fields: return None
        tree = build_tree_from_chain_extended(
            files, fields,
            _progress_cb=progress_cb if progress_cb else None
        )
        return tree, labels, files
    def _update_nodal_prog_bar(self, *_):
        pct = self._nodal_prog_var.get() / 100.0
        self._nodal_prog_inner.place(x=0, y=0, relwidth=pct, height=4)
        if pct >= 1.0:
            self.after(600, lambda: self._nodal_prog_inner.place(
                x=0, y=0, relwidth=0.0, height=4))

    def _show_preview(self):
        files = self._get_files()
        if not files:
            from tkinter import messagebox as _mb
            _mb.showinfo(_("apercu_title"),
                _("no_files_preview"),
                parent=self); return
        chain = self._resolve_chain()
        if not chain:
            from tkinter import messagebox as _mb
            _mb.showinfo(_("apercu_title"), _("no_nodes_canvas"), parent=self); return
        fields = []; labels = []
        for nid in chain:
            n = self._nodes[nid]
            if n.node_family == "argument":
                token = f"{n.field}::{n.separator}"
                fields.append(token)
                sep_hint = f" [{n.separator!r}]" if n.separator else ""
                labels.append(n.label + sep_hint)
            elif n.node_family == "folder":
                name_chain = self._get_name_chain_for_folder(nid)
                if name_chain:
                    tokens = []
                    for a in name_chain:
                        an = self._nodes[a]
                        if an.node_family == "argument":
                            tokens.append(f"arg::{an.field}::{an.separator}")
                        elif an.node_family == "liant":
                            tokens.append(f"lit::{an.label}")
                    fields.append("__folder_dyn__||" + "|".join(tokens))
                else:
                    fields.append(f"__folder__{n.label}")
                labels.append(f"📁 {n.label}")
        if not fields:
            from tkinter import messagebox as _mb
            _mb.showinfo(_("apercu_title"), "Aucun node utilisable.", parent=self); return
        label_str = " → ".join(labels)
        n_files = len(files)
        self._chain_lbl.config(text=_("chain_computing", n=n_files))
        self._status.set(f"⏳ Calcul de la structure…  0 %")
        self._nodal_prog_var.set(0)
        def _nodal_progress(done, total):
            pct = int(done / total * 100) if total else 0
            self.after(0, lambda p=pct, d=done, t=total: (
                self._status.set(
                    f"⏳ Calcul… {d:,} / {t:,} fichiers  ({p} %)"),
                self._nodal_prog_var.set(p)
            ))
        def _compute():
            try:
                print(f"[NODAL] Calcul arbre — {n_files} fichiers, fields={fields}")
                tree = build_tree_from_chain_extended(files, fields,
                                                      _progress_cb=_nodal_progress)
                print(f"[NODAL] Arbre calculé — {len(tree)} entrées racine")
                self.after(0, lambda: self._apply_preview(tree, labels, label_str, n_files))
            except Exception as _e:
                print(f"[NODAL][ERREUR] {traceback.format_exc()}")
                self.after(0, lambda msg=str(_e): (
                    self._status.set(_("err_compute", msg=msg)),
                    self._chain_lbl.config(text=_("chain_error", msg=msg))
                ))
        threading.Thread(target=_compute, daemon=True).start()


    def _apply_preview(self, tree, labels, label_str, n_files):
        self._nodal_prog_var.set(100)  # termine la barre
        self._last_tree   = tree
        self._last_labels = labels
        self._chain_lbl.config(text=_("chain_result", label=label_str, n=n_files))
        self._prev_tree.delete(*self._prev_tree.get_children())
        self._populate_preview("", tree, 0)
        self._status.set(_("preview_ready", n=n_files, label=label_str))

    def _populate_preview(self, parent_iid, tree, depth):
        if isinstance(tree, list): return
        for key, val in sorted(tree.items()):
            if isinstance(val, list):
                self._prev_tree.insert(parent_iid, "end", text=f"  {key}",
                                       values=(len(val),), open=(depth == 0))
            else:
                total = self._count_files(val)
                iid   = self._prev_tree.insert(parent_iid, "end", text=f"  {key}",
                                               values=(total,), open=(depth == 0))
                self._populate_preview(iid, val, depth+1)

    def _count_files(self, tree):
        if isinstance(tree, list): return len(tree)
        return sum(self._count_files(v) for v in tree.values())

    def refresh_lang(self):
        """Refresh all translatable widgets in the Node Editor tab."""
        for attr, key in [
            ("_lbl_title",              "node_editor_title"),
            ("_lbl_hint",               "node_editor_hint"),
            ("_btn_clear",              "clear_all"),
            ("_btn_preview",            "click_preview"),
            ("_btn_reset_view",         "reset_view"),
            ("_btn_new_preset",         "new_preset"),
            ("_btn_save_preset",        "save_preset"),
            ("_lbl_palette",            "palette"),
            ("_lbl_how_to_build",       "how_to_build"),
            ("_lbl_how_to_build_txt",   "how_to_build_txt"),
            ("_lbl_drag_hint",          "drag_nodes_hint"),
            ("_lbl_preview_struct",     "preview_structure"),
        ]:
            w = getattr(self, attr, None)
            if w:
                try: w.config(text=_(key))
                except Exception: pass
        for lbl, key in getattr(self, "_pal_legend_items", []):
            try: lbl.config(text=_(key))
            except Exception: pass
        try:
            self._prev_tree.heading("#0",    text=_("folder_node"))
            self._prev_tree.heading("count", text=_("col_count"))
        except Exception: pass
        if hasattr(self, "_chain_lbl"):
            cur = self._chain_lbl.cget("text")
            placeholders_en = (
                "Click \u00ab Preview structure \u00bb.",
                "No files indexed",
                "No files indexed. Do a scan in the Explorer tab first.",
            )
            placeholders_fr = (
                "Cliquez sur \u00ab Aper\u00e7u structure \u00bb.",
                "Aucun fichier index\u00e9",
                "Aucun fichier index\u00e9. Faites d",
            )
            is_placeholder = any(cur.startswith(p) for p in placeholders_en + placeholders_fr)
            if is_placeholder or not cur.strip():
                self._chain_lbl.config(text=_("chain_click"))
        if hasattr(self, "_build_palette_meta"):
            self._build_palette_meta()
        global NODE_TYPES
        NODE_TYPES = _build_node_types()
        if hasattr(self, "_nodes"):
            for node in list(self._nodes.values()):
                try: node.draw()
                except Exception: pass


def _files_equal_meta(src, dst):

    """Retourne True si src et dst ont la même size ET le même mtime (à 2 s près).
    Méthode rapide — ne lit pas le contenu des fichiers."""
    try:
        ss = os.stat(src)
        ds = os.stat(dst)
        if ss.st_size != ds.st_size:
            return False
        return abs(ss.st_mtime - ds.st_mtime) <= 2.0
    except OSError:
        return False

def _files_equal_full(src, dst):
    """Retourne True si src et dst sont identiques bit à bit (lecture par blocs de 256 KB)."""
    try:
        ss = os.stat(src)
        ds = os.stat(dst)
        if ss.st_size != ds.st_size:
            return False
        BUF = 1 << 18  # 256 KB
        with open(src, "rb") as fs, open(dst, "rb") as fd:
            while True:
                bs = fs.read(BUF)
                bd = fd.read(BUF)
                if bs != bd:
                    return False
                if not bs:
                    break
        return True
    except OSError:
        return False


class OrganizeTab(tk.Frame):

    def __init__(self, parent, get_nodal_editor_cb):
        super().__init__(parent, bg=BG)
        self._get_editor    = get_nodal_editor_cb
        self._ops           = []
        self._tree          = None
        self._full_tree     = None   # arbre complet avant filtrage extension
        self._all_files_ref = []     # tous les fichiers avant filtrage
        self._op_mode       = tk.StringVar(value="copy")
        self._dest_var      = tk.StringVar(value="")
        self._ext_filter_vars = {}   # {ext: BooleanVar}
        self._build_ui()

    def _build_ui(self):
        tb = tk.Frame(self, bg=SURFACE, pady=8, padx=14)
        tb.pack(fill="x")
        self._lbl_org_title = tk.Label(tb, text=_("organize_title"), bg=SURFACE, fg=PRIMARY,
                 font=("Segoe UI", 9, "bold"))
        self._lbl_org_title.pack(side="left")
        self._lbl_org_hint = tk.Label(tb,
                 text=_("organize_hint"),
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 8))
        self._lbl_org_hint.pack(side="left")

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=10)
        left_outer = tk.Frame(main, bg=SURFACE, width=360)
        left_outer.pack(side="left", fill="y", padx=(0,12))
        left_outer.pack_propagate(False)

        _lc = tk.Canvas(left_outer, bg=SURFACE, highlightthickness=0, bd=0)
        _lvsb = ttk.Scrollbar(left_outer, orient="vertical", command=_lc.yview,
                               style="Dark.Vertical.TScrollbar")
        _lc.pack(side="left", fill="both", expand=True)
        _lc.configure(yscrollcommand=_lvsb.set)

        left = tk.Frame(_lc, bg=SURFACE)
        _lw = _lc.create_window((0, 0), window=left, anchor="nw")

        def _left_update_scroll(e=None):
            _lc.configure(scrollregion=_lc.bbox("all"))
            ch = _lc.winfo_height()
            if left.winfo_reqheight() > ch + 2:
                if not _lvsb.winfo_ismapped():
                    _lvsb.pack(side="right", fill="y", before=_lc)
            else:
                if _lvsb.winfo_ismapped():
                    _lvsb.pack_forget()
                    _lc.yview_moveto(0)

        left.bind("<Configure>", _left_update_scroll)
        _lc.bind("<Configure>", lambda e: (_lc.itemconfig(_lw, width=e.width),
                                            _left_update_scroll()))

        def _lscroll(e): _lc.yview_scroll(int(-1*(e.delta/120)), "units")
        _lc.bind("<MouseWheel>", _lscroll)
        left.bind("<MouseWheel>", _lscroll)

        def section(parent, title):
            f = tk.Frame(parent, bg=SURFACE)
            f.pack(fill="x", padx=14, pady=(14,0))
            f.bind("<MouseWheel>", _lscroll)
            tk.Label(f, text=title, bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 7, "bold")).pack(anchor="w")
            tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=4)
            return f
        self._s_struct = s1 = section(left, _("nodal_structure"))
        self._struct_lbl = tk.Label(s1,
            text=_("no_structure"),
            bg=SURFACE, fg=MUTED, font=("Segoe UI", 8), justify="left", wraplength=320)
        self._struct_lbl.pack(anchor="w", pady=4)
        self._load_btn = tk.Button(s1, text=_("load_structure"),
                  bg=SURFACE2, fg=PRIMARY, relief="flat",
                  font=("Segoe UI", 9), padx=8, pady=5,
                  cursor="hand2", command=self._load_structure)
        self._load_btn.pack(fill="x", pady=(4,0))
        self._s_ext = s_ext = section(left, _("sect_ext"))
        self._ext_filter_frame = tk.Frame(s_ext, bg=SURFACE)
        self._ext_filter_frame.pack(fill="x", pady=(2,0))
        self._ext_filter_empty_lbl = self._lbl_load_ext = tk.Label(s_ext,
            text=_("load_ext_hint"),
            bg=SURFACE, fg=MUTED, font=("Segoe UI", 8), justify="left", wraplength=320)
        self._ext_filter_empty_lbl.pack(anchor="w", pady=4)
        ext_btn_row = tk.Frame(s_ext, bg=SURFACE)
        ext_btn_row.pack(fill="x", pady=(4,0))
        self._btn_check_all = tk.Button(ext_btn_row, text=_("check_all"), bg=SURFACE2, fg=SUCCESS, relief="flat",
                  font=("Segoe UI", 8), padx=6, pady=2, cursor="hand2",
                  command=lambda: self._select_all_exts(True))
        self._btn_check_all.pack(side="left", padx=(0,4))
        self._btn_check_none = tk.Button(ext_btn_row, text=_("check_none"), bg=SURFACE2, fg=MUTED, relief="flat",
                  font=("Segoe UI", 8), padx=6, pady=2, cursor="hand2",
                  command=lambda: self._select_all_exts(False))
        self._btn_check_none.pack(side="left")
        s2 = section(left, _("op_section")); self._s_op_section = s2
        self._op_radios = []
        for val,key,col in [
            ("copy","sect_mode_copy",SUCCESS),
            ("move","sect_mode_move",ORANGE),
        ]:
            _rb=tk.Radiobutton(s2,text=_(key),variable=self._op_mode,value=val,
                           bg=SURFACE,fg=col,selectcolor=SURFACE2,
                           activebackground=SURFACE,font=("Segoe UI",9),cursor="hand2")
            _rb.pack(anchor="w",pady=2)
            self._op_radios.append((_rb,key))
        self._s_dup = section(left, _("dup_section"))
        self._dup_mode = tk.StringVar(value="ask")
        self._dup_radios = []
        for val, key, col in [
            ("ask",          "dup_ask",         TEXT),
            ("skip",         "dup_skip",        MUTED),
            ("replace",      "dup_replace_auto",ORANGE),
            ("rename",       "dup_rename_auto", PRIMARY),
            ("compare_meta", "dup_meta",        "#4f98a3"),
            ("compare_full", "dup_full_cmp",    "#a86fdf"),
        ]:
            rb = tk.Radiobutton(self._s_dup, text=_(key), variable=self._dup_mode, value=val,
                           bg=SURFACE, fg=col, selectcolor=SURFACE2,
                           activebackground=SURFACE, font=("Segoe UI", 9),
                           cursor="hand2")
            rb.pack(anchor="w", pady=1)
            self._dup_radios.append((rb, key))
        s3 = section(left, _("sect_dest")); self._s_dest = s3
        dr = tk.Frame(s3, bg=SURFACE); dr.pack(fill="x")
        tk.Entry(dr, textvariable=self._dest_var, bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, ipady=5)
        self._btn_browse = tk.Button(dr, text=_("browse"), bg=SURFACE2, fg=TEXT, relief="flat",
                  font=("Segoe UI", 9), padx=8, pady=5,
                  cursor="hand2", command=self._pick_dest)
        self._btn_browse.pack(side="left", padx=(6,0))
        s4 = section(left, _("summary_section")); self._s_summary_section = s4
        self._summary_lbl = tk.Label(s4, text="—", bg=SURFACE, fg=MUTED,
                                     font=("Segoe UI", 8), justify="left", wraplength=320)
        self._summary_lbl.pack(anchor="w", pady=4)
        s5 = tk.Frame(left, bg=SURFACE)
        s5.pack(fill="x", padx=14, pady=(20,14))
        self._cancel_flag = False

        btn_row = tk.Frame(s5, bg=SURFACE)
        btn_row.pack(fill="x")
        self._run_btn = tk.Button(btn_row, text=_("apply_structure"),
                                  bg=PRIMARY, fg="#0f3638",
                                  activebackground=PRIMARY_H, activeforeground="#0f3638",
                                  relief="flat", font=("Segoe UI", 10, "bold"),
                                  padx=16, pady=8, cursor="hand2",
                                  command=self._run, state="disabled")
        self._run_btn.pack(side="left", fill="x", expand=True)
        self._stop_btn = tk.Button(btn_row, text="⏹",
                                   bg="#a13544", fg="white",
                                   activebackground="#782b33", activeforeground="white",
                                   relief="flat", font=("Segoe UI", 11, "bold"),
                                   padx=10, pady=8, cursor="hand2",
                                   command=self._request_cancel)
        self._progress = ttk.Progressbar(s5, mode="determinate",
                                         style="Custom.Horizontal.TProgressbar")
        self._progress.pack(fill="x", pady=(8,0))
        self._prog_lbl = tk.Label(s5, text="", bg=SURFACE, fg=MUTED, font=("Segoe UI", 8))
        self._prog_lbl.pack(anchor="w")
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(right, bg=SURFACE, pady=6, padx=10)
        hdr.pack(fill="x")
        self._lbl_ops_preview = tk.Label(hdr, text=_("ops_preview"), bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"))
        self._lbl_ops_preview.pack(side="left")
        self._ops_count_lbl = tk.Label(hdr, text="", bg=SURFACE, fg=PRIMARY,
                                       font=("Segoe UI", 8))
        self._ops_count_lbl.pack(side="left", padx=8)
        self._nomatch_count_lbl = tk.Label(hdr, text="", bg=SURFACE, fg=ORANGE,
                                           font=("Segoe UI", 8))
        self._nomatch_count_lbl.pack(side="left", padx=4)
        style = ttk.Style()
        style.configure("Ops.TNotebook", background=BG, borderwidth=0, tabmargins=0)
        style.configure("Ops.TNotebook.Tab",
            background=SURFACE2, foreground=MUTED,
            font=("Segoe UI", 8), padding=(10, 4))
        style.map("Ops.TNotebook.Tab",
            background=[("selected", BG)],
            foreground=[("selected", TEXT)])

        self._ops_notebook = ttk.Notebook(right, style="Ops.TNotebook")
        self._ops_notebook.pack(fill="both", expand=True)
        tab_all = tk.Frame(self._ops_notebook, bg=BG)
        self._ops_notebook.add(tab_all, text=_("tab_all_ops"))
        cols = ("src", "dst")
        tv_fr = tk.Frame(tab_all, bg=BG)
        tv_fr.pack(fill="both", expand=True)
        self._ops_tree = ttk.Treeview(tv_fr, columns=cols,
                                      show="headings", style="Custom.Treeview")
        self._ops_tree.heading("src", text=_("col_src"))
        self._ops_tree.heading("dst", text=_("col_dst"))
        self._ops_tree.column("src", width=300, anchor="w")
        self._ops_tree.column("dst", width=520, anchor="w")
        vsb = ttk.Scrollbar(tv_fr, orient="vertical",   command=self._ops_tree.yview, style="Dark.Vertical.TScrollbar")
        hsb = ttk.Scrollbar(tv_fr, orient="horizontal", command=self._ops_tree.xview, style="Dark.Horizontal.TScrollbar")
        self._ops_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x"); vsb.pack(side="right", fill="y")
        self._ops_tree.pack(fill="both", expand=True)
        tab_nm = tk.Frame(self._ops_notebook, bg=BG)
        self._ops_notebook.add(tab_nm, text=_("tab_unmatched"))
        nm_fr = tk.Frame(tab_nm, bg=BG)
        nm_fr.pack(fill="both", expand=True)
        self._nomatch_tree = ttk.Treeview(nm_fr, columns=("file", "reason"),
                                          show="headings", style="Custom.Treeview")
        self._nomatch_tree.heading("file",   text=_("col_file"))
        self._nomatch_tree.heading("reason", text=_("col_reason"))
        self._nomatch_tree.column("file",   width=300, anchor="w")
        self._nomatch_tree.column("reason", width=520, anchor="w")
        self._nomatch_tree.tag_configure("nm", foreground=ORANGE)
        vsb2 = ttk.Scrollbar(nm_fr, orient="vertical",   command=self._nomatch_tree.yview, style="Dark.Vertical.TScrollbar")
        hsb2 = ttk.Scrollbar(nm_fr, orient="horizontal", command=self._nomatch_tree.xview, style="Dark.Horizontal.TScrollbar")
        self._nomatch_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        hsb2.pack(side="bottom", fill="x"); vsb2.pack(side="right", fill="y")
        self._nomatch_tree.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value=_("start_status"))
        tk.Label(self, textvariable=self._status_var, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8), anchor="w", padx=10, pady=4).pack(fill="x", side="bottom")
        self._prog_bar_var = tk.IntVar(value=0)
        self._prog_bar_frame = tk.Frame(self, bg=SURFACE, height=4)
        self._prog_bar_frame.pack(fill="x", side="bottom")
        self._prog_bar_frame.pack_propagate(False)
        self._prog_bar_inner = tk.Frame(self._prog_bar_frame, bg=PRIMARY, height=4)
        self._prog_bar_inner.place(x=0, y=0, relwidth=0.0, height=4)
        self._prog_bar_var.trace_add("write", self._update_prog_bar)
    def _update_prog_bar(self, *_):
        pct = self._prog_bar_var.get() / 100.0
        self._prog_bar_inner.place(x=0, y=0, relwidth=pct, height=4)
        if pct >= 1.0:
            self.after(600, lambda: self._prog_bar_inner.place(
                x=0, y=0, relwidth=0.0, height=4))

    def _load_structure(self):
        editor = self._get_editor()
        if editor is None:
            messagebox.showinfo(_("structure_info"),
                "L'éditeur nodal n'est pas encore initialisé.\nOuvrez d'abord l'onglet Éditeur Nodal.",
                parent=self); return
        raw = editor.get_structure()
        if raw is None:
            messagebox.showinfo(_("structure_info"),
                "Aucune structure définie dans l'éditeur nodal.\n"
                "Ajoutez des nodes et cliquez sur '▶ Aperçu structure'.",
                parent=self); return
        tree_data, labels, files = raw
        label_str = " → ".join(labels)
        self._status_var.set(_("chain_computing", n=len(files)))
        self._struct_lbl.config(text=_("chain_computing", n=0))
        self._load_btn.config(state="disabled")
        self._all_files_ref = files
        import threading
        total_files = len(files)
        def _progress(done, total):
            self.after(0, lambda d=done, t=total: (
                self._status_var.set(
                    f"⏳ Calcul… {d:,} / {t:,} fichiers  "
                    f"({int(d/t*100) if t else 0} %)"),
                self._prog_bar_var.set(int(d / t * 100) if t else 0)
            ))
        def _worker():
            result = editor.get_structure_for_files(files, progress_cb=_progress)
            self.after(0, lambda: self._on_structure_ready(result, label_str, files))
        threading.Thread(target=_worker, daemon=True).start()

    def _on_structure_ready(self, result, label_str, files):
        self._prog_bar_var.set(100)
        self._load_btn.config(state="normal")
        if result is None:
            self._status_var.set(_("chain_click"))
            return
        tree, labels, result_files = result
        self._full_tree = tree
        self._tree      = tree
        self._struct_lbl.config(text=_("chain_result", label=label_str, n=len(files)))
        self._build_ext_filter(files)
        dest = self._dest_var.get().strip()
        self._refresh_ops(tree, dest or "/destination/")
        self._update_summary()
        self._check_ready()
        self._status_var.set(_("chain_result", label=label_str, n=len(files)))

    def _build_ext_filter(self, files):
        """Reconstruit les checkboxes d'extension à partir de la liste de files."""
        for w in self._ext_filter_frame.winfo_children():
            w.destroy()
        self._ext_filter_vars.clear()
        cat_exts = defaultdict(set)
        for f in files:
            cat_exts[get_category(f["ext"])].add(f["ext"].lower() or "(sans ext)")
        self._ext_filter_empty_lbl.pack_forget()
        row = None
        col_idx = 0
        for cat in sorted(cat_exts.keys()):
            color = EXTENSION_COLORS.get(cat, MUTED)
            cat_lbl = tk.Label(self._ext_filter_frame, text=f"● {cat.capitalize()}",
                               bg=SURFACE, fg=color, font=("Segoe UI", 7, "bold"))
            cat_lbl.pack(anchor="w", padx=4, pady=(6,1))
            row = tk.Frame(self._ext_filter_frame, bg=SURFACE)
            row.pack(fill="x", padx=4)
            col_idx = 0
            for ext in sorted(cat_exts[cat]):
                var = tk.BooleanVar(value=True)
                self._ext_filter_vars[ext] = var
                cb = tk.Checkbutton(row, text=ext.lstrip(".").upper() or "—",
                                    variable=var, bg=SURFACE, fg=TEXT, selectcolor=SURFACE2,
                                    activebackground=SURFACE, font=("Segoe UI", 8),
                                    cursor="hand2", command=self._on_ext_filter_change)
                cb.grid(row=col_idx // 3, column=col_idx % 3, sticky="w", padx=2)
                col_idx += 1

    def _select_all_exts(self, value):
        for var in self._ext_filter_vars.values():
            var.set(value)
        self._on_ext_filter_change()

    def _on_ext_filter_change(self):
        """Recalculatione les opérations selon les extensions cochées (avec debounce)."""
        if hasattr(self, "_ext_debounce_id") and self._ext_debounce_id:
            self.after_cancel(self._ext_debounce_id)
        self._ext_debounce_id = self.after(120, self._do_ext_filter_change)

    def _do_ext_filter_change(self):
        self._ext_debounce_id = None
        if self._full_tree is None or not self._all_files_ref:
            return
        selected_exts = {ext for ext, var in self._ext_filter_vars.items() if var.get()}
# Extension filters are applied on the cached file list so the structure can be recomputed without rescanning the disk.
        filtered_files = [f for f in self._all_files_ref
                          if (f["ext"].lower() or "(sans ext)") in selected_exts]
        editor = self._get_editor()
        if editor is None:
            return
        n_sel = len(selected_exts)
        n_filt = len(filtered_files)
        n_all  = len(self._all_files_ref)
        self._status_var.set(_("ops_recalc", n=n_filt))
        import threading
        def _progress2(done, total):
            self.after(0, lambda d=done, t=total: (
                self._status_var.set(
                    f"⏳ Recalcul… {d:,} / {t:,}  "
                    f"({int(d/t*100) if t else 0} %)"),
                self._prog_bar_var.set(int(d / t * 100) if t else 0)
            ))
        def _worker():
            result = editor.get_structure_for_files(filtered_files, progress_cb=_progress2)
            self.after(0, lambda: self._on_ext_filter_ready(
                result, filtered_files, n_sel, n_filt, n_all))
        threading.Thread(target=_worker, daemon=True).start()

    def _on_ext_filter_ready(self, result, filtered_files, n_sel, n_filt, n_all):
        self._prog_bar_var.set(100)
        if result is None:
            self._ops = []
            self._ops_tree.delete(*self._ops_tree.get_children())
            self._nomatch_tree.delete(*self._nomatch_tree.get_children())
            self._ops_count_lbl.config(text=_("zero_files"))
            self._update_summary()
            self._check_ready()
            return
        tree, labels, result_files = result
        self._tree = tree
        dest = self._dest_var.get().strip()
        self._refresh_ops(tree, dest or "/destination/")
        self._update_summary()
        self._check_ready()
        self._status_var.set(
            _("ops_selected", n=n_filt, t=n_all, e=n_sel))

    def _refresh_ops(self, tree, dest_base):
        all_ops = flatten_tree_to_operations(tree, dest_base)
        self._ops = all_ops
        ok_ops  = [(s, d) for s, d in all_ops if "?" not in d]
        nm_ops  = [(s, d) for s, d in all_ops if "?" in d]
        self._ops_tree.delete(*self._ops_tree.get_children())
        for src, dst in all_ops:
            tag = "nomatch" if "?" in dst else ""
            self._ops_tree.insert("", "end",
                values=(os.path.basename(src), dst), tags=(tag,))
        self._ops_tree.tag_configure("nomatch", foreground=ORANGE)
        self._ops_count_lbl.config(text=_("ops_count", n=len(all_ops)))
        self._nomatch_tree.delete(*self._nomatch_tree.get_children())
        for src, dst in nm_ops:
            self._nomatch_tree.insert("", "end",
                values=(os.path.basename(src), dst), tags=("nm",))
        tab_title = _("ops_unmatched_tab", n=len(nm_ops)) if nm_ops else _("tab_unmatched")
        self._ops_notebook.tab(1, text=tab_title)
        if nm_ops:
            self._nomatch_count_lbl.config(text=_("ops_unmatched", n=len(nm_ops)))
        else:
            self._nomatch_count_lbl.config(text="")

    def _update_summary(self):
        mode_str = _("copy_mode") if self._op_mode.get() == "copy" else _("move_mode")
        dest = self._dest_var.get().strip() or _("dest_undefined")
        self._summary_lbl.config(
            text=_("summary_template", n=len(self._ops), mode=mode_str, dest=dest))

    def _pick_dest(self):
        folder = filedialog.askdirectory(title=_("dlg_choose_dest"), parent=self)
        if folder:
            self._dest_var.set(folder)
            if self._tree is not None:
                self._refresh_ops(self._tree, folder)
            self._update_summary()
            self._check_ready()

    def _check_ready(self):
        ok = bool(self._dest_var.get().strip()) and bool(self._ops)
        self._run_btn.config(state="normal" if ok else "disabled")

    def _run(self):
        dest = self._dest_var.get().strip()
        if not dest or not self._ops: return
        mode = self._op_mode.get()
        verb = _("verb_copy") if mode == "copy" else _("verb_move")
        warn = ("\n" + _("warn_move") if mode == "move" else "")
        if not messagebox.askyesno(_("dlg_confirm"),
                _("ops_confirm", verb=verb, n=len(self._ops)) + _("dest_label", dest=dest) + warn, parent=self):
            return
        collisions = [(src, dst) for src, dst in self._ops
                      if "?" not in dst and os.path.exists(dst)]
        dup_mode = self._dup_mode.get()
        if collisions:
            if dup_mode == "ask":
                action = self._ask_collision_action(collisions)
                if action is None:
                    return
            else:
                action = dup_mode   # skip / replace / rename / compare_meta / compare_full
        else:
            action = "replace"

        self._cancel_flag = False
        self._run_btn.config(state="disabled")
        self._stop_btn.pack(in_=self._run_btn.master, side="left", padx=(6,0))
        self._progress.config(maximum=len(self._ops), value=0)
        threading.Thread(target=self._do_run,
                         args=(list(self._ops), mode, dest, action),
                         daemon=True).start()

    def _ask_collision_action(self, collisions):
        """Boite de dialogue quand des files existent déjà à destination.
        Retourne 'skip', 'replace', 'rename' ou None (annuler)."""
        win = tk.Toplevel(self)
        win.title(_("collision_title"))
        win.configure(bg=SURFACE)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        tk.Label(win,
                 text=_("ops_collision", n=len(collisions)),
                 bg=SURFACE, fg=ORANGE, font=("Segoe UI", 10, "bold"),
                 pady=10, padx=16).pack(anchor="w")

        lf = tk.Frame(win, bg=SURFACE2, padx=12, pady=8)
        lf.pack(fill="x", padx=16, pady=(0, 8))
        for _src, dst in collisions[:8]:
            tk.Label(lf, text=f"• {os.path.basename(dst)}",
                     bg=SURFACE2, fg=MUTED, font=("Segoe UI", 8),
                     anchor="w").pack(fill="x")
        if len(collisions) > 8:
            tk.Label(lf, text=_("n_others", n=len(collisions)-8),
                     bg=SURFACE2, fg=MUTED, font=("Segoe UI", 8, "italic"),
                     anchor="w").pack(fill="x")

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", pady=(4, 8))
        tk.Label(win, text=_("duplicates_q"),
                 bg=SURFACE, fg=TEXT, font=("Segoe UI", 9),
                 padx=16).pack(anchor="w", pady=(0, 6))

        chosen = tk.StringVar(value="")

        btn_frame = tk.Frame(win, bg=SURFACE)
        btn_frame.pack(fill="x", padx=16, pady=(0, 14))

        def pick(val):
            chosen.set(val)
            win.destroy()

        tk.Button(btn_frame, text=_("dup_ignore"),
                  bg=SURFACE2, fg=MUTED, relief="flat",
                  font=("Segoe UI", 9), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick("skip")).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text=_("dup_replace"),
                  bg=ORANGE, fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick("replace")).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text=_("dup_rename"),
                  bg=PRIMARY, fg="#0f3638", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick("rename")).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text=_("cancel"),
                  bg=SURFACE2, fg=TEXT, relief="flat",
                  font=("Segoe UI", 9), padx=10, pady=6, cursor="hand2",
                  command=lambda: pick("")).pack(side="right")

        win.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width()//2 - win.winfo_width()//2
        py = self.winfo_rooty() + self.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{px}+{py}")
        win.wait_window()

        val = chosen.get()
        return val if val else None

    def _request_cancel(self):
        """Demande l'arrêt des opérations en cours."""
        self._cancel_flag = True
        self._stop_btn.config(state="disabled", text="⏳")
        self._prog_lbl.config(text=_("cancelling"))

    def _do_run(self, ops, mode, dest, collision_action="replace"):
        import shutil
        done = 0; errors = 0; err_list = []; cancelled = False
        for src, dst in ops:
            if self._cancel_flag:
                cancelled = True
                break
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    if collision_action == "skip":
                        done += 1
                        self.after(0, self._update_progress, done, len(ops), errors)
                        continue
                    elif collision_action == "compare_meta":
                        if _files_equal_meta(src, dst):
                            done += 1
                            self.after(0, self._update_progress, done, len(ops), errors)
                            continue
                    elif collision_action == "compare_full":
                        if _files_equal_full(src, dst):
                            done += 1
                            self.after(0, self._update_progress, done, len(ops), errors)
                            continue
                    elif collision_action == "rename":
                        base, ext = os.path.splitext(dst)
                        candidate = base + "-doublon" + ext
                        counter = 1
                        while os.path.exists(candidate):
                            candidate = base + f"-doublon{counter}" + ext
                            counter += 1
                        dst = candidate
                if mode == "copy":
                    shutil.copy2(src, dst)
                else:
                    shutil.move(src, dst)
                done += 1
            except Exception as ex:
                errors += 1
                err_list.append(f"{os.path.basename(src)}: {ex}")
            self.after(0, self._update_progress, done, len(ops), errors)
        self.after(0, self._finish, done, errors, err_list, cancelled)

    def _update_progress(self, done, total, errors):
        self._progress["value"] = done
        self._prog_lbl.config(
            text=_("ops_progress", done=done, total=total)
                 + (_("ops_errors", n=errors) if errors else ""))

    def _finish(self, done, errors, err_list, cancelled=False):
        self._stop_btn.pack_forget()
        self._stop_btn.config(state="normal", text="⏹")
        self._cancel_flag = False
        self._run_btn.config(state="normal")
        verb = _("verb_copied") if self._op_mode.get() == "copy" else _("verb_moved")
        if cancelled:
            msg = _("ops_cancelled", done=done, verb=verb)
            if errors:
                msg += _("ops_cancelled_err", n=errors)
            messagebox.showwarning(_("dlg_cancelled"), msg, parent=self)
            self._status_var.set(_("ops_status_cancel", done=done, verb=verb) +
                                 (_("n_errors_status", n=errors) if errors else ""))
        else:
            msg  = _("ops_done_msg", done=done, verb=verb)
            if errors:
                msg += _("ops_done_err", n=errors) + "\n".join(err_list[:10])
                if len(err_list) > 10: msg += _("n_others", n=len(err_list)-10)
            messagebox.showinfo(_("dlg_done"), msg, parent=self)
            self._status_var.set(_("ops_status_done", done=done, verb=verb) +
                                 (_("n_errors_status", n=errors) if errors else ""))


    def refresh_lang(self):
        """Refreshes all translatable widgets in the Organize tab."""
        for attr, key in [
            ("_lbl_org_title",   "organize_title"),
            ("_lbl_org_hint",    "organize_hint"),
            ("_load_btn",        "load_structure"),
            ("_lbl_load_ext",    "load_ext_hint"),
            ("_btn_check_all",   "check_all"),
            ("_btn_check_none",  "check_none"),
            ("_btn_browse",      "browse"),
            ("_run_btn",         "apply_structure"),
            ("_lbl_ops_preview", "ops_preview"),
        ]:
            w = getattr(self, attr, None)
            if w:
                try: w.config(text=_(key))
                except Exception: pass
        if hasattr(self, "_struct_lbl"):
            try:
                cur = self._struct_lbl.cget("text")
                _ph = ("No structure defined", "Aucune structure définie", "")
                if not cur.strip() or any(cur.startswith(p) for p in _ph):
                    self._struct_lbl.config(text=_("no_structure"))
            except Exception:
                pass
        for rb, key in getattr(self, "_op_radios", []):
            try: rb.config(text=_(key))
            except Exception: pass
        for rb, key in getattr(self, "_dup_radios", []):
            try: rb.config(text=_(key))
            except Exception: pass
        for attr, key in [
            ("_s_struct",          "nodal_structure"),
            ("_s_ext",             "sect_ext"),
            ("_s_op_section",      "op_section"),
            ("_s_summary_section", "summary_section"),
            ("_s_dup",             "dup_section"),
            ("_s_dest",            "sect_dest"),
        ]:
            sec = getattr(self, attr, None)
            if sec:
                for w in sec.winfo_children():
                    if isinstance(w, tk.Label):
                        try: w.config(text=_(key)); break
                        except Exception: pass
        try:
            self._ops_tree.heading("src",    text=_("col_src"))
            self._ops_tree.heading("dst",    text=_("col_dst"))
            self._nomatch_tree.heading("file",   text=_("col_file"))
            self._nomatch_tree.heading("reason", text=_("col_reason"))
        except Exception: pass
        try:
            self._ops_notebook.tab(0, text=_("tab_all_ops"))
            self._ops_notebook.tab(1, text=_("tab_unmatched"))
        except Exception: pass
        try:
            cur_st = self._status_var.get()
            placeholders = (
                "Load a structure from the node editor to begin.",
                "Chargez une structure depuis l\u2019\u00e9diteur nodal pour commencer.",
                "Chargez une structure depuis l'\u00e9diteur nodal pour commencer.",
            )
            if cur_st in placeholders:
                self._status_var.set(_("start_status"))
        except Exception: pass
        self._update_summary()

class FileExplorer(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Strucnode - Statistiques & Organisation Nodale")
        self.geometry("1500x900"); self.minsize(1100,660); self.configure(bg=BG)
        self._cat_files=defaultdict(list); self._active_cat=None; self._active_ext_filter=None
        self._file_rows=[]; self._file_sort_col="name"; self._file_sort_rev=False
        self._filter_widgets={}; self._all_ext_rows=[]; self._ext_sort_col="count"; self._ext_sort_rev=True
        self._current_preview_path=None; self._current_is_360=False
        self._current_is_video=False; self._current_is_raw=False
        self._preview_img=None; self._video_player=None; self._muted=False
        self._indexed = False
        self._summary_card_data: list = []
        self._all_files = []
        self._build_ui()
        self._video_player = VideoPlayer(self.preview_canvas, PREVIEW_W, PREVIEW_H)
        self.protocol("WM_DELETE_WINDOW", self._on_close)


    def _set_language(self, lang: str):
        """Switches the UI language and refreshes all translatable widgets dynamically."""
        global NODE_TYPES
        set_locale(lang)
        NODE_TYPES = _build_node_types()
        if lang == "en":
            self._lang_en_btn.config(relief="sunken", bg=SURFACE2)
            self._lang_fr_btn.config(relief="flat",   bg=SURFACE)
        else:
            self._lang_fr_btn.config(relief="sunken", bg=SURFACE2)
            self._lang_en_btn.config(relief="flat",   bg=SURFACE)
        self.scan_btn.config(text=_("analyze"))
        if hasattr(self, "_btn_choose_folder"):
            self._btn_choose_folder.config(text=_("choose_folder"))
        cur_path = self.path_var.get()
        if not cur_path or cur_path in ("No folder selected",
                                         "Aucun dossier sélectionné",
                                         "Aucun dossier selectionne"):
            self.path_var.set(_("no_folder"))
        cur_st = self.status_var.get()
        if cur_st in ("Ready — choose a folder to begin",
                      "Ready — choose a folder to begin",
                      "Prêt — choisissez un dossier pour commencer",
                      "Prêt — choisissez un dossier pour commencer"):
            self.status_var.set(_("status_ready"))
        for key, lkey in [("explorer","tab_explorer"),
                           ("nodal",   "tab_nodal"),
                           ("organize","tab_organize")]:
            if key in self._tab_btns:
                self._tab_btns[key].config(text=_(lkey))
        self._lock_lbl.config(text=_("available_after") if not self._indexed else "")
        for attr, key in [
            ("_lbl_summary",       "resume"),
            ("_lbl_by_cat",        "by_category"),
            ("_lbl_click_filter",  "click_filter"),
            ("_lbl_detail_ext",    "detail_ext"),
            ("_lbl_preview",       "preview"),
            ("_lbl_metadata",      "metadata"),
            ("_lbl_click_enlarge", "click_enlarge"),
            ("_lbl_filter_name",   "filter_name"),
            ("_lbl_filter_ext",    "filter_ext"),
            ("_btn_reset_filter",  "reset"),
        ]:
            w = getattr(self, attr, None)
            if w:
                try: w.config(text=_(key))
                except Exception: pass
        if hasattr(self, "file_section_lbl"):
            try: self.file_section_lbl.config(text=_("files_select"))
            except Exception: pass
        if hasattr(self, "_summary_card_data") and self._summary_card_data:
            for w in self.summary_frame.winfo_children():
                w.destroy()
            for ck, cv, cc in self._summary_card_data:
                self._card(self.summary_frame, _(ck), cv, cc)
        if hasattr(self, "ext_tree"):
            try:
                self.ext_tree.heading("extension", text=_("col_extension"))
                self.ext_tree.heading("category",  text=_("col_category"))
                self.ext_tree.heading("count",     text=_("col_files"))
                self.ext_tree.heading("size",      text=_("col_total_size"))
                self.ext_tree.heading("percent",   text=_("col_percent"))
            except Exception: pass
        if hasattr(self, "file_tree"):
            try:
                self.file_tree.heading("name",  text=_("col_name"))
                self.file_tree.heading("ext",   text=_("col_extension"))
                self.file_tree.heading("size",  text=_("col_size"))
                self.file_tree.heading("mtime", text=_("col_date"))
            except Exception: pass
            for col,key in [("ISO","col_iso"),("Focale","col_focal"),("Appareil","col_device"),
                             ("Marque","col_brand"),("Ouverture","col_aperture"),
                             ("Exposition","col_exposure")]:
                try: self.file_tree.heading(col, text=_(key))
                except Exception: pass
        if hasattr(self, "_filter_widgets"):
            _old_all = ("All", "Toutes", "Tous")
            for _fk in ("ext", "name"):
                if _fk not in self._filter_widgets:
                    continue
                try:
                    v, cb = self._filter_widgets[_fk]
                    if cb is not None:
                        vals = list(cb["values"])
                        if vals and vals[0] in _old_all:
                            vals[0] = _("filter_all")
                            cb["values"] = vals
                    if v.get() in _old_all:
                        v.set(_("filter_all"))
                except Exception:
                    pass
        try: self.title(_("window_title"))
        except Exception: pass
        if self._nodal_editor and hasattr(self._nodal_editor, "refresh_lang"):
            self._nodal_editor.refresh_lang()
        if hasattr(self, "_organize_tab") and self._organize_tab                 and hasattr(self._organize_tab, "refresh_lang"):
            self._organize_tab.refresh_lang()

    def _on_close(self):
        if self._video_player: self._video_player.stop()
        self.destroy()

    def _build_ui(self):
        self._style()
        topbar=tk.Frame(self,bg=SURFACE,pady=8,padx=16); topbar.pack(fill="x")
        tk.Label(topbar,text="📁",bg=SURFACE,fg=PRIMARY,font=("Segoe UI",18)).pack(side="left")
        tk.Label(topbar, text=_("app_title"),bg=SURFACE,fg=TEXT,font=("Segoe UI",13,"bold")).pack(side="left",padx=(6,20))
        self.path_var=tk.StringVar(value=_("no_folder"))
        tk.Entry(topbar,textvariable=self.path_var,bg=SURFACE2,fg=TEXT,insertbackground=TEXT,
                 relief="flat",font=("Segoe UI",10)).pack(side="left",fill="x",expand=True,ipady=5,padx=(0,8))
        self._btn_choose_folder=tk.Button(topbar,text=_("choose_folder"),bg=PRIMARY,fg="#0f3638",activebackground=PRIMARY_H,
                  activeforeground="#0f3638",relief="flat",font=("Segoe UI",10,"bold"),padx=12,pady=5,
                  cursor="hand2",command=self._pick_folder)
        self._btn_choose_folder.pack(side="left")
        self.scan_btn=tk.Button(topbar,text=_("analyze"),bg=SURFACE2,fg=TEXT,relief="flat",
                                font=("Segoe UI",10),padx=12,pady=5,cursor="hand2",command=self._scan)
        self.scan_btn.pack(side="left",padx=(8,0))
        lang_frame = tk.Frame(topbar, bg=SURFACE)
        lang_frame.pack(side="right", padx=(4, 8))
        self._lang_fr_btn = tk.Button(
            lang_frame, text="🇫🇷", bg=SURFACE, fg=TEXT, relief="flat",
            font=("Segoe UI", 15), cursor="hand2", bd=0,
            activebackground=SURFACE2,
            command=lambda: self._set_language("fr"))
        self._lang_fr_btn.pack(side="right", padx=2)
        self._lang_en_btn = tk.Button(
            lang_frame, text="🇬🇧", bg=SURFACE2, fg=TEXT, relief="sunken",
            font=("Segoe UI", 15), cursor="hand2", bd=0,
            activebackground=SURFACE2,
            command=lambda: self._set_language("en"))
        self._lang_en_btn.pack(side="right", padx=2)
        tab_bar = tk.Frame(self, bg=SURFACE2)
        tab_bar.pack(fill="x")
        self._tab_btns = {}
        self._tab_frames = {}

        for key, label in [("explorer", _("tab_explorer")), ("nodal", _("tab_nodal")), ("organize", _("tab_organize"))]:
            btn = tk.Button(tab_bar, text=label, bg=SURFACE2, fg=MUTED,
                            relief="flat", font=("Segoe UI", 10), padx=12, pady=8,
                            cursor="hand2", activebackground=BG, activeforeground=TEXT,
                            command=lambda k=key: self._switch_tab(k))
            btn.pack(side="left")
            self._tab_btns[key] = btn

        self._lock_lbl = tk.Label(tab_bar,
            text=_("available_after"),
            bg=SURFACE2, fg=MUTED, font=("Segoe UI", 8))
        self._lock_lbl.pack(side="left")
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True)
        exp_frame = tk.Frame(self._content, bg=BG)
        self._tab_frames["explorer"] = exp_frame
        self._build_explorer_tab(exp_frame)
        nod_frame = tk.Frame(self._content, bg=BG)
        self._tab_frames["nodal"] = nod_frame
        self._nodal_editor = None
        org_frame = tk.Frame(self._content, bg=BG)
        self._tab_frames["organize"] = org_frame
        self._organize_tab = None
        self.status_var=tk.StringVar(value=_("status_ready"))
        self.progress=ttk.Progressbar(self,mode="indeterminate",style="Custom.Horizontal.TProgressbar")
        sb=tk.Frame(self,bg=SURFACE,pady=4,padx=14); sb.pack(fill="x",side="bottom")
        tk.Label(sb,textvariable=self.status_var,bg=SURFACE,fg=TEXT,font=("Segoe UI",9)).pack(side="left")

        self._switch_tab("explorer")

    def _switch_tab(self, key):
        if key in ("nodal", "organize") and not self._indexed:
            return
        self._current_tab = key
        for k, f in self._tab_frames.items():
            f.pack_forget()
        self._tab_frames[key].pack(fill="both", expand=True)
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.config(bg=BG, fg=PRIMARY, font=("Segoe UI", 10, "bold"))
            else:
                btn.config(bg=SURFACE2, fg=MUTED, font=("Segoe UI", 10))
        if key == "nodal" and self._nodal_editor is None:
            self._nodal_editor = NodeEditorTab(self._tab_frames["nodal"], lambda: self._all_files)
            self._nodal_editor.pack(fill="both", expand=True)
            self._nodal_editor.refresh_palette()
            self._nodal_editor.refresh_lang()   # apply current locale on first open
        if key == "organize" and self._organize_tab is None:
            self._organize_tab = OrganizeTab(self._tab_frames["organize"],
                                             lambda: self._nodal_editor)
            self._organize_tab.pack(fill="both", expand=True)
            self._organize_tab.refresh_lang()   # apply current locale on first open

    def _unlock_nodal_tab(self):
        self._indexed = True
        self._all_files = []
        for files in self._cat_files.values():
            self._all_files.extend(files)
        self._lock_lbl.config(text="")
        self._tab_btns["nodal"].config(fg=TEXT)
        self._tab_btns["organize"].config(fg=TEXT)
        if self._nodal_editor is not None:
            self._nodal_editor.refresh_palette()

    def _build_explorer_tab(self, parent):
        body=tk.Frame(parent,bg=BG); body.pack(fill="both",expand=True,padx=14,pady=10)
        self.left=tk.Frame(body,bg=BG,width=250); self.left.pack(side="left",fill="y",padx=(0,10))
        self.left.pack_propagate(False)
        self._lbl_summary=tk.Label(self.left,text=_("resume"),bg=BG,fg=MUTED,font=("Segoe UI",9,"bold")); self._lbl_summary.pack(anchor="w",pady=(0,6))
        self.summary_frame=tk.Frame(self.left,bg=BG); self.summary_frame.pack(fill="x")
        self._lbl_by_cat=tk.Label(self.left,text=_("by_category"),bg=BG,fg=MUTED,font=("Segoe UI",9,"bold")); self._lbl_by_cat.pack(anchor="w",pady=(12,2))
        self._lbl_click_filter=tk.Label(self.left,text=_("click_filter"),bg=BG,fg=MUTED,font=("Segoe UI",7)); self._lbl_click_filter.pack(anchor="w",pady=(0,6))
        self.cat_frame=tk.Frame(self.left,bg=BG); self.cat_frame.pack(fill="x")
        center=tk.Frame(body,bg=BG); center.pack(side="left",fill="both",expand=True,padx=(0,10))
        self.paned=tk.PanedWindow(center,orient="vertical",bg=BG,sashwidth=6,sashrelief="flat")
        self.paned.pack(fill="both",expand=True)
        top_fr=tk.Frame(self.paned,bg=BG); self.paned.add(top_fr,minsize=120)
        hdr=tk.Frame(top_fr,bg=BG); hdr.pack(fill="x",pady=(0,5))
        self._lbl_detail_ext=tk.Label(hdr,text=_("detail_ext"),bg=BG,fg=MUTED,font=("Segoe UI",9,"bold")); self._lbl_detail_ext.pack(side="left")
        self.ext_filter_var=tk.StringVar()
        self.ext_filter_var.trace_add("write",lambda *_:self._apply_ext_filter())
        tk.Label(hdr,text="🔍",bg=BG,fg=MUTED,font=("Segoe UI",10)).pack(side="right")
        tk.Entry(hdr,textvariable=self.ext_filter_var,bg=SURFACE2,fg=TEXT,insertbackground=TEXT,
                 relief="flat",font=("Segoe UI",9),width=18).pack(side="right",ipady=3,padx=(0,2))
        ext_tree_fr=tk.Frame(top_fr,bg=SURFACE); ext_tree_fr.pack(fill="both",expand=True)
        cols=("extension","category","count","size","percent")
        self.ext_tree=ttk.Treeview(ext_tree_fr,columns=cols,show="headings",
                                    selectmode="browse",style="Custom.Treeview",cursor="hand2")
        for c,lbl,w in [("extension",_("col_extension"),110),("category",_("col_category"),110),
                         ("count",_("col_files"),80),("size",_("col_total_size"),140),("percent",_("col_percent"),80)]:
            self.ext_tree.heading(c,text=lbl,command=lambda _c=c:self._sort_ext_by(_c))
            self.ext_tree.column(c,width=w,anchor="center" if c in ("count","percent") else "w")
        vsb_e=ttk.Scrollbar(ext_tree_fr,orient="vertical",command=self.ext_tree.yview,style="Dark.Vertical.TScrollbar")
        self.ext_tree.configure(yscrollcommand=vsb_e.set)
        vsb_e.pack(side="right",fill="y"); self.ext_tree.pack(fill="both",expand=True)
        self.ext_tree.bind("<<TreeviewSelect>>",self._on_ext_row_click)

        bot_fr=tk.Frame(self.paned,bg=BG); self.paned.add(bot_fr,minsize=160)
        file_hdr=tk.Frame(bot_fr,bg=BG); file_hdr.pack(fill="x",pady=(6,0))
        self.file_section_lbl=tk.Label(file_hdr,
            text=_("files_select"),
            bg=BG,fg=MUTED,font=("Segoe UI",9,"bold"))
        self.file_section_lbl.pack(side="left")
        self.file_count_lbl=tk.Label(file_hdr,text="",bg=BG,fg=MUTED,font=("Segoe UI",9))
        self.file_count_lbl.pack(side="right")
        self.filter_bar=tk.Frame(bot_fr,bg=SURFACE,padx=10,pady=5)
        self.filter_bar.pack(fill="x",pady=(3,0))
        self._build_filter_bar_base()
        file_tree_fr=tk.Frame(bot_fr,bg=SURFACE)
        file_tree_fr.pack(fill="both",expand=True,pady=(3,0))
        self._file_cols_base=("name","ext","size","mtime")
        self._file_cols_exif=("ISO","Focale","Appareil","Marque","Ouverture","Exposition")
        self._file_cols=self._file_cols_base
        self.file_tree=ttk.Treeview(file_tree_fr,columns=self._file_cols,
                                     show="headings",selectmode="browse",style="Custom.Treeview")
        self._setup_file_tree_cols(self._file_cols)
        vsb_f=ttk.Scrollbar(file_tree_fr,orient="vertical",command=self.file_tree.yview,style="Dark.Vertical.TScrollbar")
        hsb_f=ttk.Scrollbar(file_tree_fr,orient="horizontal",command=self.file_tree.xview,style="Dark.Horizontal.TScrollbar")
        self.file_tree.configure(yscrollcommand=vsb_f.set,xscrollcommand=hsb_f.set)
        vsb_f.pack(side="right",fill="y"); hsb_f.pack(side="bottom",fill="x")
        self.file_tree.pack(fill="both",expand=True)
        self.file_tree.bind("<<TreeviewSelect>>",self._on_file_select)
        self.file_tree.bind("<Double-1>",self._open_selected_file)
        self.path_lbl=tk.Label(bot_fr,text="",bg=SURFACE2,fg=TEXT,font=("Segoe UI",8),anchor="w",padx=8)
        preview_col=tk.Frame(body,bg=BG,width=300)
        preview_col.pack(side="left",fill="y"); preview_col.pack_propagate(False)
        self._lbl_preview=tk.Label(preview_col,text=_("preview"),bg=BG,fg=MUTED,font=("Segoe UI",9,"bold")); self._lbl_preview.pack(anchor="w",pady=(0,4))
        self._badge_360=tk.Label(preview_col,text=" 360 ",bg=ORANGE,fg="#1c1b19",font=("Segoe UI",8,"bold"))
        self._badge_raw=tk.Label(preview_col,text=" RAW ",bg="#5591c7",fg="white",font=("Segoe UI",8,"bold"))
        self.preview_frame=tk.Frame(preview_col,bg=SURFACE,width=PREVIEW_W,height=PREVIEW_H)
        self.preview_frame.pack(fill="x"); self.preview_frame.pack_propagate(False)
        self.preview_canvas=tk.Canvas(self.preview_frame,bg=SURFACE,highlightthickness=0,
                                       width=PREVIEW_W,height=PREVIEW_H)
        self.preview_canvas.pack(fill="both",expand=True)
        self._draw_preview_placeholder()
        self._video_ctrl_frame=tk.Frame(preview_col,bg=SURFACE2)
        self._seek_var=tk.DoubleVar(value=0.0)
        ttk.Scale(self._video_ctrl_frame,from_=0,to=1,orient="horizontal",variable=self._seek_var,
                  command=self._on_seek,style="Video.Horizontal.TScale").pack(fill="x",padx=8,pady=(4,2))
        ctrl_row=tk.Frame(self._video_ctrl_frame,bg=SURFACE2); ctrl_row.pack(fill="x",padx=8,pady=(0,4))
        self._play_btn=tk.Button(ctrl_row,text="\u25b6",bg="#dd6974",fg="white",relief="flat",
                                  font=("Segoe UI",12,"bold"),width=3,cursor="hand2",
                                  activebackground="#b94a57",activeforeground="white",
                                  command=self._toggle_play)
        self._play_btn.pack(side="left",padx=(0,4))
        self._mute_btn=tk.Button(ctrl_row,text="\U0001f50a",bg=SURFACE2,fg=TEXT,relief="flat",
                                  font=("Segoe UI",11),cursor="hand2",activebackground=BORDER,
                                  activeforeground=TEXT,command=self._toggle_mute)
        self._mute_btn.pack(side="left",padx=(0,2))
        self._vol_var=tk.DoubleVar(value=1.0)
        ttk.Scale(ctrl_row,from_=0,to=1,orient="horizontal",variable=self._vol_var,
                  command=self._on_volume,style="Video.Horizontal.TScale",length=52).pack(side="left",padx=(0,6))
        self._time_lbl=tk.Label(ctrl_row,text="0:00 / 0:00",bg=SURFACE2,fg=MUTED,font=("Segoe UI",8))
        self._time_lbl.pack(side="left")
        tk.Button(ctrl_row,text="\u26f6",bg=SURFACE2,fg=TEXT,relief="flat",font=("Segoe UI",11),
                  padx=4,cursor="hand2",activebackground=BORDER,
                  command=self._open_video_fullscreen).pack(side="right")
        self._update_seek_bar()

        self._lbl_click_enlarge=tk.Label(preview_col,text=_("click_enlarge"),bg=BG,fg=MUTED,font=("Segoe UI",7))
        self.preview_canvas.bind("<Button-1>",self._on_preview_click)

        self._lbl_metadata=tk.Label(preview_col,text=_("metadata"),bg=BG,fg=MUTED,font=("Segoe UI",9,"bold")); self._lbl_metadata.pack(anchor="w",pady=(6,4))
        meta_wrap=tk.Frame(preview_col,bg=SURFACE); meta_wrap.pack(fill="both",expand=True)
        mc=tk.Canvas(meta_wrap,bg=SURFACE,highlightthickness=0)
        ms=ttk.Scrollbar(meta_wrap,orient="vertical",command=mc.yview,style="Dark.Vertical.TScrollbar")
        self.meta_inner=tk.Frame(mc,bg=SURFACE)
        self.meta_inner.bind("<Configure>",lambda e:mc.configure(scrollregion=mc.bbox("all")))
        mc.create_window((0,0),window=self.meta_inner,anchor="nw"); mc.configure(yscrollcommand=ms.set)
        ms.pack(side="right",fill="y"); mc.pack(side="left",fill="both",expand=True)
        self._show_meta({})
    def _toggle_play(self):
        if self._video_player: self._video_player.toggle()

    def _toggle_mute(self):
        self._muted = not self._muted
        if self._video_player: self._video_player.set_muted(self._muted)
        self._mute_btn.config(text="\U0001f507" if self._muted else "\U0001f50a",
                              fg="#dd6974" if self._muted else TEXT)

    def _on_volume(self, val):
        v = float(val)
        if self._video_player: self._video_player.set_volume(v)
        if v == 0: self._muted=True; self._mute_btn.config(text="\U0001f507",fg="#dd6974")
        elif self._muted:
            self._muted=False
            if self._video_player: self._video_player.set_muted(False)
            self._mute_btn.config(text="\U0001f50a",fg=TEXT)

    def _on_video_state(self, playing):
        self._play_btn.config(text="\u23f8" if playing else "\u25b6",
                              bg=SUCCESS if playing else "#dd6974")

    def _on_seek(self, val):
        if self._video_player: self._video_player.seek(float(val))

    def _update_seek_bar(self):
        if self._video_player and self._current_is_video:
            try:
                self._seek_var.set(self._video_player.progress)
                self._time_lbl.config(text=self._video_player.time_str)
            except Exception: pass
        self.after(200, self._update_seek_bar)

    def _open_video_fullscreen(self):
        if not self._current_preview_path: return
        if self._video_player: self._video_player.pause()
        FullscreenVideoPlayer(self, self._current_preview_path)
    def _draw_preview_placeholder(self):
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(PREVIEW_W//2, PREVIEW_H//2,
            text=_("select_file"), fill=MUTED, font=("Segoe UI",11), justify="center")

    def _show_preview(self, filepath):
        if self._video_player: self._video_player.stop()
        ext=Path(filepath).suffix.lower()
        self.preview_canvas.delete("all")
        self._badge_360.pack_forget(); self._badge_raw.pack_forget()
        self._lbl_click_enlarge.pack_forget(); self._video_ctrl_frame.pack_forget()
        self._current_is_360=False; self._current_is_video=False; self._current_is_raw=False

        if ext in RAW_EXTS:
            self._current_is_raw=True
            self._badge_raw.pack(anchor="center",pady=(0,2))
            self._lbl_click_enlarge.pack(anchor="center",pady=(0,4))
            self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2-15,text="\u23f3",fill=MUTED,font=("Segoe UI",28))
            self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2+25,text=_("decoding_raw"),fill=MUTED,font=("Segoe UI",9))
            threading.Thread(target=self._load_raw_preview,args=(filepath,),daemon=True).start()
            return

        if ext in IMAGE_EXTS:
            try:
                from PIL import Image, ImageTk
                img=Image.open(filepath); self._current_is_360=is_360_image(filepath)
                img.thumbnail((PREVIEW_W-4,PREVIEW_H-4),Image.LANCZOS)
                self._preview_img=ImageTk.PhotoImage(img); tw,th=img.size
                self.preview_canvas.create_image((PREVIEW_W-tw)//2,(PREVIEW_H-th)//2,anchor="nw",image=self._preview_img)
                if self._current_is_360: self._badge_360.pack(anchor="center",pady=(0,2))
                self._lbl_click_enlarge.pack(anchor="center",pady=(0,4)); return
            except Exception: pass

        if ext in VIDEO_EXTS:
            self._current_is_video=True
            self._video_ctrl_frame.pack(fill="x",pady=(0,4))
            self._play_btn.config(text="\u25b6",bg="#dd6974")
            self._seek_var.set(0.0); self._time_lbl.config(text="0:00 / 0:00")
            self._muted=False; self._mute_btn.config(text="\U0001f50a",fg=TEXT); self._vol_var.set(1.0)
            self._video_player.load(filepath,on_state_change=self._on_video_state)
            return

        icons={"audio":("\U0001f3b5","#6daa45"),"code":("\u2328","#4f98a3"),"docs":("\U0001f4c4","#a86fdf"),
               "data":("\U0001f4ca","#5591c7"),"archives":("\U0001f4e6","#bb653b"),"other":("\U0001f4ce","#797876")}
        cat=get_category(ext); icon,color=icons.get(cat,("\U0001f4c4",MUTED))
        self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2-20,text=icon,fill=color,font=("Segoe UI",48))
        self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2+30,text=ext.upper() if ext else "?",fill=color,font=("Segoe UI",14,"bold"))

    def _load_raw_preview(self, filepath):
        img = open_raw_thumbnail(filepath)
        if img:
            from PIL import ImageTk
            img.thumbnail((PREVIEW_W-4,PREVIEW_H-4))
            tk_img = ImageTk.PhotoImage(img)
            def show():
                self._preview_img=tk_img; self.preview_canvas.delete("all")
                tw,th=img.size; self.preview_canvas.create_image((PREVIEW_W-tw)//2,(PREVIEW_H-th)//2,anchor="nw",image=self._preview_img)
            self.after(0,show)
        else:
            def show_err():
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2-15,text="\U0001f39e",fill="#5591c7",font=("Segoe UI",30))
                self.preview_canvas.create_text(PREVIEW_W//2,PREVIEW_H//2+20,
                    text=_("rawpy_required"),fill=MUTED,font=("Segoe UI",8),justify="center")
            self.after(0,show_err)

    def _on_preview_click(self, event=None):
        print("[ORGANIZE] _on_preview_click triggered")
        path=self._current_preview_path
        if not path: return
        ext=Path(path).suffix.lower()
        if ext in RAW_EXTS or ext in IMAGE_EXTS:
            if self._current_is_360: Viewer360(self,path)
            else: FullscreenViewer(self,path)
        elif ext in VIDEO_EXTS:
            self._toggle_play()

    def _show_meta(self, info):
        for w in self.meta_inner.winfo_children(): w.destroy()
        if not info:
            tk.Label(self.meta_inner,text=_("no_metadata"),bg=SURFACE,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w",padx=8,pady=4); return
        for key,val in info.items():
            row=tk.Frame(self.meta_inner,bg=SURFACE); row.pack(fill="x",padx=6,pady=1)
            tk.Label(row,text=key,bg=SURFACE,fg=MUTED,font=("Segoe UI",8),width=14,anchor="w").pack(side="left")
            tk.Label(row,text=str(val),bg=SURFACE,fg=TEXT,font=("Segoe UI",8),anchor="w",wraplength=155).pack(side="left",fill="x",expand=True)
    def _setup_file_tree_cols(self,cols):
        hdrs={"name":"Nom","ext":"Extension","size":"Taille","mtime":"Modifie le",
              "ISO":"ISO","Focale":"Focale","Appareil":"Appareil","Marque":"Marque",
              "Ouverture":"Ouverture","Exposition":"Exposition"}
        widths={"name":250,"ext":75,"size":85,"mtime":125,"ISO":60,"Focale":80,
                "Appareil":140,"Marque":100,"Ouverture":75,"Exposition":85}
        self.file_tree.configure(columns=cols)
        for c in cols:
            self.file_tree.heading(c,text=hdrs.get(c,c),command=lambda _c=c:self._sort_files_by(_c))
            self.file_tree.column(c,width=widths.get(c,100),anchor="w" if c=="name" else "center")

    def _build_filter_bar_base(self):
        for w in self.filter_bar.winfo_children(): w.destroy()
        self._filter_widgets={}
        self._lbl_filter_name=tk.Label(self.filter_bar,text=_("filter_name"),bg=SURFACE,fg=MUTED,font=("Segoe UI",9)); self._lbl_filter_name.pack(side="left")
        v=tk.StringVar(); v.trace_add("write",lambda *_:self._apply_file_filter())
        tk.Entry(self.filter_bar,textvariable=v,bg=SURFACE2,fg=TEXT,insertbackground=TEXT,
                 relief="flat",font=("Segoe UI",9),width=14).pack(side="left",ipady=3,padx=(3,12))
        self._filter_widgets["name"]=(v,None)
        self._lbl_filter_ext=tk.Label(self.filter_bar,text=_("filter_ext"),bg=SURFACE,fg=MUTED,font=("Segoe UI",9)); self._lbl_filter_ext.pack(side="left")
        v2=tk.StringVar(value=_("filter_all"))
        cb=ttk.Combobox(self.filter_bar,textvariable=v2,values=["Toutes"],width=10,state="readonly",font=("Segoe UI",9))
        cb.pack(side="left",padx=(3,12)); cb.bind("<<ComboboxSelected>>",lambda *_:self._apply_file_filter())
        self._filter_widgets["ext"]=(v2,cb)
        self._exif_lbl=tk.Label(self.filter_bar,text="",bg=SURFACE,fg=ORANGE,font=("Segoe UI",8))
        self._exif_lbl.pack(side="right",padx=(0,6))
        self._btn_reset_filter=tk.Button(self.filter_bar,text=_("reset"),bg=SURFACE2,fg=MUTED,relief="flat",
                  font=("Segoe UI",8),padx=6,pady=2,cursor="hand2",
                  command=self._reset_file_filters)
        self._btn_reset_filter.pack(side="right")

    def _add_exif_filters(self):
        for key,lbl in [("ISO","ISO :"),("Focale","Focale :"),("Appareil","Appareil :"),("Ouverture","Ouv. :")]:
            tk.Label(self.filter_bar,text=lbl,bg=SURFACE,fg=MUTED,font=("Segoe UI",9)).pack(side="left")
            v=tk.StringVar(value=_("filter_all2"))
            cb=ttk.Combobox(self.filter_bar,textvariable=v,values=["Tous"],width=10,state="readonly",font=("Segoe UI",9))
            cb.pack(side="left",padx=(3,10)); cb.bind("<<ComboboxSelected>>",lambda *_:self._apply_file_filter())
            self._filter_widgets[key]=(v,cb)

    def _populate_exif_combos(self):
        for key in ("ISO","Focale","Appareil","Ouverture"):
            if key not in self._filter_widgets: continue
            vals=sorted({f["meta"].get(key,"") for f in self._file_rows if f.get("meta",{}).get(key)})
            self._filter_widgets[key][1]["values"]=["Tous"]+vals

    def _reset_file_filters(self):
        for key,(v,w) in self._filter_widgets.items():
            v.set("Toutes" if key=="ext" else ("" if key=="name" else "Tous"))
        self._apply_file_filter()

    def _style(self):
        s=ttk.Style(self); s.theme_use("default")
        s.configure("Custom.Treeview",background=SURFACE,fieldbackground=SURFACE,foreground=TEXT,
                    bordercolor=BORDER,rowheight=26,font=("Segoe UI",9))
        s.configure("Custom.Treeview.Heading",background=SURFACE2,foreground=MUTED,
                    font=("Segoe UI",9,"bold"),relief="flat",borderwidth=0)
        s.map("Custom.Treeview",background=[("selected",PRIMARY_H)],foreground=[("selected","#0f3638")])
        s.configure("Custom.Horizontal.TProgressbar",troughcolor=SURFACE2,background=PRIMARY,bordercolor=BORDER)
        s.configure("Video.Horizontal.TScale",background=SURFACE2,troughcolor=BORDER,sliderlength=12,sliderrelief="flat")
        s.configure("Dark.Vertical.TScrollbar",
            background=SURFACE2, troughcolor=SURFACE,
            bordercolor=SURFACE, arrowcolor=MUTED,
            relief="flat", borderwidth=0)
        s.map("Dark.Vertical.TScrollbar",
            background=[("active", BORDER), ("pressed", PRIMARY_H)],
            arrowcolor=[("active", TEXT)])
        s.configure("Dark.Horizontal.TScrollbar",
            background=SURFACE2, troughcolor=SURFACE,
            bordercolor=SURFACE, arrowcolor=MUTED,
            relief="flat", borderwidth=0)
        s.map("Dark.Horizontal.TScrollbar",
            background=[("active", BORDER), ("pressed", PRIMARY_H)],
            arrowcolor=[("active", TEXT)])

    def _pick_folder(self):
        folder=filedialog.askdirectory(title=_("choose_folder"))
        if folder:
            self.path_var.set(folder)
            self._lock_tabs()
            self._scan()

    def _lock_tabs(self):
        self._indexed = False
        self._all_files = []
        self._cat_files = defaultdict(list)
        self._lock_lbl.config(text=_("indexing"))
        self._tab_btns["nodal"].config(fg=MUTED)
        self._tab_btns["organize"].config(fg=MUTED)
        current = getattr(self, "_current_tab", "explorer")
        if current in ("nodal", "organize"):
            self._switch_tab("explorer")

    def _scan(self):
        folder=self.path_var.get()
        if not folder or folder==_("no_folder"):
            messagebox.showwarning(_("dlg_warning"), _("need_folder")); return
        if not os.path.isdir(folder):
            messagebox.showerror(_("error"), _("dlg_folder_missing", folder=folder)); return
        if self._video_player: self._video_player.stop()
        self.scan_btn.configure(state="disabled")
        self.progress.pack(fill="x",side="bottom",before=self.winfo_children()[-1])
        self.progress.start(10); self.status_var.set("Demarrage de l'analyse...")
        self._active_cat=None; self._active_ext_filter=None; self._file_rows=[]; self._clear_file_panel()
        threading.Thread(target=self._do_scan,args=(folder,),daemon=True).start()

    def _do_scan(self,folder):
        ext_count=defaultdict(int); ext_size=defaultdict(int); cat_files=defaultdict(list)
        total_files=total_dirs=total_size=errors=0; _last=[0]
        for root,dirs,files in os.walk(folder):
            total_dirs+=len(dirs)
            for fname in files:
                fpath=os.path.join(root,fname); ext=Path(fname).suffix.lower() or "(sans extension)"
                try: st=os.stat(fpath); size=st.st_size; mtime=st.st_mtime
                except OSError as _e: errors+=1; size=0; mtime=0; print(f"[SCAN][OSError] {fpath!r}: {_e}")
                ext_count[ext]+=1; ext_size[ext]+=size; total_files+=1; total_size+=size
                cat=get_category(ext)
                try:
                    mdt=datetime.datetime.fromtimestamp(mtime) if mtime else None
                except (OSError, OverflowError, ValueError):
                    mdt=None
                cat_files[cat].append({"path":fpath,"name":fname,"ext":ext,
                    "size":fmt_size(size),"size_bytes":size,
                    "mtime":mdt.strftime("%d/%m/%Y %H:%M") if mdt else "","mtime_ts":mtime,"meta":{}})
                if total_files-_last[0]>=200:
                    _last[0]=total_files; sf,ss=total_files,total_size
                    self.after(0,lambda f=sf,s=ss:self.status_var.set(_("status_files", f=f, size=fmt_size(s))))
        self._cat_files=cat_files
        self.after(0,self._display_results,ext_count,ext_size,total_files,total_dirs,total_size,errors)


    def _display_results(self,ext_count,ext_size,total_files,total_dirs,total_size,errors):
        self.progress.stop(); self.progress.pack_forget(); self.scan_btn.configure(state="normal")
        self.status_var.set(
            _("status_scan", files=total_files, dirs=total_dirs, size=fmt_size(total_size))
            + (_("status_errors", n=errors) if errors else ""))
        self._unlock_nodal_tab()
        for w in self.summary_frame.winfo_children(): w.destroy()
        self._summary_card_data = [
            ("card_files",      f"{total_files:,}",    PRIMARY),
            ("card_subfolders", f"{total_dirs:,}",     ORANGE),
            ("card_total_size", fmt_size(total_size),  SUCCESS),
            ("card_extensions", f"{len(ext_count):,}", PURPLE),
        ]
        for _ck,_cv,_cc in self._summary_card_data:
            self._card(self.summary_frame, _(_ck), _cv, _cc)
        for w in self.cat_frame.winfo_children(): w.destroy()
        cat_counts=defaultdict(int); cat_sizes=defaultdict(int)
        for ext,cnt in ext_count.items():
            cat=get_category(ext); cat_counts[cat]+=cnt; cat_sizes[cat]+=ext_size[ext]
        for cat,cnt in sorted(cat_counts.items(),key=lambda x:-x[1]):
            self._cat_bar(self.cat_frame,cat,cnt,total_files,EXTENSION_COLORS.get(cat,MUTED),cat_sizes[cat])
        self._all_ext_rows=[]
        for ext,cnt in ext_count.items():
            sz=ext_size[ext]; pct=(cnt/total_files*100) if total_files else 0
            self._all_ext_rows.append((ext,get_category(ext),cnt,sz,pct))
        self._apply_ext_filter()

    def _card(self,parent,label,value,color):
        f=tk.Frame(parent,bg=SURFACE,pady=7,padx=10); f.pack(fill="x",pady=(0,5))
        tk.Label(f,text=label,bg=SURFACE,fg=MUTED,font=("Segoe UI",8)).pack(anchor="w")
        tk.Label(f,text=value,bg=SURFACE,fg=color,font=("Segoe UI",14,"bold")).pack(anchor="w")

    def _cat_bar(self,parent,cat,count,total,color,cat_size=0):
        f=tk.Frame(parent,bg=SURFACE,pady=4,padx=8,cursor="hand2"); f.pack(fill="x",pady=(0,4))
        row=tk.Frame(f,bg=SURFACE); row.pack(fill="x")
        tk.Label(row,text="●",bg=SURFACE,fg=color,font=("Segoe UI",9)).pack(side="left")
        lbl=tk.Label(row,text=f" {cat.capitalize()}",bg=SURFACE,fg=TEXT,font=("Segoe UI",9)); lbl.pack(side="left")
        cnt_lbl=tk.Label(row,text=f"{count:,}  •  {fmt_size(cat_size)}",bg=SURFACE,fg=color,font=("Segoe UI",9,"bold")); cnt_lbl.pack(side="right")
        bar_bg=tk.Frame(f,bg=SURFACE2,height=3); bar_bg.pack(fill="x",pady=(2,0))
        bar_bg.update_idletasks(); fill_w=max(4,int(bar_bg.winfo_width()*(count/total if total else 0)))
        tk.Frame(bar_bg,bg=color,height=3,width=fill_w).place(x=0,y=0)
        def on_enter(e):
            for w in (f,row,bar_bg,lbl,cnt_lbl)+tuple(row.winfo_children()):
                try: w.configure(bg=SURFACE2)
                except: pass
        def on_leave(e):
            for w in (f,row,bar_bg,lbl,cnt_lbl)+tuple(row.winfo_children()):
                try: w.configure(bg=SURFACE)
                except: pass
        for w in (f,row,bar_bg,lbl,cnt_lbl)+tuple(row.winfo_children()):
            w.bind("<Enter>",on_enter); w.bind("<Leave>",on_leave)
            w.bind("<Button-1>",lambda e,c=cat:self._load_category(c,ext_filter=None))

    def _on_ext_row_click(self,event):
        sel=self.ext_tree.selection()
        if not sel: return
        vals=self.ext_tree.item(sel[0],"values")
        if vals: self._load_category(get_category(vals[0]),ext_filter=vals[0])

    def _load_category(self,cat,ext_filter=None):
        self._active_cat=cat; self._active_ext_filter=ext_filter
        files=self._cat_files.get(cat,[]); self._file_rows=files
        color=EXTENSION_COLORS.get(cat,MUTED)
        label=cat.capitalize()+(f"  /  {ext_filter}" if ext_filter else "")
        self.file_section_lbl.config(text=_("files_section", label=label), fg=color)
        is_img=(cat=="images")
        new_cols=self._file_cols_base+(self._file_cols_exif if is_img else ())
        self._file_cols=new_cols; self._setup_file_tree_cols(new_cols)
        self._build_filter_bar_base()
        if is_img: self._add_exif_filters()
        exts=sorted({f["ext"] for f in files})
        v,cb=self._filter_widgets["ext"]; cb["values"]=["Toutes"]+exts
        v.set(ext_filter if (ext_filter and ext_filter in exts) else "Toutes")
        self._apply_file_filter()
        if is_img:
            self._exif_lbl.config(text=_("reading_exif"))
            threading.Thread(target=self._load_exif_bg,daemon=True).start()

    def _load_exif_bg(self):
        for f in self._file_rows:
            if not f["meta"]: f["meta"]=read_exif(f["path"])
        self.after(0,self._on_exif_loaded)

    def _on_exif_loaded(self): self._exif_lbl.config(text=""); self._populate_exif_combos(); self._apply_file_filter()

    def _translate_category_label(self, cat):
        raw = str(cat).strip().lower()
        key = f"cat_{raw}"
        if key in _STRINGS:
            return _(key)
        fallback = {
            "images": {"en": "Images", "fr": "Images"},
            "videos": {"en": "Videos", "fr": "Vidéos"},
            "audio": {"en": "Audio", "fr": "Audio"},
            "code": {"en": "Code", "fr": "Code"},
            "docs": {"en": "Documents", "fr": "Documents"},
            "data": {"en": "Data", "fr": "Données"},
            "archives": {"en": "Archives", "fr": "Archives"},
            "other": {"en": "Other", "fr": "Autres"},
        }
        if raw in fallback:
            return fallback[raw].get(_LOCALE, fallback[raw]["en"])
        return raw.capitalize()

    def _render_summary_cards(self):
        if not hasattr(self, 'summaryframe'):
            return
        try:
            for w in self.summaryframe.winfo_children():
                w.destroy()
        except Exception:
            return
        for item in (getattr(self, 'summarycarddata', None) or []):
            try:
                if isinstance(item, dict):
                    ck = item.get('key', '')
                    raw_value = item.get('value', '')
                    color = item.get('color', MUTED)
                    kind = item.get('kind')
                elif len(item) >= 4:
                    ck, raw_value, color, kind = item[:4]
                elif len(item) == 3:
                    ck, raw_value, color = item
                    kind = None
                else:
                    continue
                display_value = raw_value
                if kind == 'size':
                    try:
                        display_value = fmt_size(float(raw_value))
                    except Exception:
                        pass
                elif kind == 'count':
                    try:
                        display_value = f"{int(raw_value):,}"
                    except Exception:
                        pass
                self.card(self.summaryframe, ck, display_value, color)
            except Exception:
                continue

    def _render_category_bars(self):
        if not hasattr(self, 'catsframe'):
            return
        try:
            for w in self.catsframe.winfo_children():
                w.destroy()
        except Exception:
            return
        data = getattr(self, '_category_render_data', None) or []
        for item in data:
            try:
                cat, count, total, color, catsize = item
                self.catbar(self.catsframe, self._translate_category_label(cat), count, total, color, catsize)
            except Exception:
                continue

    def _refresh_scan_status_text(self):
        if not hasattr(self, 'statusvar'):
            return
        stats = getattr(self, '_last_scan_stats', None)
        if not stats:
            return
        try:
            msg = _('status_scan', files=int(stats.get('files', 0)), dirs=int(stats.get('dirs', 0)), size=fmt_size(float(stats.get('size', 0))))
            err = int(stats.get('errors', 0) or 0)
            if err:
                msg += _('status_errors', n=err)
            self.statusvar.set(msg)
        except Exception:
            pass

    def _refresh_dynamic_texts_after_locale(self):
        for fn_name in ('_render_summary_cards', '_render_category_bars', '_refresh_scan_status_text'):
            try:
                getattr(self, fn_name)()
            except Exception:
                pass

    def _clear_file_panel(self):
        self.file_section_lbl.config(text=_("files_select"),fg=MUTED)
        self.file_count_lbl.config(text=""); self.file_tree.delete(*self.file_tree.get_children())
        self.path_lbl.pack_forget(); self._draw_preview_placeholder(); self._show_meta({})
        self._badge_360.pack_forget(); self._badge_raw.pack_forget()
        self._lbl_click_enlarge.pack_forget(); self._video_ctrl_frame.pack_forget(); self._current_preview_path=None

    def _apply_file_filter(self):
        name_q=self._filter_widgets["name"][0].get().lower().strip() if "name" in self._filter_widgets else ""
        ext_q=self._filter_widgets["ext"][0].get() if "ext" in self._filter_widgets else "Toutes"
        exif_keys=("ISO","Focale","Appareil","Ouverture")
        exif_f={k:self._filter_widgets[k][0].get() for k in exif_keys if k in self._filter_widgets}
        rows=[]
        for f in self._file_rows:
            if name_q and name_q not in f["name"].lower(): continue
            if ext_q!="Toutes" and f["ext"]!=ext_q: continue
            if any(v!="Tous" and f.get("meta",{}).get(k,"")!=v for k,v in exif_f.items()): continue
            rows.append(f)
        rev=self._file_sort_rev; col=self._file_sort_col
        if col=="size":        rows.sort(key=lambda x:x["size_bytes"],reverse=rev)
        elif col=="mtime":     rows.sort(key=lambda x:x["mtime_ts"],reverse=rev)
        elif col in exif_keys: rows.sort(key=lambda x:x.get("meta",{}).get(col,""),reverse=rev)
        else:                  rows.sort(key=lambda x:x.get(col,"").lower(),reverse=rev)
        self.file_tree.delete(*self.file_tree.get_children())
        for f in rows:
            meta=f.get("meta",{})
            vals=(f["name"],f["ext"],f["size"],f["mtime"])
            if self._active_cat=="images":
                vals+=(meta.get("ISO",""),meta.get("Focale",""),meta.get("Appareil",""),meta.get("Marque",""),meta.get("Ouverture",""),meta.get("Exposition",""))
            self.file_tree.insert("","end",iid=f["path"],values=vals)
        color=EXTENSION_COLORS.get(self._active_cat,MUTED); n=len(rows); t=len(self._file_rows)
        self.file_count_lbl.config(text=_("files_count", n=n, t=t), fg=color if n<t else MUTED)

    def _sort_files_by(self,col):
        self._file_sort_rev=not self._file_sort_rev if self._file_sort_col==col else False
        self._file_sort_col=col; self._apply_file_filter()

    def _apply_ext_filter(self):
        q=self.ext_filter_var.get().lower().strip()
        rows=[r for r in self._all_ext_rows if not q or q in r[0].lower() or q in r[1].lower()]
        ci={"extension":0,"category":1,"count":2,"size":3,"percent":4}
        rows.sort(key=lambda r:r[ci[self._ext_sort_col]],reverse=self._ext_sort_rev)
        self.ext_tree.delete(*self.ext_tree.get_children())
        for ext,cat,cnt,sz,pct in rows:
            tag=f"c_{cat}"
            self.ext_tree.insert("","end",iid=f"{ext}||{cat}",
                values=(ext,cat.capitalize(),f"{cnt:,}",fmt_size(sz),f"{pct:.1f}%"),tags=(tag,))
            self.ext_tree.tag_configure(tag,foreground=EXTENSION_COLORS.get(cat,MUTED))

    def _sort_ext_by(self,col):
        self._ext_sort_rev=not self._ext_sort_rev if self._ext_sort_col==col else True
        self._ext_sort_col=col; self._apply_ext_filter()

    def _on_file_select(self,event):
        sel=self.file_tree.selection()
        if not sel: return
        path=sel[0]; self._current_preview_path=path
        self.path_lbl.config(text=f"  {path}"); self.path_lbl.pack(fill="x",side="bottom")
        self._show_preview(path)
        f_info=next((f for f in self._file_rows if f["path"]==path),None)
        if f_info:
            meta=f_info.get("meta",{}) or {}
            info={"Nom":f_info["name"],"Taille":f_info["size"],"Modifié":f_info["mtime"],"Type":f_info["ext"].upper()}
            if self._current_is_360: info["360°"]="Oui (équirectangulaire)"
            if self._current_is_raw: info["Format"]="RAW"
            info.update(meta); self._show_meta(info)

    def _open_selected_file(self,event):
        sel=self.file_tree.selection()
        if not sel: return
        open_file(sel[0],self)

if __name__ == "__main__":
    app = FileExplorer()
    app.mainloop()



