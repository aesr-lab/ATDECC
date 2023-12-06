#!/bin/bash

# $1 ... SOURCE file
# $2 ... DEST file

if [ -z "$VERSION" ]; then
        if [ -f .version ]; then
                VERSION=$(cat .version)
        else
                VERSION="0.01-0"
                echo "No version given: assuming $VERSION" > /dev/stderr
        fi
fi

ver_norev=${VERSION%-*}
rev=${VERSION##*-}

if [ -z "$ver_norev" ] || [ -z "$rev" ]; then
        echo "Version string $VERSION incorrect" > /dev/stderr
        exit -1
fi

# Writing new revision number to .version file
echo $ver_norev-$((rev+1)) > .version

if [ -z "$DATE" ]; then
        DATE=$(date +"%a, %d %b %Y %H:%I:%S %z")
fi

VERSION=$VERSION DATE=$DATE envsubst <"$1" >"$2"
