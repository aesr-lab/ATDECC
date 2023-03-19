#!/bin/bash

function patch {
	tmpfile=$(mktemp)
	cp "${1}" "$tmpfile"
	sed -e "s/${2}/${3}/g" "$tmpfile" > "$1"
	rm -f "$tmpfile"
}

# comment out syntactically wrong type definitions ending with ' * 0()'
patch "${1}" '^.*[[:space:]]\*[[:space:]]0().*$' '#&'

# patch buggy uint16_t type definition
patch "${1}" '^uint16_t = .*$' 'uint16_t = ctypes.c_uint16'

# patch const_string_t type definition which varies across OSs   
patch "${1}" '^const_string_t = .*$' 'const_string_t = ctypes.POINTER(ctypes.c_char)'
