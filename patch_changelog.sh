#!/bin/bash

# $1 ... SOURCE file
# $2 ... DEST file

if [ -z "$VERSION" ]; then
	VERSION="0.01-0"
#	echo "No version given: assuming $VERSION" > /dev/stderr
fi

ver_norev=${VERSION%-*}

if [ -z "$CI_PIPELINE_IID" ]; then
	rev=${VERSION##*-}
else
	rev="$CI_PIPELINE_IID"
fi

if [ -z "$ver_norev" ] || [ -z "$rev" ]; then
        echo "Version string $VERSION incorrect" > /dev/stderr
        exit -1
fi

VERSION="$ver_norev-$rev" 

if [ -z "$DATE" ]; then
        DATE=$(LANG= date -R)
fi

VERSION="$VERSION" DATE="$DATE" envsubst <"$1" >"$2"
