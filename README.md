"awt" is an abbreviation of "ABIF web tool".  A running instance of this can be found at [https://abif.electorama.com](https://abif.electorama.com)

Installing and Running
============

Here's some steps for installing and running awt.py that should result in a running web server:

1. Check out the awt repository into a convenient directory (example:
   `~/src/awt`)
2. Check out the abiftool repository into a different directory
   (example: `~/src/abiftool`)
3. Edit the `awt/env_vars.sh` script to match the locations in which
   you checked out `awt` and `abiftool`
4. Within the `abiftool` directory, run `fetchmgr.py fetchspecs/*` to
   fetch several example election files from the web and convert them to
   `.abif`
5. Within the `awt` directory, run the `RUNAWT.sh` script
6. After answering a question or two, you should have a web server
   running at a random port on your machine.  The URL to your local
   homepage should be part of the initial output of the script.