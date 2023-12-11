#!/bin/bash

# $1 ... SOURCE file
# $2 ... DEST file

if [ -z "$VERSION" ]; then
	VERSION="0.01-0"
	echo "No version given: assuming $VERSION" > /dev/stderr
fi

ver_norev=${VERSION%-*}

if [ -z "$CI_JOB_ID" ]; then
	rev=${VERSION##*-}
else
	rev="$CI_JOB_ID"
fi

if [ -z "$ver_norev" ] || [ -z "$rev" ]; then
        echo "Version string $VERSION incorrect" > /dev/stderr
        exit -1
fi

# Writing new revision number to .version file
VERSION="$ver_norev-$rev" 

if [ -z "$DATE" ]; then
        DATE=$(LANG= date +"%a, %d %b %Y %H:%I:%S %z")
fi

VERSION="$VERSION" DATE="$DATE" envsubst <"$1" >"$2"
