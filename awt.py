#!/usr/bin/env python3
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
    add_ratings_to_jabmod_votelines
)
from flask import Flask, render_template, request, redirect, send_from_directory
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

AWT_DIR = os.path.expanduser('~/src/awt')
ABIFTOOL_DIR = os.path.expanduser('~/src/abiftool')
sys.path.append(ABIFTOOL_DIR)

TESTFILEDIR = Path(ABIFTOOL_DIR) / 'testdata'


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


def build_examplelist():
    '''Load the list of examples from abif_list.yml'''
    yampathlist = [
        Path(AWT_DIR, "abif_list.yml")
    ]

    retval = []
    for yampath in yampathlist:
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


def get_fileentry_from_examplelist(filekey, examplelist):
    """Returns entry of ABIF file matching filekey

    Args:
        examplelist: A list of dictionaries.
        filekey: The id value to lookup.

    Returns:
        The single index if exactly one match is found.
        None if no matches are found.
    """
    matchlist = [i for i, d in enumerate(examplelist)
                 if d['id'] == filekey]

    if not matchlist:
        return None
    elif len(matchlist) == 1:
        return examplelist[matchlist[0]]
    else:
        raise ValueError("Multiple file entries found with the same id.")


def get_fileentries_by_tag(tag, examplelist):
    """Returns ABIF file entries having given tag
    """
    retval = []
    for i, d in enumerate(examplelist):
        if d.get('tags') and tag and tag in d.get('tags'):
            retval.append(d)
    return retval


def get_all_tags_in_examplelist(examplelist):
    retval = set()
    for i, d in enumerate(examplelist):
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
        retval['starscaled'][candtok] = \
            round(retval['canddict'][candtok]['scaled_score'])
        selline = ", ".join(".s%02d" % j for j in range(
            curstart, retval['starscaled'][candtok] + curstart))
        retval['colorlines'][candtok] = f".g{i+1}"
        if selline:
            retval['colorlines'][candtok] += ", " + selline
        retval['colorlines'][candtok] += " { color: " + colors[i] + "; }"
        curstart += retval['starscaled'][candtok]
    try:
        retval['starratio'] = \
            round(retval['total_all_scores'] / retval['scaled_total'])
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
    file_array = build_examplelist()
    debug_flag = webenv['debugFlag']
    debug_output = webenv['debugIntro']

    if tag is not None:
        toppage = "tag"

    webenv['toppage'] = toppage

    mytagarray = sorted(get_all_tags_in_examplelist(file_array),
                        key=str.casefold)
    match toppage:
        case "awt":
            retval = render_template('default-index.html',
                                     abifinput='',
                                     abiftool_output=None,
                                     main_file_array=file_array[0:5],
                                     other_files=file_array[5:],
                                     example_list=file_array,
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
                tag_file_array = get_fileentries_by_tag(tag, file_array)
                debug_output += f"{tag=}"
                retval = render_template('default-index.html',
                                         abifinput='',
                                         abiftool_output=None,
                                         main_file_array=tag_file_array[0:5],
                                         other_files=tag_file_array[5:],
                                         example_list=file_array,
                                         webenv=webenv,
                                         msgs=msgs,
                                         debug_output=debug_output,
                                         debug_flag=debug_flag,
                                         tag=tag,
                                         tagarray=mytagarray
                                         )
            else:
                retval = render_template('tag-index.html',
                                         example_list=file_array,
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


@app.route('/id/<identifier>/dot/svg')
def get_svg_dotdiagram(identifier):
    '''FIXME FIXME July 2024'''
    examplelist = build_examplelist()
    fileentry = get_fileentry_from_examplelist(identifier, examplelist)
    jabmod = convert_abif_to_jabmod(fileentry['text'], cleanws=True)
    copecount = full_copecount_from_abifmodel(jabmod)
    return copecount_diagram(copecount, outformat='svg')


@app.route('/id/<identifier>', methods=['GET'])
@app.route('/id/<identifier>/<resulttype>', methods=['GET'])
def get_by_id(identifier, resulttype=None):
    '''Populate template variables based on id of the election

    As of May 2025, most variables should be populated via a
    "ResultConduit" object.  Prior to May 2025, the awt templates
    needed an ad hoc collection of variables, and probably still will
    into the future.

    '''
    rtypemap = {
        'wlt': 'win-loss-tie (pairwise) results',
        'dot': 'pairwise diagram',
        'IRV': 'RCV/IRV results',
        'STAR': 'STAR results',
        'FPTP': 'choose-one (FPTP) results'
    }
    msgs = {}
    msgs['placeholder'] = \
        "Enter ABIF here, possibly using one of the examples below..."
    examplelist = build_examplelist()
    webenv = WebEnv.wenvDict()
    debug_output = webenv.get('debugIntro') or ""
    WebEnv.sync_web_env()
    fileentry = get_fileentry_from_examplelist(identifier, examplelist)
    if fileentry:
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

        resconduit = conduits.ResultConduit(jabmod=jabmod)
        resconduit = resconduit.update_FPTP_result(jabmod)
        resconduit = resconduit.update_IRV_result(jabmod)
        resconduit = resconduit.update_pairwise_result(jabmod)
        ratedjabmod = add_ratings_to_jabmod_votelines(jabmod)
        resconduit = resconduit.update_STAR_result(ratedjabmod)
        resblob = resconduit.resblob
        if not resulttype or resulttype == 'all':
            rtypelist = ['dot', 'FPTP', 'IRV', 'STAR', 'wlt']
        else:
            rtypelist = [resulttype]

        debug_output += pformat(resblob.keys()) + "\n"
        debug_output += f"result_types: {rtypelist}\n"

        return render_template('results-index.html',
                               abifinput=fileentry['text'],
                               abif_id=identifier,
                               example_list=examplelist,
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


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description="Run the AWT server.")
    parser.add_argument("--port", type=int, help="Port to listen on")
    parser.add_argument("--debug", action="store_true",
                        help="Run in debug mode")
    args = parser.parse_args()

    port = args.port or DEFAULT_PORT or find_free_port()
    debug_mode = args.debug or os.environ.get("FLASK_ENV") == "development"

    print(f"Running on http://127.0.0.1:{port}/ (debug={debug_mode})")
    app.run(host="127.0.0.1", port=port, debug=debug_mode, use_reloader=False)


if __name__ == "__main__":
    main()
