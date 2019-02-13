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
The "Connect" dialog box.
"""

from PySide import QtGui, QtCore

from ConnectionDetail import CloudConnectionDetail, DirectConnectionDetail


class ConnectDialog(QtGui.QDialog):
    """
    The "Connect" dialog box, for providing server address details.

    On successful completion with a well-formed address, raises an
    onNewConnectionRequest event with the connection details.
    """

    DEFAULT_WINDOW_TITLE = "richViewerPython - Connect"
    IMAGE_WINDOW = "icons/application.png"

    # emit (connection details)
    onNewConnectionRequest = QtCore.Signal(object)
    # emit ()
    onReject = QtCore.Signal()

    def __init__(self):
        QtGui.QDialog.__init__(self)
        self.setModal(True)

        connectLabel = QtGui.QLabel("VNC Cloud &address or IP address")
        self.connectAddress = QtGui.QLineEdit()
        connectLabel.setBuddy(self.connectAddress)

        buttons = QtGui.QDialogButtonBox()
        buttons.addButton("&Ok", buttons.AcceptRole)
        buttons.addButton("&Cancel", buttons.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtGui.QFormLayout()
        layout.setSpacing(10)
        layout.addRow(connectLabel)
        layout.addRow(self.connectAddress)
        layout.addRow(buttons)

        self.setWindowTitle(self.DEFAULT_WINDOW_TITLE)
        self.setWindowIcon(QtGui.QIcon(self.IMAGE_WINDOW))
        self.setLayout(layout)

        # Increase the width so that the title bar text doesn't get truncated
        self.setFixedSize(self.minimumSizeHint().width() + 200,
                          self.minimumSizeHint().height())

    # Dialog visibility handlers

    def showEvent(self, event):
        # Reset the dialog state
        self.connectAddress.setText("")
        self.connectAddress.setFocus()

    #
    # Dialog event handlers
    #

    def reject(self):
        self.onReject.emit()
        super(ConnectDialog, self).reject()

    def accept(self):
        connection = self.generateConnection()
        if connection is None:
            self.reject()
        else:
            self.onNewConnectionRequest.emit(connection)
            super(ConnectDialog, self).accept()

    #
    # Helpers
    #

    def generateConnection(self):
        address = self.connectAddress.text()
        try:
            # IPv4/hostname addresses take the format "address:port".
            # Cloud addresses are 79 characters and do not contain a ":".
            # IPv6 formats are not supported for this sample.

            if ':' in address:
                host, port = address.rsplit(':', 1)
                return DirectConnectionDetail(host, int(port))

            # The best check for a cloud address is its length, and the fact
            # that it wasn't any type of direct connection.
            if len(address) == 79:
                return CloudConnectionDetail(address)

            # Assume the argument is a hostname, using port 5900.
            if len(address) > 0:
                return DirectConnectionDetail(address, 5900)

            return None
        except EnvironmentError as e:
            QtGui.QMessageBox.critical(
                self, "Connection error",
                "Failure creating connector: " + e.message)
            return None
