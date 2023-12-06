.PHONY: all clean debpkg

all:
	$(MAKE) -C src

builddeps: debpkg/debian/control
	# install packages listed in "Build-Depends:" section
	echo "Y" | mk-build-deps -i "$<"
	# check again
	dpkg-checkbuilddeps "$<"

debpkg: debpkg/debian/control debpkg/debian/changelog
	cd debpkg && dpkg-buildpackage --build=source,any

debpkg/debian/changelog: debpkg/debian/changelog.in ./patch_changelog.sh
	./patch_changelog.sh "$<" "$@"

clean: debpkg/debian/control debpkg/debian/changelog
	$(MAKE) -C src clean
	cd debpkg && dh clean
