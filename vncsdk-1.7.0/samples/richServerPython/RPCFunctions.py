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

from ConnectionDetail import canUseMessaging
from RPCHandler import RPCHandler


class RPCFunctions(RPCHandler):

    def __init__(self, sdkThread, server, connection, callbacks):
        RPCHandler.__init__(self, ['selectDisplay'])
        self._sdkThread = sdkThread
        self._server = server
        self._connection = connection
        self._callbacks = callbacks
        self._callbacks.onMessageReceived.connect(self._messageReceived)

    #
    # Overrides for superclass methods.
    #

    def release(self):
        self._callbacks.onMessageReceived.disconnect(self._messageReceived)

    def _sendMessage(self, message):
        if canUseMessaging():
            self._sdkThread.sendMessageToConnection(
                self._server, self._connection, message)

    #
    # Public API for outgoing RPC calls.
    #

    def sendDisplayData(self, displays):
        self._sendBinaryCallMessage('displaysChanged', displays)

    #
    # Public API for incoming RPC calls.
    #
    # Only methods in the list passed to RPCHandler's constructor are exposed.
    #

    def selectDisplay(self, index):
        self._sdkThread.selectDisplay(self._server, index)

    #
    # Handlers for the results of outgoing RPC calls.
    #

    def onDisplaysChangedResult(self, _result):
        return
