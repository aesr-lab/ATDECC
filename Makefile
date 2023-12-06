.PHONY: all clean debpkg

all:
	$(MAKE) -C src

builddeps: sources/debian/control
	# install packages listed in "Build-Depends:" section
	echo "Y" | mk-build-deps -i "$<"
	# check again
	dpkg-checkbuilddeps "$<"

debpkg: sources/debian/control sources/debian/changelog
	cd debpkg && dpkg-buildpackage --build=source,any

debpkg/debian/changelog: sources/debian/changelog.in ./patch_changelog.sh
	./patch_changelog.sh "$<" "$@"

clean:
	$(MAKE) -C src clean
	cd debpkg && dh clean
