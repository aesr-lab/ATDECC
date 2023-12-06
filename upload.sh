#!/bin/bash

# Put *.deb files to remote '$path' folder

path="$1"

if [ -z "$(ls *.deb)" ]; then
	echo "No files to upload" >> /dev/stderr
	exit -1
fi

lftp<<EOF
set sftp:auto-confirm yes
set ssl:verify-certificate no
open sftp://$SFTP_HOST:$SFTP_PORT
user $SFTP_USER $SFTP_PASSWORD
mkdir -pf $SFTP_PATH/$path
cd $SFTP_PATH/$path
mput *.deb
bye
EOF
