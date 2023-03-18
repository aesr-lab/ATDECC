#!/bin/bash

tmpfile=$(mktemp)

cp "$1" "$tmpfile"
sed -e 's/^.*0().*$/#&/g' "$tmpfile" > "$1"

cp "$1" "$tmpfile"
sed -e 's/^uint16_t = .*/uint16_t = ctypes.c_uint16/g' "$tmpfile" > "$1"

rm -f "$tmpfile"

