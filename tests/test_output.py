"""
HTML Output Testing with BeautifulSoup

This test file uses BeautifulSoup selectors and methods to validate HTML structure and content.

Test parameters:
- post_data: Dictionary of form data to POST to /awt
- selector_method: BeautifulSoup method name ('find', 'find_all', 'select', etc.)
- selector_args: Arguments to pass to the selector method
- test_type: Type of test ('exists', 'count', 'text_contains', 'text_equals', 'attr_equals')
- expected_value: Expected result value
"""

import pytest
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from awt import app
import os

# Tennessee example ABIF data for consistent testing
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

# Test data list using pytest.param with identifiers
html_testlist = [
    # soup.find() - Finds the FIRST element matching the criteria
    # Usage: soup.find("tag_name") or soup.find("tag", {"attr": "value"})
    pytest.param(
        {"abifinput": TN_ABIF},
        "find",
        ["h1"],
        "text_contains",
        "ABIF Electorama results",
        id="output_001_h1_title"
    ),

    # soup.find_all() - Finds ALL elements matching the criteria, returns a list
    # Usage: soup.find_all("tag_name") - useful for counting elements
    pytest.param(
        {"abifinput": TN_ABIF},
        "find_all",
        ["table"],
        "count",
        1,  # Should have exactly one table
        id="output_002_table_count"
    ),

    # soup.select() - Uses CSS selectors, returns a list (like jQuery)
    # Usage: soup.select("css_selector") - supports #id, .class, tag combinations
    pytest.param(
        {"abifinput": TN_ABIF},
        "select",
        ["h2#results"],
        "count",
        1,  # Should have one h2 with id="results"
        id="output_003_results_section"
    ),

    # soup.select_one() - CSS selector that returns FIRST match (like find but with CSS syntax)
    # Usage: soup.select_one("css_selector") - returns single element or None
    pytest.param(
        {"abifinput": TN_ABIF},
        "select_one",
        ["form"],
        "exists",
        True,
        id="output_004_form_exists"
    ),

    # Testing specific content from an existing election using URL path
    # This demonstrates fetching election results by ID rather than POSTing ABIF data
    pytest.param(
        {"url_path": "/id/TNexample"},
        "find",
        [{"string": "Knox (83-17; margin: 66)"}],
        "exists",
        True,
        id="output_005_pairwise_margin"
    ),

    pytest.param(
        {"url_path": "/awt"},
        "select",
        ["ul.tab-links"],
        "count",
        1,
        id="homepage_001_tab_structure_exists"
    ),

    pytest.param(
        {"url_path": "/awt"},
        "select",
        ["div.tab-content.active"],
        "count",
        1,
        id="homepage_002_only_one_active_content"
    ),
]


def get_html_from_awt(post_data=None, url_path=None):
    """
    Helper function to get HTML from AWT

    Args:
        post_data: Dictionary of form data to POST to /awt (for form submissions)
        url_path: URL path to GET (for existing elections like /id/TNexample)

    Note: Exactly one of post_data or url_path should be provided
    """
    client = app.test_client()

    if url_path is not None:
        # GET request to specific URL path
        resp = client.get(url_path)
    elif post_data is not None:
        # POST request to /awt with form data
        resp = client.post("/awt", data=post_data)
    else:
        raise ValueError("Either post_data or url_path must be provided")

    return resp.data.decode("utf-8")


def run_bs4_test(html, selector_method, selector_args, test_type, expected_value):
    """
    Run a BeautifulSoup-based test on HTML content

    Args:
        html: HTML string to parse
        selector_method: BeautifulSoup method name ('find', 'find_all', 'select', 'select_one')
        selector_args: Arguments to pass to the selector method (list/tuple)
        test_type: Type of test to perform ('exists', 'count', 'text_contains', 'text_equals', 'attr_equals')
        expected_value: Expected result
    """
    soup = BeautifulSoup(html, "html.parser")

    # Get the BeautifulSoup method and call it with unpacked args
    method = getattr(soup, selector_method)

    # Handle special case where we need to pass string as keyword argument
    if len(selector_args) == 1 and isinstance(selector_args[0], dict) and 'string' in str(selector_args[0]):
        # Convert string="value" in args to proper keyword argument
        args = []
        kwargs = {}
        for arg in selector_args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    if k == 'string':
                        kwargs['string'] = v
                    else:
                        if not args:
                            args.append({})
                        args[0][k] = v
            else:
                args.append(arg)
        result = method(*args, **kwargs) if args else method(**kwargs)
    else:
        result = method(*selector_args)

    # Perform the test based on test_type
    if test_type == "exists":
        assert (result is not None) == expected_value
    elif test_type == "count":
        # For methods that return lists (find_all, select), check length
        # For methods that return single elements (find, select_one), count as 1 or 0
        if hasattr(result, '__len__') and not isinstance(result, str):
            assert len(result) == expected_value
        else:
            assert (1 if result else 0) == expected_value
    elif test_type == "text_contains":
        assert result is not None, f"No element found with {selector_method}({selector_args})"
        text = result.get_text() if hasattr(result, 'get_text') else str(result)
        assert expected_value in text
    elif test_type == "text_equals":
        assert result is not None, f"No element found with {selector_method}({selector_args})"
        text = result.get_text().strip() if hasattr(result, 'get_text') else str(result).strip()
        assert text == expected_value
    elif test_type == "attr_equals":
        # expected_value should be tuple of (attr_name, attr_value)
        attr_name, attr_value = expected_value
        assert result is not None, f"No element found with {selector_method}({selector_args})"
        assert result.get(attr_name) == attr_value
    else:
        raise ValueError(f"Unknown test_type: {test_type}")


@pytest.mark.parametrize(
    'request_params, selector_method, selector_args, test_type, expected_value',
    html_testlist
)
def test_html_output(request_params, selector_method, selector_args, test_type, expected_value):
    """Test HTML output structure and content using BeautifulSoup"""
    if BeautifulSoup is None:
        pytest.skip("BeautifulSoup4 is required for HTML output tests")

    # Get HTML from AWT - handle both POST data and URL paths
    if isinstance(request_params, dict) and 'url_path' in request_params:
        html = get_html_from_awt(url_path=request_params['url_path'])
    else:
        # Assume it's POST data (backward compatibility)
        html = get_html_from_awt(post_data=request_params)

    # Run the BeautifulSoup test
    run_bs4_test(html, selector_method, selector_args, test_type, expected_value)


# Additional helper test for debugging HTML structure
@pytest.mark.parametrize("dummy", [None], ids=["output_900_debug_post"])
def test_debug_html_structure(dummy):
    """Debug helper - prints HTML structure for manual inspection"""
    if BeautifulSoup is None:
        pytest.skip("BeautifulSoup4 is required for HTML debugging")

    html = get_html_from_awt(post_data={"abifinput": TN_ABIF})
    soup = BeautifulSoup(html, "html.parser")

    # Print some basic structure info for debugging
    print("\n=== HTML Structure Debug ===")
    print(f"Title tag: {soup.find('title').get_text() if soup.find('title') else 'No title found'}")
    print(f"H1: {soup.find('h1').get_text() if soup.find('h1') else 'No h1 found'}")
    print(f"All headings: {[(tag.name, tag.get('id'), tag.get_text()[:50]) for tag in soup.find_all(['h1', 'h2', 'h3'])]}")
    print(f"Method sections: {len(soup.find_all('div', class_='method-section'))}")
    print(f"Tab buttons: {len(soup.select('#method-tabs .tab-button'))}")
    print(f"Tables: {len(soup.find_all('table'))}")
    print(f"Table contents: {[t.get_text()[:100] for t in soup.find_all('table')]}")
    print(f"All text content (first 500 chars): {soup.get_text()[:500]}")
    print("=============================\n")


@pytest.mark.parametrize("dummy", [None], ids=["output_901_debug_tnexample"])
def test_debug_tnexample_structure(dummy):
    """Debug helper for TNexample specific content"""
    if BeautifulSoup is None:
        pytest.skip("BeautifulSoup4 is required for HTML debugging")

    html = get_html_from_awt(url_path="/id/TNexample")
    soup = BeautifulSoup(html, "html.parser")

    print("\n=== TNexample Debug ===")
    print(f"Title: {soup.find('title').get_text() if soup.find('title') else 'No title'}")
    # Look for text containing "Chat" and "Knox"
    chat_elements = soup.find_all(string=lambda text: text and "Chat" in text and "Knox" in text)
    print(f"Elements with Chat and Knox: {[elem.strip() for elem in chat_elements]}")
    # Look for margin text
    margin_elements = soup.find_all(string=lambda text: text and "margin" in text)
    print(f"Elements with 'margin': {[elem.strip() for elem in margin_elements]}")
    print("========================\n")
