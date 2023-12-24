#!/bin/bash

PIDFILE=/var/run/${0##*/}.pid

#. /etc/elak-spl/atdecc-py.conf

case "$1" in
start)
	python3 -m atdecc.atdecc -d &
	echo $! > $PIDFILE
	;;
stop)
	if [ -f $PIDFILE ]; then
		kill $(cat $PIDFILE)
		rm $PIDFILE
	fi
	;;
restart)
	$0 stop
	$0 start
	;;
status)
	if [ -f $PIDFILE ]; then
		echo "$0: process $(cat $PIDFILE) is running"
	else
		echo "$0 is NOT running"
		exit 1
	fi
	;;
*)
	echo "Usage: $0 {start|stop|status|restart}"
esac

exit 0
