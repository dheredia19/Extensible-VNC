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
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.AppCompatActivity;
import android.text.TextUtils;
import android.util.Log;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;

import com.realvnc.vncsdk.Library;
import com.realvnc.vncsdk.DirectTcp;

/**
 * The activity loaded on app initialization. This just provides a single button to start a
 * connection to the provided cloud address.
 */
public class MainActivity extends AppCompatActivity {

    /**
     * For Cloud connections, hard-code the Cloud address for the Viewer. Example address:
     * LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
     */
    private static final String LOCAL_CLOUD_ADDRESS = "";

    /**
     * Hard-code the Cloud password associated with this Cloud address. Example password:
     * KMDgGgELSvAdvscgGfk2
     */
    private static final String LOCAL_CLOUD_PASSWORD = "";

    /**
     * Hard-code the Cloud address of the Server (peer) to connect to. Example address:
     * LxyDgGgrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRydf9ZczNo13BcD
     */
    private static final String PEER_CLOUD_ADDRESS = "";


    /*
     * Specify if to use cloud or direct TCP connectivity - this will default to using
     * cloud connectivity.
     */
    private boolean USE_CLOUD_CONNECTIVITY = true;

    /* To enable direct TCP connectivity you need to copy the content of your
    add-on code (available from your RealVNC account) into the string below. */
    private static final String DIRECT_TCP_ADDON_CODE = "";

    /*
     * For direct TCP connection you must provide the server's TCP host address
     * and port number. Either edit the macros below OR provide these connection
     * details via an alert view which will pop up when you click start.
     * The default direct TCP port number can be specified below by using
     * DirectTcp.DEFAULT_PORT.
     *
     * Ignore these strings if you are not using the Direct TCP add-on */
    private static final String TCP_ADDRESS = "";
    private static final int TCP_PORT = DirectTcp.DEFAULT_PORT;

    private static final String TAG = "MainActivity";

    /**
     * Used to display a dialog requesting where the viewer wants to connect to.
     * @note Using this functionality requires the Direct TCP Add-on.
     */
    private AlertDialog mConnectionDialog;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        Log.d(TAG, "onCreate");

        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);

        Button btn = (Button) findViewById(R.id.button);
        btn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                connect();
            }
        });
    }

    /**
     * This method initialises an Intent with the local cloud address and password and the remote
     * cloud address, before launching the {@link ConnectionActivity} with that information.
     */
    private void connect() {
        if (USE_CLOUD_CONNECTIVITY) {
            // Using cloud connectivity:
            Intent intent = new Intent(this, ConnectionActivity.class);
            intent.putExtra(ConnectionActivity.LOCAL_CLOUD_ADDRESS, LOCAL_CLOUD_ADDRESS);
            intent.putExtra(ConnectionActivity.LOCAL_CLOUD_PASSWORD, LOCAL_CLOUD_PASSWORD);
            intent.putExtra(ConnectionActivity.PEER_CLOUD_ADDRESS, PEER_CLOUD_ADDRESS);
            intent.putExtra(ConnectionActivity.USE_CLOUD_CONNECTIVITY, USE_CLOUD_CONNECTIVITY);

            startActivity(intent);
        } else if (!TextUtils.isEmpty(DIRECT_TCP_ADDON_CODE)) {
            // Using Direct TCP Connectivity:
            if (TCP_ADDRESS.length() > 0) {
                connectViaTcp(TCP_ADDRESS, TCP_PORT);
            } else {
                mConnectionDialog = buildConnectionDialog();

                // Show the keyboard when the connection dialog appears.
                mConnectionDialog.setOnShowListener(new DialogInterface.OnShowListener() {
                    @Override
                    public void onShow(DialogInterface dialog) {
                        EditText address = (EditText) mConnectionDialog.findViewById(R.id.connection_address);
                        InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);

                        if (imm != null) {
                            imm.showSoftInput(address, 0);
                        }
                    }
                });
                mConnectionDialog.show();
            }
        } else {
            AlertDialog.Builder builder = new AlertDialog.Builder(this);

            builder.setMessage(R.string.failed_no_tcp_addon_code)
                    .setPositiveButton(R.string.ok, null)
                    .setCancelable(false)
                    .create()
                    .show();
        }
    }

    private void connectViaTcp(String address, int port) {
        Intent intent = new Intent(this, ConnectionActivity.class);
        int tcpPort = port > 0 ? port : TCP_PORT;
        intent.putExtra(ConnectionActivity.USE_CLOUD_CONNECTIVITY, USE_CLOUD_CONNECTIVITY);
        intent.putExtra(ConnectionActivity.DIRECT_TCP_ADDON_CODE, DIRECT_TCP_ADDON_CODE);
        intent.putExtra(ConnectionActivity.DIRECT_TCP_ADDRESS, address);
        intent.putExtra(ConnectionActivity.DIRECT_TCP_PORT, tcpPort);

        startActivity(intent);
    }

    /**
     * Build the direct TCP connection dialog.
     */
    private AlertDialog buildConnectionDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        final View connectionDialogView = getLayoutInflater().inflate(R.layout.connection_dialog, null);

        return builder.setView(connectionDialogView)
                .setNegativeButton(R.string.cancel, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        dismissDialogs();
                    }
                })
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        final String address = ((EditText) connectionDialogView.findViewById(R.id.connection_address)).getText()
                                .toString();
                        String portString = ((EditText) connectionDialogView.findViewById(R.id.connection_port)).getText().toString();
                        int port = 0;
                        if (!TextUtils.isEmpty(portString)) {
                            port = Integer.parseInt(portString);
                        }

                        dismissDialogs();
                        connectViaTcp(address, port);
                    }
                })
                .setCancelable(false)
                .create();
    }

    private void dismissDialogs() {
        if (mConnectionDialog != null && mConnectionDialog.isShowing()) {
            mConnectionDialog.dismiss();
        }
    }
}
