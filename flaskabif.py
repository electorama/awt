#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect
from markupsafe import escape
from pathlib import Path
import json
import urllib

app = Flask(__name__)

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

def build_example_array():
    import yaml
    with open("examplelist.yml") as fp:
        retval = yaml.safe_load(fp)
    for i, f in enumerate(retval):
        retval[i]['text'] = escape(Path(TESTFILEDIR,
                                        f['filename']).read_text())
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


def my_webhost():
    my_url = request.url
    my_hostname = urllib.parse.urlsplit(my_url).hostname
    is_dev = ( my_hostname == "localhost" )
    if is_dev:
        my_statusstr = "(ldev) "
    else:
        my_statusstr = ""
    return {
        'is_dev':  is_dev,
        'my_statusstr': my_statusstr,
        'my_url': my_url,
        'my_hostname': my_hostname,
        }


@app.route('/')
def homepage():
    return redirect('/awt', code=302)


@app.route('/<toppage>', methods=['GET'])
def awt_get(toppage):
    msgs = {}
    msgs['pagetitle'] = \
        f"{my_webhost()['my_statusstr']}ABIF web tool (awt) on Electorama!"
    msgs['placeholder'] = \
        "Enter ABIF here, possibly using one of the examples below..."
    msgs['lede'] = "FIXME-flaskabif.py"
    match toppage:
        case "awt":
            return render_template('default-index.html',
                                   abifinput='',
                                   abiftool_output=None,
                                   example_array=build_example_array(),
                                   my_webhost=my_webhost(),
                                   rows=15,
                                   cols=80,
                                   msgs=msgs
                                   )
        case _:
            msgs['pagetitle'] = "NOT FOUND"
            msgs['lede'] = (
                "I'm not sure what you're looking for, " +
                "but you shouldn't look here."
            )
            return render_template('not-found.html',
                                   toppage=toppage,
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
            debug_dict = {}
            scoremodel = STAR_result_from_abifmodel(jabmod)
            debug_dict['scoremodel'] = scoremodel
            stardict = scaled_scores(jabmod, target_scale=50)
            debug_dict['starscale'] = \
                add_html_hints_to_stardict(debug_dict['scoremodel'], stardict)
            debug_output = json.dumps(debug_dict, indent=4)
            scorestardict=debug_dict
    msgs={}
    msgs['pagetitle'] = \
        f"{my_webhost()['my_statusstr']}ABIF Electorama results"
    msgs['placeholder'] = \
        "Try other ABIF, or try tweaking your input (see below)...."
    return render_template('results-index.html',
                           abifinput=abifinput,
                           pairwise_html=pairwise_html,
                           dotsvg_html=dotsvg_html,
                           STAR_html=STAR_html,
                           scorestardict=scorestardict,
                           my_webhost=my_webhost(),
                           error_html=error_html,
                           example_array=build_example_array(),
                           lower_abif_caption="Input",
                           lower_abif_text=escape(abifinput),
                           rows=15,
                           cols=80,
                           msgs=msgs,
                           debug_output=debug_output,
                           debug_flag=False,
                           )


if __name__ == '__main__':
    app.run(debug=True)

