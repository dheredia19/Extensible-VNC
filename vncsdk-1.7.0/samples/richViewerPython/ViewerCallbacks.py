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

from PySide import QtCore


class ViewerCallbacks(vncsdk.Viewer.ConnectionCallback,
                      vncsdk.Viewer.FramebufferCallback,
                      vncsdk.Viewer.ServerEventCallback,
                      vncsdk.Viewer.AuthenticationCallback,
                      vncsdk.Viewer.PeerVerificationCallback,
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

    # notification of connection status
    # emit(viewer)
    onConnecting = QtCore.Signal(object)
    # must use an object here since python converts it into a signed int otherwise
    # emit(viewer, annotationColor)
    onConnected = QtCore.Signal(object, object)

    # emit(viewer, reason, alert user hint, can reconnect)
    onDisconnected = QtCore.Signal(object, str, bool, bool)

    # notification that the window should be resized
    # emit(viewer, width, height)
    onFBResized = QtCore.Signal(object, int, int)

    # notification that the buffer has been changed and should be redrawn
    # emit(viewer, x, y, w, h)
    onFBUpdated = QtCore.Signal(object, int, int, int, int)

    # emit(viewer, new clipboard text)
    onClipBoardTextChanged = QtCore.Signal(object, str)

    # emit(viewer, new server name)
    onServerNameChanged = QtCore.Signal(object, str)

    # emit(viewer, needUsername, needPassword)
    onCredentialsRequired = QtCore.Signal(object, bool, bool)
    onCredentialsRequiredCanceled = QtCore.Signal(object)

    # emit(viewer, hex_fingerprint, catchphrase_fingerprint, server_rsa_public)
    onPeerVerification = QtCore.Signal(object, str, str, object)

    # emit(viewer)
    onPeerVerificationCancel = QtCore.Signal(object)

    # emit(annotationMgr, availability)
    onAnnotationAvailChanged = QtCore.Signal(object, bool)

    # emit(messagingMgr, connection, message)
    onMessageReceived = QtCore.Signal(object, object, object)

    # the viewer is the item that we will be listening to events from
    def __init__(self):
        QtCore.QObject.__init__(self)
        vncsdk.Viewer.ConnectionCallback.__init__(self)
        vncsdk.Viewer.FramebufferCallback.__init__(self)
        vncsdk.Viewer.ServerEventCallback.__init__(self)
        vncsdk.Viewer.AuthenticationCallback.__init__(self)
        vncsdk.Viewer.PeerVerificationCallback.__init__(self)
        vncsdk.AnnotationManager.Callback.__init__(self)
        vncsdk.MessagingManager.Callback.__init__(self)
        self.attached = False

    def attachViewer(self, viewer):
        viewer.set_connection_callback(self)
        viewer.set_framebuffer_callback(self)
        viewer.set_server_event_callback(self)
        viewer.set_authentication_callback(self)
        viewer.set_peer_verification_callback(self)
        viewer.get_annotation_manager().set_callback(self)
        if ConnectionDetail.canUseMessaging():
            viewer.get_messaging_manager().set_callback(self)
        self.attached = True

    def detachViewer(self, viewer):
        viewer.set_connection_callback(None)
        viewer.set_framebuffer_callback(None)
        viewer.set_server_event_callback(None)
        viewer.set_authentication_callback(None)
        viewer.set_peer_verification_callback(None)
        viewer.get_annotation_manager().set_callback(None)
        if ConnectionDetail.canUseMessaging():
            viewer.get_messaging_manager().set_callback(None)
        self.attached = False

    #
    # ConnectionCallback functions
    #

    def connecting(self, viewer):
        self.onConnecting.emit(viewer)

    def connected(self, viewer):
        mgr = viewer.get_annotation_manager()
        annoColor = mgr.get_pen_color()
        self.onConnected.emit(viewer, annoColor)

    def disconnected(self, viewer, reason, flags):
        canReconnect = vncsdk.Viewer.DisconnectFlags.CAN_RECONNECT in flags
        alertUserHint = vncsdk.Viewer.DisconnectFlags.ALERT_USER in flags
        self.onDisconnected.emit(viewer, reason, alertUserHint, canReconnect)

    #
    # FramebufferCallback functions
    #

    def viewer_fb_updated(self, viewer, x, y, w, h):
        self.onFBUpdated.emit(viewer, x, y, w, h)

    def server_fb_size_changed(self, viewer, w, h):
        self.onFBResized.emit(viewer, w, h)

    #
    # ServerEventCallback functions
    #

    def server_clipboard_text_changed(self, viewer, text):
        self.onClipBoardTextChanged.emit(viewer, text)

    def server_friendly_name_changed(self, viewer, name):
        self.onServerNameChanged.emit(viewer, name)

    #
    # PeerVerificationCallback functions
    #

    def verify_peer(self, viewer, hex_fingerprint, catchphrase_fingerprint, server_rsa_public):
        self.onPeerVerification.emit(viewer, hex_fingerprint, catchphrase_fingerprint, server_rsa_public)

    def cancel_peer_verification(self, viewer):
        self.onPeerVerificationCancel.emit(viewer)

    #
    # AuthenticationCallback functions
    #

    def request_user_credentials(self, viewer, needUser, needPassword):
        self.onCredentialsRequired.emit(viewer, needUser, needPassword)

    def cancel_user_credentials_request(self, viewer):
        self.onCredentialsRequiredCanceled.emit(viewer)

    #
    # AnnotationManager.Callback functions
    #

    def availability_changed(self, annotationMgr, availability):
        self.onAnnotationAvailChanged.emit(annotationMgr, availability)

    #
    # MessagingManager.Callback functions
    #

    def message_received(self, messagingMgr, connection, messageBuffer):
        # Extract the message data (a byte string) from the DataBuffer.
        # Must be done on the same thread while the buffer is still valid.
        message = messageBuffer.get_data()[:]
        self.onMessageReceived.emit(messagingMgr, connection, message)
