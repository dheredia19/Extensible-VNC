# Building and running the basic Viewer sample app for iOS

This sample Viewer app can connect to any sample Server app. Note to send 
Ctrl+Alt+Del to a sample Server app*, press the app toolbar button.

*You cannot send Ctrl+Alt+Del to a Windows computer running 
<vnc-sdk>/samples/basicServer because it doesn't have sufficient permissions 
to inject the sequence. Try <vnc-sdk>/samples/serviceServerWin instead.


## Requirements

* Xcode 7+
* Xcode developer tools (xcode-select --install)
* iOS 9+ SDK


## Providing connectivity information

You can either join VNC Cloud and let it manage connectivity for you, or 
establish direct TCP connections to computers listening on known IP addresses 
and ports. Or enable the sample app to do both.

### Joining VNC Cloud

1) Obtain a separate Cloud address for each device you deploy the sample app to. 
   Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain Cloud addresses in 
   conjunction with your sandbox API key, or call the VNC Cloud API directly.
2) Hard-code the Cloud address, the associated Cloud password, and the (peer) 
   Cloud address of the computer to connect to in BasicVieweriOS/AppDelegate.m.

### Establishing direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in BasicVieweriOS/AppDelegate.m.
3) Set #define USE_CLOUD_CONNECTIVITY to false.
4) Optionally hard-code the IP address and port of the computer to connect to 
   as well. Alternatively, instruct device users to provide this information 
   at run-time.


## Building and running the sample app

1) In Xcode, open <vnc-sdk>/samples/basicVieweriOS/basicVieweriOS.xcodeproj 
   in the normal way.
2) Choose the target (either a connected iOS device or the Simulator)
   and build and run in the normal way.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
