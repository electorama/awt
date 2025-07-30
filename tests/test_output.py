import pytest
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from awt import app
import os

# Use TNexample as a known-good test case
TN_ABIF = '''
# Tennessee example
# https://github.com/electorama/abiftool/blob/main/testdata/mock-elections/tennessee-example-scores.abif
{"title": "Tennessee capitol example"}
{"description": "Hypothetical example of selecting capitol of Tennessee, frequently used on Wikipedia and electowiki.  The proportion of voters is loosely based on the people who live in the metropolitan areas of the four largest cities in Tennessee, and the numeric ratings are based on crow-flying mileage to the city from the other metro areas."}
# See https://electowiki.org/wiki/Tennessee_example for illustrations
=Memph:[Memphis, TN]
=Nash:[Nashville, TN]
=Chat:[Chattanooga, TN]
=Knox:[Knoxville, TN]
# -------------------------
# Ratings are 400 miles minus crow-flying mileage to city
42:Memph/400>Nash/200>Chat/133>Knox/45
26:Nash/400>Chat/290>Knox/240>Memph/200
15:Chat/400>Knox/296>Nash/290>Memph/133
17:Knox/400>Chat/296>Nash/240>Memph/45
'''


@pytest.mark.parametrize("use_jinja", [False, True])
def test_pairwise_table_structure(use_jinja):
    pytest.importorskip(
        "bs4", reason="BeautifulSoup4 is required for this test.")
    os.environ["ABIFLIB_USE_JINJA"] = "1" if use_jinja else "0"
    client = app.test_client()
    # POST to /awt to get the rendered HTML
    resp = client.post(
        "/awt", data={"abifinput": TN_ABIF, "include_pairtable": "yes"})
    html = resp.data.decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")
    # Find the pairwise table by searching for a <th> whose text contains Nashville
    th_nash = None
    for th in soup.find_all("th"):
        if "Nashville" in th.get_text():
            th_nash = th
            break
    assert th_nash, "Cannot find string 'Nashville' in any <th>!"
    table = th_nash.find_parent("table")
    assert table, "Cannot find parent table for Nashville header!"
    # Check for '3 victories' in the pairwise table
    found_victories = False
    for cell in table.find_all(["th", "td"]):
        if "3 victories" in cell.get_text():
            found_victories = True
            break
    assert found_victories, "Missing '3 victories' in pairwise table!"
    # Optionally: check matchup order/content if you want to be even stricter
