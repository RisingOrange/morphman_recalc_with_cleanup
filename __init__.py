import importlib
from itertools import chain

from aqt import mw
from aqt.utils import tooltip
from PyQt5.QtWidgets import *

# cards that match these queries will be deleted
queries = [
    'tag:morphman is:new tag:mm_comprehension',
    'tag:morphman is:new tag:mm_fresh',
    'tag:morphman tag:mm_tooShort',
    'tag:morphman is:suspended',
]

movies2anki_for_mmm_note_type_id = 1598115874278

addon_name = "Morphman Recalc with Cleanup"

def setup_toolbar_menu():
    # Add "Post-Morphman cleanup" submenu
    morphman_cleanup_menu = QMenu(addon_name, mw)
    mw.form.menuTools.addMenu(morphman_cleanup_menu)

    # Add "Run" button
    a = QAction('&Run', mw)
    a.triggered.connect(morphman_recalc_with_cleanup)
    morphman_cleanup_menu.addAction(a)    

def morphman_recalc_with_cleanup():
    run_mm_recalc()
    note_ids = cleanup()
    fix_movies2anki_name_mismatch()
    mw.reset()
    
    tooltip(f"Deleted {len(note_ids)} notes")

def run_mm_recalc():
    mm_main = importlib.import_module('morphman_dev.morph.main')
    mm_main.main()

def cleanup():
    note_ids = set(chain(*[
        mw.col.find_notes(query)
        for query in queries
    ]))
    mw.col.remNotes(note_ids)
    return note_ids


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