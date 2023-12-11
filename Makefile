.PHONY: clean debpkg

builddeps: debian/control
	# install packages listed in "Build-Depends:" section
	echo "Y" | mk-build-deps -i "$<"
	# check again
	dpkg-checkbuilddeps "$<"

debpkg: debian/control debian/changelog
	dpkg-buildpackage --build=source,any

debian/changelog: debian/changelog.in ./patch_changelog.sh
	./patch_changelog.sh "$<" "$@"

clean: debian/control debian/changelog
	$(MAKE) -C src/atdecc_py clean
#	dh clean
