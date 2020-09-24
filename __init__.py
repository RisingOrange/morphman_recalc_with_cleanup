import importlib
from itertools import chain

from aqt import mw
from aqt.utils import tooltip, showText
from PyQt5.QtWidgets import *


mm_tag = 'morphman'

# cards that match these queries will be deleted
queries = [
    f'"tag:{mm_tag}" is:new tag:mm_comprehension',
    f'"tag:{mm_tag}" is:new tag:mm_fresh',
    f'"tag:{mm_tag}" tag:mm_tooShort',
    f'"tag:{mm_tag}" is:suspended',
]

# for fixing name mismatch between media filenames and filenames on notes
movies2anki_for_mmm_note_type_id = 1598115874278


addon_name = "Morphman Recalc with Cleanup"

def setup_toolbar_menu():
    # Add "Post-Morphman cleanup" submenu
    morphman_cleanup_menu = QMenu(addon_name, mw)
    mw.form.menuTools.addMenu(morphman_cleanup_menu)

    # Add "Run" button
    a = QAction('&Run', mw)
    a.triggered.connect(morphman_recalc_with_cleanup_action)
    morphman_cleanup_menu.addAction(a)

    # Add "Just clean up" button
    a = QAction('&Just clean up', mw)
    a.triggered.connect(just_cleanup_action)
    morphman_cleanup_menu.addAction(a)    

def morphman_recalc_with_cleanup_action():
    run_mm_recalc()
    note_ids = cleanup()
    fix_movies2anki_name_mismatch()
    mw.reset()
    
    tooltip(f"Deleted {len(note_ids)} notes")

def just_cleanup_action():
    note_ids = cleanup()
    mw.reset()

def run_mm_recalc():
    mm_main = importlib.import_module('morphman_dev.morph.main')
    mm_main.main()

def cleanup():
    note_ids_from_queries = remove_query_matches()
    note_ids_from_duplicates = remove_unnecessary_duplicates()
    return note_ids_from_queries + note_ids_from_duplicates

def remove_query_matches():
    note_ids = set(chain(*[
        mw.col.find_notes(query)
        for query in queries
    ]))
    mw.col.remNotes(note_ids)
    return list(note_ids)

def remove_unnecessary_duplicates():

    def notes_with_morph_ids(morph, new=False):
        return mw.col.find_notes(f'"tag:{mm_tag}" "TargetMorph:{morph}" {"is:new" if new else ""}')

    notes_to_remove = []
    notes_to_process = set(mw.col.find_notes(f'"tag{mm_tag}": TargetMorph:_* edited:2'))
    while notes_to_process:
        cur_note = next(iter(notes_to_process))
        cur_morph = mw.col.getNote(cur_note)['TargetMorph']

        notes_with_cur_morph = set(notes_with_morph_ids(cur_morph))
        new_notes_with_cur_morph = set(notes_with_morph_ids(cur_morph, new=True))
        if len(notes_with_cur_morph) == len(new_notes_with_cur_morph):
            # if all notes are new, pick random note to keep, delete others
            note_to_keep = next(iter(new_notes_with_cur_morph))
            notes_to_remove.extend(new_notes_with_cur_morph - set([note_to_keep]))
        else:
            # else, delete all new ones
            notes_to_remove.extend(new_notes_with_cur_morph)
        
        notes_to_process.difference_update(notes_with_cur_morph)

    if notes_to_remove:
        showText('\n'.join(
            mw.col.getNote(note)['TargetMorph']
            for note in notes_to_remove
        ))
        mw.col.remNotes(notes_to_remove)
        
    return notes_to_remove

def fix_movies2anki_name_mismatch():

    def extract_file_name(line):
        return line[len('[sound:') : -1]

    note_ids = mw.col.find_notes(f'mid:"{movies2anki_for_mmm_note_type_id}"')
    for note in [ mw.col.getNote(id_) for id_ in note_ids ]:
        new_audio_file_name = extract_file_name(note['Audio Sound'])
        note['Audio'] = new_audio_file_name

        new_video_file_name = extract_file_name(note['Video Sound'])
        note['Video'] = new_video_file_name

        note.flush()


setup_toolbar_menu()