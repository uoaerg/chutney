#!/bin/sh

./tools/simpletest.sh --flavour netem-basic
./tools/simpletest.sh --flavour netem-basic-3G
./tools/simpletest.sh --flavour netem-basic-dsl
./tools/simpletest.sh --flavour netem-basic-edge
./tools/simpletest.sh --flavour netem-basic-lte
./tools/simpletest.sh --flavour netem-basic-min
./tools/simpletest.sh --flavour netem-basic-vbad
./tools/simpletest.sh --flavour netem-basic-wifi
./tools/simpletest.sh --flavour netem-basic-wifiac
