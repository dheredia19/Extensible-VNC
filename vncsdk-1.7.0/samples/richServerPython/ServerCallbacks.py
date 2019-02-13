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

"""
A proxy which receives RealVNC SDK event callbacks and emits Qt signals.
"""

import vncsdk
import ConnectionDetail
import Connection

from PySide import QtCore


class ServerCallbacks(vncsdk.CloudListener.Callback,
                      vncsdk.DisplayManager.Callback,
                      vncsdk.Server.SecurityCallback,
                      vncsdk.Server.ConnectionCallback,
                      vncsdk.AnnotationManager.Callback,
                      vncsdk.MessagingManager.Callback,
                      QtCore.QObject):
    """
    A proxy which receives RealVNC SDK event callbacks and emits Qt signals.

    Similar to the basic server, here we only resize the window or send events
    to the window in the callback functions.

    All the functions are expected to be called from the SDK Thread, meaning
    that SDK functions can safely be called as a reaction before emitting
    signals.
    """

    # emit(listener, status)
    onCloudStatuschanged = QtCore.Signal(object, int)

    # emit(listener, error, retryTime)
    onCloudListeningFailed = QtCore.Signal(object, int, int)

    # emit(displayManager)
    onDisplaysChanged = QtCore.Signal(object)

    # emit(connection)
    onConnectionStarted = QtCore.Signal(object)

    # emit(connection)
    onConnectionEnded = QtCore.Signal(object)

    # emit(annotationMgr, availability)
    onAnnotationAvailChanged = QtCore.Signal(bool)

    # emit(messagingMgr, connection, message)
    onMessageReceived = QtCore.Signal(object, object, object)

    def __init__(self, sdkThread):
        QtCore.QObject.__init__(self)
        vncsdk.CloudListener.Callback.__init__(self)
        vncsdk.DisplayManager.Callback.__init__(self)
        vncsdk.Server.SecurityCallback.__init__(self)
        vncsdk.Server.ConnectionCallback.__init__(self)
        vncsdk.AnnotationManager.Callback.__init__(self)
        vncsdk.MessagingManager.Callback.__init__(self)
        self.attached = False
        self.password = None
        self._sdkThread = sdkThread
        self._connections = {}

    def setPassword(self, password):
        self.password = password

    def _getDisplayManager(self, server):
        try:
            return server.get_display_manager()
        except vncsdk.VncException as exc:
            if exc.errorCode == 'NotSupported':
                return None
            else:
                raise

    def attachServer(self, server):
        server.set_connection_callback(self)
        server.set_security_callback(self)
        server.get_annotation_manager().set_callback(self)
        displayManager = self._getDisplayManager(server)
        if displayManager:
            displayManager.set_callback(self)
        if ConnectionDetail.canUseMessaging():
            server.get_messaging_manager().set_callback(self)
        self.attached = True

    def detachServer(self, server):
        server.set_connection_callback(None)
        server.set_security_callback(None)
        server.get_annotation_manager().set_callback(None)
        displayManager = self._getDisplayManager(server)
        if displayManager:
            displayManager.set_callback(None)
        if ConnectionDetail.canUseMessaging():
            server.get_messaging_manager().set_callback(None)
        self.attached = False

    #
    # CloudListener.Callback functions
    #

    def listening_status_changed(self, listener, status):
        self.onCloudStatuschanged.emit(listener, status)

    def listening_failed(self, listener, err, suggested_retry):
        self.onCloudListeningFailed.emit(listener, err, suggested_retry)

    #
    # DisplayManager.Callback functions
    #

    def displays_changed(self, displayManager):
        self.onDisplaysChanged.emit(displayManager)

    #
    # Server.SecurityCallback functions
    #

    def is_user_name_required(self, server, connection):
        return False

    def authenticate_user(self, server, connection, username, password):
        if self.password == password:
            return set([vncsdk.Server.Permissions.PERM_ALL])
        else:
            return set([])

    #
    # ConnectionCallback.Callback functions
    #

    def connection_started(self, server, connection):
        con = Connection.Connection(connection=connection,
                         server=server,
                         sdkThread=self._sdkThread,
                         callbacks=self)
        self._connections[connection] = con
        self.onConnectionStarted.emit(con)

    def connection_ended(self, server, connection):
        con = self._connections[connection]
        del self._connections[connection]
        con.connectionEnded()

    #
    # AnnotationManager.Callback functions
    #

    def availability_changed(self, annotationMgr, availability):
        self.onAnnotationAvailChanged.emit(availability)

    #
    # MessagingManager.Callback functions
    #

    def message_received(self, messagingMgr, connection, messageBuffer):
        # Extract the message data (a byte string) from the DataBuffer.
        # Must be done on the same thread while the buffer is still valid.
        message = messageBuffer.get_data()[:]
        self.onMessageReceived.emit(messagingMgr, connection, message)
