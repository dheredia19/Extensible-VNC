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
Mappings between value representations.
"""

from PySide import QtCore, QtGui

import vncsdk
import sys


def ARGBToQtColor(color):
    return QtGui.QColor((color >> 16) & 0xff,
                        (color >> 8) & 0xff,
                        color & 0xff,
                        (color >> 24) & 0xff)


def QtColorToARGB(color):
    return ((color.alpha() << 24) +
            (color.red() << 16) +
            (color.green() << 8) +
            color.blue())


class QtToRealVNCMappings(object):
    """
    Provides mappings between Qt values and equivalent RealVNC SDK values.
    """

    def __init__(self):
        # A mapping between the Qt non-printable keys and the SDK keysyms.
        self.KEY_MAP = {
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

            int(QtCore.Qt.Key_Control): vncsdk.Keyboard.XK_Control_L,
            int(QtCore.Qt.Key_Meta): vncsdk.Keyboard.XK_Super_L
        }

        # A mapping between the Qt mouse buttons and the SDK mouse buttons
        self.MOUSE_MAP = {
            int(QtCore.Qt.LeftButton):
                vncsdk.Viewer.MouseButton.MOUSE_BUTTON_LEFT,
            int(QtCore.Qt.RightButton):
                vncsdk.Viewer.MouseButton.MOUSE_BUTTON_RIGHT,
            int(QtCore.Qt.MiddleButton):
                vncsdk.Viewer.MouseButton.MOUSE_BUTTON_MIDDLE
        }

        self.updateKeyMapForPlatform()

    # The key bindings for MAC are a little different to other OS's
    def updateKeyMapForPlatform(self):
        self.CTRL_MODIFIER = QtCore.Qt.ControlModifier
        if sys.platform == 'darwin':  # Mac OS X
            self.KEY_MAP[int(QtCore.Qt.Key_Control)] = vncsdk.Keyboard.XK_Alt_L
            self.KEY_MAP[int(QtCore.Qt.Key_Meta)] = vncsdk.Keyboard.XK_Control_L
            self.CTRL_MODIFIER = QtCore.Qt.MetaModifier

    # Translate a Qt keycode/text to a RealVNC SDK keysym.
    def translateKeys(self, keycode, text, modifiers):
        keysym = self.KEY_MAP.get(keycode)
        if keysym:
            return [keysym]

        ret = []

        # If the Ctrl key is down then the result of e.text() is
        # platform-dependent, so instead we use e.keys() if it lies
        # within the printable ASCII range, otherwise we ignore the key.
        if modifiers & self.CTRL_MODIFIER:
            if 0x20 <= keycode <= 0x7e:
                char = chr(keycode)
                # If Shift is NOT down then we need to convert the character
                # to lowercase, otherwise the server will press Shift for us.
                if not (modifiers & QtCore.Qt.ShiftModifier):
                    char = char.lower()
                ret.append(vncsdk.unicode_to_keysym(ord(char)))
        else:
            for unichar in text:
                ret.append(vncsdk.unicode_to_keysym(ord(unichar)))

        return ret
