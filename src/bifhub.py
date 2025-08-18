#!/usr/bin/env python3
"""
Catalog Management for AWT Elections

This module handles election file discovery, metadata management, and catalog operations.
Eventually intended to become a separate bifhub service.
"""

import os
import re
import sys
import yaml
from pathlib import Path


def abif_catalog_init(extra_dirs=None, catalog_filename="abif_list.yml"):
    """Initialize and locate the ABIF catalog file"""
    # Import here to avoid circular dependency
    from abiflib.util import get_abiftool_dir

    awt_dir = Path(__file__).parent.parent  # Go up from src/bifhub.py to awt/
    testfiledir = Path(get_abiftool_dir()) / 'testdata'

    basedir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [str(awt_dir),
                   os.path.join(sys.prefix, "abif-catalog"),
                   str(awt_dir)]
    if extra_dirs:
        search_dirs = extra_dirs + search_dirs

    for dir in search_dirs:
        path = os.path.join(dir, catalog_filename)
        if os.path.exists(path):
            return path
    else:
        raise Exception(
            f"{catalog_filename} not found in {', '.join(search_dirs)}")


def build_election_list():
    """Load the list of elections from abif_list.yml"""
    from abiflib.util import get_abiftool_dir

    yampath = abif_catalog_init()
    testfiledir = Path(get_abiftool_dir()) / 'testdata'

    retval = []
    with open(yampath) as fp:
        retval.extend(yaml.safe_load(fp))

    for i, f in enumerate(retval):
        apath = Path(testfiledir, f['filename'])
        try:
            retval[i]['text'] = apath.read_text()
        except FileNotFoundError:
            retval[i]['text'] = f'NOT FOUND: {f["filename"]}\n'
        retval[i]['taglist'] = []
        if type(retval[i].get('tags')) is str:
            for t in re.split('[ ,]+', retval[i]['tags']):
                retval[i]['taglist'].append(t)
        else:
            retval[i]['taglist'] = ["UNTAGGED"]

    return retval


def get_fileentry_from_election_list(filekey, election_list):
    """Returns entry of ABIF file matching filekey

    Args:
        election_list: A list of dictionaries.
        filekey: The id value to lookup.

    Returns:
        The single index if exactly one match is found.
        None if no matches are found.
    """
    matchlist = [i for i, d in enumerate(election_list)
                 if d['id'] == filekey]

    if not matchlist:
        return None
    elif len(matchlist) == 1:
        return election_list[matchlist[0]]
    else:
        raise ValueError("Multiple file entries found with the same id.")


def get_fileentries_by_tag(tag, election_list):
    """Returns ABIF file entries having given tag

    Note: Fixed to use 'taglist' which is created by build_election_list()
    instead of the raw 'tags' string.
    """
    retval = []
    for i, d in enumerate(election_list):
        if d.get('taglist') and tag and tag in d.get('taglist'):
            retval.append(d)
    return retval


def get_all_tags_in_election_list(election_list):
    """Get all unique tags from the election list"""
    retval = set()
    for i, d in enumerate(election_list):
        if d.get('taglist'):
            for t in d['taglist']:
                retval.add(t)
    return retval
