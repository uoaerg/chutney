#!/bin/sh

./tools/onionperf.sh --flavour netem-basic
./tools/onionperf.sh --flavour netem-basic-3G
./tools/onionperf.sh --flavour netem-basic-dsl
./tools/onionperf.sh --flavour netem-basic-edge
./tools/onionperf.sh --flavour netem-basic-lte
./tools/onionperf.sh --flavour netem-basic-min
./tools/onionperf.sh --flavour netem-basic-vbad
./tools/onionperf.sh --flavour netem-basic-wifi
./tools/onionperf.sh --flavour netem-basic-wifiac
