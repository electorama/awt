#!/usr/bin/env python3
from flask import Flask, render_template, request
from markupsafe import escape
from pathlib import Path

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
    retval = [
        {'filename': 'tenn-example/tennessee-example-simple.abif',
         'title': 'Simple example (Tennessee capitol)',
         'desc': 'This example is compatible with many web election tools.'},
        {'filename': 'tenn-example/tennessee-example-scores.abif',
         'title': 'More complicated example (Tennessee capitol)',
         'desc': ( 'This example is a more ornate example, which shows off ' +
                   'how to embed metadata in an ABIF file, as well as' +
                   'scores for the competing candidates.' ) },
        {'filename': 'burl2009/burl2009.abif',
         'title': 'A real-world example (Burlington)',
         'desc': ( 'This example is based on the electoral results ' +
                   'from the Burlington mayoral race in 2009.') },
        {'filename': 'tenn-example/tennessee-example-STAR.abif',
         'title': 'Example with STAR voting (Tennessee capitol)',
         'desc': ( 'This is the TN capitol example with embedded scores' +
                   '(with 0-5 "stars").') }
         ]
    for i, f in enumerate(retval):
        retval[i]['text'] = escape(Path(TESTFILEDIR,
                                        f['filename']).read_text())
    return retval


@app.route('/', methods=['GET'])
def index_get():
    placeholder = "Enter ABIF here, possibly using one of the examples below..."
    return render_template('default-index.html',
                           abifinput='',
                           abiftool_output=None,
                           example_array=build_example_array(),
                           rows=30,
                           cols=80,
                           placeholder=placeholder,
                           pagetitle="abif web tool (examples provided)")


@app.route('/', methods=['POST'])
def index_post():
    abifinput = ""
    abifinput = request.form['abifinput']
    pairwise_html = None
    dotsvg_html = None
    STAR_html = None
    placeholder = "Try other ABIF, or try tweaking your input (see below)...."
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
            debug_dict['starscale'] = scaled_scores(jabmod, target_scale=50)
            import json
            debug_output = json.dumps(debug_dict, indent=4)
            scorestardict=debug_dict
    return render_template('results-index.html',
                           abifinput=abifinput,
                           pairwise_html=pairwise_html,
                           dotsvg_html=dotsvg_html,
                           STAR_html=STAR_html,
                           scorestardict=scorestardict,
                           error_html=error_html,
                           example_array=build_example_array(),
                           lower_abif_caption="Input",
                           lower_abif_text=escape(abifinput),
                           rows=10,
                           cols=80,
                           placeholder=placeholder,
                           pagetitle="abif web tool (results)",
                           debug_output=debug_output)


if __name__ == '__main__':
    app.run(debug=True)

