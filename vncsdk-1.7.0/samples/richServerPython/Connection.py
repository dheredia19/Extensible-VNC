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
#
# Note this sample makes use of PySide, which is licensed under the terms of
# the LGPL v2.1.

import threading

from PySide import QtCore, QtGui

from RPCFunctions import RPCFunctions


class Connection(QtCore.QObject):
    '''
    This thread-safe class wraps a VNC connection object, and ensures that
    no operations are performed on a connection that is disconnected.
    '''

    onConnectionEnded = QtCore.Signal(object)
    onDisplayDataReady = QtCore.Signal(object)

    def __init__(self, server, sdkThread, connection, callbacks):
        QtCore.QObject.__init__(self)
        self._server = server
        self._sdkThread = sdkThread
        self._connection = connection
        self._callbacks = callbacks
        self._lock = threading.Lock()
        self._rpcWorker = None

        # Transfer this connection object to the main application thread.
        self.moveToThread(QtGui.QApplication.instance().thread())

    def init(self):
        '''
        Sets up event listeners and windows for this connection.
        Call on the UI thread only.
        '''
        with self._lock:
            self._rpcWorker = RPCFunctions(self._sdkThread, self._server, self, self._callbacks)
            self.onConnectionEnded.connect(self._connectionEnded)
            self.onDisplayDataReady.connect(self.sendDisplayData)
            self._sdkThread.getDisplayListing(self._server, self.onDisplayDataReady)

    def getVNCConnection(self):
        with self._lock:
            return self._connection

    def sendDisplayData(self, data):
        with self._lock:
            if self._rpcWorker is not None:
                self._rpcWorker.sendDisplayData(data)

    def connectionEnded(self):
        with self._lock:
            self._connection = None
            self.onConnectionEnded.emit(self)

    def _connectionEnded(self, connection):
        with self._lock:
            self._rpcWorker.release()
            self._rpcWorker = None
