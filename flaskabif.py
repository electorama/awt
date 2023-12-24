from flask import Flask, render_template, request
from pathlib import Path

app = Flask(__name__)

TESTFILEDIR='/home/robla/tags/abiftool/testdata'
# EXAMPLEFILENAME='burl2009/burl2009.abif'
EXAMPLEFILENAME='tennessee-example/tennessee-example-scores.abif'
example_abif = Path(TESTFILEDIR, EXAMPLEFILENAME).read_text()
from abiflib import convert_abif_to_jabmod, htmltable_pairwise_and_winlosstie

@app.route('/', methods=['GET', 'POST'])
def index():
    # abiftool.py -f abif -t html_snippet abiftool/testdata/burl2009/burl2009.abif
    if request.method == 'POST':
        thisformtitle = f'abiftool for the web'
        abifinput = request.form['abifinput']
        abifmodel = convert_abif_to_jabmod(abifinput)
        abifout = htmltable_pairwise_and_winlosstie(abifmodel,
                                                    snippet = True,
                                                    validate = True,
                                                    modlimit = 2500)
        placeholder = "Try other ABIF, or try tweaking your input (see below)...."
        return render_template('index.html',
                               abifinput=abifinput,
                               formtitle=thisformtitle,
                               abiftool_output=abifout,
                               lower_abif_caption="Input",
                               lower_abif_text=abifinput,
                               rows=10,
                               cols=80,
                               placeholder=placeholder)
    else:
        thisformtitle = f'abiftool for the web'
        placeholder = "Enter ABIF here, possibly using example below..."
        return render_template('index.html',
                               abifinput='',
                               formtitle=thisformtitle,
                               abiftool_output=None,
                               lower_abif_caption="Example ABIF file",
                               lower_abif_text=example_abif,
                               rows=30,
                               cols=80,
                               placeholder=placeholder)

if __name__ == '__main__':
    app.run(debug=True)

