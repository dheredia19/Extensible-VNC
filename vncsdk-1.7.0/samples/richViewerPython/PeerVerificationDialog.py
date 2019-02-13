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
The "Verify peer" dialog box.
"""

from PySide import QtGui


class PeerVerificationDialog(QtGui.QDialog):
    """
    The "Verify peer" dialog box, for displaying the server's credentials.

    The displayed details provide a form of proof of the server's identity,
    its "fingerprints". A change in details could indicate a man-in-the-middle
    attack.
    """

    DEFAULT_WINDOW_TITLE = "richViewerPython - Verify peer"
    IMAGE_WINDOW = "icons/application.png"

    def __init__(self, sdkThread, viewer, catchphraseFingerprint, hexFingerprint):
        QtGui.QDialog.__init__(self)
        self.setModal(True)

        self.sdkThread = sdkThread
        self.viewer = viewer
        self.terminated = False

        layout = QtGui.QFormLayout(self)
        layout.setSpacing(10)
        layout.addRow("Server catchphrase:", QtGui.QLabel(catchphraseFingerprint))
        layout.addRow("Server signature:", QtGui.QLabel(hexFingerprint))

        buttons = QtGui.QDialogButtonBox()
        buttons.addButton("&Ok", buttons.AcceptRole)
        buttons.addButton("&Cancel", buttons.RejectRole).setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setWindowTitle(self.DEFAULT_WINDOW_TITLE)
        self.setWindowIcon(QtGui.QIcon(self.IMAGE_WINDOW))
        self.setLayout(layout)

        # Increase the width so that the title bar text doesn't get truncated
        self.setFixedSize(self.minimumSizeHint().width() + 200,
                          self.minimumSizeHint().height())

    def cancel(self):
        """
        Close the dialog due to termination of the underlying authentication
        process.
        """
        self.terminated = True
        self.close()

    #
    # Dialog event handlers
    #

    def reject(self):
        if not self.terminated:
            self.sdkThread.sendPeerVerify(self.viewer, False)
        super(PeerVerificationDialog, self).reject()

    def accept(self):
        self.sdkThread.sendPeerVerify(self.viewer, True)
        super(PeerVerificationDialog, self).accept()
