#!/bin/sh

# kimchi-firewalld.sh
#
# Add or remove service from a specified zone.
#
# It should be called like this:
#
#     ./kimchi-firewalld.sh public add http
#     ./kimchi-firewalld.sh public del http
#
# Author: Murilo Opsfelder Araujo <muriloo@br.ibm.com>


function usage() {
	me="$(basename $0)"
	echo -e "Usage:

\t$me <zone> <action> <service>

Example:

\t$me public add http
\t$me public del http"
}


# check argv
if [ "$#" -lt 3 ]; then
	echo "ERROR: Insuficient argv parameters"
	usage
	exit 255
fi


# read argv
ZONE="$1"
ACTION="$2"
SERVICE="$3"


# settings
ZONES_DIR="/usr/lib/firewalld/zones"
ZONE_FILE="${ZONES_DIR}/${ZONE}.xml"
TEMP_ZONE=$(mktemp)


# save IFS
OLDIFS=$IFS


function service_exists() {
	service="$1"

	if grep -q "\"$service\"" $ZONE_FILE; then
		return 0
	else
		return 1
	fi
}


function add_service() {
	service="$1"

	IFS="
"
	for LINE in $(<$ZONE_FILE); do
		if expr match "$LINE" "^.*/zone.*$" >/dev/null 2>&1; then
			echo "  <service name=\"${service}\"/>" >> $TEMP_ZONE
			echo $LINE >> $TEMP_ZONE
		else
			echo $LINE >> $TEMP_ZONE
		fi
	done
	IFS=$OLDIFS
}


function del_service() {
	service="$1"

	IFS="
"
	for LINE in $(<$ZONE_FILE); do
		if ! expr match "$LINE" "^.*\"${service}\".*$" >/dev/null 2>&1; then
			echo $LINE >> $TEMP_ZONE
		fi
	done
	IFS=$OLDIFS
}


CHANGED=no
if [ "$ACTION" = "add" ]; then
	if ! service_exists "$SERVICE"; then
		add_service "$SERVICE"
		CHANGED=yes
	fi
elif [ "$ACTION" = "del" ]; then
	if service_exists "$SERVICE"; then
		del_service "$SERVICE"
		CHANGED=yes
	fi
else
	echo "ERROR: Unrecognized <action>"
	usage
	exit 254
fi


# restore IFS
IFS="$OLDIFS"


# override zone if changed
if [ "$CHANGED" = "yes" ]; then
	mv -f $TEMP_ZONE $ZONE_FILE
fi


exit 0
