# Building and running the view-only basic Server sample app for Android

This sample Server app runs as a service and can remote any screen the 
device can display. However, it cannot inject input events, so 
Viewer app users can remotely observe but not control Android devices.


## Requirements

* Android Studio (recommended)
* Android SDK (you can typically bootstrap this from within Android Studio)
* JDK 7


## Providing connectivity information

You can either join VNC Cloud and let it manage connectivity for you, or 
listen for direct TCP connections on a (known, static) IP address and 
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

1) Obtain a separate Cloud address for each device you deploy the sample app to. 
   Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain Cloud addresses in 
   conjunction with your sandbox API key, or call the VNC Cloud API directly.
2) Hard-code the Cloud address and associated Cloud password in
   MainActivity.java.

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in SdkService.java.
3) Specify a port to listen on in MainActivity.java.

Note the sample app will listen on all IPv4 and IPv6 addresses available to
the device (check the device's Advanced Wi-Fi settings). To deter MITM
attacks, inform sample Viewer app users of the device's unique, memorable
catchphrase; to find this out, run the following command from a connected
computer: adb logcat | grep catchphrase


## Building and running the sample app

1) In Android Studio, choose to "Import project (Eclipse ADT, Gradle, etc.)", 
   and select the <vnc-sdk>/samples/basicServerAndroid directory. (Do not 
   choose to open an existing Android Studio project.)
2) Choose a device target and run in the normal way. Note if this is the
   emulator, first turn off Use Host GPU in the Android Virtual Device
   settings.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
