#!/bin/bash
sed -e 's/^.*0().*$/#&/g' "$1" > "$1".new
mv "$1".new "$1"
