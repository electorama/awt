#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect
from markupsafe import escape
from pathlib import Path
from pprint import pformat
import json
import os
import re
import sys
import urllib
import yaml

app = Flask(__name__)
AWT_DIR = os.getenv('AWT_DIR')
ABIFTOOL_DIR = os.getenv('ABIFTOOL_DIR')
HOME_DIR = os.getenv('HOME')
sys.path.append(ABIFTOOL_DIR)

if not AWT_DIR:
    AWT_DIR = Path(HOME_DIR) / 'awt'
if not ABIFTOOL_DIR:
    ABIFTOOL_DIR = Path(HOME_DIR) / 'abiftool'

TESTFILEDIR = Path(ABIFTOOL_DIR) / 'testdata'

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
    pairwise_count_dict,
    STAR_result_from_abifmodel,
    scaled_scores
    )

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
        WebEnv.__env['debugFlag'] = ( os.getenv('AWT_STATUS') == "debug" )
        WebEnv.__env['debugIntro'] = "Set AWT_STATUS=prod to turn off debug mode\n"

        if WebEnv.__env['debugFlag']:
            WebEnv.__env['statusStr'] = "(DEBUG) "
            WebEnv.__env['environ'] = os.environ
        else:
            WebEnv.__env['statusStr'] = ""


def build_examplelist():
    '''Load the list of examples from examplelist.yml'''
    yampathlist = [
        Path(AWT_DIR, "examplelist.yml")
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
            retval[i]['taglist'] = [ "UNTAGGED" ]

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


def add_html_hints_to_stardict(scores, stardict):
    retval = stardict
    retval['starscaled'] = {}
    retval['colordict'] = {}
    retval['colorlines'] = {}
    colors0 = ['#d0ffce', '#cee1ff', '#ffcece', '#ffeab9']
    colors1 = ['#cc6666', '#ccc666', '#70cc66', '#66ccbb', '#667bcc', '#b166cc', '#cc6686', '#cc8666']
    colors2 = ['#b1cc66', '#66cc7b', '#66bbcc', '#7066cc', '#cc66c6', '#cc6666', '#cca666', '#90cc66']
    colors3 = ['#66cc9b', '#669bcc', '#9066cc', '#cc66a6']
    colors = colors0 + colors1 + colors2 + colors3

    curstart = 1
    for i, candtok in enumerate(scores['ranklist']):
        retval['colordict'][candtok] = colors[i]
        retval['starscaled'][candtok] = \
            round(retval['canddict'][candtok]['scaled_score'])
        selline = ", ".join(".s%02d" % j for j in range(
            curstart, retval['starscaled'][candtok] + curstart))
        retval['colorlines'][candtok] = \
            f".g{i+1}, " + selline + " { color: " + colors[i] + "; }"
        curstart += retval['starscaled'][candtok]
    retval['starratio'] = \
        round(retval['total_all_scores'] / retval['scaled_total'])
    return retval


def _get_jabmod_to_eledata(abifstr, stuff_to_get=['dot', 'wlt', 'IRV', 'STAR']):
    returndata = {}
    try:
        jabmod = convert_abif_to_jabmod(abifstr, cleanws=True, add_ratings=True)
        error_html = None
    except ABIFVotelineException as e:
        jabmod = None
        error_html = e.message
    returndata['jabmod'] = jabmod
    returndata['error_html'] = error_html

    if 'dot' in stuff_to_get or 'wlt' in stuff_to_get:
        copecount = full_copecount_from_abifmodel(jabmod)
        cwstring = ", ".join(get_Copeland_winners(copecount))
        returndata['copewinnerstring'] = cwstring
    if 'dot' in stuff_to_get:
        returndata['dotsvg_html'] = copecount_diagram(copecount, outformat='svg')

    if 'wlt' in stuff_to_get:
        returndata['pairwise_dict'] = pairwise_count_dict(jabmod)
        returndata['pairwise_html'] = htmltable_pairwise_and_winlosstie(jabmod,
                                                                        snippet = True,
                                                                        validate = True,
                                                                        modlimit = 2500)
    if 'STAR' in stuff_to_get:
        scorestar = {}
        returndata['STAR_html'] = html_score_and_star(jabmod)
        scoremodel = STAR_result_from_abifmodel(jabmod)
        scorestar['scoremodel'] = scoremodel
        stardict = scaled_scores(jabmod, target_scale=50)
        scorestar['starscale'] = \
            add_html_hints_to_stardict(scorestar['scoremodel'], stardict)
        # scorestar['star_lede'] = 'STAR results follow....'
        if jabmod['metadata'].get('is_ranking_to_rating') == True:
            scorestar['star_foot'] = \
                'NOTE: Since ratings or stars are not present in the provided ballots, ' + \
                'allocated stars are estimated using a Borda-like formula.'
        returndata['scorestardict']=scorestar
    if 'IRV' in stuff_to_get:
        returndata['IRV_dict'] = IRV_dict_from_jabmod(jabmod)
        returndata['IRV_text'] = get_IRV_report(returndata['IRV_dict'])
    return returndata


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
                                     tagarray = mytagarray,
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
                                         tag = tag,
                                         tagarray = mytagarray
                                         )
            else:
                retval = render_template('tag-index.html',
                                         example_list=file_array,
                                         webenv=webenv,
                                         msgs=msgs,
                                         tag = tag,
                                         tagarray = mytagarray
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
    jabmod = convert_abif_to_jabmod(fileentry['text'], cleanws = True)
    copecount = full_copecount_from_abifmodel(jabmod)
    return copecount_diagram(copecount, outformat='svg')

@app.route('/id/<identifier>', methods=['GET'])
@app.route('/id/<identifier>/<resulttype>', methods=['GET'])
def get_by_id(identifier, resulttype=None):
    rtypemap = {
        'wlt': 'win-loss-tie (pairwise) results',
        'dot': 'pairwise diagram',
        'IRV': 'RCV/IRV results',
        'STAR': 'STAR results'
    }
    if not resulttype or resulttype == 'all':
        rtypelist = ['wlt', 'dot', 'IRV', 'STAR']
    else:
        rtypelist = [ resulttype ]
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
        # eledata was added 2024-06-19 as data to feed to templates
        # creating pages, and hopefully leads to deprecating/replacing
        # large chunks of code and hopefully simplifies passing data
        # to templates over the long term.
        eledata = _get_jabmod_to_eledata(fileentry['text'])
        debug_output += pformat(eledata.keys()) + "\n"
        debug_output += f"result_types: {rtypelist}\n"

        return render_template('results-index.html',
                               abifinput=fileentry['text'],
                               abif_id=identifier,
                               example_list=examplelist,
                               copewinnerstring=eledata['copewinnerstring'],
                               dotsvg_html=eledata['dotsvg_html'],
                               eledata=eledata,
                               error_html=eledata['error_html'],
                               IRV_dict=eledata['IRV_dict'],
                               IRV_text=eledata['IRV_text'],
                               lower_abif_caption="Input",
                               lower_abif_text=fileentry['text'],
                               msgs=msgs,
                               pairwise_dict=eledata['pairwise_dict'],
                               pairwise_html=eledata['pairwise_html'],
                               result_types=rtypelist,
                               STAR_html=eledata['STAR_html'],
                               scorestardict=eledata['scorestardict'],
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
    abifinput = ""
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
                                           cleanws = True)
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
        if request.form.get('include_pairtable'):
            rtypelist.append('wlt')
            pairwise_dict = pairwise_count_dict(abifmodel)
            debug_output += "\npairwise_dict:\n"
            debug_output += pformat(pairwise_dict)
            debug_output += "\n"
            pairwise_html = htmltable_pairwise_and_winlosstie(abifmodel,
                                                              snippet = True,
                                                              validate = True,
                                                              modlimit = 2500)
        if request.form.get('include_STAR'):
            rtypelist.append('STAR')
            jabmod = convert_abif_to_jabmod(abifinput,
                                            cleanws = True,
                                            add_ratings = True)
            STAR_html = html_score_and_star(jabmod)
            scoremodel = STAR_result_from_abifmodel(jabmod)
            debug_dict['scoremodel'] = scoremodel
            stardict = scaled_scores(jabmod, target_scale=50)
            debug_dict['starscale'] = \
                add_html_hints_to_stardict(debug_dict['scoremodel'], stardict)
            scorestardict=debug_dict
        if request.form.get('include_IRV'):
            rtypelist.append('IRV')
            jabmod = convert_abif_to_jabmod(abifinput,
                                            cleanws = True,
                                            add_ratings = True)
            IRV_dict = IRV_dict_from_jabmod(jabmod)
            IRV_text = get_IRV_report(IRV_dict)
            debug_output += "\nIRV_dict:\n"
            debug_output += pformat(IRV_dict)
            debug_output += "\n"

    msgs={}
    msgs['pagetitle'] = \
        f"{webenv['statusStr']}ABIF Electorama results"
    msgs['placeholder'] = \
        "Try other ABIF, or try tweaking your input (see below)...."
    webenv = WebEnv.wenvDict()
    return render_template('results-index.html',
                           abifinput=abifinput,
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


if __name__ == '__main__':
    app.run(debug=True, port=0)
