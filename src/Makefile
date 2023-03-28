LIBNAME=avdecc_api
APIMOD=$(LIBNAME).py

.PHONY: clean all

SYS := $(shell gcc -dumpmachine)
DEBUG ?= 0

C_HDRS=$(wildcard ../jdksavdecc-c/include/*.h) 
CPP_SRCS=$(wildcard *.cpp) 
C_SRCS=$(wildcard ../jdksavdecc-c/src/*.c) $(wildcard ../avdecc-cmd/src/*.c)
OBJS=$(patsubst %.c,%.o,$(C_SRCS)) $(patsubst %.cpp,%.opp,$(CPP_SRCS))

INCLUDES=-I../jdksavdecc-c/include -I../avdecc-cmd/include

LD_FLAGS=-lpcap

OPTIONS=$(INCLUDES) -Davdecc_c_EXPORTS -fPIC -fvisibility=hidden

ifeq ($(DEBUG), 1)
OPTIONS+=-O0 -g -DDEBUG
LD_FLAGS+=-g
else
OPTIONS+=-O3 -DNDEBUG
endif

C_FLAGS=$(OPTIONS)
CPP_FLAGS=$(OPTIONS) -std=c++11
CLANG_FLAGS=$(INCLUDES)

ifneq (, $(findstring darwin, $(SYS)))
# MacOS
SHLIB_EXT=dylib
LD_FLAGS+=-dynamiclib
else ifneq (, $(findstring linux, $(SYS)))
# linux
SHLIB_EXT=so
LD_FLAGS+=-shared
endif

DYLIB=$(LIBNAME)_mod.$(SHLIB_EXT)


all: $(APIMOD)

%.o: %.c
	$(CC) -c $< $(C_FLAGS) -o $@

interface.opp: interface.cpp interface.h Makefile
	$(CXX) -c $< $(CPP_FLAGS) -o $@

$(DYLIB): $(OBJS)
	$(CXX) $^ $(LD_FLAGS) -o $@

$(APIMOD): interface.h $(DYLIB) Makefile ./patch_api.sh $(C_HDRS)
	-mkdir ./include
	for f in $(C_HDRS); do ./cvt_header.py "$$f" "./include/$${f##*/}"; done
	clang2py -l$(DYLIB) -i --clang-args="-I./include $(CLANG_FLAGS)" $< -o $@
	test -s $@
	./patch_api.sh "$@"

clean:
	rm -f $(OBJS) $(DYLIB) $(APIMOD)
