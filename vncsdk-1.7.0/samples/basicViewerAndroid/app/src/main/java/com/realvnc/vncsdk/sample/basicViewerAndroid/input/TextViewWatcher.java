/*
Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software without
specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

package com.realvnc.vncsdk.sample.basicViewerAndroid.input;

import android.text.Editable;
import android.text.TextWatcher;
import android.widget.EditText;

import com.realvnc.vncsdk.Keyboard;
import com.realvnc.vncsdk.Library;

import java.util.Vector;

/**
 * Class used to watch the hidden input field for text changes.
 *
 * The general approach for capturing input events in this viewer is to use a hidden
 * EditText instance and to register a TextWatcher to be notified of any text input by the
 * user.
 *
 * The TextWatcher object is notified before, on and after any text changes in the input field.
 * This covers the basic case where the user inputs or deletes printable text, but doesn't cover the
 * following:
 *
 * 1. Any non-printable key events such as the F-(function) keys, arrow keys are not supported.
 *
 * 2. Any modifier keys such as alt, ctrl or shift are similarly not supported.
 *
 * 3. Printable hardware key events will be picked up by the hidden input field, but as per 1. and
 *    2. above, non-printable or modifier keys will not be detected.
 *
 * We notify the {@link Callback} to send key events to the VNC server.
 */
public class TextViewWatcher implements TextWatcher  {
    private final Callback mCallback;
    private final EditText mEditText;
    private String mBeforeText;
    private String mAfterText;

    public void reset() {
        mEditText.removeTextChangedListener(this);
        // The text field must contain at least one character before the cursor so that backspaces
        // can be detected.
        mEditText.setText(" ");
        mBeforeText = mAfterText = " ";
        mEditText.setSelection(1);
        mEditText.addTextChangedListener(this);
    }

    public interface Callback {
        void sendKeyEvents(Vector<KeyEvent> keyEvents);
        void sendKeyEvent(KeyEvent keyEvent);
    }

    public class KeyEvent {
        public int unicodeChar;
        public boolean down;

        public KeyEvent(int unicodeChar, boolean down) {
            this.unicodeChar = unicodeChar;
            this.down = down;
        }
    }

    @Override
    public void beforeTextChanged(CharSequence s, int start, int count, int after) {
        // Convert to String, as CharSequences are mutable and String objects aren't.
        mBeforeText = s.toString();
    }

    @Override
    public void onTextChanged(CharSequence s, int start, int before, int count) {
        // Convert to String, as CharSequences are mutable and String objects aren't.
        mAfterText = s.toString();
    }

    @Override
    public void afterTextChanged(Editable s) {
        // Index into mBeforeText
        int i = 0;
        // Index into mAfterText
        int j = 0;

        Vector<KeyEvent> keyEvents = new Vector<>(10);

        // Iterate over each string until the first difference between
        // the two string is found
        for (; (i < mBeforeText.length()) && (j < mAfterText.length()); i++, j++) {
            char c = mBeforeText.charAt(i);
            char d = mAfterText.charAt(j);

            if (c != d) {
                break;
            }
        }

        // Delete the remaining characters of text before that are
        // currently on the server
        for (; i < mBeforeText.length(); i++) {
            keyEvents.add(new KeyEvent(Keyboard.XK_BackSpace, true));
            keyEvents.add(new KeyEvent(Keyboard.XK_BackSpace, false));
        }

        // Send the remaining characters of text after that are not
        // currently on the server
        for (; j < mAfterText.length(); j++) {
            char c = mAfterText.charAt(j);

            keyEvents.add(new KeyEvent(Library.unicodeToKeysym(c), true));
            keyEvents.add(new KeyEvent(Library.unicodeToKeysym(c), false));
        }

        mCallback.sendKeyEvents(keyEvents);

        if (mAfterText.length() == 0) {
            reset();
        }
    }

    public TextViewWatcher(EditText textView, Callback callback) {
        mEditText = textView;
        reset();
        mCallback = callback;
    }
}
