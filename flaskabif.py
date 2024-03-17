#!/usr/bin/env python3
from flask import Flask, render_template, request
from markupsafe import escape
from pathlib import Path

app = Flask(__name__)

TESTFILEDIR='/home/robla/tags/abiftool/testdata'
from abiflib import (
    convert_abif_to_jabmod,
    htmltable_pairwise_and_winlosstie,
    ABIFVotelineException
    )

def build_example_array():
    EXAMPLEFILENAME='tenn-example/tennessee-example-simple.abif'
    EXAMPLEFILENAME2='tenn-example/tennessee-example-scores.abif'
    example_abif = Path(TESTFILEDIR, EXAMPLEFILENAME).read_text()
    example_abif2 = Path(TESTFILEDIR, EXAMPLEFILENAME2).read_text()
    return [
        escape(example_abif),
        escape(example_abif2)
    ]


# TODO - split the index function into index_get and index_post
@app.route('/', methods=['GET'])
def index_get():
    placeholder = "Enter ABIF here, possibly using example below..."
    return render_template('example-index.html',
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
    return render_template('results-index.html',
                           abifinput=abifinput,
                           abiftool_output=abifout,
                           example_array=build_example_array(),
                           lower_abif_caption="Input",
                           lower_abif_text=escape(abifinput),
                           rows=10,
                           cols=80,
                           placeholder=placeholder,
                           pagetitle="abif web tool (results)")


if __name__ == '__main__':
    app.run(debug=True)

