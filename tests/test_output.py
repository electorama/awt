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
    # Find the pairwise table by searching for the <th> with Nashville
    th_nash = soup.find("th", string=lambda s: s and "Nashville" in s)
    table = th_nash.find_parent("table")
    assert table, "Cannot find string 'Nashville' in table!"
    # Find all rows in the table
    rows = soup.find_all("tr")
    # Check the first row (should be Nash) for 'victories' cell
    first_row = rows[0]
    first_cells = first_row.find_all(["th", "td"])
    found_victories_first = any("↓" in cell.get_text() for cell in first_cells)
    assert found_victories_first, "Missing 'victories' cell in first row!"
    # Only check the last row (should be Memph)
    last_row = rows[-1]
    cells = last_row.find_all(["th", "td"])
    # For TNexample, last row should have 6 columns
    assert(len(cells) == 6,
           f"Last row has {len(cells)} columns, expected 6: {last_row}")
    # Check that the last cell is always 'losses' or 'is undefeated'
    last_text = cells[-1].get_text()
    assert("losses" in last_text or "undefeated" in last_text,
           f"Last cell is not losses/undefeated: {last_text}")
    # Optionally: check matchup order/content if you want to be even stricter
