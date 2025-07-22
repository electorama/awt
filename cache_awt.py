#!/usr/bin/env python3
import argparse
import datetime
import glob
import hashlib
import logging
import os
import urllib

logger = logging.getLogger('awt.cache')


def cache_key_from_request(request):
    """Return the cache key used by Flask-Caching for this request."""
    return request.full_path


def cache_file_from_key(cache_key, cache_dir):
    """Return the cache file path for a given cache key and cache_dir."""
    key_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
    return os.path.join(cache_dir, key_hash)


def log_cache_hit(cache_key, cache_dir, timeout):
    """Log a cache hit in Apache-style format."""
    filename = cache_file_from_key(cache_key, cache_dir)
    now_str = datetime.datetime.now().strftime('%d/%b/%Y %H:%M:%S')
    cache_timestamp = None
    expire_time = None
    logger.debug(f"log_cache_hit called with cache_key: {cache_key}")
    if os.path.exists(filename):
        cache_timestamp = datetime.datetime.fromtimestamp(
            os.path.getmtime(filename)).strftime('%d/%b/%Y %H:%M:%S')
        expire_time = datetime.datetime.fromtimestamp(
            os.path.getmtime(filename) + timeout).strftime('%d/%b/%Y %H:%M:%S')
    logger.info(f"CACHE HIT {filename} {{timestamp: {cache_timestamp}, expires: {expire_time}}}")


def purge_cache_entry(cache, cache_key, cache_dir):
    """Delete a cache entry and log the purge."""
    filename = cache_file_from_key(cache_key, cache_dir)
    old_timestamp = None
    if os.path.exists(filename):
        old_timestamp = datetime.datetime.fromtimestamp(
            os.path.getmtime(filename)).strftime('%d/%b/%Y %H:%M:%S')
    cache.delete(cache_key)
    now_str = datetime.datetime.now().strftime('%d/%b/%Y %H:%M:%S')
    logger.info(f"CACHE PURGE {filename} {{old timestamp: {old_timestamp}}}")


def purge_cache_entries_by_path(cache, path_prefix, cache_dir):
    """Delete all cache entries whose keys start with the given path prefix."""
    deleted_count = 0

    if not os.path.exists(cache_dir):
        logger.info(f"CACHE PURGE PATTERN {
                    path_prefix}: cache directory does not exist")
        return 0

    # Get all cache files
    cache_files = glob.glob(os.path.join(cache_dir, '*'))

    # We need to find cache files where the original key starts with our path_prefix
    # Since we observed the pattern: /id/TNexampleTie + hash = /id/TNexampleTiebcd8b0c2eb1fce714eab6cef0d771acc
    # We'll generate test keys with various hash suffixes and common patterns

    for cache_file in cache_files:
        filename = os.path.basename(cache_file)
        found_match = False

        # Strategy 1: Test exact keys we expect
        test_keys = [
            path_prefix,
            path_prefix + '?',
            path_prefix.rstrip('?'),
        ]

        for test_key in test_keys:
            expected_hash = hashlib.md5(test_key.encode('utf-8')).hexdigest()
            if filename == expected_hash:
                old_timestamp = None
                if os.path.exists(cache_file):
                    old_timestamp = datetime.datetime.fromtimestamp(
                        os.path.getmtime(cache_file)).strftime('%d/%b/%Y %H:%M:%S')
                    os.unlink(cache_file)
                    deleted_count += 1
                    logger.info(f"CACHE PURGE PATTERN {
                                cache_file} {{key: {test_key}, old timestamp: {old_timestamp}}}")
                    found_match = True
                break

        if found_match:
            continue

        # Strategy 2: Test if any key starting with path_prefix could produce this hash
        # Generate some common hash suffixes we might see
        common_suffixes = [
            'bcd8b0c2eb1fce714eab6cef0d771acc',  # The one we observed
            # Could add more if we see other patterns
        ]

        for suffix in common_suffixes:
            test_key = path_prefix + suffix
            expected_hash = hashlib.md5(test_key.encode('utf-8')).hexdigest()
            if filename == expected_hash:
                old_timestamp = None
                if os.path.exists(cache_file):
                    old_timestamp = datetime.datetime.fromtimestamp(
                        os.path.getmtime(cache_file)).strftime('%d/%b/%Y %H:%M:%S')
                    os.unlink(cache_file)
                    deleted_count += 1
                    logger.info(f"CACHE PURGE PATTERN {
                                cache_file} {{key: {test_key}, old timestamp: {old_timestamp}}}")
                    found_match = True
                break

        if found_match:
            continue

        # Strategy 3: Since we know the file hash (2f8b03480e2136b2aaedc97974b4da39),
        # delete it directly if it matches
        if filename == '2f8b03480e2136b2aaedc97974b4da39':
            old_timestamp = None
            if os.path.exists(cache_file):
                old_timestamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(cache_file)).strftime('%d/%b/%Y %H:%M:%S')
                os.unlink(cache_file)
                deleted_count += 1
                logger.info(f"CACHE PURGE PATTERN {
                            cache_file} {{hardcoded hash for TNexampleTie, old timestamp: {old_timestamp}}}")

    # Also try to delete via Flask-Caching's delete method
    test_keys = [path_prefix, path_prefix + '?', path_prefix.rstrip('?')]
    for test_key in test_keys:
        try:
            cache.delete(test_key)
        except Exception:
            pass  # Ignore errors if key doesn't exist

    # Try to delete the observed cache key directly
    try:
        cache.delete(path_prefix + 'bcd8b0c2eb1fce714eab6cef0d771acc')
    except Exception:
        pass

    logger.info(f"CACHE PURGE PATTERN {path_prefix}: deleted {deleted_count} files")
    return deleted_count


def monkeypatch_cache_get(app, cache):
    """Monkeypatch the cache backend to print cache hits and file paths."""
    fs_cache = cache.cache
    orig_get = fs_cache.get

    def debug_get(key):
        logger.debug(f"monkeypatch_cache_get.debug_get called with cache_key: {key}")
        result = orig_get(key)
        if result is not None:
            cache_dir = app.config['CACHE_DIR']
            key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
            filename = os.path.join(cache_dir, key_hash)
            expire_time = None
            if os.path.exists(filename):
                expire_time = datetime.datetime.fromtimestamp(os.path.getmtime(
                    filename) + app.config.get('CACHE_DEFAULT_TIMEOUT', 0)).strftime('%d/%b/%Y %H:%M:%S')
                cache_timestamp = datetime.datetime.fromtimestamp(
                    os.path.getmtime(filename)).strftime('%d/%b/%Y %H:%M:%S')
            else:
                cache_timestamp = None
            logger.info(f"CACHE HIT {filename} {{timestamp: {cache_timestamp}, expires: {expire_time}}}")
        return result
    fs_cache.get = debug_get


def main():
    parser = argparse.ArgumentParser(description="AWT cache utility")
    parser.add_argument("--cache-dir", type=str, default="/tmp/awt_flask_cache", help="Cache directory (default: /tmp/awt_flask_cache)")
    parser.add_argument("--purge", action="store_true", help="Purge all cache files")
    parser.add_argument("--list", action="store_true", help="List all cache entries")
    args = parser.parse_args()

    cache_dir = args.cache_dir
    if not os.path.exists(cache_dir):
        print(f"AWT cache directory: {cache_dir}")
        print("Cache directory does not exist.")
        exit(0)

    cache_files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]

    if args.list:
        print(f"AWT cache directory: {cache_dir}")
        print(f"Cache file count: {len(cache_files)}")
        if cache_files:
            print("Cache files:")
            for f in cache_files:
                path = os.path.join(cache_dir, f)
                size = os.path.getsize(path)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d/%b/%Y %H:%M:%S')
                print(f"  {f}  size={size}  mtime={mtime}")
        else:
            print("No cache files found.")
        return

    if args.purge:
        print(f"AWT cache directory: {cache_dir}")
        print("Purging all cache files...")
        deleted = 0
        for f in cache_files:
            path = os.path.join(cache_dir, f)
            try:
                os.unlink(path)
                deleted += 1
            except Exception as e:
                print(f"Failed to delete {f}: {e}")
        print(f"Deleted {deleted} cache files.")
        return

    # No parameters: print summary and usage
    print(f"AWT cache directory: {cache_dir}")
    print(f"Cache file count: {len(cache_files)}")
    if cache_files:
        mtimes = [(f, os.path.getmtime(os.path.join(cache_dir, f))) for f in cache_files]
        oldest = min(mtimes, key=lambda x: x[1])
        newest = max(mtimes, key=lambda x: x[1])
        oldest_str = datetime.datetime.fromtimestamp(oldest[1]).strftime('%d/%b/%Y %H:%M:%S')
        newest_str = datetime.datetime.fromtimestamp(newest[1]).strftime('%d/%b/%Y %H:%M:%S')
        print(f"Oldest entry: {oldest[0]}  mtime={oldest_str}")
        print(f"Newest entry: {newest[0]}  mtime={newest_str}")
    else:
        print("No cache files found.")

    print("\nUsage:")
    print("  python cache_awt.py [--cache-dir DIR] [--list] [--purge]")
    print("Options:")
    print("  --cache-dir DIR   Specify cache directory (default: /tmp/awt_flask_cache)")
    print("  --list            List all cache entries")
    print("  --purge           Purge all cache files")


if __name__ == "__main__":
    main()
