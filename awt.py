#!/usr/bin/env python3
import tempfile
import logging
from abiflib import (
    convert_abif_to_jabmod,
    htmltable_pairwise_and_winlosstie,
    get_Copeland_winners,
    html_score_and_star,
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
from flask import Flask, render_template, request, redirect, send_from_directory, url_for
from flask_caching import Cache
from markupsafe import escape
from pathlib import Path
from pprint import pformat
import argparse
import colorsys
import conduits
import os
import re
import socket
import sys
import threading
import urllib
import yaml
from dotenv import load_dotenv


# --- Cache utility functions ---
from cache_awt import (
    cache_key_from_request,
    cache_file_from_key,
    log_cache_hit,
    purge_cache_entry,
    monkeypatch_cache_get
)

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
    app.config['CACHE_TYPE'] = 'null'
elif wsgi_cache_type == "simple":
    app.config['CACHE_TYPE'] = 'simple'
else:  # filesystem
    app.config['CACHE_TYPE'] = 'filesystem'
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
sys.path.append(ABIFTOOL_DIR)
TESTFILEDIR = Path(ABIFTOOL_DIR) / 'testdata'

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


def generate_golden_angle_palette(count=250, start_hex='#d0ffce',
                                  initial_colors=None,
                                  master_list_size=250):
    """Generates a list of visually distinct colors, with an option for a custom start.

    If an `initial_colors` list is provided, it will be used as the
    start of the palette, and seed the rest of the list from the hue
    of the last color in that list.  Otherwise, gnerate a full palette
    starting from `start_hex` using the golden angle (137.5 degrees)
    for hue rotation. Saturation and value are adjusted based on a
    `master_list_size` to ensure colors are always consistent
    regardless of the total count requested.

    Args:
        count (int): The total number of colors to generate.
        start_hex (str): The starting hex color if `initial_colors` is not given.
        initial_colors (list[str], optional): A list of hex colors to start the
                                              palette with. Defaults to None.
        master_list_size (int): The reference size for consistent generation.
    Returns:
        list[str]: A list of color strings in hex format.

    """
    colors_hex = []
    start_index = 0

    if initial_colors:
        # Start with the provided hand-picked colors.
        colors_hex.extend(initial_colors)
        if count <= len(colors_hex):
            return colors_hex[:count]

        # The algorithm will start generating after the initial colors.
        start_index = len(colors_hex)
        # The new starting point is the last of the initial colors.
        start_hex = initial_colors[-1]

    if not start_hex.startswith('#') or len(start_hex) != 7:
        raise ValueError("start_hex must be in #RRGGBB format.")

    # --- 1. Convert the starting hex color to its HSV representation ---
    start_r = int(start_hex[1:3], 16) / 255.0
    start_g = int(start_hex[3:5], 16) / 255.0
    start_b = int(start_hex[5:7], 16) / 255.0
    start_h, start_s, start_v = colorsys.rgb_to_hsv(start_r, start_g, start_b)

    # --- 2. Generate the rest of the palette ---
    golden_angle_increment = 137.5 / 360.0

    # Loop from the start_index to the desired total count.
    for i in range(start_index, count):
        # The hue jump is based on the color's position relative to the start.
        # This ensures the spiral continues correctly from the initial colors.
        hue_jump_index = i - start_index
        hue = (start_h + (hue_jump_index + 1) * golden_angle_increment) % 1.0

        # Vary saturation and value based on the color's absolute index.
        # This maintains consistency across different list lengths.
        saturation = start_s + (i / master_list_size) * 0.1
        value = start_v - (i / master_list_size) * 0.15

        # Ensure saturation and value stay within the valid 0-1 range.
        saturation = max(0, min(1, saturation))
        value = max(0, min(1, value))

        # Convert the new HSV color back to RGB.
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)

        # Convert RGB to a hex string.
        hex_color = '#{:02x}{:02x}{:02x}'.format(
            int(r * 255), int(g * 255), int(b * 255)
        )
        colors_hex.append(hex_color)

    return colors_hex


def add_html_hints_to_stardict(scores, stardict):
    retval = stardict
    retval['starscaled'] = {}
    retval['colordict'] = {}
    retval['colorlines'] = {}
    colors = generate_golden_angle_palette(count=len(scores['ranklist']),
                                           initial_colors=[
                                               '#d0ffce', '#cee1ff', '#ffcece', '#ffeab9']
                                           )

    curstart = 1
    for i, candtok in enumerate(scores['ranklist']):
        retval['colordict'][candtok] = colors[i]
        retval['starscaled'][candtok] = round(
            retval['canddict'][candtok]['scaled_score'])
        selline = ", ".join(".s%02d" % j for j in range(
            curstart, retval['starscaled'][candtok] + curstart))
        retval['colorlines'][candtok] = f".g{i + 1}"
        if selline:
            retval['colorlines'][candtok] += ", " + selline
        retval['colorlines'][candtok] += " { color: " + colors[i] + "; }"
        curstart += retval['starscaled'][candtok]
    try:
        retval['starratio'] = round(
            retval['total_all_scores'] / retval['scaled_total'])
    except ZeroDivisionError:
        retval['starratio'] = 0
    return retval


@app.route('/')
def homepage():
    return redirect('/awt', code=302)


@app.route('/tag/<tag>', methods=['GET'])
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

# Route for '/id' with no identifier


@app.route('/id', methods=['GET'])
@cache.cached(timeout=AWT_DEFAULT_CACHE_TIMEOUT, query_string=True)
def id_no_identifier():
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
        import logging
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
            'IRV': 'RCV/IRV results',
            'STAR': 'STAR results',
            'FPTP': 'choose-one (FPTP) results'
        }
        print(
            f" 00001 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id({identifier=} {resulttype=})")
        debug_output += f" 00001 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id({identifier=} {resulttype=})\n"
        msgs = {}
        msgs['placeholder'] = "Enter ABIF here, possibly using one of the examples below..."
        election_list = build_election_list()
        fileentry = get_fileentry_from_election_list(identifier, election_list)
        print(
            f" 00002 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
        debug_output += f" 00002 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"

        # --- Server-side profiling if AWT_PROFILE_OUTPUT is set ---
        prof = None
        cprof_path = os.environ.get('AWT_PROFILE_OUTPUT')
        if cprof_path:
            prof = cProfile.Profile()
            prof.enable()

        if fileentry:
            print(
                f" 00003 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
            debug_output += f" 00003 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"
            msgs['pagetitle'] = f"{webenv['statusStr']}{fileentry['title']}"
            msgs['lede'] = (
                f"Below is the ABIF from the \"{fileentry['id']}\" election" +
                f" ({fileentry['title']})"
            )
            msgs['results_name'] = rtypemap.get(resulttype)
            msgs['taglist'] = fileentry['taglist']

            try:
                jabmod = convert_abif_to_jabmod(fileentry['text'])
                error_html = None
            except ABIFVotelineException as e:
                jabmod = None
                error_html = e.message

            import time
            print(
                f" 00004 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
            debug_output += f" 00004 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"
            resconduit = conduits.ResultConduit(jabmod=jabmod)

            t_fptp = time.time()
            resconduit = resconduit.update_FPTP_result(jabmod)
            fptp_time = time.time() - t_fptp
            print(
                f" 00006 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [FPTP: {fptp_time:.2f}s]")
            debug_output += f" 00006 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [FPTP: {fptp_time:.2f}s]\n"

            t_irv = time.time()
            resconduit = resconduit.update_IRV_result(jabmod)
            irv_time = time.time() - t_irv
            print(
                f" 00007 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [IRV: {irv_time:.2f}s]")
            debug_output += f" 00007 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [IRV: {irv_time:.2f}s]\n"

            t_pairwise = time.time()
            resconduit = resconduit.update_pairwise_result(jabmod)
            pairwise_time = time.time() - t_pairwise
            print(
                f" 00008 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [Pairwise: {pairwise_time:.2f}s]")
            debug_output += f" 00008 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [Pairwise: {pairwise_time:.2f}s]\n"

            t_starprep = time.time()
            ratedjabmod = add_ratings_to_jabmod_votelines(jabmod)
            starprep_time = time.time() - t_starprep
            print(
                f" 00009 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR prep: {starprep_time:.2f}s]")
            debug_output += f" 00009 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR prep: {starprep_time:.2f}s]\n"

            t_star = time.time()
            resconduit = resconduit.update_STAR_result(ratedjabmod)
            star_time = time.time() - t_star
            print(
                f" 00010 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR: {star_time:.2f}s]")
            debug_output += f" 00010 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id() [STAR: {star_time:.2f}s]\n"
            resblob = resconduit.resblob
            if not resulttype or resulttype == 'all':
                rtypelist = ['dot', 'FPTP', 'IRV', 'STAR', 'wlt']
            else:
                rtypelist = [resulttype]

            debug_output += pformat(resblob.keys()) + "\n"
            debug_output += f"result_types: {rtypelist}\n"

            print(
                f" 00011 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()")
            debug_output += f" 00011 ---->  [{datetime.datetime.now():%d/%b/%Y %H:%M:%S}] get_by_id()\n"
            if prof:
                prof.disable()
                prof.dump_stats(cprof_path)
                print(f"[SERVER PROFILE] Profile saved to {cprof_path}")
            return render_template('results-index.html',
                                   abifinput=fileentry['text'],
                                   abif_id=identifier,
                                   election_list=election_list,
                                   copewinnerstring=resblob['copewinnerstring'],
                                   dotsvg_html=resblob['dotsvg_html'],
                                   error_html=resblob.get('error_html'),
                                   IRV_dict=resblob['IRV_dict'],
                                   IRV_text=resblob['IRV_text'],
                                   lower_abif_caption="Input",
                                   lower_abif_text=fileentry['text'],
                                   msgs=msgs,
                                   pairwise_dict=resblob['pairwise_dict'],
                                   pairwise_html=resblob['pairwise_html'],
                                   resblob=resblob,
                                   result_types=rtypelist,
                                   STAR_html=resblob['STAR_html'],
                                   scorestardict=resblob['scorestardict'],
                                   webenv=webenv,
                                   debug_output=debug_output,
                                   debug_flag=webenv['debugFlag'],
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
            copewinnerstring = ", ".join(get_Copeland_winners(copecount))
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
            pairwise_dict = pairwise_count_dict(abifmodel)
            debug_output += "\npairwise_dict:\n"
            debug_output += pformat(pairwise_dict)
            debug_output += "\n"
            pairwise_html = htmltable_pairwise_and_winlosstie(abifmodel,
                                                              snippet=True,
                                                              validate=True,
                                                              modlimit=2500)
            resconduit = resconduit.update_pairwise_result(abifmodel)
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
            resconduit = resconduit.update_IRV_result(abifmodel)
            IRV_dict = resconduit.resblob['IRV_dict']
            IRV_text = resconduit.resblob['IRV_text']
        if request.form.get('include_STAR'):
            rtypelist.append('STAR')
            ratedjabmod = add_ratings_to_jabmod_votelines(abifmodel)
            resconduit = resconduit.update_STAR_result(ratedjabmod)
            STAR_html = resconduit.resblob['STAR_html']
            scorestardict = resconduit.resblob['scorestardict']
        resblob = resconduit.resblob

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
                           pairwise_html=pairwise_html,
                           dotsvg_html=dotsvg_html,
                           result_types=rtypelist,
                           STAR_html=STAR_html,
                           IRV_dict=IRV_dict,
                           IRV_text=IRV_text,
                           scorestardict=scorestardict,
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
    args = parser.parse_args()

    abif_catalog_init()

    # Set AWT_PROFILE_OUTPUT env var if --profile-output is given
    if args.profile_output:
        os.environ["AWT_PROFILE_OUTPUT"] = args.profile_output

    # Configure Flask-Caching
    if args.caching == "none":
        app.config['CACHE_TYPE'] = 'null'
    elif args.caching == "simple":
        app.config['CACHE_TYPE'] = 'simple'
    elif args.caching == "filesystem":
        app.config['CACHE_TYPE'] = 'filesystem'
        app.config['CACHE_DIR'] = args.cache_dir
    app.config['CACHE_DEFAULT_TIMEOUT'] = args.cache_timeout

    cache.init_app(app)

    # If using filesystem cache, monkeypatch the cache backend to print cache hits and file paths
    if app.config['CACHE_TYPE'] == 'filesystem':
        monkeypatch_cache_get(app, cache)

    # Print cache configuration for debugging
    print(f"[awt.py] Flask-Caching: CACHE_TYPE={app.config['CACHE_TYPE']}")
    if app.config['CACHE_TYPE'] == 'filesystem':
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
