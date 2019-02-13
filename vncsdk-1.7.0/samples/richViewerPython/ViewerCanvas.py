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
An interactive image display canvas.
"""

import Mappings

import vncsdk

from math import floor, fabs, copysign
from PySide import QtCore, QtGui


class ViewerCanvas(QtGui.QLabel):
    """
    An interactive image display canvas.

    This class is responsible for the image displayed to the user of the
    remote machine, as well as being responsible for handling any mouse
    events.

    This class can persist connections.
    """

    # event when a framebuffer can be associated with this window
    # emit (buffer, width, height)
    onFBAvailable = QtCore.Signal(object, int, int)

    # emit ()
    onAnnotatingChanged = QtCore.Signal()

    def __init__(self, mainWindow, sdkThread, callbacks):
        QtGui.QLabel.__init__(self)

        # Ability to convert from QT bindings to RealVNC Key Bindings
        self.mappings = Mappings.QtToRealVNCMappings()
        self.MOUSE_MAP = self.mappings.MOUSE_MAP
        self.KEY_MAP = self.mappings.KEY_MAP
        self.CTRL_MODIFIER = self.mappings.CTRL_MODIFIER

        # Mechanism to get/send requests to the RealVNC SDK
        self.sdkThread = sdkThread
        self.callbacks = callbacks
        self.mainWindow = mainWindow
        self.bufferRequestCount = 0
        self.isConnected = False
        self.canAnnotate = False
        self.isAnnotating = False

        # Store of the size of the server desktop and the ratio that we
        # currently show it at - allowing us to switch desktops keeping the same ratio
        self.trueServerSizeX = self.trueServerSizeY = 0
        self.ratio = 0.0  # A ratio of zero => scale to fit parent.

        # What the RealVNC SDK will populate & what we draw on screen...
        # keep a reference to these so they don't get cleaned up by mistake
        self.buffer = None
        self.registerCallbackListeners()

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)

    #
    # Helper functions used only by other functions in this class
    #

    def getViewer(self):
        return self.mainWindow.viewer

    def isViewerOfInterest(self, viewer):
        return self.mainWindow.viewer == viewer

    # Add functions to all the signals in the event Listener
    def registerCallbackListeners(self):
        # RealVNC SDK signals
        self.callbacks.onDisconnected.connect(self.viewerDisconnected)
        self.callbacks.onConnected.connect(self.viewerConnected)

        self.callbacks.onFBResized.connect(self.framebufferResized)
        self.callbacks.onFBUpdated.connect(self.framebufferUpdated)
        self.callbacks.onAnnotationAvailChanged.connect(self.enableAnnotations)

        # self signals
        self.onFBAvailable.connect(self.attachNewBuffer)

    # reverts the above function so that we don't keep a reference to this object by mistake
    def unregisterCallbackListeners(self):
        # RealVNC SDK signals
        self.callbacks.onDisconnected.disconnect(self.viewerDisconnected)
        self.callbacks.onConnected.disconnect(self.viewerConnected)

        self.callbacks.onFBResized.disconnect(self.framebufferResized)
        self.callbacks.onFBUpdated.disconnect(self.framebufferUpdated)
        self.callbacks.onAnnotationAvailChanged.disconnect(self.enableAnnotations)

        # Parent signals
        self.mainWindow.onAnnotationChanged.disconnect(self.annotatingStateChanged)

        # self signals
        self.onFBAvailable.disconnect(self.attachNewBuffer)

    # The cursor should be hidden while the cursor is in the viewer window so that we use the
    # server mouse cursor.  If we're annotating, then use another cursor to make it clear.
    def updateCursor(self):
        if self.isAnnotating:
            self.setCursor(QtCore.Qt.CrossCursor)
        elif self.isConnected:
            self.setCursor(QtCore.Qt.BlankCursor)
        else:
            self.unsetCursor()

    #
    # Functions that impact the behaviour of this class
    #

    def setIsAnnotating(self, isAnnotating):
        if not self.canAnnotate:
            isAnnotating = False

        if isAnnotating == self.isAnnotating:
            return

        self.isAnnotating = isAnnotating
        self.updateCursor()
        self.onAnnotatingChanged.emit()

    def getIsAnnotating(self):
        return self.isAnnotating

    def getCanAnnotate(self):
        return self.canAnnotate

    def setScale(self, ratio):
        self.ratio = ratio
        self.rescale()

    def rescale(self):
        ratio = self.ratio
        if not ratio:
            # Fill parent
            xRatio = float(self.parent().size().width())/self.trueServerSizeX
            yRatio = float(self.parent().size().height())/self.trueServerSizeY
            ratio = min(xRatio, yRatio)

        xSize = int(self.trueServerSizeX * ratio)
        ySize = int(self.trueServerSizeY * ratio)
        if self.bufferRequestCount == 0:
            self.sdkThread.resizeFrameBuffer(self.getViewer(),
                                             xSize, ySize,
                                             self.onFBAvailable)
        self.bufferRequestCount += 1

    #
    # Self callbacks
    #

    def attachNewBuffer(self, buffer, width, height):
        self.buffer = buffer
        self.image = QtGui.QImage(
            buffer,
            width, height,
            QtGui.QImage.Format_RGB32
        )
        self.setPixmap(QtGui.QPixmap.fromImage(self.image))
        self.resize(width, height)
        self.update()
        if self.bufferRequestCount > 1:
            self.bufferRequestCount = 0
            self.rescale()
        else:
            self.bufferRequestCount = 0

    #
    # Signal callbacks - caused by changes raised by the RealVNC SDK
    #

    ## Connection status events

    def viewerConnected(self, viewer, annotationColor):
        if not self.isViewerOfInterest(viewer):
            return
        self.isConnected = True

    def viewerDisconnected(self, viewer, message, shouldAlert, canReconnect):
        if not self.isViewerOfInterest(viewer):
            return
        self.isConnected = False
        self.buffer = None
        self.setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage()))
        self.resize(0, 0)
        self.update()

    ## FrameBuffer status events

    def framebufferResized(self, viewer, width, height):
        if not self.isViewerOfInterest(viewer):
            return
        self.trueServerSizeX = width
        self.trueServerSizeY = height
        self.rescale()

    def framebufferUpdated(self, viewer, x, y, w, h):
        if not self.isViewerOfInterest(viewer):
            return

        if self.buffer is None:
            return

        self.image = QtGui.QImage(
            self.buffer,
            self.size().width(), self.size().height(),
            QtGui.QImage.Format_RGB32
        )
        self.setPixmap(QtGui.QPixmap.fromImage(self.image))

        # There seems to be an issue with this running on the latest
        # version of Qt on Mac, so we use the above as a workaround
        #self.update(x,y,w,h)

    ## Annotations events

    def enableAnnotations(self, annotationMgr, enabled):
        if self.getViewer() is None or self.getViewer().get_annotation_manager() != annotationMgr:
            return
        self.canAnnotate = enabled
        if not enabled:
            self.setIsAnnotating(False)

    ## Events raised by Qt

    # See https://srinikom.github.io/pyside-docs/PySide/QtGui/QWidget.html
    # for when these events are raised.

    # Required for the ability to send tabs to the server rather than change widget.
    def focusNextPrevChild(self, next):
        return False

    # Allows the CtrlKey (and Ctrl only) to send annotations also.
    def keyPressEvent(self, e):
        if e.count() == 1 and (e.modifiers() & self.CTRL_MODIFIER) and not self.isAnnotating:
            self.setIsAnnotating(True)
        else:
            self.setIsAnnotating(False)

        keycode = e.key()
        sdkKeys = self.mappings.translateKeys(keycode, e.text(), e.modifiers())
        for key in sdkKeys:
            self.sdkThread.sendKeyPress(self.getViewer(), key, keycode)

    def keyReleaseEvent(self, e):
        self.setIsAnnotating(False)
        self.sdkThread.releaseKey(self.getViewer(), e.key())

    # We will allow clicking and dragging to have the feature where we
    # maintain the control of the mouse as this is Qt default.  It means that
    # people may attempt to drag or annotate outside the visible area which
    # will be rejected by the host; but on re-entering the window re-allowed.
    # Thus a jump will be seen.  It will also allow dragging in areas that
    # can't be seen on the viewer, but do exist on the server; e.g. an area
    # that's cut off by the scroll bars.  This will make dragging an item
    # from one end of the monitors to the other much easier.
    def mouseEvent(self, e):
        raw_buttons = int(e.buttons())
        px = e.x()
        py = e.y()

        mouse_mask = set(v for k, v in self.MOUSE_MAP.items() if k & raw_buttons)
        if not self.isAnnotating:
            self.sdkThread.sendPointerEvent(self.getViewer(), px, py, mouse_mask)

        # Always move the annotation pointer around so that
        # when we start the first line doesn't start somewhere unexpected
        # ie either (0,0) or last annotation stop
        penDown = self.isAnnotating and (e.buttons() & QtCore.Qt.LeftButton)
        self.sdkThread.sendAnnotationEvent(self.getViewer(), px, py, penDown)

    mouseMoveEvent = mouseEvent
    mousePressEvent = mouseEvent
    mouseReleaseEvent = mouseEvent

    # https://srinikom.github.io/pyside-docs/PySide/QtGui/QWheelEvent.html#PySide.QtGui.PySide.QtGui.QWheelEvent.delta
    # In Summary:
    # Most mouse types have steps of 15 degrees.
    # Qt's units are in 8th's of a degree for delta.
    # The SDK's units are 'ticks'.
    # We must keep the delta as we can't guarantee the rate of these events.

    wheelStepsRemaining = 0.0

    def wheelEvent(self, e):
        degrees = e.delta() / 8
        steps = self.wheelStepsRemaining + degrees / 15

        stepsToSend = int(copysign(floor(fabs(steps)), steps))
        self.wheelStepsRemaining = steps - stepsToSend
        axis = vncsdk.Viewer.MouseWheel.MOUSE_WHEEL_VERTICAL
        self.sdkThread.sendScrollEvent(self.getViewer(), stepsToSend, axis)

    # Ensure that we don't keep sending key presses when we're no longer in focus
    def focusOutEvent(self, e):
        self.sdkThread.releaseAllKeys(self.getViewer())
