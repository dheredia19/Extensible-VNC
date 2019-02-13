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

package com.realvnc.vncsdk.sample.basicServerAndroid;

import android.annotation.SuppressLint;
import android.app.Notification;
import android.app.PendingIntent;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.ComponentName;
import android.net.Uri;
import android.os.Bundle;
import android.os.IBinder;
import android.provider.Settings;
import android.support.v7.app.AppCompatActivity;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.media.projection.MediaProjectionManager;

/**
 * The activity loaded on app initialization. This allows the service to be
 * started and stopped, and displays the current status and password.
 */
public class MainActivity extends AppCompatActivity {

    // For Cloud connections, hard-code the Cloud address for the Server, for example:
    // LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
    private static final String LOCAL_CLOUD_ADDRESS = "";

    // Hard-code the Cloud password associated with this Cloud address, for example:
    // KMDgGgELSvAdvscgGfk2
    private static final String LOCAL_CLOUD_PASSWORD = "";

    // For direct TCP connections you must provide a TCP listening port number here.
    // In addition, you must also specify your add-on code in SdkService.java.
    // The default direct TCP port number can be specified below by importing
    // com.realvnc.vncsdk.DirectTcp and using DirectTcp.DEFAULT_PORT.
    private static final int LOCAL_PORT_NUMBER = -1;

    private static final String TAG = "MainActivity";

    private static final int MEDIA_PROJECTION_REQUEST_ID = 1;
    private static final int OVERLAY_REQUEST_ID = 2;
    private static final int NUM_PERMISSION_REQUESTS = 2;

    private int mPermissionRequestsComplete;
    private boolean mRequiredPermissionDenied;
    private Intent mServiceIntent;
    private SdkService mService;
    private TextView mStatusText;
    private Button mStartBtn;
    private Button mStopBtn;
    
    private final ServiceConnection mServiceConn = new ServiceConnection() {
        public void onServiceConnected(ComponentName className,
                                       IBinder service) {
            SdkService.LocalBinder binder = (SdkService.LocalBinder)service;
            mService = binder.getService();
            updateStatus(true);
        }
        public void onServiceDisconnected(ComponentName className) {
            mService = null;
            updateStatus(false);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        Log.d(TAG, "onCreate");

        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);

        mServiceIntent = new Intent(this, SdkService.class);
        mServiceIntent.putExtra(SdkService.LOCAL_CLOUD_ADDRESS, LOCAL_CLOUD_ADDRESS);
        mServiceIntent.putExtra(SdkService.LOCAL_CLOUD_PASSWORD, LOCAL_CLOUD_PASSWORD);
        mServiceIntent.putExtra(SdkService.LOCAL_PORT_NUMBER, LOCAL_PORT_NUMBER);

        // Create a notification for the service to use
        Intent thisIntent = new Intent(this, MainActivity.class);
        Notification notification = new Notification.Builder(this)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.running))
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .setContentIntent(PendingIntent.getActivity(this, 0, thisIntent, 0))
            .build();
        mServiceIntent.putExtra(SdkService.SERVICE_NOTIFICATION, notification);
        
        mStartBtn = (Button) findViewById(R.id.start);
        mStartBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startSdkService();
            }
        });

        mStopBtn = (Button) findViewById(R.id.stop);
        mStopBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                stopSdkService();
            }
        });

        mStatusText = (TextView) findViewById(R.id.status);

        bindService(mServiceIntent, mServiceConn, 0);
        updateStatus(mService != null);
    }

    @Override
    protected void onDestroy() {
        Log.d(TAG, "onDestroy");
        unbindService(mServiceConn);
        super.onDestroy();
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        Log.d(TAG, "onActivityResult");

        boolean granted = false;
        String permissionName = "unknown";
        switch (requestCode) {
            case MEDIA_PROJECTION_REQUEST_ID:
                permissionName = "media projection";
                granted = (resultCode == RESULT_OK);
                if (!granted) {
                    mRequiredPermissionDenied = true;
                }
                break;
            case OVERLAY_REQUEST_ID:
                permissionName = "overlay";
                // The approval status is not indicated by resultCode in this case.
                // Even if granted, the user may revoke the permission at any time.
                granted = canDrawOverlays();
                break;
        }
        String status = granted ? "granted" : "denied";
        Log.d(TAG, String.format("Permission %s: %s", status, permissionName));

        mPermissionRequestsComplete++;
        if (mPermissionRequestsComplete < NUM_PERMISSION_REQUESTS) {
            return;
        }

        if (mRequiredPermissionDenied) {
            Log.i(TAG, "Required permission denied");
        } else {
            Log.i(TAG, "All required permissions granted");
            mServiceIntent.putExtra(SdkService.MEDIA_PROJECTION_DATA, data);
            startService(mServiceIntent);
            bindService(mServiceIntent, mServiceConn, 0);
            updateStatus(mService != null);
        }
    }

    @SuppressLint("NewApi")
    private boolean canDrawOverlays() {
        try {
            return Settings.canDrawOverlays(this);
        } catch (NoSuchMethodError e) {
            // Older device. In-app permission checks are not supported.
            return true;
        }
    }

    private void startSdkService() {
        Log.d(TAG, "startSdkService");

        // Request elevated permissions
        mPermissionRequestsComplete = 0;
        mRequiredPermissionDenied = false;

        MediaProjectionManager mpm =
                (MediaProjectionManager)getSystemService(MEDIA_PROJECTION_SERVICE);
        startActivityForResult(mpm.createScreenCaptureIntent(), MEDIA_PROJECTION_REQUEST_ID);

        @SuppressLint("InlinedApi") Intent intent = new Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName())
        );
        try {
            startActivityForResult(intent, OVERLAY_REQUEST_ID);
        } catch (ActivityNotFoundException e) {
            Log.d(TAG, "No activity found to grant permission: overlay");
            // Probably an older device. Assume it's not needed.
            // We will still get an onActivityResult callback.
        }
    }

    private void stopSdkService() {
        Log.d(TAG, "stopSdkService");
        stopService(mServiceIntent);
    }

    private void updateStatus(boolean running) {
        mStartBtn.setEnabled(!running);
        mStopBtn.setEnabled(running);
        if (running) {
            String text = getString(R.string.running) + "\n\n" +
                getString(R.string.password) + " " + mService.getPassword();
            mStatusText.setText(text);
            
        } else {
            mStatusText.setText(R.string.not_running);
        }
    }
}
