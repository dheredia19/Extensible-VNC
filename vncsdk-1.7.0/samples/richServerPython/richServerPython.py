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

"""This file contains the richServerPython sample.

This sample shows how to implement a rich VNC server using the Python bindings
for the VNC SDK.

Two types of connectivity are supported: Cloud-based and direct TCP
connection, with the server permitted to use both mechanisms concurrently.

To use direct TCP you will need to obtain a add-on code; a trial code
is available from your RealVNC account. You can ignore TCP-related code below
if you do not intend to use the Direct TCP add-on.

The server listens for incoming connections using connectivity details that
can be either specified on the command line, or hard-coded by editing the
Python file.

Each time it starts, the server generates a new random 4-digit password and
prints this to the console. A viewer must specify this password when prompted
in order to successfully connect.

This sample app also demonstrates messaging over the custom data channel.
Note this feature requires a separate add-on code; a trial code is
also available from your RealVNC account.

Messages relating to the list of displays currently attached to the Server
computer are sent to the Viewer in a modified JSON-RPC 2.0 format, with an
app-specific prefix. For more information, see www.jsonrpc.org/specification.
"""

import os
import random
import signal
import sys

from PySide import QtCore, QtGui

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
import ConnectionDetail

from SDKThread import SDKThread
from ServerCallbacks import ServerCallbacks


# Number of random digits in the auto-generated server password
SERVER_PASSWORD_LENGTH = 4


class Server(QtCore.QObject):
    # Data ready signals
    onServerReady = QtCore.Signal(object)
    onTCPListenerReady = QtCore.Signal(object)
    onCloudListenerReady = QtCore.Signal(object)
    onDisplayDataReady = QtCore.Signal(object)

    def __init__(self, sdkThread):
        QtCore.QObject.__init__(self)
        self._sdkThread = sdkThread
        self._tcpListener = None
        self._cloudListener = None
        self._server = None
        self._connectedViewers = set()
        self._serverCallbacks = ServerCallbacks(sdkThread)

        # Server callback registration
        self._serverCallbacks.onCloudStatuschanged.connect(self.cloudStatusChanged)
        self._serverCallbacks.onCloudListeningFailed.connect(self.cloudListeningFailed)
        self._serverCallbacks.onDisplaysChanged.connect(self.displaysChanged)
        self._serverCallbacks.onConnectionStarted.connect(self.connectionStarted)

        # Data ready registration
        self.onServerReady.connect(self.serverCreated)
        self.onCloudListenerReady.connect(self.cloudListenerCreated)
        self.onTCPListenerReady.connect(self.tcpListenerCreated)

        # Get things started!
        self._sdkThread.createServer("../../lib", self.onServerReady)

    def setPassword(self, password):
        self._serverCallbacks.setPassword(password)

    def shutdown(self):
        self._sdkThread.destroyTCPListener(self._tcpListener)
        self._sdkThread.destroyCloudListener(self._cloudListener)
        self._sdkThread.destroyServer(self._server)

        self._serverCallbacks.onCloudStatuschanged.disconnect(self.cloudStatusChanged)
        self._serverCallbacks.onCloudListeningFailed.disconnect(self.cloudListeningFailed)
        self._serverCallbacks.onDisplaysChanged.disconnect(self.displaysChanged)
        self._serverCallbacks.onConnectionStarted.disconnect(self.connectionStarted)

    #
    # Data objects ready signals
    #

    def serverCreated(self, server):
        self._server = server
        self._serverCallbacks.attachServer(self._server)
        canListen = False

        if ConnectionDetail.LOCAL_CLOUD_ADDRESS is not None:
            self._sdkThread.createCloudListener(server, self._serverCallbacks,
                                                self.onCloudListenerReady)
            canListen = True
        if ConnectionDetail.DIRECT_TCP_ADDON_CODE is not None:
            self._sdkThread.createTCPListener(server, self.onTCPListenerReady)
            canListen = True
        if not canListen:
            raise Exception("Unable to start listening")

    def cloudListenerCreated(self, listener):
        self._cloudListener = listener

    def tcpListenerCreated(self, listener):
        self._tcpListener = listener

    #
    # ServerCallback Signals
    #

    def cloudStatusChanged(self, listener, status):
        if status == vncsdk.CloudListener.Status.STATUS_SEARCHING:
            print("The listener is in the process of establishing "
                  "an association with VNC Cloud")
        else:
            print("Listening for VNC Cloud connections")

    def cloudListeningFailed(self, listener, cloud_error, suggested_retry_time):
        raise Exception("VNC Cloud listening error: {0}".format(cloud_error))

    def displaysChanged(self, *args):
        self._sdkThread.getDisplayListing(self._server, self.onDisplayDataReady)

    #
    # Connection signals (note - not RVSDK connection!)
    #

    def connectionStarted(self, connection):
        connection.init()
        connection.onConnectionEnded.connect(self.connectionEnded)
        self.onDisplayDataReady.connect(connection.onDisplayDataReady)
        self._connectedViewers.add(connection)

    def connectionEnded(self, connection):
        connection.onConnectionEnded.disconnect(self.connectionEnded)
        self.onDisplayDataReady.disconnect(connection.onDisplayDataReady)

        if connection in self._connectedViewers:
            self._connectedViewers.remove(connection)


def manageSignals():
    '''Install a signal handler to shut down the application on Ctrl-C or
       Ctrl-Break.'''
    signal.signal(signal.SIGINT, lambda *args: QtGui.QApplication.quit())
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, lambda *args: QtGui.QApplication.quit())

    # Run some Python code regularly so the signal handler takes effect.
    def checkSignals():
        QtCore.QTimer.singleShot(50, checkSignals)

    checkSignals()


def fatalExceptionCaught(stackTrace):
    sys.stderr.write(stackTrace)
    application.exit(1)


if __name__ == '__main__':
    sdkThread = SDKThread()

    application = QtGui.QApplication(sys.argv)
    manageSignals()

    sdkThread.onFatalExceptionCaught.connect(fatalExceptionCaught)
    sdkThread.start()

    password = ''.join(random.choice('0123456789')
                       for i in range(SERVER_PASSWORD_LENGTH))

    server = Server(sdkThread)
    server.setPassword(password)
    print("Server password: {0}".format(password))

    try:
        # Run until the application is shut down with Ctrl-C or Ctrl-Break.
        application.exec_()
    finally:
        server.shutdown()
        sdkThread.onFatalExceptionCaught.disconnect(fatalExceptionCaught)
        sdkThread.terminateThread()
        sdkThread.join(10.0)
