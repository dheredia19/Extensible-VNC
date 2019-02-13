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
The main application window.

Note this sample app demonstrates messaging over the custom data channel.

Messages relating to the list of displays currently attached to the Server
computer are received by the Viewer in JSON-RPC 2.0 format, with an app-specific
prefix. For more information, see www.jsonrpc.org/specification.
"""

from PySide import QtCore, QtGui

from ConnectDialog import ConnectDialog
from CredentialDialog import CredentialDialog
from PreferencesDialog import PreferencesDialog
from PeerVerificationDialog import PeerVerificationDialog
from ViewerCanvas import ViewerCanvas
from Mappings import ARGBToQtColor
from RPCFunctions import RPCFunctions


class MainWindow(QtGui.QMainWindow):
    """
    The main application window.

    All methods are run from the main thread, which is ensured by the
    QtCore.Signal class.

    This window can't use shortcuts with the actions since, for example, a
    Ctrl-C for connect would result in the connect dialog opening when trying
    to send a clipboard copy request.

    Any methods that get a viewer callback should check to make sure that the
    viewer provided in the callback match the viewer that we're trying to process
    In this example, we're only ever working with a single viewer; so it's a little
    redundant; but if the  application were updated to allow multiple windows to
    be created for multiple connections then it would be required.
    """

    # Some values for strings / sizes etc
    DEFAULT_WINDOW_TITLE = "richViewerPython"
    DEFAULT_SIZE_X = 800
    DEFAULT_SIZE_Y = 600
    ICON_PIXMAP_SIZE = 24

    IMAGE_APPLICATION = "icons/application.png"
    IMAGE_SCALE = "icons/scale.png"
    IMAGE_ANNOTATE = "icons/annotate.png"

    MESSAGE_DISCONNECTED = "Disconnected"
    MESSAGE_CONNECTING = "Connecting"
    MESSAGE_VERIFY_PEER = "Awaiting peer verification"
    MESSAGE_AWAITING_CREDENTIALS = "Awaiting credentials"
    MESSAGE_CONNECTED_CONTROLLING = "Connected - Controlling"
    MESSAGE_CONNECTED_ANNOTATING = "Connected - Annotating"

    DEFAULT_COLORS = ((0xa048D1CC, "&Cyan"),
                      (0xa0FF0000, "&Red"),
                      (0xa0228B22, "&Green"),
                      (0xa09400D3, "&Purple"),
                      (0xa0FFA500, "&Orange"),
                      (0xa04169E1, "&Blue"),
                      (0xa0FF69B4, "P&ink"),
                      (0xa0FFD700, "Go&ld"),
                      (0xc0FFFF00, "Bright &yellow"),
                      (0xc0ADFF2F, "Bright gr&een"),
                      )

    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2

    # Event raised when a viewer can be associated with this window.
    # emit (viewer)
    onViewerAvailable = QtCore.Signal(object)
    onViewerDestroyed = QtCore.Signal()

    def __init__(self, sdkThread, callbacks):
        QtGui.QMainWindow.__init__(self)

        self.callbacks = callbacks

        # Mechanism to get/send requests to the RealVNC SDK
        self.sdkThread = sdkThread
        self.connectionStatus = self.DISCONNECTED
        self.viewer = None
        self.shutdownOnViewerDestroyed = False
        self.canAnnotate = False
        self.serverAnnotationColor = 0xFF000000
        self.viewerAnnotationColor = None
        self.remoteCallId = 0
        self.displays = []
        self.rpcFunctions = None

        # We can't create a viewer directly, so we keep track of how many
        # we've asked for, vs. how many we've destroyed.
        self.viewerCount = 0

        # When connecting to a new target, we have to make requests to the SDK thread
        # to recreate / destroy the viewer we're working with.  To handle the fact that
        # we can't just create a new viewer we must create a cache of the next connection
        # we would like to make so that once a new viewer has been created we can send the
        # request to connect.
        self.lastConnectTarget = self.nextConnectTarget = None

        # Prepare the additional GUI parts that we will use for this window
        self.createMenuBar()
        self.createToolBar()
        self.createStatusBar()
        self.createDialogs()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.canvas = ViewerCanvas(self, sdkThread, callbacks)
        self.setFocusProxy(self.canvas)
        self.scrollArea = QtGui.QScrollArea()
        self.scrollArea.setWidget(self.canvas)
        self.scrollArea.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self.setCentralWidget(self.scrollArea)

        # With everything setup, we can now register our listeners to all
        # the events that we're interested in from all sources
        self.registerCallbackListeners()

        # Set up the GUI of this window
        self.updateAnnotationButtons()
        self.statusBar().showMessage(self.MESSAGE_DISCONNECTED)
        self.updateScaleIcon()
        self.updateDisplays([])
        self.serverNameChanged(self.viewer, None)
        self.setWindowIcon(QtGui.QIcon(self.IMAGE_APPLICATION))

        # Make the window a sane size and put it in the middle of the screen
        desktopWidget = QtGui.QDesktopWidget()
        screen = desktopWidget.screen()
        self.resize(self.DEFAULT_SIZE_X, self.DEFAULT_SIZE_Y)
        self.move((screen.availableGeometry().width() - self.DEFAULT_SIZE_X)/2,
                  (screen.availableGeometry().height() - self.DEFAULT_SIZE_Y)/2)

        # And we're ready!
        self.setVisible(True)

    @property
    def annotationColor(self):
        if self.viewerAnnotationColor is None:
            return self.serverAnnotationColor
        else:
            return self.viewerAnnotationColor

    #
    # Helper functions used only by other functions in this class
    #

    # Add functions to all the signals in the event Listener
    def registerCallbackListeners(self):
        # Signal for connection failure due to an exception.
        self.sdkThread.onConnectionFailure.connect(self.cancelConnection)

        # RealVNC SDK signals
        self.callbacks.onConnecting.connect(self.viewerConnecting)
        self.callbacks.onConnected.connect(self.viewerConnected)
        self.callbacks.onDisconnected.connect(self.viewerDisconnected)
        self.callbacks.onServerNameChanged.connect(self.serverNameChanged)

        self.callbacks.onPeerVerification.connect(self.newVerifyPeerDialog)
        self.callbacks.onPeerVerificationCancel.connect(self.closeVerifyPeerDialog)
        self.callbacks.onCredentialsRequired.connect(self.newCredentialDialog)
        self.callbacks.onCredentialsRequiredCanceled.connect(self.closeCredentialDialog)
        self.callbacks.onAnnotationAvailChanged.connect(self.enableAnnotations)

        # Window signals
        self.connectDialog.onNewConnectionRequest.connect(self.makeNewConnection)
        self.connectDialog.onReject.connect(self.cancelConnection)
        self.preferencesDialog.onAnnotationPreferenceChanged.connect(self.sendAnnotationsPreferences)
        self.preferencesDialog.onAnnotationPreferenceChanged.connect(self.updateAnnotationButtons)
        self.preferencesDialog.onPictureQualityPreferenceChanged.connect(self.sendPictureQualityPreference)
        self.canvas.onAnnotatingChanged.connect(self.updateAnnotationButtonsAndMessage)
        self.onViewerAvailable.connect(self.viewerCreated)
        self.onViewerDestroyed.connect(self.viewerDestroyed)

    # reverts the above function so that we don't keep a reference to this object by mistake
    def unregisterCallbackListeners(self):
        # Signal for connection failure due to an exception.
        self.sdkThread.onConnectionFailure.disconnect(self.cancelConnection)

        # RealVNC SDK signals
        self.callbacks.onConnecting.disconnect(self.viewerConnecting)
        self.callbacks.onConnected.disconnect(self.viewerConnected)
        self.callbacks.onDisconnected.disconnect(self.viewerDisconnected)
        self.callbacks.onServerNameChanged.disconnect(self.serverNameChanged)

        self.callbacks.onPeerVerification.disconnect(self.newVerifyPeerDialog)
        self.callbacks.onPeerVerificationCancel.disconnect(self.closeVerifyPeerDialog)
        self.callbacks.onCredentialsRequired.disconnect(self.newCredentialDialog)
        self.callbacks.onCredentialsRequiredCanceled.disconnect(self.closeCredentialDialog)
        self.callbacks.onAnnotationAvailChanged.disconnect(self.enableAnnotations)

        # Window signals
        self.connectDialog.onNewConnectionRequest.disconnect(self.makeNewConnection)
        self.connectDialog.onReject.disconnect(self.cancelConnection)
        self.preferencesDialog.onAnnotationPreferenceChanged.disconnect(self.sendAnnotationsPreferences)
        self.preferencesDialog.onAnnotationPreferenceChanged.disconnect(self.updateAnnotationButtons)
        self.preferencesDialog.onPictureQualityPreferenceChanged.disconnect(self.sendPictureQualityPreference)
        self.canvas.onAnnotatingChanged.disconnect(self.updateAnnotationButtonsAndMessage)
        self.onViewerAvailable.disconnect(self.viewerCreated)
        self.onViewerDestroyed.disconnect(self.viewerDestroyed)

    # Create references to all the windows that this main window might try to open
    def createDialogs(self):
        self.connectDialog = ConnectDialog()
        self.credentialDialog = None
        self.peerVerifyDialog = None
        self.preferencesDialog = PreferencesDialog()

    # Create the menu bar at the top of the window
    def createMenuBar(self):
        self.fileMenu = self.menuBar().addMenu('&File')

        self.connectAction = QtGui.QAction('&Connect', self)
        self.connectAction.setStatusTip('Connect to VNC Server')
        self.connectAction.triggered.connect(self.connectRequested)
        self.fileMenu.addAction(self.connectAction)

        self.disconnectAction = QtGui.QAction('&Disconnect', self)
        self.disconnectAction.setStatusTip('Disconnect from VNC Server')
        self.disconnectAction.triggered.connect(self.disconnectRequested)
        self.disconnectAction.setEnabled(False)
        self.fileMenu.addAction(self.disconnectAction)

        preferencesAction = QtGui.QAction('&Preferences', self)
        preferencesAction.setStatusTip('Edit preferences')
        preferencesAction.triggered.connect(self.preferencesRequested)
        self.fileMenu.addAction(preferencesAction)

        self.fileMenu.addSeparator()

        exitAction = QtGui.QAction('E&xit', self)
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.closeRequested)
        self.fileMenu.addAction(exitAction)

    def getColorIcon(self, color):
        pixmap = QtGui.QPixmap(self.ICON_PIXMAP_SIZE, self.ICON_PIXMAP_SIZE)
        pixmap.fill(ARGBToQtColor(color))
        return QtGui.QIcon(pixmap)

    def createToolBar(self):
        self.toolbar = QtGui.QToolBar('Toolbar')
        self.toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.addToolBar(self.toolbar)

        ## Scale

        scaleMenu = QtGui.QMenu("Scale")
        scaleActionGroup = QtGui.QActionGroup(scaleMenu)
        scaleActionGroup.setExclusive(True)
        scaleAction = QtGui.QAction('Scale to &fit', self)
        scaleAction.setStatusTip('Scale to fit')
        scaleAction.triggered.connect(lambda: self.setScale(0.0))
        scaleAction.setCheckable(True)
        scaleAction.setChecked(True)
        scaleActionGroup.addAction(scaleAction)
        scaleMenu.addAction(scaleAction)
        for i in range(1, 5):
            scaleAction = QtGui.QAction('1:&' + str(i), self)
            scaleAction.setStatusTip('Scale 1:' + str(i))
            scaleAction.setCheckable(True)
            scaleAction.triggered.connect(lambda d=i: self.setScale(1.0/d))
            scaleActionGroup.addAction(scaleAction)
            scaleMenu.addAction(scaleAction)

        self.scaleButton = QtGui.QToolButton()
        showDropdownAction = QtGui.QAction(self)
        showDropdownAction.triggered.connect(self.scaleButton.showMenu)
        self.scaleButton.setDefaultAction(showDropdownAction)

        self.scaleButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.scaleButton.setText("&Scale")
        self.scaleButton.setIcon(QtGui.QIcon(self.IMAGE_SCALE))
        self.scaleButton.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        self.scaleButton.setMenu(scaleMenu)
        self.toolbar.addWidget(self.scaleButton)

        ## Annotation toggle

        self.annotateToggleButton = QtGui.QToolButton()
        self.annotateToggleButton.setCheckable(True)
        self.annotateToggleAction = QtGui.QAction(self)
        self.annotateToggleAction.setIcon(QtGui.QIcon(self.IMAGE_ANNOTATE))
        self.annotateToggleAction.setIconText("&Annotate")
        self.annotateToggleAction.triggered.connect(self.toggleIsAnnotating)
        self.annotateToggleAction.setCheckable(True)

        self.annotateToggleButton.setDefaultAction(self.annotateToggleAction)
        self.annotateToggleButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.toolbar.addWidget(self.annotateToggleButton)

        ## Annotation color

        annotationColorMenu = QtGui.QMenu("Color")
        annotationColorGroup = QtGui.QActionGroup(annotationColorMenu)
        annotationColorGroup.setExclusive(True)
        colorIcon = self.getColorIcon(self.serverAnnotationColor)
        self.serverColorAction = QtGui.QAction(colorIcon, "&Server-suggested", self)
        self.serverColorAction.triggered.connect(lambda: self.setAnnotationColor(None))
        self.serverColorAction.setCheckable(True)
        self.serverColorAction.setChecked(True)
        self.serverColorAction.setStatusTip("Annotation color: " + self.serverColorAction.iconText())
        annotationColorGroup.addAction(self.serverColorAction)
        annotationColorMenu.addAction(self.serverColorAction)
        annotationColorMenu.addSeparator()
        for colorData in self.DEFAULT_COLORS:
            colorAction = QtGui.QAction(self.getColorIcon(colorData[0]), colorData[1], self)
            colorAction.triggered.connect(lambda d=colorData[0]: self.setAnnotationColor(d))
            colorAction.setCheckable(True)
            colorAction.setStatusTip("Annotation color: " + colorAction.iconText())
            annotationColorGroup.addAction(colorAction)
            annotationColorMenu.addAction(colorAction)

        self.annotationColorButton = QtGui.QToolButton()
        showDropdownAction = QtGui.QAction(self)
        showDropdownAction.triggered.connect(self.annotationColorButton.showMenu)
        self.annotationColorButton.setDefaultAction(showDropdownAction)

        self.annotationColorButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.annotationColorButton.setText("&Color")
        self.annotationColorButton.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        self.annotationColorButton.setMenu(annotationColorMenu)
        self.toolbar.addWidget(self.annotationColorButton)

        ## Display selector

        self.displayListLabel = QtGui.QLabel("&Display: ")
        self.toolbar.addWidget(self.displayListLabel)

        self.displayList = QtGui.QComboBox()
        self.displayList.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.displayList.currentIndexChanged.connect(self.setDisplay)
        self.displayListLabel.setBuddy(self.displayList)
        self.toolbar.addWidget(self.displayList)

    def createStatusBar(self):
        self.setStatusBar(QtGui.QStatusBar())
        self.statusBar().showMessage(self.MESSAGE_DISCONNECTED)

    # Cleans up all the viewers that were ever associated with this
    def shutdown(self):
        self.connectDialog.close()
        self.preferencesDialog.close()
        self.closeCredentialDialog(self.viewer)
        self.closeVerifyPeerDialog(self.viewer)

        if self.viewer is not None:
            self.shutdownOnViewerDestroyed = True
            self.sdkThread.destroyViewer(self.viewer, self.onViewerDestroyed)
            self.viewer = None

        return (self.viewerCount == 0)

    def toggleIsAnnotating(self):
        self.canvas.setIsAnnotating(not self.canvas.getIsAnnotating())

    def updateAnnotationButtons(self):
        self.annotationColorButton.setIcon(self.getColorIcon(self.annotationColor))
        self.annotationColorButton.setEnabled(self.canAnnotate)
        self.annotateToggleButton.setEnabled(self.canAnnotate)
        self.annotateToggleButton.setChecked(self.canvas.getIsAnnotating())

    def updateAnnotationButtonsAndMessage(self):
        self.updateAnnotationButtons()

        if self.connectionStatus == self.CONNECTED:
            if self.canvas.getIsAnnotating():
                self.statusBar().showMessage(self.MESSAGE_CONNECTED_ANNOTATING)
            else:
                self.statusBar().showMessage(self.MESSAGE_CONNECTED_CONTROLLING)

    def updateScaleIcon(self):
        if self.connectionStatus == self.CONNECTED:
            self.scaleButton.setEnabled(True)
        else:
            self.scaleButton.setEnabled(False)

    #
    #  Misc
    #

    def updateDisplays(self, displays):
        if self.connectionStatus != self.CONNECTED:
            displays = []

        # The display selector will only be enabled if a messaging add-on code
        # has been provided (see `canUseMessaging()`) and if the server has
        # responded with a non-empty list of displays.
        if displays:
            self.displayListLabel.setEnabled(True)
            self.displayList.setEnabled(True)
            if displays != self.displays:
                currentDisplay = self.displayList.currentText()
                self.displayList.clear()
                self.displayList.addItem('All displays')
                for display in displays:
                    self.displayList.addItem(display)
                if currentDisplay in displays:
                    self.displayList.setCurrentIndex(
                        displays.index(currentDisplay))
        else:
            self.displayListLabel.setEnabled(False)
            self.displayList.setEnabled(False)
            self.displayList.clear()

        self.displays = displays

    # There's a chunk at the top of the window we don't want to draw over
    def centerChildWindow(self, window):
        mySize = self.size()
        otherSize = window.size()
        otherPositionX = self.pos().x() + mySize.width()/2 - otherSize.width()/2
        otherPositionY = self.pos().y() + mySize.height()/2 - otherSize.height()/2
        window.move(otherPositionX, otherPositionY)

    #
    # Self callbacks
    #

    def viewerCreated(self, viewer):
        if self.viewer:
            self.sdkThread.destroyViewer(self.viewer)

        self.viewer = viewer
        self.callbacks.attachViewer(viewer)

        if self.nextConnectTarget is not None:
            self.makeNewConnection(self.nextConnectTarget)

    def viewerDestroyed(self):
        self.viewerCount -= 1
        if self.viewerCount == 0 and self.shutdownOnViewerDestroyed:
            self.close()

    #
    # Menu/Toolbar callbacks
    #

    def closeRequested(self):
        if self.shutdown():
            self.close()

    def connectRequested(self):
        self.onConnectionStart()
        self.centerChildWindow(self.connectDialog)
        self.connectDialog.setVisible(True)
        self.connectDialog.activateWindow()
        self.connectDialog.raise_()

    def disconnectRequested(self):
        if self.viewer is not None:
            self.sdkThread.vncDisconnect(self.viewer)

    def preferencesRequested(self):
        self.centerChildWindow(self.preferencesDialog)
        self.preferencesDialog.setVisible(True)
        self.preferencesDialog.activateWindow()
        self.preferencesDialog.raise_()

    def setAnnotationColor(self, color):
        self.viewerAnnotationColor = color
        self.updateAnnotationButtons()
        self.sendAnnotationsPreferences()

    def setScale(self, ratio):
        self.canvas.setScale(ratio)

    def setDisplay(self, listItemIndex):
        if listItemIndex == -1:
            displayIndex = -1
        else:
            displayIndex = listItemIndex - 1
        if self.rpcFunctions is not None:
            self.rpcFunctions.sendDisplayChange(displayIndex)

    #
    # Signal callbacks - caused by other windows
    #

    def cancelConnection(self):
        self.onConnectionCancelled()

    def makeNewConnection(self, details):
        if self.connectionStatus != self.DISCONNECTED:
            self.nextConnectTarget = details
            self.sdkThread.vncDisconnect(self.viewer)
            return

        if self.viewer is None:
            self.sdkThread.createViewer(self.onViewerAvailable)
            self.viewerCount += 1
            self.lastConnectTarget = self.nextConnectTarget = details
            return

        if self.lastConnectTarget != details:
            self.sdkThread.destroyViewer(self.viewer, self.onViewerDestroyed)
            self.viewer = None
            self.sdkThread.createViewer(self.onViewerAvailable)
            self.viewerCount += 1
            self.lastConnectTarget = self.nextConnectTarget = details
            return

        self.nextConnectTarget = None
        self.lastConnectTarget = details
        self.sdkThread.setEncryptionLevel(self.viewer, self.preferencesDialog.encryptionLevel)
        self.sdkThread.vncConnect(self.viewer, details)

    def sendAnnotationsPreferences(self):
        self.sdkThread.sendAnnotationPreferences(
            self.viewer,
            self.preferencesDialog.annotationPersistDuration,
            self.preferencesDialog.annotationFadeDuration,
            self.preferencesDialog.annotationPenSize,
            self.annotationColor)

        self.updateAnnotationButtons()

    def sendPictureQualityPreference(self):
        self.sdkThread.sendPictureQualityPreference(
            self.viewer,
            self.preferencesDialog.pictureQuality)

    #
    # Signal callbacks - caused by changes raised by the RealVNC SDK
    #

    ## Authentication events

    def newCredentialDialog(self, viewer, needUsername, needPassword):
        # Here we must make sure that the viewer provided matches the viewer
        # we're using.
        if self.viewer != viewer:
            return

        # The SDK guarantees needUsername and needPassword are not both false.
        # Always create a new credential window to ensure that we can't cache
        # the password by mistake.
        self.credentialDialog = CredentialDialog(needUsername, needPassword, self.sdkThread, viewer)
        self.centerChildWindow(self.credentialDialog)
        self.credentialDialog.setVisible(True)
        self.statusBar().showMessage(self.MESSAGE_AWAITING_CREDENTIALS)

    def closeCredentialDialog(self, viewer):
        if self.viewer != viewer:
            return
        self.onConnectionEnd()
        if self.credentialDialog is not None:
            self.credentialDialog.cancel()
            self.credentialDialog = None

    ## Peer verification events

    def newVerifyPeerDialog(self, viewer, hexFingerprint, catchphraseFingerprint, serverRSAPublic):
        if self.viewer != viewer:
            return
        if self.lastConnectTarget.autoVerifyPeer():
            self.sdkThread.sendPeerVerify(self.viewer, True)
            return
        self.peerVerifyDialog = PeerVerificationDialog(self.sdkThread, viewer, catchphraseFingerprint, hexFingerprint)
        self.centerChildWindow(self.peerVerifyDialog)
        self.peerVerifyDialog.setVisible(True)
        self.statusBar().showMessage(self.MESSAGE_VERIFY_PEER)

    def closeVerifyPeerDialog(self, viewer):
        self.onConnectionEnd()
        if self.peerVerifyDialog is not None:
            self.peerVerifyDialog.cancel()
            self.peerVerifyDialog = None

    ## Connection state management

    def onConnectionStart(self):
        # Prevent multiple simultaneous attempts.
        self.connectAction.setEnabled(False)
        self.disconnectAction.setEnabled(True)
        self.preferencesDialog.encryptionLevelDropdown.setEnabled(False)

    def onConnectionStarted(self):
        self.connectionStatus = self.CONNECTING
        self.statusBar().showMessage(self.MESSAGE_CONNECTING)

    def onConnectionSuccess(self, viewer, serverAnnotationColor):
        self.connectionStatus = self.CONNECTED
        self.serverAnnotationColor = serverAnnotationColor
        self.serverColorAction.setIcon(self.getColorIcon(serverAnnotationColor))

        self.updateScaleIcon()
        self.updateAnnotationButtonsAndMessage()
        self.toolbar.setEnabled(True)

        self.canvas.rescale()
        self.rpcFunctions = RPCFunctions(self.sdkThread, viewer, self.callbacks)
        self.rpcFunctions.onDisplaysUpdated.connect(self.updateDisplays)

    def onConnectionCancelled(self):
        self.connectionStatus = self.DISCONNECTED
        self.connectAction.setEnabled(True)
        self.disconnectAction.setEnabled(False)
        self.toolbar.setEnabled(False)
        self.preferencesDialog.encryptionLevelDropdown.setEnabled(True)

    def onConnectionEnd(self):
        wasConnected = self.connectionStatus == self.CONNECTED

        self.onConnectionCancelled()
        self.updateScaleIcon()
        self.updateAnnotationButtons()
        self.updateDisplays([])
        self.serverNameChanged(self.viewer, None)
        self.statusBar().showMessage(self.MESSAGE_DISCONNECTED)

        if wasConnected:
            self.rpcFunctions.onDisplaysUpdated.disconnect(self.updateDisplays)
            self.rpcFunctions.release()
            self.rpcFunctions = None

    ## Connection status events

    def viewerConnecting(self, viewer):
        if self.viewer != viewer:
            return
        self.onConnectionStarted()

    def viewerConnected(self, viewer, serverAnnotationColor):
        if self.viewer != viewer:
            return

        self.onConnectionSuccess(viewer, serverAnnotationColor)

        # Send the viewer's preferences to the server.
        self.sendPictureQualityPreference()
        self.sendAnnotationsPreferences()

    def viewerDisconnected(self, viewer, message, shouldAlert, canReconnect):
        if self.viewer != viewer:
            return

        wasConnected = self.connectionStatus == self.CONNECTED
        self.onConnectionEnd()

        # Handle attempts to connect to the next place
        if self.nextConnectTarget is not None:
            self.makeNewConnection(self.nextConnectTarget)
            return

        # Handle errors
        if shouldAlert and message:
            preamble = "Disconnected while attempting to establish a connection\nReason: "
            if wasConnected:
                preamble = "Disconnected\nReason: "

            msg = preamble + message
            box = QtGui.QMessageBox(QtGui.QMessageBox.NoIcon, "richViewerPython Error", msg,
                                    buttons=QtGui.QMessageBox.Ok, parent=self)
            box.exec_()
            # If we failed to connect, show the ConnectionDialog again
            if not wasConnected:
                self.connectRequested()

        # Cleanup
        self.sdkThread.destroyViewer(self.viewer, self.onViewerDestroyed)
        self.viewer = None

    ## Misc events

    def serverNameChanged(self, viewer, name):
        if self.viewer != viewer:
            return
        if name is None:
            self.setWindowTitle(self.DEFAULT_WINDOW_TITLE)
        else:
            self.setWindowTitle("{title} - {name}".format(
                title=self.DEFAULT_WINDOW_TITLE,
                name=name
            ))

    def enableAnnotations(self, annotationMgr, enabled):
        if self.viewer is None or self.viewer.get_annotation_manager() != annotationMgr:
            return
        self.canAnnotate = enabled
        self.updateAnnotationButtons()

    ## Events raised by Qt

    # See https://srinikom.github.io/pyside-docs/PySide/QtGui/QWidget.html
    # for when these events are raised.

    def closeEvent(self, e):
        if self.shutdown():
            self.unregisterCallbackListeners()
            e.accept()
        else:
            e.ignore()

    def resizeEvent(self, event):
        if self.connectionStatus == self.CONNECTED:
            self.canvas.rescale()
