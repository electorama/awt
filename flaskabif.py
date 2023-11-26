from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        abifinput = request.form['abifinput']
        return render_template('index.html',
                               abifinput=abifinput,
                               formtitle='moo',
                               abiftool_output='moo23')
    else:
        return render_template('index.html',
                               abifinput='',
                               formtitle='moo',
                               abiftool_output='moo22')

if __name__ == '__main__':
    app.run(debug=True)
