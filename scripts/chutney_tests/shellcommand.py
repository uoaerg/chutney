import pyroute2
import subprocess
import os
import pwd

import chutney.Templating
import chutney.TorNet

# run a loop back test for each client in the network
def run_test(network):
    boot_time= network._dfltEnv['bootstrap_time']
    cmdline = network._dfltEnv['cmdline']

    cmdline = cmdline[3:]
    print("Running commad with chutney test network {}".format(cmdline))

    testsrun = 0
    # walk the network, find the first client network to use
    for node in network._nodes:
        if node._env['nick'].endswith('c'):
            node._env['authorities'] = get_auth_lines(node._env)
            node._env['torrc'] = 'base.tmpl'

            temp = chutney.Templating.Template("$${include:$torrc}",
                includePath=node._env['torrc_template_path'])
            torrc = temp.format(node._env)

            netns = 'chtny' + node._env['nick']
            socksport = node._env['socksport']
            controlport = node._env['controlport']

            if run_cmd_netns(cmdline, netns, torrc, socksport, controlport):
                testsrun = testsrun + 1

    if testsrun == 0:
        print('run_test: unable to find a client node for test')
        return False

def get_auth_lines(env):
    torrc_file = chutney.Templating.Template("${torrc_fname}", ".").format(env)
    authlines = []

    with open(torrc_file) as torrc:
        for line in torrc:
            if line.startswith("DirAuthority"):
                authlines.append(line)
    return "".join(authlines)

def run_cmd_netns(cmdline, netns, torrc, socksport, controlport):
    print("Running command in client namespace {}\n{}".format(netns, cmdline))

    env = os.environ.copy()
    env["BASETORRC"] = torrc
    env["SOCKS_PORT"] = str(socksport)
    env["CONTROL_PORT"] = str(controlport)

    p = pyroute2.NSPopen(netns, cmdline,shell=True, env=env,
			 preexec_fn=drop_privilege())
    p.wait()

    if p.returncode == 0:
        return True
    else:
        return False

def drop_privilege(user=None):
    print(os.environ['SUDO_USER'])

    if not user:
        user = os.environ['SUDO_USER']
        if not user:
            print("not running under sudo, cannot find user for unpriviledged commands")
            exit()
    if os.geteuid() == 0:
        pw_record = pwd.getpwnam(user)
        print("[DEBUG] TODO: drop privileges on process start")
        #os.setgid(pw_record.pw_uid)
        #os.setuid(pw_record.pw_gid)

if __name__ == "__main__":
    cmdline = "onionperf measure --tgen=/home/tom/shadow/src/plugin/shadow-plugin-tgen/build/tgen --oneshot"
    run_cmd_netns(cmdline.split(" "), "ns1")
