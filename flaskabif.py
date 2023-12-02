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
        submission_title = '(unknown abif title)'
        thisformtitle = f'abiftool for the web {submission_title}'
        abifinput = request.form['abifinput']
        abifmodel = convert_abif_to_jabmod(abifinput)
        abifout = htmltable_pairwise_and_winlosstie(abifmodel,
                                  snippet = True,
                                  validate = True,
                                  modlimit = 2500)

        return render_template('index.html',
                               abifinput=abifinput,
                               formtitle=thisformtitle,
                               abiftool_output=abifout,
                               abif_to_display=abifinput)
    else:
        submission_title = '(empty form)'
        thisformtitle = f'abiftool for the web {submission_title}'
        return render_template('index.html',
                               abifinput='',
                               formtitle=thisformtitle,
                               abiftool_output='(no output yet FIXME)',
                               abif_to_display=example_abif)

if __name__ == '__main__':
    app.run(debug=True)

