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
The main routine.  Run this to start the application.

This sample shows how to implement a rich VNC viewer using the Python bindings
for the VNC SDK.

Two types of connectivity are demonstrated: Cloud-based and direct TCP
connection.

To use direct TCP you will need to obtain a add-on code; a trial code
is available from your RealVNC account. You can ignore TCP-related code
if you do not intend to use the Direct TCP add-on.

This sample app also demonstrates messaging over the custom data channel.
Note this feature requires a separate add-on code; a trial code is
also available from your RealVNC account.

Messages relating to the list of displays currently attached to the Server
computer are received by the Viewer in JSON-RPC 2.0 format, with an
app-specific prefix. For more information, see www.jsonrpc.org/specification.

Add-on codes and VNC Cloud addresses should be applied in ConnectionDetail.py.
"""


import os
import signal
import sys

from PySide import QtGui, QtCore


# Prepare the environment variable so that the SDK knows where the DLL is
# (and also so that python knows where the vncsdk.py file is!
sample_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['VNCSDK_LIBRARY'] = os.path.join(sample_dir, '..', '..', 'lib')
sys.path.append(os.path.join(sample_dir, '..', '..', 'lib', 'python'))

import vncsdk


def manageSignals():
    '''Install a signal handler to shut down the application on Ctrl-C or
       Ctrl-Break.'''
    signal.signal(signal.SIGINT, lambda *args: QtGui.QApplication.quit())
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, lambda *args: QtGui.QApplication.quit())

    # Run some Python code regularly so the signal handler takes effect.
    def checkSignals():
        QtCore.QTimer.singleShot(50, checkSignals)

    checkSignals()


def main():
    # On the main thread, we create the QApplication and our main window.
    # These control the application's UI.
    application = QtGui.QApplication(sys.argv)
    manageSignals()

    try:
        # Provide the chance for everything to fail nicely on load
        from MainWindow import MainWindow
        from SDKThread import SDKThread
        from ViewerCallbacks import ViewerCallbacks
    except Exception as e:
        QtGui.QMessageBox.critical(None, "richViewerPython Error", str(e))
        sys.exit(1)

    # Get the icon on the taskbar right on Windows 7 and later.
    if os.name == "nt":
        import ctypes
        myappid = 'realvnc.richViewerPython'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                myappid)
        except AttributeError:
            pass  # Pre-Win7.

    def fatalExceptionCaught(stackTrace):
        QtGui.QMessageBox.critical(
            mainWindow, "richViewerPython Exception",
            stackTrace)
        mainWindow.close()

    def exceptionCaught(exception):
        if isinstance(exception, vncsdk.VncException) and \
           exception.errorCode == 'PeerNotSupported':
            # There's no need to report unsupported features as errors.
            return
        QtGui.QMessageBox.critical(
            mainWindow, "richViewerPython Exception",
            "Exception: " + str(exception))

    sdkThread = SDKThread()
    sdkThread.onFatalExceptionCaught.connect(fatalExceptionCaught)
    sdkThread.onNonFatalExceptionCaught.connect(exceptionCaught)
    sdkThread.start()

    # We create the main window here, on the main UI thread, once the
    # SDK thread is ready.
    try:
        callbacks = ViewerCallbacks()
        mainWindow = MainWindow(sdkThread, callbacks)

        # QApplication's exec_() method runs the main UI thread's event loop,
        # which runs until the main window has closed.
        application.exec_()
    finally:
        sdkThread.onFatalExceptionCaught.disconnect(fatalExceptionCaught)
        sdkThread.onNonFatalExceptionCaught.disconnect(exceptionCaught)
        sdkThread.terminateThread()
        sdkThread.join(10.0)


if __name__ == '__main__':
    main()
