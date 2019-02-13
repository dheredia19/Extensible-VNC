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

import traceback
try:
    import cPickle as pickle
except ImportError:
    import pickle


# These samples use this message prefix. Your application should use its own.
MESSAGE_PREFIX = b'SAMPLEv2'


class RPCHandler(object):
    """
    A base class that implements remote procedure calls (RPC).

    Caution! For simplicity we use the standard library pickle module here.
    This is not safe to use with untrusted peers. A production implementation
    should use a safer encoding such as MessagePack. For details, see `PEP-307
    <https://www.python.org/dev/peps/pep-0307/#security-issues>`_.
    """

    def __init__(self, publicRpcMethods):
        self._publicRpcMethods = publicRpcMethods  # A list of method names.
        self._remoteCallId = 0
        self._outstandingCalls = {}

    def release(self):
        # Subclasses may implement this to release resources.
        pass

    #
    # Incoming message handler.
    #

    def _messageReceived(self, messagingMgr, connection, message):
        # Ignore unexpected messages for forwards compatibility.
        if message.startswith(MESSAGE_PREFIX):
            self._handlePayload(self._unpackMessage(message))

    #
    # Incoming RPC request dispatch.
    #

    def _handlePayload(self, payload):
        if 'method' in payload:
            self._handleRemoteCall(payload)
        elif 'result' in payload and 'id' in payload:
            self._handleRemoteResult(payload)
        elif 'error' in payload and 'id' in payload:
            self._handleRemoteError(payload)

    def _handleRemoteCall(self, payload):
        def reply(**kwargs):
            if 'id' in payload:
                message = self._makeMessage(dict(kwargs, id=payload['id']))
                self._sendMessage(message)

        method = payload['method']
        args = payload.get('params', [])

        # Dispatch to allowed methods of this object, as per JSON-RPC.
        if method not in self._publicRpcMethods:
            reply(error={'code': -32601, 'message': "Method not found"})
        else:
            try:
                result = getattr(self, method)(*args)
                reply(result=result)
            except Exception:
                traceback.print_exc()
                reply(error={'code': -32000, 'message': "Server error"})

    def _handleRemoteResult(self, payload):
        sentCall = self._outstandingCalls.pop(payload['id'], None)
        if sentCall:
            # Call the "on<MethodName>Result" method on this object.
            method = sentCall['method']
            target = 'on' + method[0].upper() + method[1:] + 'Result'
            getattr(self, target)(payload['result'])

    def _handleRemoteError(self, payload):
        sentCall = self._outstandingCalls.pop(payload['id'], None)
        if sentCall:
            print('Remote error: {method}: {error}'.format(
                method=sentCall['method'], error=payload['error']))

    #
    # Message packing/unpacking.
    #

    def _makeMessage(self, payload):
        """Return the bytes of a message that encodes the payload dict."""
        payload = payload.copy()
        payload['binrpc'] = '1.0'
        return MESSAGE_PREFIX + self._encodePayload(payload)

    def _unpackMessage(self, message):
        payloadBytes = message[len(MESSAGE_PREFIX):]
        return self._decodePayload(payloadBytes)

    #
    # Message payload encoding/decoding.
    #
    # As noted in the class docstring, production implementations should
    # use an alternative serialization format.
    #

    def _encodePayload(self, payload):
        return pickle.dumps(payload, protocol=1)

    def _decodePayload(self, payloadBytes):
        return pickle.loads(payloadBytes)

    #
    # Functions to send RPC calls.
    #

    def _nextRemoteCallId(self):
        self._remoteCallId += 1
        return self._remoteCallId

    def _sendBinaryCallMessage(self, method, *args):
        """
        Send a message representing a remote procedure call (RPC) to the named
        method, passing the other arguments. When a result is returned it will
        be passed to the correspondingly-named `self.on<Method>Result()`
        (capitalizing the first letter of `method`).
        """
        id = self._nextRemoteCallId()
        payload = dict(id=id, method=method, params=args)
        self._outstandingCalls[id] = payload
        message = self._makeMessage(payload)
        self._sendMessage(message)

    def _sendMessage(self, message):
        raise NotImplementedError("Subclass should implement this method")
