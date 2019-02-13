# Building and running the basic Viewer sample app for Mac

This sample Viewer app can connect to any sample Server app. Note to send 
Ctrl+Alt+Del to a sample Server app*, press Ctrl+Command+Delete.

*You cannot send Ctrl+Alt+Del to a Windows computer running the 
<vnc-sdk>/samples/basicServer because it doesn't have sufficient permissions 
to inject the sequence. Try <vnc-sdk>/samples/serviceServerWin instead.


## Requirements

* Xcode 7+
* Xcode developer tools (xcode-select --install)
* macOS 10.10+ SDK
* CMake 2.8.12.2+ (make sure this is on your path)


## Building the sample app

You can optionally hard-code connectivity information in 
basicViewerMac/AppDelegate.mm before compiling. This may be convenient if you 
are deploying to a single device. If you are deploying to multiple devices, 
instruct device users to provide this information at run-time instead. See the 
final section for more information.

To build, either generate an Xcode project, or makefiles:

### Generating an Xcode project

1) Navigate to the <vnc-sdk>/samples/basicViewerMac directory.
2) Run the following command (make sure to include the space and period): 
   cmake -G"Xcode" .
3) To compile the sample app, either:
   * Open the project in Xcode, change ALL_BUILD to BasicViewerMac, and build 
     and run in the normal way.
   * Run the following command, and check the /Debug directory for output: 
     xcodebuild

### Generating makefiles

1) Navigate to the <vnc-sdk>/samples/basicViewerMac directory.
2) Run the following command (make sure to include the space and period): 
   cmake .
3) Run the following command to compile the sample app: make


## Deploying the sample app to other devices

Deploy the entire BasicViewerMac.app directory to target devices.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or 
establish direct TCP connections to computers listening on known IP addresses 
and ports. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the Viewer 
Cloud address, Viewer Cloud password, and Server (peer) Cloud address to 
connect to in basicViewerMac/AppDelegate.mm before compiling.

To deploy to multiple devices, do not hard-code but instead instruct device 
users to provide this information at run-time in the following format:
 
Debug/BasicViewerMac.app/Contents/MacOS/BasicViewerMac 
  <Viewer-Cloud-addr> <Viewer-Cloud-pwd> <Server-Cloud-addr>
 
### Establishing direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in basicViewerMac/AppDelegate.mm and recompile. If the 
   sample app will run on a single device, optionally hard-code the IP address 
   and port of the computer to connect to as well.
3) If deploying to multiple devices, instruct device users to provide this 
   information at run-time instead:

   Debug/BasicViewerMac.app/Contents/MacOS/BasicViewerMac
     <Server-ip-address> <Server-tcp-port>
 

Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
