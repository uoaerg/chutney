#!/usr/bin/python
#
# Copyright 2011 Nick Mathewson, Michael Stone
#
#  You may do anything with this work that copyright law would normally
#  restrict, so long as you retain the above notice(s) and this license
#  in all redistributed copies and derived works.  There is no warranty.

from __future__ import with_statement

import cgitb
cgitb.enable(format="plain")

import os
import signal
import subprocess
import sys
import re
import errno
import time

import chutney.Templating


def mkdir_p(d):
    try:
        os.makedirs(d)
    except OSError, e:
        if e.errno == errno.EEXIST:
            return
        raise

class Node(object):
    ########
    # Users are expected to call these:
    def __init__(self, parent=None, **kwargs):
        self._parent = parent
        self._env = self._createEnviron(parent, kwargs)

    def getN(self, N):
        return [ Node(self) for _ in xrange(N) ]

    def specialize(self, **kwargs):
        return Node(parent=self, **kwargs)

    def expand(self, pat, includePath=(".",)):
        return chutney.Templating.Template(pat, includePath).format(self._env)


    #######
    # Users are NOT expected to call these:
    def _getTorrcFname(self):
        return self.expand("${torrc_fname}")

    def _createTorrcFile(self, checkOnly=False):
        fn_out = self._getTorrcFname()
        torrc_template = self._getTorrcTemplate()
        output = torrc_template.format(self._env)
        if checkOnly:
            return
        with open(fn_out, 'w') as f:
            f.write(output)

    def _getTorrcTemplate(self):
        template_path = self._env['torrc_template_path']
        return chutney.Templating.Template("$${include:$torrc}",
            includePath=template_path)

    def _getFreeVars(self):
        template = self._getTorrcTemplate()
        return template.freevars(self._env)

    def _createEnviron(self, parent, argdict):
        if parent:
            parentenv = parent._env
        else:
            parentenv = self._getDefaultEnviron()
        return TorEnviron(parentenv, **argdict)

    def _getDefaultEnviron(self):
        return _BASE_ENVIRON

    def _checkConfig(self, net):
        self._createTorrcFile(checkOnly=True)

    def _preConfig(self, net):
        self._makeDataDir()
        if self._env['authority']:
            self._genAuthorityKey()
        if self._env['relay']:
            self._genRouterKey()

    def _config(self, net):
        self._createTorrcFile()
        #self._createScripts()

    def _postConfig(self, net):
        #self.net.addNode(self)
        pass

    def _setnodenum(self, num):
        self._env['nodenum'] = num

    def _makeDataDir(self):
        datadir = self._env['dir']
        mkdir_p(os.path.join(datadir, 'keys'))

    def _genAuthorityKey(self):
        datadir = self._env['dir']
        tor_gencert = self._env['tor_gencert']
        lifetime = self._env['auth_cert_lifetime']
        idfile   = os.path.join(datadir,'keys',"authority_identity_key")
        skfile   = os.path.join(datadir,'keys',"authority_signing_key")
        certfile = os.path.join(datadir,'keys',"authority_certificate")
        addr = self.expand("${ip}:${dirport}")
        passphrase = self._env['auth_passphrase']
        if all(os.path.exists(f) for f in [idfile, skfile, certfile]):
            return
        cmdline = [
            tor_gencert,
            '--create-identity-key',
            '--passphrase-fd', '0',
            '-i', idfile,
            '-s', skfile,
            '-c', certfile,
            '-m', str(lifetime),
            '-a', addr]
        print "Creating identity key %s for %s with %s"%(
            idfile,self._env['nick']," ".join(cmdline))
        p = subprocess.Popen(cmdline, stdin=subprocess.PIPE)
        p.communicate(passphrase+"\n")
        assert p.returncode == 0 #XXXX BAD!

    def _genRouterKey(self):
        datadir = self._env['dir']
        tor = self._env['tor']
        idfile = os.path.join(datadir,'keys',"identity_key")
        cmdline = [
            tor,
            "--quiet",
            "--list-fingerprint",
            "--orport", "1",
            "--dirserver",
                 "xyzzy 127.0.0.1:1 ffffffffffffffffffffffffffffffffffffffff",
            "--datadirectory", datadir ]
        p = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        fingerprint = "".join(stdout.split()[1:])
        assert re.match(r'^[A-F0-9]{40}$', fingerprint)
        self._env['fingerprint'] = fingerprint

    def _getDirServerLine(self):
        if not self._env['authority']:
            return ""

        datadir = self._env['dir']
        certfile = os.path.join(datadir,'keys',"authority_certificate")
        v3id = None
        with open(certfile, 'r') as f:
            for line in f:
                if line.startswith("fingerprint"):
                    v3id = line.split()[1].strip()
                    break

        assert v3id is not None

        return "DirServer %s v3ident=%s orport=%s %s %s:%s %s\n" %(
            self._env['nick'], v3id, self._env['orport'],
            self._env['dirserver_flags'], self._env['ip'], self._env['dirport'],
            self._env['fingerprint'])


    ##### Controlling a node.  This should probably get split into its
    # own class. XXXX

    def getPid(self):
        pidfile = os.path.join(self._env['dir'], 'pid')
        if not os.path.exists(pidfile):
            return None

        with open(pidfile, 'r') as f:
            return int(f.read())

    def isRunning(self, pid=None):
        if pid is None:
            pid = self.getPid()
        if pid is None:
            return False

        try:
            os.kill(pid, 0) # "kill 0" == "are you there?"
        except OSError, e:
            if e.errno == errno.ESRCH:
                return False
            raise

        # okay, so the process exists.  Say "True" for now.
        # XXXX check if this is really tor!
        return True

    def check(self, listRunning=True, listNonRunning=False):
        pid = self.getPid()
        running = self.isRunning(pid)
        nick = self._env['nick']
        dir = self._env['dir']
        if running:
            if listRunning:
                print "%s is running with PID %s"%(nick,pid)
            return True
        elif os.path.exists(os.path.join(dir, "core.%s"%pid)):
            if listNonRunning:
                print "%s seems to have crashed, and left core file core.%s"%(
                   nick,pid)
            return False
        else:
            if listNonRunning:
                print "%s is stopped"%nick
            return False

    def hup(self):
        pid = self.getPid()
        running = self.isRunning()
        nick = self._env['nick']
        if self.isRunning():
            print "Sending sighup to %s"%nick
            os.kill(pid, signal.SIGHUP)
            return True
        else:
            print "%s is not running"%nick
            return False

    def start(self):
        if self.isRunning():
            print "%s is already running"%self._env['nick']
            return
        torrc = self._getTorrcFname()
        cmdline = [
            self._env['tor'],
            "--quiet",
            "-f", torrc,
            ]
        p = subprocess.Popen(cmdline)
        # XXXX this requires that RunAsDaemon is set.
        p.wait()
        if p.returncode != 0:
            print "Couldn't launch %s (%s): %s"%(self._env['nick'],
                                                 " ".join(cmdline),
                                                 p.returncode)
            return False
        return True

    def stop(self, sig=signal.SIGINT):
        pid = self.getPid()
        if not self.isRunning(pid):
            print "%s is not running"%self._env['nick']
            return
        os.kill(pid, sig)


DEFAULTS = {
    'authority' : False,
    'relay' : False,
    'connlimit' : 60,
    'net_base_dir' : 'net',
    'tor' : 'tor',
    'auth_cert_lifetime' : 12,
    'ip' : '127.0.0.1',
    'dirserver_flags' : 'no-v2',
    'privnet_dir' : '.',
    'torrc_fname' : '${dir}/torrc',
    'orport_base' : 6000,
    'dirport_base' : 7000,
    'controlport_base' : 8000,
    'socksport_base' : 9000,
    'dirservers' : "Dirserver bleargh bad torrc file!",
    'core' : True,
}

class TorEnviron(chutney.Templating.Environ):
    def __init__(self,parent=None,**kwargs):
        chutney.Templating.Environ.__init__(self, parent=parent, **kwargs)

    def _get_orport(self, my):
        return my['orport_base']+my['nodenum']

    def _get_controlport(self, my):
        return my['controlport_base']+my['nodenum']

    def _get_socksport(self, my):
        return my['socksport_base']+my['nodenum']

    def _get_dirport(self, my):
        return my['dirport_base']+my['nodenum']

    def _get_dir(self, my):
        return os.path.abspath(os.path.join(my['net_base_dir'],
                                            "nodes",
                                         "%03d%s"%(my['nodenum'], my['tag'])))

    def _get_nick(self, my):
        return "test%03d%s"%(my['nodenum'], my['tag'])

    def _get_tor_gencert(self, my):
        return my['tor']+"-gencert"

    def _get_auth_passphrase(self, my):
        return self['nick'] # OMG TEH SECURE!

    def _get_torrc_template_path(self, my):
        return [ os.path.join(my['privnet_dir'], 'torrc_templates') ]


class Network(object):
    def __init__(self,defaultEnviron):
        self._nodes = []
        self._dfltEnv = defaultEnviron
        self._nextnodenum = 0

    def _addNode(self, n):
        n._setnodenum(self._nextnodenum)
        self._nextnodenum += 1
        self._nodes.append(n)

    def _checkConfig(self):
        for n in self._nodes:
            n._checkConfig(self)

    def configure(self):
        network = self
        dirserverlines = []

        self._checkConfig()

        # XXX don't change node names or types or count if anything is
        # XXX running!

        for n in self._nodes:
            n._preConfig(network)
            dirserverlines.append(n._getDirServerLine())

        self._dfltEnv['dirservers'] = "".join(dirserverlines)

        for n in self._nodes:
            n._config(network)

        for n in self._nodes:
            n._postConfig(network)

    def status(self):
        statuses = [n.check() for n in self._nodes]
        n_ok = len([x for x in statuses if x])
        print "%d/%d nodes are running"%(n_ok,len(self._nodes))

    def restart(self):
        self.stop()
        self.start()

    def start(self):
        print "Starting nodes"
        return all([n.start() for n in self._nodes])

    def hup(self):
        print "Sending SIGHUP to nodes"
        return all([n.hup() for n in self._nodes])

    def stop(self):
        for sig, desc in [(signal.SIGINT, "SIGINT"),
                          (signal.SIGINT, "another SIGINT"),
                          (signal.SIGKILL, "SIGKILL")]:
            print "Sending %s to nodes"%desc
            for n in self._nodes:
                if n.isRunning():
                    n.stop(sig=sig)
            print "Waiting for nodes to finish."
            for n in xrange(15):
                time.sleep(1)
                if all(not n.isRunning() for n in self._nodes):
                    return
                sys.stdout.write(".")
                sys.stdout.flush()
            for n in self._nodes:
                n.check(listNonRunning=False)

def ConfigureNodes(nodelist):
    network = _THE_NETWORK

    for n in nodelist:
        network._addNode(n)

def usage(network):
    return "\n".join(["Usage: chutney {command} {networkfile}",
       "Known commands are: %s" % (
        " ".join(x for x in dir(network) if not x.startswith("_")))])

def runConfigFile(verb, f):
    _GLOBALS = dict(_BASE_ENVIRON= _BASE_ENVIRON,
                    Node=Node,
                    ConfigureNodes=ConfigureNodes,
                    _THE_NETWORK=_THE_NETWORK)

    exec f in _GLOBALS
    network = _GLOBALS['_THE_NETWORK']

    if not hasattr(network, verb):
        print usage(network)
        print "Error: I don't know how to %s." % verb
        return

    getattr(network,verb)()

def main():
    global _BASE_ENVIRON
    global _THE_NETWORK
    _BASE_ENVIRON = TorEnviron(chutney.Templating.Environ(**DEFAULTS))
    _THE_NETWORK = Network(_BASE_ENVIRON)

    if len(sys.argv) < 3:
        print usage(_THE_NETWORK)
        print "Error: Not enough arguments given."
        sys.exit(1)

    f = open(sys.argv[2])
    runConfigFile(sys.argv[1], f)

if __name__ == '__main__':
    main()