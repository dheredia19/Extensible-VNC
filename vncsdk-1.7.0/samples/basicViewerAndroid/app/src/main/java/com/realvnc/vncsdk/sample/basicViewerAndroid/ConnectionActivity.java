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

package com.realvnc.vncsdk.sample.basicViewerAndroid;

import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AppCompatActivity;
import android.text.TextUtils;
import android.util.Log;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;

import com.realvnc.vncsdk.CloudConnector;
import com.realvnc.vncsdk.DirectTcp;
import com.realvnc.vncsdk.DirectTcpConnector;
import com.realvnc.vncsdk.ImmutableDataBuffer;
import com.realvnc.vncsdk.Keyboard;
import com.realvnc.vncsdk.Library;
import com.realvnc.vncsdk.Viewer;
import com.realvnc.vncsdk.sample.basicViewerAndroid.input.TextViewWatcher;
import com.realvnc.vncsdk.sample.basicViewerAndroid.input.TouchEventAdapter;
import com.realvnc.vncsdk.sample.basicViewerAndroid.ui.FrameBufferView;

import java.util.EnumSet;
import java.util.Vector;

/**
 * This class represents the main screen used to show the server's framebuffer.
 */
public class ConnectionActivity extends AppCompatActivity implements TouchEventAdapter.Callback,
        TextViewWatcher.Callback, Viewer.AuthenticationCallback, Viewer.PeerVerificationCallback,
        SdkThread.Callback {

    private static final String TAG = "ConnectionActivity";

    // Constants used as keys in an Intent object used to start this activity.
    public static final String USE_CLOUD_CONNECTIVITY = "use_cloud_connectivity";

    public static final String LOCAL_CLOUD_ADDRESS = "local_cloud_address";
    public static final String LOCAL_CLOUD_PASSWORD = "local_cloud_password";
    public static final String PEER_CLOUD_ADDRESS = "peer_cloud_address";

    public static final String DIRECT_TCP_ADDRESS = "direct_tcp_address";
    public static final String DIRECT_TCP_PORT = "direct_tcp_port";
    public static final String DIRECT_TCP_ADDON_CODE = "direct_tcp_addon_code";

    private Viewer mViewer;
    private CloudConnector mCloudConnector;
    private DirectTcpConnector mDirectTcpConnector;

    private FrameBufferView mFrameBufferView;
    private InputMethodManager mInputMethodManager;
    private EditText mHiddenEditText;
    private TextViewWatcher mTextViewWatcher;

    private AlertDialog mAuthDialog;

    private ProgressDialog mProgressDialog;
    private AlertDialog mDisconnectDlg;
    private AlertDialog mAlertDialog;
    private AlertDialog mPeerDialog;
    private View mExtensionKeyboardView;

    // region dialog builders

    /**
     * Helper method to build a disconnect confirmation dialog
     *
     * @return
     */
    private AlertDialog buildDisconnectAlertDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);

        return builder.setMessage(R.string.confirm_disconnect)
                .setNegativeButton(R.string.cancel, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        dialog.dismiss();
                    }
                })
                .setPositiveButton(R.string.disconnect, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {

                        dialog.dismiss();
                        SdkThread.getInstance().post(
                                new Runnable() {
                                    @Override
                                    public void run() {
                                        try {
                                            mViewer.disconnect();
                                        } catch (Library.VncException e) {
                                            Log.e(TAG, "Disconnect error:", e);
                                        }
                                    }
                                }
                        );

                    }
                })
                .create();
    }

    /**
     * Builds the disconnected dialog.
     *
     * @param disconnectedReason The string displayed by the AlertDialog.
     * @return
     */
    private AlertDialog buildAlertDialog(String disconnectedReason) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);

        return builder.setMessage(disconnectedReason)
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        cleanup();
                    }
                })
                .setCancelable(false)
                .create();
    }

    /**
     * Build the authentication dialog.
     *
     * @return
     * @param needUser
     * @param needPassword
     */
    private AlertDialog buildAuthDialog(boolean needUser, boolean needPassword) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        final View authDialogView = getLayoutInflater().inflate(R.layout.auth_dialog, null);
        if (!needUser) {
            authDialogView.findViewById(R.id.auth_username).setVisibility(View.GONE);
        }
        if (!needPassword) {
            authDialogView.findViewById(R.id.auth_password).setVisibility(View.GONE);
        }

        return builder.setView(authDialogView)
                .setNegativeButton(R.string.cancel, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        SdkThread.getInstance().post(new Runnable() {
                            @Override
                            public void run() {
                                try {
                                    mViewer.sendAuthenticationResponse(false, "", "");
                                    mViewer.disconnect();
                                } catch (Library.VncException e) {
                                    Log.w(TAG, "userPasswdResult", e);
                                    displayMessage(R.string.sending_authentication_response_failed, e.getMessage());
                                }
                            }
                        });
                        dismissDialogs();
                    }
                })
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        final String username = ((EditText) authDialogView.findViewById(R.id.auth_username)).getText()
                                .toString();
                        final String password = ((EditText) authDialogView.findViewById(R.id.auth_password)).getText()
                                .toString();
                        SdkThread.getInstance().post(new Runnable() {
                            @Override
                            public void run() {
                                try {
                                    mViewer.sendAuthenticationResponse(true, username, password);
                                } catch (Library.VncException e) {
                                    Log.w(TAG, "userPasswdResult", e);
                                    displayMessage(R.string.sending_authentication_response_failed, e.getMessage());
                                }
                            }
                        });
                    }
                })
                .setCancelable(false)
                .create();
    }

    /**
     * Build the peer verification dialog.
     *
     * @return
     * @param hexFingerprint
     * @param catchphraseFingerprint
     */
    private AlertDialog buildPeerVerificationDialog(String hexFingerprint,
                                                    String catchphraseFingerprint) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle(R.string.peer_verification_title);

        String message;
        try {
            String address = mViewer.getPeerAddress();
            message = getResources().getString(R.string.peer_verification_message,
                    address, hexFingerprint, catchphraseFingerprint);
        } catch (Library.VncException e) {
            Log.w(TAG, "Unable to get peer address");
            message = getResources().getString(R.string.peer_verification_message,
                    "Unknown", hexFingerprint, catchphraseFingerprint);
        }

        builder.setMessage(message);

        return builder.setNegativeButton(R.string.cancel, new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                SdkThread.getInstance().post(new Runnable() {
                    @Override
                    public void run() {
                        sendPeerIdentityResponse(false);
                    }
                });
                dismissDialogs();
            }
        })
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        SdkThread.getInstance().post(new Runnable() {
                            @Override
                            public void run() {
                                sendPeerIdentityResponse(true);
                            }
                        });
                        dismissDialogs();
                    }
                })
                .setCancelable(false)
                .create();
    }
    // endregion

    // region Activity overrides
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        Log.d(TAG, "onCreate");
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_connection);

        mFrameBufferView = (FrameBufferView) findViewById(R.id.frameBufferView);
        mHiddenEditText = (EditText) findViewById(R.id.hiddenEditText);
        mExtensionKeyboardView = findViewById(R.id.ExtensionKeyboard);

        // Set up touch event handling
        mFrameBufferView.setTouchEventAdapter(new TouchEventAdapter(this, this));

        mTextViewWatcher = new TextViewWatcher(mHiddenEditText, this);

        ActionBar actionBar = getSupportActionBar();
        if (actionBar != null) {
            actionBar.setDisplayShowTitleEnabled(false);
        }

        // Keep device awake
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        final Button f1Button = (Button) findViewById(R.id.f1Button);
        f1Button.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                // Perform action on click

                SdkThread.getInstance().post(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            mViewer.sendKeyDown(Keyboard.XK_F1, Keyboard.XK_F1);
                            mViewer.sendKeyUp(Keyboard.XK_F1);
                        } catch (Library.VncException e) {
                            Log.w(TAG, "Unable to send key event:", e);
                        }
                    }
                });
            }
        });

        final Button cadButton = (Button) findViewById(R.id.cadButton);
        cadButton.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                // Perform action on click

                SdkThread.getInstance().post(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            mViewer.sendKeyDown(Keyboard.XK_Control_L, Keyboard.XK_Control_L);
                            mViewer.sendKeyDown(Keyboard.XK_Alt_L, Keyboard.XK_Alt_L);
                            mViewer.sendKeyDown(Keyboard.XK_Delete, Keyboard.XK_Delete);
                            mViewer.sendKeyUp(Keyboard.XK_Delete);
                            mViewer.sendKeyUp(Keyboard.XK_Alt_L);
                            mViewer.sendKeyUp(Keyboard.XK_Control_L);
                        } catch (Library.VncException e) {
                            Log.w(TAG, "Unable to send key event:", e);
                        }
                    }
                });
            }
        });
    }

    @Override
    protected void onPause() {
        if (SdkThread.getInstance().initComplete()) {
            SdkThread.getInstance().post(new Runnable() {
                @Override
                public void run() {
                    if (mViewer != null && mViewer.getConnectionStatus() == Viewer.ConnectionStatus.CONNECTED) {
                        try {
                            // Disconnect when the activity is hidden.
                            mViewer.disconnect();
                        } catch (Library.VncException e) {
                            Log.e(TAG, "Disconnect error:", e);
                        }
                    }
                }
            });
        }

        dismissDialogs();
        super.onPause();
    }

    @Override
    protected void onResume() {
        Log.d(TAG, "onResume");
        super.onResume();
        init();
    }

    /**
     * Inflate the action bar menu (containing the keyboard toggle button).
     *
     * @param menu
     * @return
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        MenuInflater inflater = getMenuInflater();
        inflater.inflate(R.menu.menu_connection, menu);
        return super.onCreateOptionsMenu(menu);
    }

    /**
     * Called when any menu item (eg keyboard toggle) has been selected.
     *
     * @param item
     * @return
     */
    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.action_toggle_keyboard) {
            mInputMethodManager.toggleSoftInputFromWindow(mHiddenEditText.getWindowToken(), 0, 0);

            // Clear the hidden input field
            mTextViewWatcher.reset();

            // We've handled the menu item event
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    public void onBackPressed() {
        if (mAuthDialog != null && mAuthDialog.isShowing()) {
            mAuthDialog.cancel();
        } else if (mViewer.getConnectionStatus() == Viewer.ConnectionStatus.CONNECTED ||
                mViewer.getConnectionStatus() == Viewer.ConnectionStatus.CONNECTING) {
            mDisconnectDlg = buildDisconnectAlertDialog();
            mDisconnectDlg.show();
        } else {
            cleanup();
        }
    }
    //endregion

    // region helper methods
    /**
     * Initialization
     */
    private void init() {
        // Get a reference to the input method service
        mInputMethodManager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);

        Intent intent = getIntent();

        final boolean useCloudConnectivity = intent.getBooleanExtra(USE_CLOUD_CONNECTIVITY, true);

        final String localCloudAddress = intent.getStringExtra(LOCAL_CLOUD_ADDRESS);
        final String localCloudPassword = intent.getStringExtra(LOCAL_CLOUD_PASSWORD);
        final String peerCloudAddress = intent.getStringExtra(PEER_CLOUD_ADDRESS);

        final String tcpAddonCode = intent.getStringExtra(DIRECT_TCP_ADDON_CODE);
        final String tcpAddress = intent.getStringExtra(DIRECT_TCP_ADDRESS);
        final int tcpPort = intent.getIntExtra(DIRECT_TCP_PORT, DirectTcp.DEFAULT_PORT);

        mProgressDialog = ProgressDialog.show(ConnectionActivity.this,
                "", getString(R.string.connecting_dlg), true);

        SdkThread.getInstance().init(getFilesDir().getAbsolutePath() + "dataStore", this);

        if (!SdkThread.getInstance().initComplete()) return;

        if (!useCloudConnectivity && !TextUtils.isEmpty(tcpAddonCode)) {
            SdkThread.getInstance().post(new Runnable() {
                @Override
                public void run() {
                    try {
                        Library.enableAddOn(tcpAddonCode);
                    } catch (Library.VncException e) {
                        displayMessage(R.string.failed_to_register_tcp_addon, e.getMessage());
                        return;
                    }
                }
            });
        }

        if (useCloudConnectivity) {
            if (0 == localCloudAddress.length() ||
                    0 == localCloudPassword.length() ||
                    0 == peerCloudAddress.length()) {
                displayMessage(R.string.failed_no_vnc_cloud_settings_specified, "");
                return;
            }
        } else if (TextUtils.isEmpty(tcpAddress)) {
            displayMessage(R.string.failed_no_tcp_address, "");
            return;
        }


        SdkThread.getInstance().post(new Runnable() {
            @Override
            public void run() {
                // Set up the various callbacks
                if (mCloudConnector != null) {
                    mCloudConnector.destroy();
                }
                if (mViewer != null) {
                    mViewer.destroy();
                }

                try {
                    mViewer = new Viewer();
                } catch (Library.VncException e) {
                    displayMessage(R.string.failed_to_create_viewer, e.getMessage());
                    return;
                }

                try {
                    /*
                    These callbacks will all be run on the SDK thread, so any UI updates must be
                    done through calls to {@link #runOnUiThread}.
                     */
                    mViewer.setConnectionCallback(new Viewer.ConnectionCallback() {
                        @Override
                        public void connecting(Viewer viewer) {
                        }

                        @Override
                        public void connected(Viewer viewer) {
                            runOnUiThread(new Runnable() {
                                @Override
                                public void run() {
                                    mProgressDialog.hide();
                                    mExtensionKeyboardView.setVisibility(View.VISIBLE);
                                }
                            });
                        }

                        @Override
                        public void disconnected(Viewer viewer,
                                                 final String reason,
                                                 final EnumSet<Viewer.DisconnectFlags> disconnectFlags) {

                            final String disconnectMsg = mViewer.getDisconnectMessage() == null ?
                                    mViewer.getDisconnectReason() :
                                    String.format("%s, %s", mViewer.getDisconnectReason(), mViewer.getDisconnectMessage());

                            runOnUiThread(new Runnable() {
                                @Override
                                public void run() {
                                    mProgressDialog.hide();
                                    String message = getString(R.string.disconnected) +
                                            disconnectMsg;
                                    if (mAuthDialog != null && mAuthDialog.isShowing()) {
                                        message = getString(R.string.disconnected_authenticating) +
                                                mViewer.getDisconnectReason();
                                    }
                                    mAlertDialog = buildAlertDialog(message);

                                    if (disconnectFlags.contains(Viewer.DisconnectFlags.ALERT_USER)) {
                                        mAlertDialog.show();
                                    } else {
                                        cleanup();
                                    }
                                }
                            });
                        }
                    });
                    mViewer.setFramebufferCallback(mFrameBufferView);

                    // Set the framebuffer to a sensible default. We will be notified of the actual
                    // size (via {@link FrameBufferView#serverFbSizeChanged} before rendering
                    // anything,
                    mFrameBufferView.serverFbSizeChanged(mViewer, 1024, 768);
                    mViewer.setAuthenticationCallback(ConnectionActivity.this);

                    if (useCloudConnectivity) {
                        mCloudConnector = new CloudConnector(localCloudAddress, localCloudPassword);
                        mCloudConnector.connect(peerCloudAddress, mViewer.getConnectionHandler());
                    } else {
                        mViewer.setPeerVerificationCallback(ConnectionActivity.this);
                        mDirectTcpConnector = new DirectTcpConnector();
                        mDirectTcpConnector.connect(tcpAddress, tcpPort, mViewer.getConnectionHandler());
                    }

                } catch (Library.VncException e) {
                    Log.e(TAG, "Connection error", e);
                    displayMessage(R.string.failed_to_make_vnc_cloud_connection, e.getMessage());
                }
            }
        });
    }

    private void dismissDialogs() {
        if (mProgressDialog != null && mProgressDialog.isShowing()) {
            mProgressDialog.dismiss();
        }
        if (mAuthDialog != null && mAuthDialog.isShowing()) {
            mAuthDialog.dismiss();
        }
        if (mDisconnectDlg != null && mDisconnectDlg.isShowing()) {
            mDisconnectDlg.dismiss();
        }
        if (mAlertDialog != null && mAlertDialog.isShowing()) {
            mAlertDialog.dismiss();
        }
        if (mPeerDialog != null && mPeerDialog.isShowing()) {
            mPeerDialog.dismiss();
        }
    }

    private void cleanup() {
        if (SdkThread.getInstance().initComplete()) {
            SdkThread.getInstance().post(new Runnable() {
                @Override
                public void run() {
                    if (mCloudConnector != null) {
                        mCloudConnector.destroy();
                        mCloudConnector = null;
                    }
                    if (mViewer != null) {
                        mViewer.destroy();
                        mViewer = null;
                    }
                }
            });
        }
        finish();
    }

    // endregion

    @Override
    public void onPointerEvent(int x, int y, EnumSet<Viewer.MouseButton> mouseButtons) {
        mTextViewWatcher.reset();
        mFrameBufferView.sendPointerEvent(mViewer, x, y, mouseButtons, false);
    }

    @Override
    public void onScaleChanged(float scale) {
        mFrameBufferView.setScaleFactor(scale);
    }

    @Override
    public void onScroll(float x, float y) {
        mFrameBufferView.setOffset(x, y);
    }

    @Override
    public void sendKeyEvents(Vector<TextViewWatcher.KeyEvent> keyEvents) {
        for (TextViewWatcher.KeyEvent keyEvent : keyEvents) {
            sendKeyEvent(keyEvent);
        }
    }

    @Override
    public void sendKeyEvent(final TextViewWatcher.KeyEvent keyEvent) {
        SdkThread.getInstance().post(new Runnable() {
            @Override
            public void run() {
                try {
                    if (keyEvent.down) {
                        mViewer.sendKeyDown(keyEvent.unicodeChar, (int) keyEvent.unicodeChar);
                    } else {
                        mViewer.sendKeyUp((int) keyEvent.unicodeChar);
                    }
                } catch (Library.VncException e) {
                    Log.w(TAG, "unable to send key event:", e);
                }
            }
        });
    }

    // region Authentication callbacks
    @Override
    public void requestUserCredentials(Viewer viewer, final boolean needUser, final boolean needPassword) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mAuthDialog = buildAuthDialog(needUser, needPassword);

                // Show the keyboard when the auth dialog appears.
                mAuthDialog.setOnShowListener(new DialogInterface.OnShowListener() {
                    @Override
                    public void onShow(DialogInterface dialog) {
                        View usernameView = mAuthDialog.findViewById(R.id.auth_username);
                        View passwordView = mAuthDialog.findViewById(R.id.auth_password);
                        View focusView = null;
                        if (usernameView.getVisibility() == View.VISIBLE) {
                            focusView = usernameView;
                        } else if (passwordView.getVisibility() == View.VISIBLE) {
                            focusView = passwordView;
                        }
                        InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);

                        if (imm != null) {
                            imm.showSoftInput(focusView, 0);
                        }
                    }
                });
                mAuthDialog.show();
            }
        });
    }

    @Override
    public void cancelUserCredentialsRequest(Viewer viewer) {
        displayMessage(R.string.authentication_check_cancelled, "");
    }

    // endregion

    // region Peer Verification callbacks
    @Override
    public void verifyPeer(Viewer viewer, final String hexFingerprint,
                           final String catchphraseFingerprint, ImmutableDataBuffer serverRsaPublic) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mPeerDialog = buildPeerVerificationDialog(hexFingerprint, catchphraseFingerprint);
                mPeerDialog.show();
            }
        });
    }

    private void sendPeerIdentityResponse(final boolean accept) {
        SdkThread.getInstance().post(new Runnable() {
            @Override
            public void run() {
                try {
                    mViewer.sendPeerVerificationResponse(accept);
                } catch (Library.VncException e) {
                    displayMessage(R.string.peer_verification_failed, e.getMessage());
                }
            }
        });
    }

    @Override
    public void cancelPeerVerification(Viewer viewer) {
        displayMessage(R.string.peer_verification_cancelled, "");
    }

    @Override
    public void displayMessage(final int msgId, final String message) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mAlertDialog = buildAlertDialog(getString(msgId) + message);
                mAlertDialog.show();
            }
        });
    }
}
