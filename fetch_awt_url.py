#!/usr/bin/env python3
import argparse
import base64
import binascii
import os

# Ensure WSGI cache doesn't attempt to write temp files during import
os.environ.setdefault('AWT_CACHE_TYPE', 'none')

from awt import app, cache

def fetch_url(url, use_cache=False, follow_redirects=False, debug=False):
    """Fetch content from a local AWT URL via Flask test client.

    Returns the full response object so callers can decide how to handle
    text vs. binary content.
    """
    if not use_cache:
        # Disable caching for this session for clearer debugging
        app.config['CACHE_TYPE'] = 'flask_caching.backends.NullCache'
        cache.init_app(app)

    if debug:
        app.debug = True

    client = app.test_client()
    return client.get(url, follow_redirects=follow_redirects)

def main():
    """
    Main function to parse arguments and fetch URL content.
    """
    parser = argparse.ArgumentParser(
        description="Fetch content from a local AWT URL and print or save it."
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
        help="Allow the request to be served from cache (default: disabled)."
    )
    parser.add_argument(
        "-o", "--output",
        help="Write response body to this file (useful for binary content)."
    )
    parser.add_argument(
        "--base64",
        action="store_true",
        help="Print base64 of binary content to stdout when no --output is given."
    )
    parser.add_argument(
        "--headers",
        action="store_true",
        help="Print response status and headers to stderr for debugging."
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow HTTP redirects (useful for routes that 302 to static content)."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for server (does not auto-append ?debug=json)."
    )
    args = parser.parse_args()

    resp = fetch_url(args.url, use_cache=args.cache, follow_redirects=args.follow, debug=args.debug)
    if args.headers:
        import sys
        sys.stderr.write(f"Status: {resp.status}\n")
        for k, v in resp.headers.items():
            sys.stderr.write(f"{k}: {v}\n")

    ctype = resp.headers.get('Content-Type', '')
    body = resp.data
    is_text = ctype.startswith('text/') or 'xml' in ctype or 'json' in ctype
    status = resp.status_code

    if is_text:
        try:
            print(body.decode('utf-8'))
        except UnicodeDecodeError:
            # Fallback if mislabelled
            print(body.decode('latin-1', errors='replace'))
    else:
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(body)
            print(f"[fetch] {args.url} -> {args.output} ({len(body)} bytes, {ctype}, status={status})")
        elif args.base64:
            print(base64.b64encode(body).decode('ascii'))
        else:
            # Print a short summary and a small hex prefix for debugging only
            prefix = binascii.hexlify(body[:32]).decode('ascii') if body else ''
            print(f"[binary] {ctype}; {len(body)} bytes; status={status}; head32=0x{prefix}")

if __name__ == "__main__":
    main()
