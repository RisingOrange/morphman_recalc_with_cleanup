import importlib
import logging
import pathlib
import re
from collections import defaultdict
from itertools import chain
from logging.handlers import RotatingFileHandler

from aqt import mw
from aqt.utils import tooltip
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

# number of cards that will be searched for name morphs
# they are taken from the top of cards sorted by due date (ascending)
num_notes_searched_for_name_morphs = 200

# only notes with this field will be searched for names as target morphs
field_searched_for_name_morphs = 'Front'

# notes will be marked with this tag as already known (name morphs)
mm_already_known_tag = 'mm_alreadyKnown'

addon_name = "Morphman Recalc with Cleanup"


# setup logger
logger = logging.getLogger()
logger.setLevel('DEBUG')
handler = RotatingFileHandler(
    filename=pathlib.Path(__file__).parent.absolute() / 'log.log',
    mode='w',
    encoding='utf-8',
    maxBytes=1000,
    backupCount=3,
)
handler.setFormatter(logging.Formatter('%(asctime)s-%(message)s'))
logger.addHandler(handler)



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
    logger.debug('starting cleanup...')

    note_ids_from_queries = remove_query_matches()
    note_ids_from_morph_dupes = remove_unnecessary_morph_dupes()
    fix_movies2anki_name_mismatch()
    handle_name_morphs()

    logger.debug('done cleaning up')

    return note_ids_from_queries + note_ids_from_morph_dupes

def remove_query_matches():
    note_ids = set(chain(*[
        mw.col.find_notes(query)
        for query in queries
    ]))
    mw.col.remNotes(note_ids)
    return list(note_ids)

def new_vocab_notes():
    # returns new vocab notes, sorted by due date (ascending)
    return list(set([
        mw.col.getCard(id).nid
        for id in
        mw.col.find_cards(
            f'"tag:{mm_tag}" TargetMorph:_* is:new',
            order="due asc"
        )
    ]))

def remove_unnecessary_morph_dupes():

    notes_to_be_removed = []

    # only process n new notes of which the cards are due next
    notes_to_be_processed = new_vocab_notes()[:num_notes_searched_for_morph_dupes]
    
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
        logging.debug(
            'notes removed because of them having morph duplicates:\n' +
            debug_note_listing(notes_to_be_removed)
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

def handle_name_morphs():
    # buries and tags notes as already known when their target morph is a name
    # a very simple heuristic is used to identify names, which only works in
    # languages where most words are lower case, except for names

    def morph(note):
        return mw.col.getNote(note)['TargetMorph']

    def text(note):
        try:
            return mw.col.getNote(note)[field_searched_for_name_morphs]
        except KeyError:
            return ''

    notes_with_name_morphs = []
    notes_to_be_processed = new_vocab_notes()[:num_notes_searched_for_name_morphs]
    for note in notes_to_be_processed:
        # if the morph is capitalized and not at the beginning of a sentence,
        # assume it's a name
        if re.search(f'[\w,; ]+{morph(note).capitalize()}', text(note)):
            notes_with_name_morphs.append(note)

    for note in notes_with_name_morphs:
        note_obj = mw.col.getNote(note)
        note_obj.addTag(mm_already_known_tag)
        note_obj.flush()

    for note in notes_with_name_morphs:
        mw.col.sched.buryNote(note)

    if notes_with_name_morphs:
        logging.debug(
            'notes buried and tagged already known:\n' +
            debug_note_listing(notes_with_name_morphs)
        )

def debug_note_listing(notes):
    return '\n'.join(
        f'{note} {mw.col.getNote(note)["TargetMorph"]}'
        for note in notes
    )

setup_toolbar_menu()
