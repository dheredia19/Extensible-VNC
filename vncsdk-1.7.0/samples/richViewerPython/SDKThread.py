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
A mechanism for calling SDK methods from other threads.
"""

import threading
import traceback

import vncsdk
import ConnectionDetail

from PySide import QtCore


class SDKThread(threading.Thread, QtCore.QObject):
    """
    A wrapper around all things relating to the SDK that need to be run on
    another thread.
    """

    # Used for terminal errors - hence the full stack trace
    # emit(traceback details)
    onFatalExceptionCaught = QtCore.Signal(str)

    # Used for exceptions that aren't fatal;
    # emit(VncException)
    onNonFatalExceptionCaught = QtCore.Signal(object)

    # emit(buffer, width, height)
    onNewFBAvailable = QtCore.Signal(object, int, int)

    # emit()
    onConnectionFailure = QtCore.Signal()

    def __init__(self):
        QtCore.QObject.__init__(self)
        threading.Thread.__init__(self)

        self.readyEvent = threading.Event()
        self.available = True
        self.terminateOnDisconnect = False
        self.viewers = set()
        self.terminateOnLastDestroy = False

    def start(self):
        threading.Thread.start(self)
        # Wait until the SDK event loop is running/failed before returning.
        self.readyEvent.wait()

    def run(self):
        try:
            try:
                vncsdk.Logger.create_stderr_logger()
                vncsdk.DataStore.create_file_store("dataStore.txt")
                vncsdk.init()
                if ConnectionDetail.MESSAGING_ADDON_CODE is not None:
                    vncsdk.enable_add_on(ConnectionDetail.MESSAGING_ADDON_CODE)
            finally:
                self.readyEvent.set()

            vncsdk.EventLoop.run()
        except Exception:
            exception = traceback.format_exc()
            self.onFatalExceptionCaught.emit("Exception: " + exception)
        finally:
            vncsdk.shutdown()

        self.available = False

    #
    # Called strictly on the SDK thread
    #

    # Don't call functions directly with vncsdk.EventLoop.run_on_loop
    # as exceptions will be just logged and nothing presented to the user.
    # This function wraps all SDK functions and passes exceptions on if required
    def _processOnSDKThread(self, callable, args=()):
        try:
            callable(*args)
        # rethrowing the exception will result in it getting logged
        except vncsdk.VncException as e:
            self.onNonFatalExceptionCaught.emit(e)
            # Trigger self.onConnectionFailure if this was for vncConnect().
            if isinstance(callable, _ConnectWrapper):
                self.onConnectionFailure.emit()
            raise e
        except Exception as e:
            exception = traceback.format_exc()
            self.onFatalExceptionCaught.emit("Exception: " + exception)
            raise e

    def _recreateFrameBuffer(self, viewer, width, height, signal):
        buffer = bytearray(width * height * 4)
        viewer.set_viewer_fb(buffer,
                             vncsdk.PixelFormat.rgb888(),
                             width, height, width)
        self.buffer = buffer
        signal.emit(buffer, width, height)

    def _performFinalCleanup(self):
        self.terminateOnLastDestroy = True

        for viewer in self.viewers:
            self._destroyViewer(viewer)

        vncsdk.EventLoop.stop()

    def _createViewer(self, signal):
        viewer = vncsdk.Viewer()
        self.viewers.add(viewer)
        signal.emit(viewer)

    def _destroyViewer(self, viewer, signal=None):
        viewer.set_connection_callback(None)
        viewer.disconnect()
        viewer.destroy()
        self.viewers.remove(viewer)
        if signal is not None:
            signal.emit()

        if self.terminateOnLastDestroy:
            vncsdk.EventLoop.stop()

    def _moveAnnotationPen(self, viewer, x, y, penDown):
        if viewer.get_annotation_manager().is_available():
            viewer.get_annotation_manager().move_pen_to(x, y, penDown)

    def _sendAnnotationPreferences(self, viewer, duration, fadeDuration, size, color):
        mgr = viewer.get_annotation_manager()
        mgr.set_fade_duration(fadeDuration)
        mgr.set_persist_duration(duration)
        mgr.set_pen_size(size)
        mgr.set_pen_color(color)

    def _clearAnnotations(self, viewer, fade):
        mgr = viewer.get_annotation_manager()
        mgr.clear_all(fade)

    def _sendPictureQualityPreference(self, viewer, quality):
        viewer.set_picture_quality(quality)

    def _setEncryptionLevel(self, viewer, encryptionLevel):
        viewer.set_encryption_level(encryptionLevel)

    def _sendMessage(self, viewer, message):
        mgr = viewer.get_messaging_manager()
        message = bytearray(message)
        mgr.send_message(message, None)

    #
    # Functions that get this thread to call various other SDK commands.
    #
    # Expected to be called from other threads, but safe to be called by the
    # SDK thread.
    #

    def createViewer(self, signal):
        if not self.available:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._createViewer, (signal, )))

    # Once this has been called, take care never to use the viewer again.
    # Any calls to it will be invalid, raising a DestroyedObjectException.
    def destroyViewer(self, viewer, signal=None):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._destroyViewer, (viewer, signal)))

    def terminateThread(self):
        if not self.available:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._performFinalCleanup,))

    def resizeFrameBuffer(self, viewer, width, height, signal):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._recreateFrameBuffer, (viewer, width, height, signal)))

    def vncConnect(self, viewer, connectionDetail):
        if not self.available or viewer is None:
            return
        handler = viewer.get_connection_handler()
        connectWrapper = _ConnectWrapper(connectionDetail.connect)
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (connectWrapper, (handler,)))

    def vncDisconnect(self, viewer):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.disconnect, ))

    def sendKeyPress(self, viewer, keysym, keycode):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.send_key_down, (keysym, keycode)))

    def releaseKey(self, viewer, keycode):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.send_key_up, (keycode,)))

    def releaseAllKeys(self, viewer):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.release_all_keys, ))

    def sendPointerEvent(self, viewer, x, y, button_mask):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.send_pointer_event, (x, y, button_mask, False)))

    def sendScrollEvent(self, viewer, delta, axis):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.send_scroll_event, (delta, axis)))

    def sendCredentials(self, viewer, username, password):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.send_authentication_response, (True, username, password)))

    def sendPeerVerify(self, viewer, verified):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.send_peer_verification_response, (verified, )))

    def cancelSendCredentials(self, viewer):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (viewer.send_authentication_response, (False, None, None)))

    def sendAnnotationEvent(self, viewer, x, y, penDown):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._moveAnnotationPen, (viewer, x, y, penDown)))

    def sendAnnotationPreferences(self, viewer, duration, fadeDuration, size, color):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._sendAnnotationPreferences, (viewer, duration, fadeDuration, size, color)))

    def clearAnnotations(self, viewer, fade):
        if not self.available or viewer is None:
            return
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._clearAnnotations, (viewer, fade)))

    def sendPictureQualityPreference(self, viewer, qualityName):
        if not self.available or viewer is None:
            return
        quality = getattr(vncsdk.Viewer.PictureQuality, qualityName)
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._sendPictureQualityPreference, (viewer, quality)))

    def setEncryptionLevel(self, viewer, encryptionLevel):
        if not self.available or viewer is None:
            return
        level = getattr(vncsdk.Viewer.EncryptionLevel, encryptionLevel)
        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._setEncryptionLevel, (viewer, level)))

    def sendMessage(self, viewer, message):
        if not self.available or viewer is None:
            return

        if not isinstance(message, type(b'')):
            raise TypeError('Expected bytes, got %r' % (type(message),))

        vncsdk.EventLoop.run_on_loop(self._processOnSDKThread, (self._sendMessage, (viewer, message)))


class _ConnectWrapper(object):
    """
    A wrapper for a callable that indicates it is a connection attempt,
    and that it raising an exception would indicate connection failure.
    """
    def __init__(self, callable):
        self.callable = callable

    def __call__(self, *args, **kwargs):
        return self.callable(*args, **kwargs)
