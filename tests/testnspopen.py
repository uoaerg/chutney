#!/usr/bin/env python

import pyroute2
import subprocess


def drop_privilege():
	print("drop")

cmdline=["ls", "/home/tom/chutney/net/nodes/000a/"]

p = pyroute2.NSPopen('ns1', cmdline,             
                     stdin=None,
                     universal_newlines=True,    
                     bufsize=-1,                 
                     preexec_fn=drop_privilege())

print(p)
result = p.wait()

print(result)

