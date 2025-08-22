#!/usr/bin/env python3
from abiflib import (
    convert_abif_to_jabmod,
    htmltable_pairwise_and_winlosstie as abiflib_htmltable_pairwise_and_winlosstie,
    get_Copeland_winners,
    html_score_and_star as abiflib_html_score_and_star,
    ABIFVotelineException,
    full_copecount_from_abifmodel,
    copecount_diagram,
    IRV_dict_from_jabmod,
    get_IRV_report,
    FPTP_result_from_abifmodel,
    get_FPTP_report,
    pairwise_count_dict,
    STAR_result_from_abifmodel,
    scaled_scores,
    add_ratings_to_jabmod_votelines,
    get_abiftool_dir
)
from abiflib.approval_tally import (
    approval_result_from_abifmodel,
    get_approval_report
)
from abiflib.util import find_ballot_type
from abiflib.score_star_tally import STAR_report
from abiflib.pairwise_tally import winlosstie_dict_from_pairdict
import argparse
from cache_awt import (
    cache_key_from_request,
    cache_file_from_key,
    log_cache_hit,
    monkeypatch_cache_get,
    purge_cache_entry,
    purge_cache_entries_by_path
)
import conduits
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, send_from_directory, url_for
from flask_caching import Cache
from html_util import generate_candidate_colors, escape_css_selector, add_html_hints_to_stardict, get_method_ordering
from jinja2 import Environment, FileSystemLoader, select_autoescape
import logging
from markupsafe import escape
from pathlib import Path
from pprint import pformat
import os
import re
import socket
import sys
import tempfile
import threading
import urllib
import yaml


def _template_loader():
    """Return a Jinja2 FileSystemLoader with robust search paths.

    Searches, in order:
    - `AWT_TEMPLATES` (env/discovered)
    - `templates` next to this file (dev tree)
    - `sys.prefix/awt-templates` (data-files in venv)
    - `<venv root>/awt-templates` (alt venv layout)
    - `site-packages/awt-templates` (data-files next to installed module)
    """
    paths = []
    try:
        if AWT_TEMPLATES:
            paths.append(AWT_TEMPLATES)
    except NameError:
        pass
    here = os.path.dirname(__file__)
    paths.append(os.path.join(here, 'templates'))
    try:
        paths.append(os.path.join(sys.prefix, 'awt-templates'))
        exe_path = Path(sys.argv[0]).resolve()
        if exe_path.name == 'python' or exe_path.name.startswith('python'):
            exe_path = Path(sys.executable).resolve()
        venv_root = exe_path.parent.parent
        paths.append(str(venv_root / 'awt-templates'))
    except Exception:
        pass
    try:
        import importlib.util as _ilu
        pkg_dir = Path(_ilu.find_spec('awt').origin).parent
        paths.append(str(pkg_dir / 'awt-templates'))
    except Exception:
        pass
    seen = set()
    exists = [p for p in paths if p and os.path.isdir(p) and not (p in seen or seen.add(p))]
    return FileSystemLoader(exists or [os.path.join(here, 'templates')])


def jinja_pairwise_snippet(abifmodel, pairdict, wltdict, colordict=None, add_desc=True, svg_text=None, is_copeland_tie=False):
    def wltstr(cand):
        retval = f"{wltdict[cand]['wins']}" + "-"
        retval += f"{wltdict[cand]['losses']}" + "-"
        retval += f"{wltdict[cand]['ties']}"
        return retval
    candtoks = sorted(
        pairdict.keys(), key=lambda x: wltdict[x]['wins'], reverse=True)
    candnames = abifmodel.get('candidates', None)
    has_ties_or_cycles = False
    for ck in candtoks:
        for rk in candtoks:
            if ck != rk and candtoks.index(ck) > candtoks.index(rk):
                rkscore = pairdict[rk][ck]
                ckscore = pairdict[ck][rk]
                if not (rkscore > ckscore):
                    has_ties_or_cycles = True

    # Generate description if not provided
    desc = abifmodel.get('desc', None) if add_desc else None
    if add_desc and not desc:
        cand_list_str = ", ".join([candnames[c] for c in candtoks])
        desc = f"Candidate matchups for {cand_list_str}"

    # Use robust loader that searches common install locations
    env = Environment(
        loader=_template_loader(),
        autoescape=select_autoescape(['html', 'xml'])
    )
    env.filters['escape_css'] = escape_css_selector

    # Generate enhanced pairwise summary using abiflib functions
    from abiflib.pairwise_tally import calculate_pairwise_victory_sizes
    victory_method = 'winning-votes'  # Default, could be made configurable
    victory_data = calculate_pairwise_victory_sizes(pairdict, victory_method)

    # Prepare structured data for template
    summary_data = {
        'victory_method': victory_method,
        'victory_data': victory_data,
        'total_ballots': abifmodel.get('metadata', {}).get('ballotcount', 0)
    }

    template = env.get_template('pairwise-snippet.html')
    html = template.render(
        title=abifmodel.get('title', 'Pairwise Table'),
        abifmodel=abifmodel,
        desc=desc,
        candtoks=candtoks,
        candnames=candnames,
        pairdict=pairdict,
        wltdict=wltdict,
        wltstr=wltstr,
        has_ties_or_cycles=has_ties_or_cycles,
        svg_text=svg_text,
        colordict=colordict,
        summary_data=summary_data,
        is_copeland_tie=is_copeland_tie
    )
    return html


def jinja_pairwise_summary_only(abifmodel, pairdict, wltdict, colordict=None, is_copeland_tie=False, copewinnerstring=None, copewinners=None):
    """Generate only the pairwise summary bullets (without the table)"""
    def wltstr(cand):
        retval = f"{wltdict[cand]['wins']}" + "-"
        retval += f"{wltdict[cand]['losses']}" + "-"
        retval += f"{wltdict[cand]['ties']}"
        return retval
    candtoks = sorted(
        pairdict.keys(), key=lambda x: wltdict[x]['wins'], reverse=True)
    candnames = abifmodel.get('candidates', None)

    env = Environment(
        loader=_template_loader(),
        autoescape=select_autoescape(['html', 'xml'])
    )
    env.filters['escape_css'] = escape_css_selector

    # Generate enhanced pairwise summary using abiflib functions
    from abiflib.pairwise_tally import calculate_pairwise_victory_sizes
    victory_method = 'winning-votes'  # Default, could be made configurable
    victory_data = calculate_pairwise_victory_sizes(pairdict, victory_method)

    # Prepare structured data for template
    summary_data = {
        'victory_method': victory_method,
        'victory_data': victory_data,
        'total_ballots': abifmodel.get('metadata', {}).get('ballotcount', 0)
    }

    template = env.get_template('pairwise-summary-only.html')
    html = template.render(
        candnames=candnames,
        wltdict=wltdict,
        colordict=colordict,
        summary_data=summary_data,
        is_copeland_tie=is_copeland_tie,
        copewinnerstring=copewinnerstring,
        copewinners=copewinners or []
    )
    return html


# Utility: Jinja2 rendering for STAR/score output
def jinja_scorestar_snippet(jabmod, basicstar=None, scaled=None):
    content = STAR_report(jabmod)
    env = Environment(
        loader=_template_loader(),
        autoescape=select_autoescape(['html', 'xml'])
    )
    template = env.get_template('scorestar-snippet.html')
    html = template.render(
        content='\n'.join(content),
        basicstar=basicstar,
        scaled=scaled
    )
    return html


# --- Cache utility functions ---
# -----------------------------
# Load environment variables from .env file in the same directory
# as this file (project root)
awt_py_dir = Path(__file__).parent.resolve()
dotenv_path = awt_py_dir / '.env'
load_dotenv(dotenv_path=dotenv_path)
if dotenv_path.exists():
    print(f"[awt.py] Loaded .env from {dotenv_path}")
else:
    print(
        f"[awt.py] No .env file found at {dotenv_path} (this is fine if you set env vars another way)")


# Global default cache timeout (1 week)
AWT_DEFAULT_CACHE_TIMEOUT = 7 * 24 * 3600
# Allow overriding port via env or CLI
DEFAULT_PORT = int(os.environ.get("PORT", 0))

# Intelligent defaults for static/template directories
AWT_STATIC = os.getenv("AWT_STATIC")
AWT_TEMPLATES = os.getenv("AWT_TEMPLATES")

# Only guess if not set by env
if not AWT_STATIC or not AWT_TEMPLATES:
    # 1. Try static/templates next to this file
    static_candidate = awt_py_dir / 'static'
    templates_candidate = awt_py_dir / 'templates'
    if not AWT_STATIC and static_candidate.is_dir():
        AWT_STATIC = str(static_candidate)
    if not AWT_TEMPLATES and templates_candidate.is_dir():
        AWT_TEMPLATES = str(templates_candidate)

# 2. Try awt-static/awt-templates in package data dir (for venv installs)
if not AWT_STATIC or not AWT_TEMPLATES:
    try:
        import importlib.util
        pkg_dir = Path(importlib.util.find_spec('awt').origin).parent
        awt_static_candidate = pkg_dir / 'awt-static'
        awt_templates_candidate = pkg_dir / 'awt-templates'
        if not AWT_STATIC and awt_static_candidate.is_dir():
            AWT_STATIC = str(awt_static_candidate)
        if not AWT_TEMPLATES and awt_templates_candidate.is_dir():
            AWT_TEMPLATES = str(awt_templates_candidate)
    except Exception:
        pass

# 2b. Try awt-static/awt-templates under sys.prefix (typical data-files target)
if not AWT_STATIC or not AWT_TEMPLATES:
    try:
        prefix_dir = Path(sys.prefix)
        awt_static_candidate = prefix_dir / 'awt-static'
        awt_templates_candidate = prefix_dir / 'awt-templates'
        if not AWT_STATIC and awt_static_candidate.is_dir():
            AWT_STATIC = str(awt_static_candidate)
        if not AWT_TEMPLATES and awt_templates_candidate.is_dir():
            AWT_TEMPLATES = str(awt_templates_candidate)
    except Exception:
        pass

# 3. Try static/templates in current working directory
if not AWT_STATIC or not AWT_TEMPLATES:
    cwd = Path.cwd()
    static_candidate = cwd / 'static'
    templates_candidate = cwd / 'templates'
    if not AWT_STATIC and static_candidate.is_dir():
        AWT_STATIC = str(static_candidate)
    if not AWT_TEMPLATES and templates_candidate.is_dir():
        AWT_TEMPLATES = str(templates_candidate)

# 4. Try awt-static/awt-templates as siblings to the executable's bin directory
if not AWT_STATIC or not AWT_TEMPLATES:
    import sys
    exe_path = Path(sys.argv[0]).resolve()
    # If running as 'python -m awt', sys.argv[0] may be 'python', so also try sys.executable
    if exe_path.name == 'python' or exe_path.name.startswith('python'):
        exe_path = Path(sys.executable).resolve()
    venv_root = exe_path.parent.parent  # bin/ -> venv/
    awt_static_candidate = venv_root / 'awt-static'
    awt_templates_candidate = venv_root / 'awt-templates'
    if not AWT_STATIC and awt_static_candidate.is_dir():
        AWT_STATIC = str(awt_static_candidate)
    if not AWT_TEMPLATES and awt_templates_candidate.is_dir():
        AWT_TEMPLATES = str(awt_templates_candidate)

missing_static = not (AWT_STATIC and Path(AWT_STATIC).is_dir())
missing_templates = not (AWT_TEMPLATES and Path(AWT_TEMPLATES).is_dir())

print(
    f"[awt.py] Using static: {AWT_STATIC if AWT_STATIC else '[not set]'}{' (MISSING)' if missing_static else ''}")
print(
    f"[awt.py] Using templates: {AWT_TEMPLATES if AWT_TEMPLATES else '[not set]'}{' (MISSING)' if missing_templates else ''}")
if missing_static or missing_templates:
    print("[awt.py] WARNING: Could not find static/templates directories. This is just a warning; the app will still run.")
    print("[awt.py] To fix this, either:")
    print("  1. Create a .env file in your project root (next to awt.py) with:")
    print("     AWT_STATIC=static\n     AWT_TEMPLATES=templates")
    print("  2. Or, create 'static' and 'templates' directories next to awt.py.")
    print("[awt.py] If these are missing, some features (like static files or templates) may not work as expected.")

# Use discovered static/template directories for Flask app
# For venv installs, static files may be flattened, so handle this case

if AWT_STATIC and Path(AWT_STATIC).name == 'awt-static':
    # If we found awt-static directory with flattened files, use it directly
    # and create a custom static URL path mapping
    static_folder = AWT_STATIC
    static_url_path = '/static'
else:
    # Otherwise use the discovered static directory directly
    static_folder = AWT_STATIC
    static_url_path = '/static'

app = Flask(__name__, static_folder=static_folder,
            template_folder=AWT_TEMPLATES, static_url_path=static_url_path)
# Accept both with and without trailing slashes on routes
app.url_map.strict_slashes = False
app.jinja_env.filters['escape_css'] = escape_css_selector


@app.route('/favicon.ico')
def favicon():
    """Serve favicon if present; otherwise, be non-fatal.

    - If a `favicon.ico` exists in the configured static directory, serve it.
    - If not present or any error occurs, return 204 No Content to avoid
      triggering the template-based 404 handler.
    """
    try:
        static_dir = AWT_STATIC or app.static_folder
        if static_dir:
            favpath = os.path.join(static_dir, 'favicon.ico')
            if os.path.isfile(favpath):
                return send_from_directory(static_dir, 'favicon.ico')
    except Exception:
        # Fall through to non-fatal response below
        pass
    # No favicon available: respond with 204 to keep things quiet in tests
    return ('', 204)


# --- Configure logging to show cache events ---
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%d/%b/%Y %H:%M:%S'
)
logging.getLogger('awt.cache').setLevel(logging.INFO)


# --- Flask-Caching Initialization for WSGI ---
# This block configures and initializes the cache when the app is imported by a
# WSGI server (e.g., on PythonAnywhere). The `main()` function below handles
# configuration when running as a standalone script with command-line arguments.
cache = Cache()  # Create cache object at module level for decorators
wsgi_cache_type = os.environ.get("AWT_CACHE_TYPE", "filesystem")
if wsgi_cache_type == "none":
    app.config['CACHE_TYPE'] = 'flask_caching.backends.NullCache'
elif wsgi_cache_type == "simple":
    app.config['CACHE_TYPE'] = 'flask_caching.backends.SimpleCache'
else:  # filesystem
    app.config['CACHE_TYPE'] = 'flask_caching.backends.FileSystemCache'
    app.config['CACHE_DIR'] = os.environ.get(
        "AWT_CACHE_DIR", os.path.join(tempfile.gettempdir(), 'awt_flask_cache'))

app.config['CACHE_DEFAULT_TIMEOUT'] = int(
    os.environ.get("AWT_CACHE_TIMEOUT", AWT_DEFAULT_CACHE_TIMEOUT))

cache.init_app(app)

# Custom static file routes for flattened venv installs
if AWT_STATIC and Path(AWT_STATIC).name == 'awt-static':
    @app.route('/static/css/<filename>')
    def static_css(filename):
        return send_from_directory(AWT_STATIC, filename)

    @app.route('/static/img/<filename>')
    def static_img(filename):
        return send_from_directory(AWT_STATIC, filename)

    @app.route('/static/js/<filename>')
    def static_js(filename):
        return send_from_directory(AWT_STATIC, filename)

    @app.route('/static/<filename>')
    def static_file(filename):
        return send_from_directory(AWT_STATIC, filename)


# Use abiflib.util.get_abiftool_dir to set ABIFTOOL_DIR and TESTFILEDIR
ABIFTOOL_DIR = get_abiftool_dir()
AWT_DIR = str(awt_py_dir)  # Directory containing this awt.py file
if ABIFTOOL_DIR and ABIFTOOL_DIR not in sys.path:
    sys.path.append(ABIFTOOL_DIR)
TESTFILEDIR = Path(ABIFTOOL_DIR) / 'testdata'
# Fallback for packaged installs where testdata is under the venv prefix
if not TESTFILEDIR.is_dir():
    prefix_testdata = Path(sys.prefix) / 'testdata'
    if prefix_testdata.is_dir():
        TESTFILEDIR = prefix_testdata
        print(f"[awt.py] Using testdata from venv: {TESTFILEDIR}")
    else:
        print(f"[awt.py] WARNING: testdata not found at {TESTFILEDIR}")

# Initialized in main()
ABIF_CATALOG = None


class WebEnv:
    __env = {}

    __env['inputRows'] = 12
    __env['inputCols'] = 80

    @staticmethod
    def wenv(name):
        return WebEnv.__env[name]

    @staticmethod
    def wenvDict():
        return WebEnv.__env

    @staticmethod
    def sync_web_env():
        WebEnv.__env['req_url'] = request.url
        WebEnv.__env['hostname'] = urllib.parse.urlsplit(request.url).hostname
        WebEnv.__env['hostcolonport'] = request.host
        WebEnv.__env['protocol'] = request.scheme
        WebEnv.__env['base_url'] = f"{request.scheme}://{request.host}"
        WebEnv.__env['pathportion'] = request.path
        WebEnv.__env['queryportion'] = request.args
        WebEnv.__env['approot'] = app.config['APPLICATION_ROOT']
        WebEnv.__env['debugFlag'] = (os.getenv('AWT_STATUS') == "debug")
        WebEnv.__env['debugIntro'] = "Set AWT_STATUS=prod to turn off debug mode\n"

        if WebEnv.__env['debugFlag']:
            WebEnv.__env['statusStr'] = "(DEBUG) "
            WebEnv.__env['environ'] = os.environ
        else:
            WebEnv.__env['statusStr'] = ""


def abif_catalog_init(extra_dirs=None,
                      catalog_filename="abif_list.yml"):
    global ABIF_CATALOG, AWT_DIR
    basedir = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [basedir,
                   os.path.join(sys.prefix, "abif-catalog"),
                   AWT_DIR]
    if extra_dirs:
        search_dirs = extra_dirs + search_dirs

    if ABIF_CATALOG:
        return ABIF_CATALOG
    else:
        for dir in search_dirs:
            path = os.path.join(dir, "abif_list.yml")
            if os.path.exists(path):
                return path
        else:
            raise Exception(
                f"{catalog_filename} not found in {', '.join(search_dirs)}")


def build_election_list():
    '''Load the list of elections from abif_list.yml'''
    yampath = abif_catalog_init()

    retval = []
    with open(yampath) as fp:
        retval.extend(yaml.safe_load(fp))

    for i, f in enumerate(retval):
        apath = Path(TESTFILEDIR, f['filename'])
        try:
            retval[i]['text'] = apath.read_text()
        except FileNotFoundError:
            # Helpful console debug to show where we looked
            try:
                print(f"[awt.py] ABIF lookup miss: {apath}")
            except Exception:
                pass
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
    """
    retval = []
    for i, d in enumerate(election_list):
        if d.get('tags') and tag and tag in d.get('tags'):
            retval.append(d)
    return retval


def get_all_tags_in_election_list(election_list):
    retval = set()
    for i, d in enumerate(election_list):
        if d.get('tags'):
            for t in re.split('[ ,]+', d['tags']):
                retval.add(t)
    return retval


@app.route('/')
@cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
def homepage():
    """Homepage route using homepage-snippet.html"""
    msgs = {}
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()

    # Handle cache purge
    if 'purge' in request.args:
        cache_key = cache_key_from_request(request)
        cache_file = cache_file_from_key(cache_key)
        purge_cache_entry(cache_key, cache_file)
        msgs['purge_message'] = f"Purged cache entry for homepage"

    msgs['pagetitle'] = f"{webenv['statusStr']}ABIF Web Tool (awt)"
    webenv['toppage'] = 'homepage'
    # Get election list for dynamic count
    from src.bifhub import build_election_list
    election_list = build_election_list()

    return render_template('homepage-index.html',
                           msgs=msgs,
                           webenv=webenv,
                           election_list=election_list), 200


@app.route('/edit')
def edit_interface():
    """Edit interface route - redirects to /awt for 0.33"""
    return redirect('/awt', code=302)


@app.route('/tag', methods=['GET'])
@cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
def list_all_tags():
    """Show an index of all tags, alphabetically, with counts"""
    # --- Cache purge support via ?action=purge ---
    if request.args.get('action') == 'purge':
        args = request.args.to_dict()
        args.pop('action', None)
        canonical_path = request.path
        cache_dir = app.config.get('CACHE_DIR')
        logging.getLogger('awt.cache').info(
            f"[DEBUG] Entering purge logic for path: {canonical_path}")
        from cache_awt import purge_cache_entries_by_path
        purge_cache_entries_by_path(cache, canonical_path, cache_dir)
        # Redirect to same URL without ?action=purge
        return redirect(url_for(request.endpoint, **args))

    msgs = {}
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    msgs['pagetitle'] = "All Tags"
    msgs['lede'] = "Browse all tags alphabetically."

    # Use bifhub functions to build list and collect tags
    from src.bifhub import build_election_list
    election_list = build_election_list()

    # Build counts per tag
    from collections import Counter
    counts = Counter()
    for d in election_list:
        for t in d.get('taglist', []) or []:
            if t:
                counts[t] += 1

    tag_items = [
        {"name": name, "count": count}
        for name, count in counts.items()
    ]
    tag_items.sort(key=lambda x: x['name'].casefold())

    return render_template('tags-index.html',
                           msgs=msgs,
                           webenv=webenv,
                           tags=tag_items), 200


@app.route('/tag/<tag>', methods=['GET'])
@cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
def list_elections(tag=None):
    """Show list of elections filtered by tag"""
    # --- Cache purge support via ?action=purge ---
    if request.args.get('action') == 'purge':
        args = request.args.to_dict()
        args.pop('action', None)
        canonical_path = request.path
        cache_dir = app.config.get('CACHE_DIR')
        logging.getLogger('awt.cache').info(
            f"[DEBUG] Entering purge logic for path: {canonical_path}")
        from cache_awt import purge_cache_entries_by_path
        purge_cache_entries_by_path(cache, canonical_path, cache_dir)
        # Redirect to same URL without ?action=purge
        return redirect(url_for(request.endpoint, **args))

    msgs = {}
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    msgs['pagetitle'] = f"Elections tagged '{tag}'"
    msgs['lede'] = f"Elections with the '{tag}' tag:"

    # Use bifhub functions
    from src.bifhub import build_election_list, get_fileentries_by_tag
    election_list = build_election_list()
    filtered_elections = get_fileentries_by_tag(tag, election_list)

    return render_template('tag-index.html',
                           msgs=msgs,
                           webenv=webenv,
                           election_list=filtered_elections,
                           tag=tag), 200


@app.route('/<toppage>', methods=['GET'])
def awt_get(toppage=None, tag=None):
    msgs = {}
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    msgs['pagetitle'] = \
        f"{webenv['statusStr']}ABIF web tool (awt) on Electorama!"
    msgs['placeholder'] = \
        "Enter ABIF here, possibly using one of the examples below..."
    msgs['lede'] = "FIXME-flaskabif.py"
    election_list = build_election_list()
    debug_flag = webenv['debugFlag']
    debug_output = webenv['debugIntro']

    if tag is not None:
        toppage = "tag"

    # Map both /awt and /edit to 'edit' for template logic
    if toppage in ['awt', 'edit']:
        webenv['toppage'] = 'edit'
    else:
        webenv['toppage'] = toppage

    mytagarray = sorted(get_all_tags_in_election_list(election_list),
                        key=str.casefold)
    match toppage:
        case "awt":
            retval = render_template('default-index.html',
                                     abifinput='',
                                     abiftool_output=None,
                                     main_file_array=election_list[0:5],
                                     other_files=election_list[5:],
                                     example_list=election_list,
                                     webenv=webenv,
                                     msgs=msgs,
                                     debug_output=debug_output,
                                     debug_flag=debug_flag,
                                     tagarray=mytagarray,
                                     )
        case "tag":
            if tag:
                msgs['pagetitle'] = \
                    f"{webenv['statusStr']}Tag: {tag}"
                tag_file_array = get_fileentries_by_tag(tag, election_list)
                debug_output += f"{tag=}"
                retval = render_template('default-index.html',
                                         abifinput='',
                                         abiftool_output=None,
                                         main_file_array=tag_file_array[0:5],
                                         other_files=tag_file_array[5:],
                                         example_list=election_list,
                                         webenv=webenv,
                                         msgs=msgs,
                                         debug_output=debug_output,
                                         debug_flag=debug_flag,
                                         tag=tag,
                                         tagarray=mytagarray
                                         )
            else:
                retval = render_template('tag-index.html',
                                         example_list=election_list,
                                         webenv=webenv,
                                         msgs=msgs,
                                         tag=tag,
                                         tagarray=mytagarray
                                         )

        case _:
            msgs['pagetitle'] = "NOT FOUND"
            msgs['lede'] = (
                "I'm not sure what you're looking for, " +
                "but you shouldn't look here."
            )
            retval = (render_template('not-found.html',
                                      toppage=toppage,
                                      webenv=webenv,
                                      msgs=msgs,
                                      debug_output=debug_output,
                                      debug_flag=debug_flag,
                                      ), 404)
    return retval


# Route for '/browse' - election discovery with tag browser
@app.route('/browse', methods=['GET'])
@cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
def browse_elections():
    # --- Cache purge support via ?action=purge ---
    if request.args.get('action') == 'purge':
        args = request.args.to_dict()
        args.pop('action', None)
        canonical_path = request.path
        cache_dir = app.config.get('CACHE_DIR')
        logging.getLogger('awt.cache').info(
            f"[DEBUG] Entering purge logic for path: {canonical_path}")
        purge_cache_entries_by_path(cache, canonical_path, cache_dir)
        # Redirect to same URL without ?action=purge
        return redirect(url_for(request.endpoint, **args))
    msgs = {}
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    msgs['pagetitle'] = \
        f"{webenv['statusStr']}ABIF web tool (awt) on Electorama!"
    msgs['pagetitle'] = "Browse Elections"
    msgs['lede'] = (
        "Browse elections by category or view the complete list:"
    )
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    election_list = build_election_list()
    return render_template('browse-index.html',
                           msgs=msgs,
                           webenv=webenv,
                           election_list=election_list
                           ), 200


# Route for '/id' with no identifier


@app.route('/id', methods=['GET'])
@cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
def id_no_identifier():
    # --- Cache purge support via ?action=purge ---
    if request.args.get('action') == 'purge':
        args = request.args.to_dict()
        args.pop('action', None)
        canonical_path = request.path
        cache_dir = app.config.get('CACHE_DIR')
        logging.getLogger('awt.cache').info(
            f"[DEBUG] Entering purge logic for path: {canonical_path}")
        from cache_awt import purge_cache_entries_by_path
        purge_cache_entries_by_path(cache, canonical_path, cache_dir)
        # Redirect to same URL without ?action=purge
        return redirect(url_for(request.endpoint, **args))
    msgs = {}
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    msgs['pagetitle'] = \
        f"{webenv['statusStr']}ABIF web tool (awt) on Electorama!"
    msgs['placeholder'] = \
        "FIXME!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    msgs['pagetitle'] = "ABIF Election List"
    msgs['lede'] = (
        "Please select one of the elections below:"
    )
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    election_list = build_election_list()
    return render_template('id-index.html',
                           msgs=msgs,
                           webenv=webenv,
                           election_list=election_list
                           ), 200


@app.route('/id/<identifier>/dot/svg')
@cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
def get_svg_dotdiagram(identifier):
    '''FIXME FIXME July 2024'''
    election_list = build_election_list()
    fileentry = get_fileentry_from_election_list(identifier, election_list)
    jabmod = convert_abif_to_jabmod(fileentry['text'], cleanws=True)
    copecount = full_copecount_from_abifmodel(jabmod)
    return copecount_diagram(copecount, outformat='svg')


@app.route('/id/<this_id>/dot')
@app.route('/id/<this_id>/wlt')
def handle_deprecated_dot_wlt(this_id):
    '''Deprecated in 0.33 - redirects /dot and /wlt to /pairwise anchors.
    Will be replaced by awt_redirect() in 0.34.'''
    # Extract route type from request path
    route_type = request.path.split('/')[-1]  # 'dot' or 'wlt'
    return redirect(f'/id/{this_id}/pairwise#{route_type}', code=302)


@app.route('/id/<identifier>', methods=['GET'])
@app.route('/id/<identifier>/<resulttype>', methods=['GET'])
def get_by_id(identifier, resulttype=None):
    import cProfile
    import pstats
    import io
    import os
    import datetime
    # --- Cache purge support via ?action=purge ---
    if request.args.get('action') == 'purge':
        # Purge all cache entries for this path
        args = request.args.to_dict()
        args.pop('action', None)
        canonical_path = request.path
        cache_dir = app.config.get('CACHE_DIR')
        logging.getLogger('awt.cache').info(
            f"[DEBUG] Entering purge logic for path: {canonical_path}")
        from cache_awt import purge_cache_entries_by_path
        purge_cache_entries_by_path(cache, canonical_path, cache_dir)
        # Redirect to same URL without ?action=purge
        return redirect(url_for(request.endpoint, identifier=identifier, resulttype=resulttype, **args))
    # Only cache normal GET requests

    @cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
    def cached_get_by_id(identifier, resulttype=None):
        webenv = WebEnv.wenvDict()
        debug_output = webenv.get('debugIntro') or ""
        WebEnv.sync_web_env()
        rtypemap = {
            'wlt': 'win-loss-tie (Condorcet) results',
            'dot': 'pairwise (Condorcet) diagram',
            'pairwise': 'Condorcet/Copeland results',
            'IRV': 'RCV/IRV results',
            'STAR': 'STAR results',
            'FPTP': 'choose-one (FPTP) results',
            'approval': 'approval voting results'
        }
        print(
            f" 00001 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id({identifier=} {resulttype=})")
        debug_output += \
            f" 00001 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id({identifier=} {resulttype=})\n"
        msgs = {}
        msgs['placeholder'] = "Enter ABIF here, possibly using one of the examples below..."
        election_list = build_election_list()
        fileentry = get_fileentry_from_election_list(identifier, election_list)
        print(
            f" 00002 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
        debug_output += \
            f" 00002 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"

        # --- Server-side profiling if AWT_PROFILE_OUTPUT is set ---
        prof = None
        cprof_path = os.environ.get('AWT_PROFILE_OUTPUT')
        if cprof_path:
            prof = cProfile.Profile()
            prof.enable()

        if fileentry:
            print(
                f" 00003 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
            debug_output += \
                f" 00003 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"
            msgs['pagetitle'] = f"{webenv['statusStr']}{fileentry['title']}"
            msgs['lede'] = (
                f"Below is the ABIF from the \"{fileentry['id']}\" election" +
                f" ({fileentry['title']})"
            )
            msgs['results_name'] = rtypemap.get(resulttype)
            msgs['taglist'] = fileentry['taglist']

            try:
                jabmod = convert_abif_to_jabmod(fileentry['text'])
                if fileentry.get('desc'):
                    jabmod['desc'] = fileentry['desc']
                if fileentry.get('title'):
                    jabmod['title'] = fileentry['title']
                error_html = None
            except ABIFVotelineException as e:
                jabmod = None
                error_html = e.message

            import time
            print(
                f" 00004 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
            debug_output += f" 00004 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"
            resconduit = conduits.ResultConduit(jabmod=jabmod)

            # Determine which computations to run based on route
            compute_all = (not resulttype) or (resulttype == 'all')
            do_FPTP = compute_all or (resulttype == 'FPTP')
            do_IRV = compute_all or (resulttype == 'IRV')
            do_pairwise = compute_all or (resulttype in ('pairwise', 'dot', 'wlt'))
            do_STAR = compute_all or (resulttype == 'STAR')
            do_approval = compute_all or (resulttype == 'approval')

            # Compute FPTP first if needed (enables color ordering by votes)
            candidate_order = []
            if do_FPTP:
                t_fptp = time.time()
                resconduit = resconduit.update_FPTP_result(jabmod)
                fptp_time = time.time() - t_fptp
                print(
                    f" 00006 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [FPTP: {fptp_time:.2f}s]")
                debug_output += f" 00006 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [FPTP: {fptp_time:.2f}s]\n"
                # Build candidate order from FPTP toppicks if available
                resblob = resconduit.resblob
                if jabmod and 'FPTP_result' in resblob:
                    fptp_toppicks = resblob['FPTP_result'].get('toppicks', {})
                    if fptp_toppicks:
                        def get_vote_count(item):
                            cand, votes = item
                            if isinstance(votes, (int, float)):
                                return votes
                            elif isinstance(votes, list) and len(votes) > 0:
                                return votes[0] if isinstance(votes[0], (int, float)) else 0
                            else:
                                return 0
                        fptp_ordered_candidates = sorted(
                            fptp_toppicks.items(), key=get_vote_count, reverse=True)
                        candidate_order = [cand for cand, votes in fptp_ordered_candidates if cand is not None]
            # If no FPTP order, fall back to alphabetical
            if not candidate_order:
                if jabmod and 'candidates' in jabmod:
                    candidate_order = sorted(jabmod['candidates'].keys())
                else:
                    candidate_order = []

            # Generate single color dictionary for all voting systems
            # Use the same canonical ordering logic as conduits.py
            from conduits import get_canonical_candidate_order
            canonical_order = get_canonical_candidate_order(jabmod)
            consistent_colordict = generate_candidate_colors(canonical_order)

            # IRV (only if requested/all)
            if do_IRV:
                t_irv = time.time()
                include_irv_extra = bool(request.args.get('include_irv_extra', True))
                resconduit = resconduit.update_IRV_result(
                    jabmod, include_irv_extra=include_irv_extra)
                irv_time = time.time() - t_irv
                print(
                    f" 00007 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [IRV: {irv_time:.2f}s]")
                debug_output += f" 00007 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [IRV: {irv_time:.2f}s]\n"

            # Pairwise/Condorcet (only if requested/all)
            if do_pairwise:
                t_pairwise = time.time()
                # Build pairwise result and summaries using the consistent colors
                pairwise_dict = pairwise_count_dict(jabmod)
                wltdict = winlosstie_dict_from_pairdict(
                    jabmod['candidates'], pairwise_dict)
                resblob = resconduit.resblob
                # Ensure notices structure exists to satisfy template expectations
                if 'notices' not in resblob:
                    resblob['notices'] = {}
                resblob['notices'].setdefault('pairwise', [])
                # Copecount-derived fields
                from abiflib import full_copecount_from_abifmodel, get_Copeland_winners, copecount_diagram
                copecount = full_copecount_from_abifmodel(jabmod, pairdict=pairwise_dict)
                copewinners = get_Copeland_winners(copecount)
                resblob['copewinners'] = copewinners
                resblob['copewinnerstring'] = ", ".join(copewinners)
                resblob['is_copeland_tie'] = len(copewinners) > 1

                # Add Copeland tie notice if needed (for GET route)
                if resblob['is_copeland_tie'] and len(copewinners) >= 2:
                    # Get candidate display names
                    candnames = jabmod.get('candidates', {}) if jabmod else {}
                    tied_names = []
                    for token in copewinners:
                        display_name = candnames.get(token, token)
                        tied_names.append(display_name)

                    tied_list = " and ".join(tied_names)

                    # Add Copeland tie notice to notices
                    copeland_notice = {
                        "notice_type": "warning",
                        "short": "No Condorcet winner found",
                        "long": f"This election has no Condorcet winner. {tied_list} are tied for the most pairwise victories (Copeland tie). Each of these candidates beats the same number of opponents in head-to-head comparisons, creating a cycle in the tournament. The Copeland/pairwise table below shows the detailed win-loss-tie records that result in this tie."
                    }
                    resblob['notices']['pairwise'].append(copeland_notice)

                resblob['dotsvg_html'] = copecount_diagram(copecount, outformat='svg')
                resblob['pairwise_dict'] = pairwise_dict
                resblob['pairwise_html'] = jinja_pairwise_snippet(
                    jabmod,
                    pairwise_dict,
                    wltdict,
                    colordict=consistent_colordict,
                    add_desc=True,
                    svg_text=None,
                    is_copeland_tie=resblob.get('is_copeland_tie', False)
                )
                resblob['pairwise_summary_html'] = jinja_pairwise_summary_only(
                    jabmod,
                    pairwise_dict,
                    wltdict,
                    colordict=consistent_colordict,
                    is_copeland_tie=resblob.get('is_copeland_tie', False),
                    copewinnerstring=resblob.get('copewinnerstring', ''),
                    copewinners=resblob.get('copewinners', [])
                )
                pairwise_time = time.time() - t_pairwise
                print(
                    f" 00008 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [Pairwise: {pairwise_time:.2f}s]")
                debug_output += f" 00008 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [Pairwise: {pairwise_time:.2f}s]\n"

            # STAR (only if requested/all)
            if do_STAR:
                t_starprep = time.time()
                ratedjabmod = add_ratings_to_jabmod_votelines(jabmod)
                starprep_time = time.time() - t_starprep
                print(
                    f" 00009 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR prep: {starprep_time:.2f}s]")
                debug_output += f" 00009 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR prep: {starprep_time:.2f}s]\n"

                t_star = time.time()
                resconduit = resconduit.update_STAR_result(
                    ratedjabmod, consistent_colordict)
                resconduit.resblob['STAR_html'] = jinja_scorestar_snippet(ratedjabmod)
                star_time = time.time() - t_star
                print(
                    f" 00010 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR: {star_time:.2f}s]")
                debug_output += f" 00010 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR: {star_time:.2f}s]\n"

            # Approval (only if requested/all)
            if do_approval:
                t_approval = time.time()
                resconduit = resconduit.update_approval_result(jabmod)
                approval_time = time.time() - t_approval
                print(
                    f" 00011 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [Approval: {approval_time:.2f}s]")
                debug_output += f" 00011 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [Approval: {approval_time:.2f}s]\n"

            resblob = resconduit.resblob

            # Store the consistent colordict and candidate order
            resblob['colordict'] = consistent_colordict
            resblob['candidate_order'] = candidate_order
            if not resulttype or resulttype == 'all':
                # Use dynamic method ordering based on metadata and ballot type
                base_methods = ['FPTP', 'IRV', 'STAR', 'approval', 'wlt']
                ordered_methods = get_method_ordering(jabmod, base_methods)
                # Insert 'dot' before 'wlt' to keep Condorcet methods together
                rtypelist = []
                for method in ordered_methods:
                    if method == 'wlt':
                        rtypelist.append('dot')
                        rtypelist.append('wlt')
                    elif method != 'dot':  # Skip 'dot' since we handle it with 'wlt'
                        rtypelist.append(method)
            else:
                if resulttype == 'pairwise':
                    rtypelist = ['dot', 'wlt']
                else:
                    rtypelist = [resulttype]

            debug_output += pformat(resblob.keys()) + "\n"
            debug_output += f"result_types (dynamic order): {rtypelist}\n"

            print(
                f" 00012 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
            debug_output += f" 00012 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"

            if prof:
                prof.disable()
                prof.dump_stats(cprof_path)
                print(f"[SERVER PROFILE] Profile saved to {cprof_path}")
            # Build dynamic method ordering list
            if not resulttype or resulttype == 'all':
                # Use dynamic method ordering based on metadata and ballot type
                base_methods = ['FPTP', 'IRV', 'STAR', 'approval', 'wlt']
                ordered_methods = get_method_ordering(jabmod, base_methods)
                # Insert 'dot' before 'wlt' to keep Condorcet methods together
                rtypelist = []
                for method in ordered_methods:
                    if method == 'wlt':
                        rtypelist.append('dot')
                        rtypelist.append('wlt')
                    elif method != 'dot':  # Skip 'dot' since we handle it with 'wlt'
                        rtypelist.append(method)
            else:
                if resulttype == 'pairwise':
                    rtypelist = ['dot', 'wlt']
                else:
                    rtypelist = [resulttype]

            # Navigation ordering (map wlt to single 'pairwise' nav item)
            nav_base = ['FPTP', 'IRV', 'approval', 'STAR', 'wlt']
            nav_order = get_method_ordering(jabmod, nav_base)
            nav_methods = ['pairwise' if m == 'wlt' else m for m in nav_order]

            return render_template('results-index.html',
                                   abifinput=fileentry['text'],
                                   abif_id=identifier,
                                   election_list=election_list,
                                   copewinnerstring=resblob.get('copewinnerstring', ''),
                                   copewinners=resblob.get('copewinners', []),
                                   dotsvg_html=resblob.get('dotsvg_html', ''),
                                   error_html=resblob.get('error_html'),
                                   IRV_dict=resblob.get('IRV_dict', {}),
                                   IRV_text=resblob.get('IRV_text', ''),
                                   IRV_candnames=jabmod.get(
                                       'candidates', {}) if jabmod else {},
                                   FPTP_candnames=jabmod.get(
                                       'candidates', {}) if jabmod else {},
                                   lower_abif_caption="Input",
                                   lower_abif_text=fileentry['text'],
                                   msgs=msgs,
                                   pairwise_dict=resblob.get('pairwise_dict', {}),
                                   pairwise_html=resblob.get('pairwise_html', ''),
                                   pairwise_summary_html=resblob.get('pairwise_summary_html', ''),
                                   resblob=resblob,
                                   result_types=rtypelist,
                                   STAR_html=resblob.get('STAR_html', ''),
                                   approval_result=resblob.get('approval_result', {}),
                                   approval_text=resblob.get('approval_text', ''),
                                   approval_notices=resblob.get('approval_notices', []),
                                   approval_candnames=jabmod.get(
                                       'candidates', {}) if jabmod else {},
                                   scorestardict=resblob.get('scorestardict', {}),
                                   colordict=resblob.get('colordict', {}),
                                   candidate_order=resblob.get(
                                       'candidate_order', []),
                                   webenv=webenv,
                                   debug_output=debug_output,
                                   debug_flag=webenv['debugFlag'],
                                   resulttype=resulttype,
                                   nav_methods=nav_methods,
                                   )
        else:
            msgs['pagetitle'] = "NOT FOUND"
            msgs['lede'] = (
                "I'm not sure what you're looking for, " +
                "but you shouldn't look here."
            )
            return render_template('not-found.html',
                                   identifier=identifier,
                                   msgs=msgs,
                                   webenv=webenv
                                   ), 404
    return cached_get_by_id(identifier, resulttype)


@app.route('/awt', methods=['POST'])
def awt_post():
    abifinput = request.form['abifinput']
    copewinners = None
    copewinnerstring = None
    webenv = WebEnv.wenvDict()
    WebEnv.sync_web_env()
    pairwise_dict = None
    pairwise_html = None
    dotsvg_html = None
    STAR_html = None
    scorestardict = None
    IRV_dict = None
    IRV_text = None
    debug_dict = {}
    debug_output = ""
    rtypelist = []
    resblob = {}  # Initialize resblob early
    consistent_colordict = {}  # Initialize colordict early
    candidate_order = []  # Initialize candidate_order early
    try:
        abifmodel = convert_abif_to_jabmod(abifinput,
                                           cleanws=True)
        error_html = None
    except ABIFVotelineException as e:
        abifmodel = None
        error_html = e.message
    if abifmodel:
        if request.form.get('include_dotsvg'):
            rtypelist.append('dot')
            copecount = full_copecount_from_abifmodel(abifmodel)
            copewinners = get_Copeland_winners(copecount)
            copewinnerstring = ", ".join(copewinners)
            debug_output += "\ncopecount:\n"
            debug_output += pformat(copecount)
            debug_output += "\ncopewinnerstring\n"
            debug_output += copewinnerstring
            debug_output += "\n"
            dotsvg_html = copecount_diagram(copecount, outformat='svg')
        else:
            copewinnerstring = None

        resconduit = conduits.ResultConduit(jabmod=abifmodel)
        resconduit = resconduit.update_FPTP_result(abifmodel)

        if request.form.get('include_pairtable'):
            rtypelist.append('wlt')
            resconduit = resconduit.update_pairwise_result(abifmodel)
            pairwise_dict = resconduit.resblob['pairwise_dict']
            wltdict = winlosstie_dict_from_pairdict(
                abifmodel['candidates'], pairwise_dict)
            pairwise_html = jinja_pairwise_snippet(
                abifmodel,
                pairwise_dict,
                wltdict,
                colordict=resconduit.resblob.get('colordict', {}),
                add_desc=True,
                svg_text=None,
                is_copeland_tie=resconduit.resblob.get('is_copeland_tie', False)
            )
            # Generate separate summary for proper positioning
            pairwise_summary_html = jinja_pairwise_summary_only(
                abifmodel,
                pairwise_dict,
                wltdict,
                colordict=resconduit.resblob.get('colordict', {}),
                is_copeland_tie=resconduit.resblob.get('is_copeland_tie', False),
                copewinnerstring=resconduit.resblob.get('copewinnerstring', ''),
                copewinners=resconduit.resblob.get('copewinners', [])
            )
        if request.form.get('include_FPTP'):
            rtypelist.append('FPTP')
            if True:
                FPTP_result = FPTP_result_from_abifmodel(abifmodel)
                FPTP_text = get_FPTP_report(abifmodel)
            # debug_output += "\nFPTP_result:\n"
            # debug_output += pformat(FPTP_result)
            # debug_output += "\n"
            # debug_output += pformat(FPTP_text)
            # debug_output += "\n"

        if request.form.get('include_IRV'):
            rtypelist.append('IRV')
            include_irv_extra = bool(request.form.get('include_irv_extra'))
            resconduit = resconduit.update_IRV_result(
                abifmodel, include_irv_extra=include_irv_extra)
            IRV_dict = resconduit.resblob['IRV_dict']
            IRV_text = resconduit.resblob['IRV_text']
            # Add candidate full names for template use
            IRV_candnames = abifmodel.get('candidates', {})
        # Create consistent candidate ordering based on FPTP results for colors (do this early)
        resblob = resconduit.resblob
        if abifmodel and 'FPTP_result' in resblob:
            # Sort candidates by FPTP vote count (descending)
            # The actual vote counts are in resblob['FPTP_result']['toppicks']
            fptp_toppicks = resblob['FPTP_result'].get('toppicks', {})
            if fptp_toppicks:
                # Handle cases where vote counts might be lists or other types
                def get_vote_count(item):
                    cand, votes = item
                    if isinstance(votes, (int, float)):
                        return votes
                    elif isinstance(votes, list) and len(votes) > 0:
                        return votes[0] if isinstance(votes[0], (int, float)) else 0
                    else:
                        return 0

                fptp_ordered_candidates = sorted(fptp_toppicks.items(),
                                                 key=get_vote_count, reverse=True)
                candidate_order = [
                    cand for cand, votes in fptp_ordered_candidates if cand is not None]
            else:
                # Fallback to alphabetical if no toppicks
                candidate_order = sorted(abifmodel['candidates'].keys())
        elif abifmodel:
            # Fallback to alphabetical if no FPTP results
            candidate_order = sorted(abifmodel['candidates'].keys())
        else:
            candidate_order = []

        # Generate single color dictionary for all voting systems
        # Use the same canonical ordering logic as conduits.py
        from conduits import get_canonical_candidate_order
        canonical_order = get_canonical_candidate_order(abifmodel)
        consistent_colordict = generate_candidate_colors(canonical_order)

        if request.form.get('include_STAR'):
            rtypelist.append('STAR')
            ratedjabmod = add_ratings_to_jabmod_votelines(abifmodel)
            resconduit = resconduit.update_STAR_result(ratedjabmod, consistent_colordict)
            STAR_html = jinja_scorestar_snippet(ratedjabmod)
            scorestardict = resconduit.resblob['scorestardict']

        if request.form.get('include_approval'):
            rtypelist.append('approval')
            resconduit = resconduit.update_approval_result(abifmodel)

        resblob = resconduit.resblob

        # Store the consistent colordict and candidate order
        resblob['colordict'] = consistent_colordict
        resblob['candidate_order'] = candidate_order

        # Apply dynamic method ordering to rtypelist
        if abifmodel and rtypelist:
            # Get optimal ordering for the selected methods
            ordered_methods = get_method_ordering(abifmodel, rtypelist)
            rtypelist = ordered_methods

    msgs = {}
    msgs['pagetitle'] = \
        f"{webenv['statusStr']}ABIF Electorama results"
    msgs['placeholder'] = \
        "Try other ABIF, or try tweaking your input (see below)...."
    webenv = WebEnv.wenvDict()

    return render_template('results-index.html',
                           abifinput=abifinput,
                           resblob=resblob,
                           copewinnerstring=copewinnerstring,
                           copewinners=copewinners if 'copewinners' in locals() else [],
                           pairwise_html=pairwise_html,
                           pairwise_summary_html=pairwise_summary_html if 'pairwise_summary_html' in locals() else '',
                           dotsvg_html=dotsvg_html,
                           result_types=rtypelist,
                           STAR_html=STAR_html,
                           approval_result=resblob.get('approval_result', {}),
                           approval_text=resblob.get('approval_text', ''),
                           IRV_dict=IRV_dict,
                           IRV_text=IRV_text,
                           IRV_candnames=abifmodel.get(
                               'candidates', {}) if abifmodel else {},
                           FPTP_candnames=abifmodel.get(
                               'candidates', {}) if abifmodel else {},
                           scorestardict=scorestardict,
                           colordict=resblob.get('colordict', {}),
                           candidate_order=resblob.get('candidate_order', []),
                           webenv=webenv,
                           error_html=error_html,
                           lower_abif_caption="Input",
                           lower_abif_text=escape(abifinput),
                           msgs=msgs,
                           debug_output=debug_output,
                           debug_flag=webenv['debugFlag'],
                           )


def find_free_port(host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description="Run the AWT server.")
    parser.add_argument("--port", type=int, help="Port to listen on")
    parser.add_argument("--debug", action="store_true",
                        help="Run in debug mode")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--profile-output", type=str, default=None,
                        help="If set, enables server-side profiling and writes .cprof to this path")
    parser.add_argument("--caching", choices=["none", "simple", "filesystem"], default="filesystem",
                        help="Caching backend: none (no cache), simple (in-memory), filesystem (default)")
    parser.add_argument("--cache-dir", type=str, default=os.path.join(tempfile.gettempdir(), 'awt_flask_cache'),
                        help="Directory for filesystem cache (default: system temp dir)")
    parser.add_argument("--cache-timeout", type=int, default=AWT_DEFAULT_CACHE_TIMEOUT,
                        help=f"Cache timeout in seconds (default: {AWT_DEFAULT_CACHE_TIMEOUT} seconds)")
    parser.add_argument("--cache-purge", action="store_true",
                        help="Purge all cache entries on startup")
    args = parser.parse_args()

    abif_catalog_init()

    # Set AWT_PROFILE_OUTPUT env var if --profile-output is given
    if args.profile_output:
        os.environ["AWT_PROFILE_OUTPUT"] = args.profile_output

    # Configure Flask-Caching
    if args.caching == "none":
        app.config['CACHE_TYPE'] = 'flask_caching.backends.NullCache'
    elif args.caching == "simple":
        app.config['CACHE_TYPE'] = 'flask_caching.backends.SimpleCache'
    elif args.caching == "filesystem":
        app.config['CACHE_TYPE'] = 'flask_caching.backends.FileSystemCache'
        app.config['CACHE_DIR'] = args.cache_dir
    app.config['CACHE_DEFAULT_TIMEOUT'] = args.cache_timeout

    cache.init_app(app)

    # Optional: purge cache at startup
    if args.cache_purge:
        try:
            cache.clear()
            cache_dir = app.config.get('CACHE_DIR')
            if cache_dir:
                print(f"[awt.py] Cache purged (dir={cache_dir})")
            else:
                print("[awt.py] Cache purged")
        except Exception as e:
            print(f"[awt.py] Cache purge failed: {e}")

    # If using filesystem cache, monkeypatch the cache backend to print cache hits and file paths
    if app.config['CACHE_TYPE'] == 'flask_caching.backends.FileSystemCache':
        monkeypatch_cache_get(app, cache)

    # Print cache configuration for debugging
    print(f"[awt.py] Flask-Caching: CACHE_TYPE={app.config['CACHE_TYPE']}")
    if app.config['CACHE_TYPE'] == 'flask_caching.backends.FileSystemCache':
        print(f"[awt.py] Flask-Caching: CACHE_DIR={app.config['CACHE_DIR']}")
    print(
        f"[awt.py] Flask-Caching: CACHE_DEFAULT_TIMEOUT={app.config['CACHE_DEFAULT_TIMEOUT']}")

    debug_mode = args.debug or os.environ.get("FLASK_ENV") == "development"
    if args.debug:
        os.environ["AWT_STATUS"] = "debug"
    host = args.host
    port = args.port or DEFAULT_PORT or find_free_port(host)
    print(f" * Starting: http://{host}:{port}/ (debug={debug_mode})")
    if host == "127.0.0.1":
        print("   Choose host '0.0.0.0' to bind to all local machine addresses")
    app.run(host=args.host, port=port, debug=debug_mode, use_reloader=False)


if __name__ == "__main__":
    main()
