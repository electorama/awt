#!/bin/bash
# RUNAWT.sh - set env variables and run on a local machine.
source env_vars.sh

kill_mypid_and_die() {
  echo "Killing awt.py server (PID $mypid) and exiting $0 script (PID $$)"
  kill $mypid
  exit 0
}

ps_for_mypid() {
  ps -f --pid $$
  ps -f --pid $mypid | tail -n +2
}

status_line() {
  echo "awt.py running with PID $mypid ($(date -Im))"
}

read -p "Open awt.py in debug mode? "
if [[ "$REPLY" =~ ^[yY] ]]; then
  export AWT_STATUS=debug
else
  export AWT_STATUS=prod
fi
python3 $AWT_DIR/awt.py &
mypid="$!"
trap kill_mypid_and_die SIGINT
sleep 1
ps_for_mypid
status_line
while true; do
  sleep 300
  status_line
done
