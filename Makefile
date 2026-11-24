# Build the two simulators into bin/ (any C++17 compiler: clang++ on macOS, g++ on Linux).
CXX ?= c++
CXXFLAGS ?= -O3 -std=c++17

all: bin/cachesim bin/tsgdsim

bin/cachesim: src/cachesim.cpp
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) -o $@ $<

bin/tsgdsim: src/tsgdsim.cpp
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) -o $@ $<

test: all
	python3 scripts/test_cachesim.py

clean:
	rm -f bin/cachesim bin/tsgdsim

.PHONY: all test clean
