#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect
from markupsafe import escape
from pathlib import Path
import json
import re
import urllib
import yaml

app = Flask(__name__)
SCRIPTDIR = '/home/robla/tags/awt'
TESTFILEDIR='/home/robla/tags/abiftool/testdata'

from abiflib import (
    convert_abif_to_jabmod,
    htmltable_pairwise_and_winlosstie,
    html_score_and_star,
    ABIFVotelineException,
    full_copecount_from_abifmodel,
    copecount_diagram,
    STAR_result_from_abifmodel,
    scaled_scores
    )


class WebEnv:
    __env = {}

    __env['isDev'] = False
    __env['debugFlag'] = True
    __env['statusStr'] = "(WEBDEV/FIXME) "
    __env['inputRows'] = 70
    __env['inputCols'] = 30

    @staticmethod
    def wenv(name):
        return WebEnv.__env[name]

    @staticmethod
    def wenvDict():
        return WebEnv.__env

    @staticmethod
    def set_web_env():
        __env['req_url'] = request.url
        __env['hostname'] = urllib.parse.urlsplit(request.url).hostname
        #__env['isDev'] = ( my_hostname == "localhost" )


def my_webhost():
    myenv = WebEnv.wenvDict()
    if myenv['isDev']:
        my_statusstr = "(ldev) "
    else:
        my_statusstr = ""

    my_url = request.url
    my_hostname = urllib.parse.urlsplit(my_url).hostname
    is_dev = ( my_hostname == "localhost" )
    is_dev = False
    return {
        'is_dev': myenv['isDev'],
        'debugFlag': myenv['debugFlag'],
        'my_statusstr': myenv['statusStr'],
        'inputRows': myenv['inputRows'],
        'inputCols': myenv['inputCols'],
        'my_url': my_url,
        'my_hostname': my_hostname,
    }


def my_ctrldata():
    return {
        'boxrows': 12,
        'boxcols': 80,
        'debugflag': True
    }


def build_examplelist():
    yampathlist = [
        Path(SCRIPTDIR, "examplelist.yml")
        ]

    retval = []
    for yampath in yampathlist:
        with open(yampath) as fp:
            retval.extend(yaml.safe_load(fp))

    for i, f in enumerate(retval):
        retval[i]['text'] = Path(TESTFILEDIR, f['filename']).read_text()
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


@app.route('/')
def homepage():
    return redirect('/awt', code=302)


@app.route('/tag/<tag>', methods=['GET'])
@app.route('/<toppage>', methods=['GET'])
def awt_get(toppage=None, tag=None):
    msgs = {}
    msgs['pagetitle'] = \
        f"{my_webhost()['my_statusstr']}ABIF web tool (awt) on Electorama!"
    msgs['placeholder'] = \
        "Enter ABIF here, possibly using one of the examples below..."
    msgs['lede'] = "FIXME-flaskabif.py"
    ctrldata = my_ctrldata()
    file_array = build_examplelist()
    debug_flag = ctrldata['debugflag']
    debug_output = "DEBUG OUTPUT:\n"

    if tag is not None:
        toppage = "tag"

    ctrldata['toppage'] = toppage
    debug_output += f"{ctrldata=}"

    match toppage:
        case "awt":
            retval = render_template('default-index.html',
                                     abifinput='',
                                     abiftool_output=None,
                                     main_file_array=file_array[0:5],
                                     other_files=file_array[5:],
                                     my_webhost=my_webhost(),
                                     ctrldata=ctrldata,
                                     msgs=msgs,
                                     debug_output=debug_output,
                                     debug_flag=debug_flag,
                                     )
        case "tag":
            if tag:
                tag_file_array = get_fileentries_by_tag(tag, file_array)
                debug_output += f"{tag=}"
                retval = render_template('default-index.html',
                                         abifinput='',
                                         abiftool_output=None,
                                         main_file_array=tag_file_array[0:5],
                                         other_files=tag_file_array[5:],
                                         my_webhost=my_webhost(),
                                         ctrldata=ctrldata,
                                         msgs=msgs,
                                         debug_output=debug_output,
                                         debug_flag=debug_flag,
                                         )
            else:
                retval = render_template('tag-index.html',
                                         tagarray = sorted(get_all_tags_in_examplelist(file_array),
                                                           key=str.casefold),
                                         my_webhost=my_webhost(),
                                         msgs=msgs
                                         )
                                         
        case _:
            msgs['pagetitle'] = "NOT FOUND"
            msgs['lede'] = (
                "I'm not sure what you're looking for, " +
                "but you shouldn't look here."
            )
            retval = (render_template('not-found.html',
                                      toppage=toppage,
                                      my_webhost=my_webhost(),
                                      msgs=msgs,
                                      debug_output=debug_output,
                                      debug_flag=debug_flag,
                                      ), 404)
    return retval


@app.route('/id/<identifier>', methods=['GET'])
def get_by_id(identifier):
    msgs = {}
    debug_output = "DEBUG OUTPUT:\n"
    msgs['placeholder'] = \
        "Enter ABIF here, possibly using one of the examples below..."
    examplelist = build_examplelist()
    ctrldata = my_ctrldata()
    fileentry = get_fileentry_from_examplelist(identifier, examplelist)
    if fileentry:
        msgs['pagetitle'] = f"{fileentry['title']}"
        msgs['lede'] = (
            f"Below is the ABIF from the \"{fileentry['id']}\" election" +
            f" ({fileentry['title']})"
        )
        msgs['results_lede'] = (
            f"The pairwise results of {fileentry['id']} are below, and " +
            f"can be edited in the field above."
        )
        try:
            abifmodel = convert_abif_to_jabmod(fileentry['text'],
                                               cleanws = True)
            error_html = None
        except ABIFVotelineException as e:
            abifmodel = None
            error_html = e.message
        pairwise_html = htmltable_pairwise_and_winlosstie(abifmodel,
                                                          add_desc = False,
                                                          snippet = True,
                                                          validate = True,
                                                          modlimit = 2500)
        return render_template('results-index.html',
                               abifinput=fileentry['text'],
                               pairwise_html=pairwise_html,
                               my_webhost=my_webhost(),
                               error_html=error_html,
                               lower_abif_caption="Input",
                               lower_abif_text=fileentry['text'],
                               ctrldata=ctrldata,
                               msgs=msgs,
                               debug_output=debug_output,
                               debug_flag=ctrldata['debugflag'],
                               )
    else:
        msgs['pagetitle'] = "NOT FOUND"
        msgs['lede'] = (
            "I'm not sure what you're looking for, " +
            "but you shouldn't look here."
        )
        return render_template('not-found.html',
                               identifier=identifier,
                               my_webhost=my_webhost(),
                               msgs=msgs
                               ), 404


@app.route('/awt', methods=['POST'])
def awt_post():
    abifinput = ""
    abifinput = request.form['abifinput']
    pairwise_html = None
    dotsvg_html = None
    STAR_html = None
    debug_dict = {}
    debug_output = ""
    try:
        abifmodel = convert_abif_to_jabmod(abifinput,
                                           cleanws = True)
        error_html = None
    except ABIFVotelineException as e:
        abifmodel = None
        error_html = e.message
    if abifmodel:
        if request.form.get('include_dotsvg'):
            copecount = full_copecount_from_abifmodel(abifmodel)
            dotsvg_html = copecount_diagram(copecount, outformat='svg')
        if request.form.get('include_pairtable'):
            pairwise_html = htmltable_pairwise_and_winlosstie(abifmodel,
                                                              snippet = True,
                                                              validate = True,
                                                              modlimit = 2500)
        if request.form.get('include_STAR'):
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
    msgs={}
    msgs['pagetitle'] = \
        f"{my_webhost()['my_statusstr']}ABIF Electorama results"
    msgs['placeholder'] = \
        "Try other ABIF, or try tweaking your input (see below)...."
    ctrldata=my_ctrldata()
    return render_template('results-index.html',
                           abifinput=abifinput,
                           pairwise_html=pairwise_html,
                           dotsvg_html=dotsvg_html,
                           STAR_html=STAR_html,
                           scorestardict=scorestardict,
                           my_webhost=my_webhost(),
                           error_html=error_html,
                           lower_abif_caption="Input",
                           lower_abif_text=escape(abifinput),
                           ctrldata=ctrldata,
                           msgs=msgs,
                           debug_output=debug_output,
                           debug_flag=ctrldata['debugflag'],
                           )


if __name__ == '__main__':
    app.run(debug=True)

