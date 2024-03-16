#!/usr/bin/env python3
from flask import Flask, render_template, request
from markupsafe import escape
from pathlib import Path

app = Flask(__name__)

TESTFILEDIR='/home/robla/tags/abiftool/testdata'
EXAMPLEFILENAME='tenn-example/tennessee-example-simple.abif'
EXAMPLEFILENAME2='tenn-example/tennessee-example-scores.abif'
example_abif = Path(TESTFILEDIR, EXAMPLEFILENAME).read_text()
example_abif2 = Path(TESTFILEDIR, EXAMPLEFILENAME2).read_text()
from abiflib import (
    convert_abif_to_jabmod,
    htmltable_pairwise_and_winlosstie,
    ABIFVotelineException
    )

@app.route('/', methods=['GET', 'POST'])
def index():
    abifinput = ""
    hasPostedData = False
    if request.method == 'POST':
        abifinput = request.form['abifinput']
        if len(abifinput) > 0:
            hasPostedData = True

    thisformtitle = f'abif web tool (Electorama)'
    if hasPostedData:
        try:
            abifmodel = convert_abif_to_jabmod(abifinput)
            abifout = htmltable_pairwise_and_winlosstie(abifmodel,
                                                        snippet = True,
                                                        validate = True,
                                                        modlimit = 2500)
        except ABIFVotelineException as e:
            abifmodel = None
            abifout = e.message
        placeholder = "Try other ABIF, or try tweaking your input (see below)...."
        return render_template('index.html',
                               abifinput=abifinput,
                               formtitle=thisformtitle,
                               abiftool_output=abifout,
                               lower_abif_caption="Input",
                               lower_abif_text=escape(abifinput),
                               rows=10,
                               cols=80,
                               placeholder=placeholder)
    else:
        placeholder = "Enter ABIF here, possibly using example below..."
        return render_template('index.html',
                               abifinput='',
                               formtitle=thisformtitle,
                               abiftool_output=None,
                               lower_abif_caption="Example ABIF files",
                               lower_abif_text=escape(example_abif),
                               lower_abif_text2=escape(example_abif2),
                               rows=30,
                               cols=80,
                               placeholder=placeholder)

if __name__ == '__main__':
    app.run(debug=True)

