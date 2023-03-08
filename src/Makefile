LIBNAME=avdecc_mod

.PHONY: clean all

SYS := $(shell gcc -dumpmachine)
DEBUG ?= 0

CPP_SRCS=$(wildcard *.cpp) 
C_SRCS=$(wildcard ../jdksavdecc-c/src/*.c) $(wildcard ../avdecc-cmd/src/*.c)
OBJS=$(patsubst %.c,%.o,$(C_SRCS)) $(patsubst %.cpp,%.opp,$(CPP_SRCS))

OPTIONS=-I../jdksavdecc-c/include -I../avdecc-cmd/include

LD_FLAGS=-lpcap

ifeq ($(DEBUG), 1)
OPTIONS+=-O0 -g -DDEBUG
LD_FLAGS+=-g
else
OPTIONS+=-O3
endif

C_FLAGS=$(OPTIONS)
CPP_FLAGS=$(OPTIONS) -std=c++11

ifneq (, $(findstring darwin, $(SYS)))
# MacOS
SHLIB_EXT=dylib
LD_FLAGS+=-dynamiclib
else ifneq (, $(findstring linux, $(SYS)))
# linux
SHLIB_EXT=so
LD_FLAGS+=-shared
endif

DYLIB=$(LIBNAME).$(SHLIB_EXT)

all: $(DYLIB)

%.o: %.c
	$(CC) -c $< $(C_FLAGS) -o $@

%.opp: %.cpp
	$(CXX) -c $< $(CPP_FLAGS) -o $@

$(DYLIB): $(OBJS)
	$(CXX) $^ $(LD_FLAGS) -o $@

clean:
	rm $(OBJS) $(DYLIB)