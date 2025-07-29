#!/usr/bin/env python3
import argparse
from awt import app, cache

def fetch_url_content(url, use_cache=False):
    """
    Fetches content from a URL using the Flask app's test client.
    """
    if not use_cache:
        # By setting the CACHE_TYPE to 'null', we effectively disable caching
        # for the test client session, which is cleaner than cache-busting.
        app.config['CACHE_TYPE'] = 'null'
        cache.init_app(app)

    client = app.test_client()
    resp = client.get(url)
    return resp.data.decode("utf-8")

def main():
    """
    Main function to parse arguments and fetch URL content.
    """
    parser = argparse.ArgumentParser(
        description="Fetch HTML content from a local AWT URL and print to stdout."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="/id/Burl2009",
        help="The URL path to fetch (e.g., /id/Burl2009). Defaults to /id/Burl2009."
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Allow the request to be served from the cache. Default is to bypass the cache."
    )
    args = parser.parse_args()

    html_content = fetch_url_content(args.url, use_cache=args.cache)
    print(html_content)

if __name__ == "__main__":
    main()
