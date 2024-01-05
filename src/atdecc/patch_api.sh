#!/bin/bash

file="${1}"

function sed_patch {
	tmpfile=$(mktemp)
	if sed -e "s/${2}/${3}/g" "${1}" > "$tmpfile"; then
		cp "$tmpfile" "${1}"
	else
		echo "Sed s/${2}/${3}/g failed" >> /dev/stderr
	fi
	rm -f "$tmpfile"
}

# Comment out syntactically wrong type definitions ending with ' * 0()'
sed_patch "${file}" '^.*[[:space:]]\*[[:space:]]0().*$' '#&' &&

# Patch buggy uint16_t type definition
sed_patch "${file}" '^uint16_t = .*$' 'uint16_t = ctypes.c_uint16' &&

# Patch const_string_t type definition which varies across OSs   
sed_patch "${file}" '^const_string_t = .*$' 'const_string_t = ctypes.POINTER(ctypes.c_char)' &&

# Patch in runtime path of shared library ( __file__.rsplit("/",1)[0] )
sed_patch "${file}" 'ctypes.CDLL(\(.*\))$' 'ctypes.CDLL(__file__\.rsplit(\"\/\"\,1)[0]+\"\/\"+\1)'
