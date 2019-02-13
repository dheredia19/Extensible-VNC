# Building and running the basic Viewer sample app for Android

This sample Viewer app can connect to any sample Server app. Note to send 
Ctrl+Alt+Del to a sample Server app*, press the toolbar button in the app.

*You cannot send Ctrl+Alt+Del to a Windows computer running the 
<vnc-sdk>/samples/basicServer because it doesn't have sufficient permissions 
to inject the sequence. Try <vnc-sdk>/samples/serviceServerWin instead.


## Requirements

* Android Studio (recommended)
* Android SDK (you can typically bootstrap this from within Android Studio)
* JDK 6+, or JDK 7+ to target Android API level 21 (Lollipop) devices.


## Providing connectivity information

You can either join VNC Cloud and let it manage connectivity for you, or 
establish direct TCP connections to computers listening on known IP addresses 
and ports. Or enable the sample app to do both.

### Joining VNC Cloud

1) Obtain a separate Cloud address for each device you deploy the sample app to. 
   Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain Cloud addresses in 
   conjunction with your sandbox API key, or call the VNC Cloud API directly.
2) Hard-code the Cloud address, the associated Cloud password, and the (peer) 
   Cloud address of the computer to connect to in MainActivity.java.

### Establishing direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in MainActivity.java.
3) Set the USE_CLOUD_CONNECTIVITY boolean to false.
4) Optionally hard-code the IP address and port of the computer to connect to
   as well. Alternatively, instruct device users to provide this information
   at run-time.


## Building and running the sample app

1) In Android Studio, choose to "Import project (Eclipse ADT, Gradle, etc.)", 
   and select the <vnc-sdk>/samples/basicViewerAndroid directory (do not 
   choose to open an existing Android Studio project).
2) Choose the target (either a connected Android device or an emulator) 
   and run in the normal way.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
