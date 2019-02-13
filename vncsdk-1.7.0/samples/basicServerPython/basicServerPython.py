# Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""This file contains the basicServerPython sample.

Usage:
    python basicServerPython.py [LOCAL_CLOUD_ADDRESS] [LOCAL_CLOUD_PASSWORD]
                                [TCP_PORT]

Arguments:
    LOCAL_CLOUD_ADDRESS   - the VNC Cloud address for this Server
    LOCAL_CLOUD_PASSWORD  - the VNC Cloud password for this Server
    TCP_PORT              - direct TCP port number

    All arguments may be omitted if they have been hard-coded in this file.


This sample shows how to implement a basic VNC server using the Python bindings
for the VNC SDK.

Two types of connectivity are supported: Cloud-based and direct TCP
connection, with the server permitted to use both mechanisms concurrently.

Note: To use direct TCP you will need to apply an add-on code; a trial
code is available from your RealVNC account. You can ignore TCP-related
code below if you do not intend to use the Direct TCP add-on.

The server listens for incoming connections using connectivity details that
can be either specified on the command line, or hard-coded by editing the
Python file.

Each time it starts, the server generates a new random 4-digit password and
prints this to the console. A viewer must specify this password when prompted
in order to successfully connect.
"""

import os
import random
import signal
import string
import sys
import threading
import time

# Before importing the SDK bindings, we set the VNCSDK_LIBRARY environment
# variable, which determines where the Python bindings (vncsdk.py) will search
# for the shared library (DLL).  This sample assumes the directory structure
# used to distribute the samples has been preserved, and searches for the
# shared accordingly.  We also append the path of the Python bindings
# themselves to the search path.
sample_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['VNCSDK_LIBRARY'] = os.path.join(sample_dir, '..', '..', 'lib')
sys.path.append(os.path.join(sample_dir, '..', '..', 'lib', 'python'))
vncagent_path = os.path.join(sample_dir, '..', '..', 'lib')
import vncsdk

# For Cloud connections, either hard-code the Cloud address for the Server OR
# specify it at the command line. Example Cloud address:
# LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
LOCAL_CLOUD_ADDRESS = None

# Either hard-code the Cloud password associated with this Cloud address OR
# specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
LOCAL_CLOUD_PASSWORD = None

# To enable direct TCP connectivity you need to copy the content of your
# add-on code into the string below.
direct_tcp_add_on_code = None

# For direct TCP connection you must provide a TCP listening port number.
# Either edit TCP_PORT variable below OR provide the port number on the command
# line. The default direct TCP port number can be specified below by using:
# TCP_PORT = vncsdk.DirectTcp.DEFAULT_PORT
# Ignore this if you are not using the Direct TCP add-on
TCP_PORT = 0

# The following flags indicate the type of connection(s) being used and they
# are set automatically according to user-supplied command line arguments and
# the macro definitions above. Each type of connection is optional.
# If you set any flag to true below then that makes that type of connection
# mandatory i.e. connectivity details MUST be provided via the command line or
# via hard-coded values from global variables above.
using_cloud = False
using_direct_tcp = False

# Number of random digits in the auto-generated server password:
SERVER_PASSWORD_LENGTH = 4


class ConnectionCallback(vncsdk.Server.ConnectionCallback):
    """Connection callback, notified when a viewer connects or disconnects."""

    def connection_started(self, server, connection):
        print("Viewer {viewer} connected".format(
            viewer=server.get_peer_address(connection)
        ))

    def connection_ended(self, server, connection):
        print("Viewer {viewer} disconnected".format(
            viewer=server.get_peer_address(connection)
        ))


class SecurityCallback(vncsdk.Server.SecurityCallback):
    """Security callback, used to authenticate incoming connections."""

    def __init__(self):
        # Generate the server password using a series of random digits,
        # selected using the system's secure generator.
        gen = random.SystemRandom()
        self.password = ''.join(
            gen.choice(string.digits) for i in range(SERVER_PASSWORD_LENGTH)
        )
        print("Server password is: {password}".format(password=self.password))

        # If you implement __init__() for a callback object, remember to call
        # the parent SDK object's __init__() method!
        vncsdk.Server.SecurityCallback.__init__(self)

    def is_user_name_required(self, server, connection):
        # Don't prompt for a username when accessing this server, just a
        # password is required
        return False

    def authenticate_user(self, server, connection, username, password):
        # Check that the password supplied by the connecting viewer is the same
        # as the server's auto-generated random password. If so, allow the
        # connection with all permissions, otherwise do not allow the
        # connection.
        if password == self.password:
            return set([vncsdk.Server.Permissions.PERM_ALL])
        else:
            return set()


def wait_for_enter_and_exit():
    """Prompt and wait for user to press enter before continuing.
    This is used when displaying error messages, allowing the user to read the
    message on systems where the terminal closes when the program exits.
    """
    if sys.version_info >= (3, 0):
        input("Press ENTER to continue...")
    else:
        raw_input("Press ENTER to continue...")
    sys.exit(1)


def usage_advice():
    """Provide usage information on console."""
    usage = sys.modules[__name__].__doc__.split('\n')[2:10]
    print('\n'.join(usage))
    wait_for_enter_and_exit()


def extract_port_num(arg):
    """Extract port number from command line argument."""
    port = 0
    try:
        port = int(arg)
    except ValueError:
        print("Invalid port number\n")
    return port


def parse_command_line():
    """Parse the command line to obtain connectivity details to be used when
    listening for incoming connections. A simplistic approach is adopted:

    3 arguments - Cloud and direct TCP connectivity to be used
                  [LOCAL_CLOUD_ADDRESS LOCAL_CLOUD_PASSWORD] [TCP_PORT]

    2 arguments - Cloud connectivity to be used
                  [LOCAL_CLOUD_ADDRESS LOCAL_CLOUD_PASSWORD]

    1 argument  - Direct TCP connectivity to be used
                  [TCP_PORT]

    0 arguments - the built-in macros must be set appropriately
    """
    global LOCAL_CLOUD_ADDRESS, LOCAL_CLOUD_PASSWORD, TCP_PORT
    global using_cloud, using_direct_tcp
    bad_args = False
    argc = len(sys.argv)

    # Parse any supplied command line arguments
    if argc >= 1 and argc <= 4:
        if argc == 4:  # Cloud and direct TCP arguments
            LOCAL_CLOUD_ADDRESS = sys.argv[1]
            LOCAL_CLOUD_PASSWORD = sys.argv[2]
            TCP_PORT = extract_port_num(sys.argv[3])
            using_cloud = using_direct_tcp = True
        elif argc == 3:  # Cloud arguments only
            LOCAL_CLOUD_ADDRESS = sys.argv[1]
            LOCAL_CLOUD_PASSWORD = sys.argv[2]
            using_cloud = True
        elif argc == 2:  # Direct TCP argument only
            TCP_PORT = extract_port_num(sys.argv[1])
            using_direct_tcp = True
        else:  # Examine initial values
            if LOCAL_CLOUD_ADDRESS or LOCAL_CLOUD_PASSWORD:
                using_cloud = True
            if TCP_PORT:
                using_direct_tcp = True

        # Check if all required connectivity details are provided either via
        # editing the global variables above, or on the command-line
        if using_cloud and (not LOCAL_CLOUD_ADDRESS or
                            not LOCAL_CLOUD_PASSWORD):
            print("You must provide a valid Cloud address and password\n")
            bad_args = True
        if using_direct_tcp and not TCP_PORT:
            print("You must provide a valid TCP port number\n")
            bad_args = True
        if not using_cloud and not using_direct_tcp:
            print("No connectivity information provided.\n")
            bad_args = True
    else:
        bad_args = True  # Invalid number of arguments

    if bad_args:
        usage_advice()


class CloudListenerCallback(vncsdk.CloudListener.Callback):
    """Cloud listener callback, used to exit the application if there is an
    error connecting to VNC Cloud.
    """

    def listening_status_changed(self, listener, status):
        if status == vncsdk.CloudListener.Status.STATUS_SEARCHING:
            print(
                "The listener is in the process of establishing " +
                "an association with VNC Cloud"
            )
        else:
            print("Listening for VNC Cloud connections")

    def listening_failed(self, listener, cloud_error, suggested_retry_time):
        vncsdk.EventLoop.stop()
        print("VNC Cloud listening error: {message}".format(
            message=cloud_error
        ))


class RsaKeyCallback(vncsdk.RsaKey.Callback):
    """RsaKey callback - key details ready"""

    def details_ready(self, rsa_public, hex_fingerprint,
                      catchphrase_fingerprint):
        print("Server id is: {fingerprint}".format(
            fingerprint=hex_fingerprint))
        print("Server catchphrase is: {fingerprint}".format(
            fingerprint=catchphrase_fingerprint))


# An event indicating that vncsdk.shutdown() has been called.
finished = threading.Event()

# Register a Ctrl-C/Ctrl-Break handler on Windows to stop the event loop.
if os.name == 'nt':
    from ctypes import WINFUNCTYPE, windll, WinError
    from ctypes.wintypes import BOOL, DWORD

    PHANDLER_ROUTINE = WINFUNCTYPE(BOOL, DWORD)

    # A top-level function so Python doesn't garbage collect it too early.
    @PHANDLER_ROUTINE
    def console_ctrl_handler(event_type):
        vncsdk.EventLoop.stop()
        finished.wait()
        return False

    kernel32 = windll.LoadLibrary('kernel32')
    SetConsoleCtrlHandler = kernel32.SetConsoleCtrlHandler
    SetConsoleCtrlHandler.argtypes = (PHANDLER_ROUTINE, BOOL)
    SetConsoleCtrlHandler.restype = BOOL
    if not SetConsoleCtrlHandler(console_ctrl_handler, True):
        raise WinError()


if __name__ == '__main__':
    # Parse command line
    parse_command_line()

    # Create a logger which outputs to sys.stderr
    vncsdk.Logger.create_stderr_logger()

    # Create a file DataStore for storing persistent data for the server.
    # Ideally this would be created in a directory that only the server
    # user has access to.
    vncsdk.DataStore.create_file_store("fileStore.txt")

    server = None
    cloud_listener = None
    direct_tcp_listener = None
    try:
        # Initialize SDK and optional Add-Ons
        vncsdk.init()
        if using_direct_tcp:
            try:
                vncsdk.enable_add_on(direct_tcp_add_on_code)
            except Exception as e:
                print("Failed to enable Direct TCP add-on: {error}".format(
                    error=e))
                wait_for_enter_and_exit()

        # Initialise the server.  Note that if the vncagent path is not
        # specified, vncagent will be searched for inside the main module's
        # directory.  We explicitly specify the agent's location, assuming
        # that the directory structure used to distribute the samples has
        # been preserved.
        server = vncsdk.Server(vncagent_path)
        server.set_connection_callback(ConnectionCallback())
        server.set_security_callback(SecurityCallback())

        # Listen on each transport that we intend to use.
        if using_cloud:
            print("Signing in to VNC Cloud")
            cloud_listener = \
                vncsdk.CloudListener(LOCAL_CLOUD_ADDRESS,
                                     LOCAL_CLOUD_PASSWORD,
                                     server.get_connection_handler(),
                                     CloudListenerCallback())
        if using_direct_tcp:
            # Start listening for connections made via direct TCP.
            # Ignore this if you do not intend to use the Direct TCP add-on.
            print("Listening for Direct TCP connections")
            direct_tcp_listener = \
                vncsdk.DirectTcpListener(TCP_PORT,
                                         None,
                                         server.get_connection_handler(),
                                         None)
            # If DirectTcp is being used, request the RSA key details to
            # display so that viewers can verify they are connecting to this
            # server.
            vncsdk.RsaKey.get_details(RsaKeyCallback(), True)

        # Server setup complete, now run the EventLoop.  If you run the SDK's
        # event loop in the Python runtime's main thread, then Python signal
        # handlers won't be fired (the SDK's run() method acts like a single
        # blocking API call), so we disable SIGINT to allow the user to kill
        # the sample using Ctrl-C.
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        vncsdk.EventLoop.run()

    except vncsdk.VncException as e:
        print(str(e))
        wait_for_enter_and_exit()

    finally:
        if server:
            server.destroy()
        if cloud_listener:
            cloud_listener.destroy()
        if direct_tcp_listener:
            direct_tcp_listener.destroy()

        vncsdk.shutdown()
        finished.set()
