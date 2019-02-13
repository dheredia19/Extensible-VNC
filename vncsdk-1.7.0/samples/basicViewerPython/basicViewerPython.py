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

"""This file contains the basicViewerPython sample.

Usage:
    python basicViewerPython.py [LOCAL_CLOUD_ADDRESS] [LOCAL_CLOUD_PASSWORD]
        [PEER_CLOUD_ADDRESS]
    python basicViewerPython.py [TCP_ADDRESS] [TCP_PORT]

Arguments:
    LOCAL_CLOUD_ADDRESS   - the VNC Cloud address for this Viewer
    LOCAL_CLOUD_PASSWORD  - the VNC Cloud password for this Viewer
    PEER_CLOUD_ADDRESSS   - the VNC Cloud address to connect to
    TCP_ADDRESS           - direct TCP address to connect to
    TCP_PORT              - direct TCP port number

    The arguments may be omitted if they have been hard-coded in this file.

This sample shows how to implement a basic VNC viewer using the VNC SDK
Python bindings, using the PySide Qt bindings.

Two types of connectivity are supported: Cloud-based and direct TCP
connection. A viewer can only use one of these mechanisms at a time.

Note: To use direct TCP you will need to apply an add-on code; a trial
code is available from your RealVNC account. You can ignore TCP-related
code below if you do not intend to use the Direct TCP add-on.

The viewer attempts to connect to a server, using either Cloud-based or
direct TCP connectivity according to user-supplied connectivity details.
These details can be provided on the command line or hard-coded by editing the
Python file.

Because both the Qt UI library and the SDK use blocking event loops, we use a
separate thread to run the SDK, and run the UI in the main thread.
"""

import os
import signal
import sys

from PySide import QtCore, QtGui
from threading import Thread, Event

# Before importing the SDK bindings, we set the VNCSDK_LIBRARY environment
# variable, which determines where the Python bindings (vncsdk.py) will search
# for the shared library (DLL).  This sample assumes the directory structure
# used to distribute the samples has been preserved, and searches for the
# shared accordingly.  We also append the path of the Python bindings
# themselves to the search path.
sample_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['VNCSDK_LIBRARY'] = os.path.join(sample_dir, '..', '..', 'lib')
sys.path.append(os.path.join(sample_dir, '..', '..', 'lib', 'python'))
import vncsdk

# For Cloud connections, either hard-code the Cloud address for the Viewer OR
# specify it at the command line. Example Cloud address:
# LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
LOCAL_CLOUD_ADDRESS = None

# Either hard-code the Cloud password associated with this Cloud address OR
# specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
LOCAL_CLOUD_PASSWORD = None

# Either hard-code the Cloud address of the Server (peer) to connect to OR
# specify it at the command line. Example peer Cloud address:
# LxyDgGgrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRydf9ZczNo13BcD
PEER_CLOUD_ADDRESS = None

# To enable direct TCP connectivity you need to copy the content of your
# add-on code into the string below.
direct_tcp_add_on_code = None

# For direct TCP connection you must provide the server's TCP host address
# and port number. Either edit TCP_ADDRESS and TCP_PORT variables below OR
# provide these connection details on the command line.
# The default direct TCP port number can be specified below by using:
# TCP_PORT = vncsdk.DirectTcp.DEFAULT_PORT
# Ignore these variables if you are not using the Direct TCP add-on
TCP_ADDRESS = None
TCP_PORT = 0

# The value of this flag is set automatically according to the user-supplied
# command line arguments and macro definitions above. Cloud connectivity is
# presumed by default here.
using_cloud = True


class ViewerWidget(QtGui.QWidget):
    """The ViewerWidget is the UI object.  All its methods are invoked in the
    main thread.
    """

    # (Qt signals must be class variables rather than instance variables.)
    signal_resized = QtCore.Signal(int, int, int, bytearray, bool)
    signal_connected = QtCore.Signal()
    signal_disconnected = QtCore.Signal(str)
    signal_updated = QtCore.Signal()
    signal_server_name_changed = QtCore.Signal(str)

    # Title for the application
    WINDOW_TITLE = "Basic Python viewer sample"

    def __init__(self):
        """Create and initialise the window and its viewer widget."""

        # Call the parent constructor
        QtGui.QWidget.__init__(self)

        # This Qt signal is fired when the Viewer connection succeeds
        self.signal_connected.connect(self.on_connected)
        # This Qt signal is fired when the Viewer connection ends
        self.signal_disconnected.connect(self.on_disconnected)
        # This Qt signal is fired when the framebuffer has been updated
        self.signal_updated.connect(self.on_framebuffer_updated)
        # This Qt signal is fired when the framebuffer has been resized
        self.signal_resized.connect(self.on_framebuffer_resized)
        # This Qt signal is fired when the Server's desktop name has changed
        self.signal_server_name_changed.connect(self.on_server_name_changed)

        self.resize_event = Event()
        self.ignore_next_resize_event = False
        self.conn_disconnected = False
        self.buffer = self.canvas = None
        self.shown = False
        self.setWindowTitle(self.WINDOW_TITLE)

        # Ensure we receive mouse and focus events
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    #
    # The following methods handle events from the Server, received via signals
    # from the SDK thread:
    #

    def on_connected(self):
        """The Viewer just succeeded in connecting to the Server"""

        # Hide the cursor - we'll see the server's cursor instead
        self.setCursor(QtCore.Qt.BlankCursor)

    def on_disconnected(self, message):
        """The Viewer connection has just ended"""
        # Reset the cursor to the default
        self.unsetCursor()

        # Display the disconnection reason, if any
        if message:
            box = QtGui.QMessageBox(QtGui.QMessageBox.NoIcon, "Error", message,
                                    buttons=QtGui.QMessageBox.Ok, parent=self)
            box.exec_()

        # Close the window.  Setting conn_disconnected prevents us subsequently
        # calling disconnect() on the connection.
        self.conn_disconnected = True
        self.close()

    def on_framebuffer_updated(self):
        """The Viewer connection has received fresh data from the Server, so we
        redraw the widget by triggering a Qt paint event.
        """
        self.update()

    def on_framebuffer_resized(self, width, height, stride, buffer,
                               resize_window):
        """The Server's framebuffer size has changed, so we reset our canvas to
        use the new buffer and resize our window to match.
        """

        # We take a reference to the buffer, to guarantee that it stays valid
        # for the lifetime of the QImage, which will use it as its backing
        # buffer.
        self.buffer = buffer
        self.canvas = QtGui.QImage(
            buffer,
            width,
            height,
            stride * 4,
            QtGui.QImage.Format_RGB32
        )

        if resize_window:
            # Set this flag so we don't enter an infinite loop of resizing
            self.ignore_next_resize_event = True
            self.resize(width, height)
        if not self.shown:
            # Until we receive a resize event from the SDK, we don't know what
            # size the window should be, so the wait for the first event before
            # showing the window.
            self.shown = True
            self.show()

    def on_server_name_changed(self, name):
        """The Server's desktop name has changed."""
        self.setWindowTitle("{title} - {name}".format(
            title=self.WINDOW_TITLE,
            name=name
        ))

    #
    # The following methods handle Qt events, received by subclassing QWidget:
    #

    def closeEvent(self, e):
        """The user has just attempted to close the Qt window."""

        if not self.conn_disconnected:
            vncsdk.EventLoop.run_on_loop(viewer_conn.on_closed)
            # We don't shut the window immediately, it should stay open until
            # the connection has been cleanly closed, at which point we receive
            # the on_disconnected() signal and exit the app.
            e.ignore()

    def paintEvent(self, e):
        """The Qt window must be redrawn, so we paint using our canvas."""

        if not self.canvas:
            # Ignore paint events before we've set up our canvas
            return
        painter = QtGui.QPainter(self)
        painter.drawImage(0, 0, self.canvas)

    def resizeEvent(self, e):
        """The user has just attempted to resize the Qt window, or we have just
        called resize() to match a change in the Server's screen size.  We
        distinguish these two cases using the ignore_next_resize_event flag.
        """

        if self.ignore_next_resize_event:
            self.ignore_next_resize_event = False
        else:
            self.resize_event.clear()
            # Don't resize frame buffer smaller than 10 x 10
            vncsdk.EventLoop.run_on_loop(viewer_conn.on_widget_resized,
                                         (max(10, e.size().width()), max(10, e.size().height()),
                                         self.resize_event))
            # Wait for the SDK thread to process the resize, to prevent us
            # from spamming it with resize requests.
            self.resize_event.wait()

    def keyPressEvent(self, e):
        """The Qt window has been sent keyboard input, which we send to the
        Server.
        """

        # A mapping between the Qt non-printable keys and the SDK keysyms
        key_map = {
            int(QtCore.Qt.Key_Escape): vncsdk.Keyboard.XK_Escape,
            int(QtCore.Qt.Key_Return): vncsdk.Keyboard.XK_Return,
            int(QtCore.Qt.Key_Enter): vncsdk.Keyboard.XK_KP_Enter,
            int(QtCore.Qt.Key_Insert): vncsdk.Keyboard.XK_Insert,
            int(QtCore.Qt.Key_Delete): vncsdk.Keyboard.XK_Delete,
            int(QtCore.Qt.Key_Pause): vncsdk.Keyboard.XK_Pause,
            int(QtCore.Qt.Key_Print): vncsdk.Keyboard.XK_Print,
            int(QtCore.Qt.Key_SysReq): vncsdk.Keyboard.XK_Sys_Req,
            int(QtCore.Qt.Key_Home): vncsdk.Keyboard.XK_Home,
            int(QtCore.Qt.Key_End): vncsdk.Keyboard.XK_End,
            int(QtCore.Qt.Key_Left): vncsdk.Keyboard.XK_Left,
            int(QtCore.Qt.Key_Up): vncsdk.Keyboard.XK_Up,
            int(QtCore.Qt.Key_Right): vncsdk.Keyboard.XK_Right,
            int(QtCore.Qt.Key_Down): vncsdk.Keyboard.XK_Down,
            int(QtCore.Qt.Key_PageUp): vncsdk.Keyboard.XK_Page_Up,
            int(QtCore.Qt.Key_PageDown): vncsdk.Keyboard.XK_Page_Down,
            int(QtCore.Qt.Key_Shift): vncsdk.Keyboard.XK_Shift_L,
            int(QtCore.Qt.Key_Alt): vncsdk.Keyboard.XK_Alt_L,

            int(QtCore.Qt.Key_F1): vncsdk.Keyboard.XK_F1,
            int(QtCore.Qt.Key_F2): vncsdk.Keyboard.XK_F2,
            int(QtCore.Qt.Key_F3): vncsdk.Keyboard.XK_F3,
            int(QtCore.Qt.Key_F4): vncsdk.Keyboard.XK_F4,
            int(QtCore.Qt.Key_F5): vncsdk.Keyboard.XK_F5,
            int(QtCore.Qt.Key_F6): vncsdk.Keyboard.XK_F6,
            int(QtCore.Qt.Key_F7): vncsdk.Keyboard.XK_F7,
            int(QtCore.Qt.Key_F8): vncsdk.Keyboard.XK_F8,
            int(QtCore.Qt.Key_F9): vncsdk.Keyboard.XK_F9,
            int(QtCore.Qt.Key_F10): vncsdk.Keyboard.XK_F10,
            int(QtCore.Qt.Key_F11): vncsdk.Keyboard.XK_F11,
            int(QtCore.Qt.Key_F12): vncsdk.Keyboard.XK_F12,
        }
        if sys.platform == 'darwin':  # Mac OS X
            key_map[int(QtCore.Qt.Key_Control)] = vncsdk.Keyboard.XK_Alt_L
            key_map[int(QtCore.Qt.Key_Meta)] = vncsdk.Keyboard.XK_Control_L
            ctrl_modifier = QtCore.Qt.MetaModifier
        else:
            key_map[int(QtCore.Qt.Key_Control)] = vncsdk.Keyboard.XK_Control_L
            key_map[int(QtCore.Qt.Key_Meta)] = vncsdk.Keyboard.XK_Super_L
            ctrl_modifier = QtCore.Qt.ControlModifier

        # Try first to send the keycode as a keysym directly, to handle non-
        # printing keycodes, which don't have associated Unicode text.
        keysym = key_map.get(e.key())
        keycode = e.key()
        if keysym:
            vncsdk.EventLoop.run_on_loop(viewer_conn.on_key_press,
                                         (keysym, False, keycode))
            return

        # Otherwise, it's presumably a Unicode key, so we should send it the
        # codepoints as Unicode keysyms.
        if e.modifiers() & ctrl_modifier:
            # If the Ctrl key is down then the result of e.text() is
            # platform-dependent, so instead we use e.keys() if it lies
            # within the printable ASCII range, otherwise we ignore the key.
            if keycode >= 0x20 and keycode <= 0x7e:
                char = chr(e.key())
                # If Shift is NOT down then we need to convert the character
                # to lowercase, otherwise the server will press Shift for us.
                if not (e.modifiers() & QtCore.Qt.ShiftModifier):
                    char = char.lower()
                vncsdk.EventLoop.run_on_loop(viewer_conn.on_key_press,
                                             (ord(char), True, keycode))
        else:
            for unichar in e.text():
                vncsdk.EventLoop.run_on_loop(viewer_conn.on_key_press,
                                             (ord(unichar), True, keycode))

    def keyReleaseEvent(self, e):
        """The Qt window has been sent keyboard input, which we send to the
        Server.
        """

        keycode = e.key()
        vncsdk.EventLoop.run_on_loop(viewer_conn.on_key_release, (keycode,))

    def mouseEvent(self, e):
        """The Qt window has been sent mouse input, which we send to the
        Server. This method only handles click and move events, not scrollwheel
        events.
        """

        # A mapping between the Qt enumerations and the SDK enumerations
        mouse_map = {
            int(QtCore.Qt.LeftButton):
                vncsdk.Viewer.MouseButton.MOUSE_BUTTON_LEFT,
            int(QtCore.Qt.RightButton):
                vncsdk.Viewer.MouseButton.MOUSE_BUTTON_RIGHT,
            int(QtCore.Qt.MiddleButton):
                vncsdk.Viewer.MouseButton.MOUSE_BUTTON_MIDDLE
        }

        raw_buttons = int(e.buttons())
        mouse_mask = {v for k, v in mouse_map.items() if k & raw_buttons}

        vncsdk.EventLoop.run_on_loop(viewer_conn.on_pointer_event,
                                     (e.x(), e.y(), mouse_mask))

    mouseMoveEvent = mouseEvent
    mousePressEvent = mouseEvent
    mouseReleaseEvent = mouseEvent

    def wheelEvent(self, e):
        """The Qt window has been sent mouse scroll input, which we send to the
        Server.
        """

        # Qt's units are scaled for high-resolution scrolling devices, whereas
        # the SDK uses the more common Windows units, so we rescale the delta
        # using Microsoft's "WHEEL_DELTA" factor of 120.
        delta = int(e.delta() / 120)
        axis = vncsdk.Viewer.MouseWheel.MOUSE_WHEEL_VERTICAL
        vncsdk.EventLoop.run_on_loop(viewer_conn.on_scroll_event,
                                     (delta, axis))

    def focusOutEvent(self, e):
        """The Qt window has lost focus, so we release all pressed keys."""
        vncsdk.EventLoop.run_on_loop(viewer_conn.on_focus_out_event)


class ViewerConn(vncsdk.Viewer.ConnectionCallback,
                 vncsdk.Viewer.FramebufferCallback,
                 vncsdk.Viewer.ServerEventCallback):
    """The ViewerConn owns the SDK's Viewer object, representing the Viewer's
    connection to the Server, and handles notifications from the SDK's
    callbacks.  All its methods are invoked in the SDK thread.
    """

    def __init__(self):
        vncsdk.Viewer.ConnectionCallback.__init__(self)
        vncsdk.Viewer.FramebufferCallback.__init__(self)
        vncsdk.Viewer.ServerEventCallback.__init__(self)

        self.viewer = vncsdk.Viewer()
        self.is_connected = False
        self.viewer.set_connection_callback(self)
        self.viewer.set_framebuffer_callback(self)
        self.viewer.set_server_event_callback(self)

        # Set the Qt widget's initial size to the initial size of the Viewer.
        w = self.viewer.get_viewer_fb_width()
        h = self.viewer.get_viewer_fb_height()
        self._set_buffer(w, h)
        viewer_widget.signal_resized.emit(w, h, w, self.buffer, True)

    def destroy(self):
        self.viewer.destroy()
        self.viewer = None

    def _set_buffer(self, width, height):
        # We set our pixel buffer to be a new buffer with a matching size, and
        # choose the SDK's rgb888() format, which corresponds to Qt's
        # QImage.Format_RGB32.
        self.buffer = bytearray(width * height * 4)
        self.viewer.set_viewer_fb(
            self.buffer,
            vncsdk.PixelFormat.rgb888(),
            width, height, width
        )

    #
    # The following methods handle notifications from the SDK of events from
    # the server.
    #

    def viewer_fb_updated(self, viewer, x, y, w, h):
        """The Server has sent fresh pixel data, so we signal the Qt window to
        redraw.
        """
        viewer_widget.signal_updated.emit()

    def server_fb_size_changed(self, viewer, w, h):
        """The Server screen size has changed, so we signal the Qt window to
        resize to match its aspect ratio.
        """
        aspect_ratio = w / float(h)
        w = self.viewer.get_viewer_fb_width()
        h = int(w / aspect_ratio)
        self._set_buffer(w, h)
        viewer_widget.signal_resized.emit(w, h, w, self.buffer, True)

    def connected(self, viewer):
        """The Viewer's connection to the Server has succeeded."""
        self.is_connected = True
        viewer_widget.signal_connected.emit()

    def disconnected(self, viewer, reason, flags):
        """The Viewer's connection to the Server has ended."""
        message = ""
        if vncsdk.Viewer.DisconnectFlags.ALERT_USER in flags:
            if not self.is_connected:
                message = \
                    "Disconnected while attempting to establish a connection"
            message = "{msg}\nDisconnect reason: {reason}".format(
                      msg=message, reason=reason)
        viewer_widget.signal_disconnected.emit(message)

    def server_friendly_name_changed(self, viewer, name):
        viewer_widget.signal_server_name_changed.emit(name)

    #
    # The following methods handle notifications of events sent from the Qt
    # widget to the SDK.
    #

    def on_closed(self):
        self.viewer.disconnect()

    def on_widget_resized(self, w, h, event):
        self._set_buffer(w, h)
        viewer_widget.signal_resized.emit(w, h, w, self.buffer, False)
        event.set()

    def on_key_press(self, keysym, translate_unichar, keycode):
        if translate_unichar:
            keysym = vncsdk.unicode_to_keysym(keysym)
        self.viewer.send_key_down(keysym, keycode)

    def on_key_release(self, keycode):
        self.viewer.send_key_up(keycode)

    def on_pointer_event(self, x, y, button_mask):
        self.viewer.send_pointer_event(x, y, button_mask, False)

    def on_scroll_event(self, delta, axis):
        self.viewer.send_scroll_event(delta, axis)

    def on_focus_out_event(self):
        self.viewer.release_all_keys()


def usage_advice():
    """Provide usage information on console."""
    usage = sys.modules[__name__].__doc__.split('\n')[2:13]
    print('\n'.join(usage))


def extract_port_num(arg):
    """Extract port number from command line argument."""
    port = 0
    try:
        port = int(arg)
    except ValueError:
        print("Invalid port number\n")
    return port


def parse_command_line():
    """Parse the command line to obtain connectivity details to be used when
    listening for incoming connections. A simplistic approach is adopted:

    3 arguments - Cloud connectivity to be used
                  [LOCAL_CLOUD_ADDRESS LOCAL_CLOUD_PASSWORD PEER_CLOUD_ADDRESS]

    2 arguments - Direct TCP connectivity to be used
                  [TCP_ADDRESS TCP_PORT]

    0 arguments - the built-in macros must be set appropriately
    """
    global LOCAL_CLOUD_ADDRESS, LOCAL_CLOUD_PASSWORD, PEER_CLOUD_ADDRESS
    global TCP_ADDRESS, TCP_PORT
    global using_cloud
    bad_args = False
    argc = len(sys.argv)

    # Parse any supplied command line arguments
    if argc == 4 or argc == 3 or argc == 1:
        if argc == 4:  # Cloud arguments
            LOCAL_CLOUD_ADDRESS = sys.argv[1]
            LOCAL_CLOUD_PASSWORD = sys.argv[2]
            PEER_CLOUD_ADDRESS = sys.argv[3]
        elif argc == 3:  # Direct TCP arguments
            TCP_ADDRESS = sys.argv[1]
            TCP_PORT = extract_port_num(sys.argv[2])
            using_cloud = False
        else:  # Examine hard-coded values from global variables above
            if LOCAL_CLOUD_ADDRESS or LOCAL_CLOUD_PASSWORD or \
               PEER_CLOUD_ADDRESS:
                using_cloud = True
            elif TCP_PORT or TCP_ADDRESS:
                using_cloud = False

        # Check if all required connectivity details are provided either via
        # editing the global variables above, or on the command-line
        if using_cloud and (not LOCAL_CLOUD_ADDRESS or
                            not LOCAL_CLOUD_PASSWORD or
                            not PEER_CLOUD_ADDRESS):
            bad_args = True
        elif not using_cloud and (not TCP_PORT or not TCP_ADDRESS):
            bad_args = True
    else:
        bad_args = True  # Invalid number of arguments

    if bad_args:
        usage_advice()
        sys.exit(1)


def sdk_main():
    """sdk_main() is the main method for the SDK thread.  It initializes the
    SDK, creates the SDK objects, and runs the SDK event loop.  When sdk_main()
    exits, the SDK thread has finished.
    """
    try:
        global using_cloud, direct_tcp_add_on_code, viewer_conn

        # Create a logger with outputs to sys.stderr
        vncsdk.Logger.create_stderr_logger()

        # Create a file DataStore for storing persistent data for the viewer.
        # Ideally this would be created in a directory that only the viewer
        # user has access to.
        vncsdk.DataStore.create_file_store("dataStore.txt")

        # Initialize SDK and optional Add-Ons
        vncsdk.init()
        if not using_cloud:
            try:
                vncsdk.enable_add_on(direct_tcp_add_on_code)
            except Exception as e:
                print("Failed to enable Direct TCP add-on: " + str(e))
                viewer_widget.signal_disconnected.emit(None)
                return

        # Create the SDK Viewer objects, and begin the connection to the Server
        viewer_conn = ViewerConn()
        viewer_handler = viewer_conn.viewer.get_connection_handler()

        if using_cloud:
            # Make a Cloud connection
            print("Connecting via VNC Cloud")
            print("    local address: {addr}".format(addr=LOCAL_CLOUD_ADDRESS))
            print("     peer address: {addr}".format(addr=PEER_CLOUD_ADDRESS))
            with vncsdk.CloudConnector(LOCAL_CLOUD_ADDRESS,
                                       LOCAL_CLOUD_PASSWORD) \
                    as cloud_connector:
                cloud_connector.connect(PEER_CLOUD_ADDRESS, viewer_handler)
        else:
            # Make a Direct TCP connection.
            # Ignore this if you do not intend to use the Direct TCP add-on
            print("Connecting to host address: {address} port: {port}".format(
                  address=TCP_ADDRESS, port=str(TCP_PORT)))
            with vncsdk.DirectTcpConnector() as tcp_connector:
                tcp_connector.connect(TCP_ADDRESS, TCP_PORT, viewer_handler)

        # Run the SDK's event loop.  This will return when the main thread
        # calls vncsdk.EventLoop.stop(), allowing the SDK thread to exit.
        vncsdk.EventLoop.run()

    except:
        import traceback
        traceback.print_exc()
        viewer_widget.signal_disconnected.emit(None)

    finally:
        if viewer_conn:
            viewer_conn.destroy()

        vncsdk.shutdown()


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


if __name__ == '__main__':
    # Parse command line
    parse_command_line()

    # On the main thread, we create the QApplication and our viewer widget.
    # These control the application's UI.
    application = QtGui.QApplication(sys.argv)
    manageSignals()

    viewer_conn = None
    viewer_widget = ViewerWidget()

    # We create a second thread for running the SDK.
    sdk_thread = Thread(target=sdk_main)
    sdk_thread.start()

    # QApplication's exec_() method runs the main UI thread's event loop, which
    # runs until the viewer window has closed.
    application.exec_()

    # After the UI has been closed, we stop the SDK thread and let it finish.
    vncsdk.EventLoop.stop()
    sdk_thread.join()
