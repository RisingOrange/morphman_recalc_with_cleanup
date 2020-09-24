import importlib
from itertools import chain
from collections import defaultdict

from aqt import mw
from aqt.utils import tooltip, showText
from PyQt5.QtWidgets import *

# only notes with this tag will be affected by the cleanup
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

# number of cards that will be searched for morph dupes
# they are taken from the top of cards sorted by due date (ascending)
num_notes_searched_for_morph_dupes = 200

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

    tooltip(f"Deleted {len(note_ids)} notes")

def run_mm_recalc():
    mm_main = importlib.import_module('morphman_dev.morph.main')
    mm_main.main()

def cleanup():
    note_ids_from_queries = remove_query_matches()
    note_ids_from_morph_dupes = remove_unnecessary_morph_dupes()
    return note_ids_from_queries + note_ids_from_morph_dupes

def remove_query_matches():
    note_ids = set(chain(*[
        mw.col.find_notes(query)
        for query in queries
    ]))
    mw.col.remNotes(note_ids)
    return list(note_ids)

def remove_unnecessary_morph_dupes():

    notes_to_be_removed = []

    # only process n new notes of which the cards are due next
    notes_to_be_processed = list(set([
        mw.col.getCard(id).nid
        for id in
        mw.col.find_cards(
            f'"tag:{mm_tag}" TargetMorph:_* is:new',
            order="due asc"
        )
    ]))[:num_notes_searched_for_morph_dupes]
    
    note_to_morph = {
        note : mw.col.getNote(note)['TargetMorph']
        for note in notes_to_be_processed
    }
    morph_to_notes = defaultdict(lambda: [])
    for note, morph in note_to_morph.items():
        morph_to_notes[morph].append(note)

    for notes_with_same_morph in (notes for notes in morph_to_notes.values() if len(notes) > 1):
        # pick random note to keep, delete others
        note_to_keep = next(iter(notes_with_same_morph))
        notes_to_be_removed.extend(set(notes_with_same_morph) - set([note_to_keep]))

    if notes_to_be_removed:
        showText(
            'These are TargetMorphs of notes that will be removed:\n' + 
            ('\n'.join(
                mw.col.getNote(note)['TargetMorph']
                for note in notes_to_be_removed
            ))
        )
        mw.col.remNotes(notes_to_be_removed)
        
    return notes_to_be_removed

def fix_movies2anki_name_mismatch():

    def extract_file_name(line):
        return line[len('[sound:') : -1]

    note_ids = mw.col.find_notes(f'"tag:{mm_tag}" mid:"{movies2anki_for_mmm_note_type_id}"')
    for note in [ mw.col.getNote(id_) for id_ in note_ids ]:
        new_audio_file_name = extract_file_name(note['Audio Sound'])
        note['Audio'] = new_audio_file_name

        new_video_file_name = extract_file_name(note['Video Sound'])
        note['Video'] = new_video_file_name

        note.flush()


setup_toolbar_menu()