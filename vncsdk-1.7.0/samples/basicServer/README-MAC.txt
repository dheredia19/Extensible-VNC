# Building and running the basic Server sample app for Mac

This single-shot sample Server app remotes the desktop of the currently 
logged-in user only. It cannot remote the login, lock, or any other elevated 
screen. Screen capture does not persist between log and switch outs. For a 
persistent sample app demonstrating this behavior, see 
<vnc-sdk>/samples/serviceServerMac.


## Requirements

* Xcode 7+
* Xcode developer tools (xcode-select --install)
* macOS 10.10+ SDK
* CMake 2.8.12.2+ (make sure this is on your path)


## Building the sample app

You can optionally hard-code connectivity information in basicServer.cxx 
before compiling. This may be convenient if you are deploying to a single 
device. If you are deploying to multiple devices, instruct device users 
to provide this information at run-time instead. See the final section 
for more information.

To build, either generate an Xcode project, or makefiles:

### Generating an Xcode project

1) Navigate to the <vnc-sdk>/samples/basicServer directory.
2) Run the following command (make sure to include the space and period): 
   cmake -G"Xcode" .
3) To compile the sample app, either:
   * Open the project in Xcode, change ALL_BUILD to basicServer, and build 
     and run in the normal way.
   * Run the following command: xcodebuild
4) Examine build output in the appropriate folder, for example Debug.

### Generating makefiles 

1) Navigate to the <vnc-sdk>/samples/basicServer directory.
2) Run the following command (make sure to include the space and period): 
   cmake .
3) Run the following command to compile the sample app: make


## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the 
following files:

* basicServer (sample app binary)
* vncagent (handles screen capture and input injection)
* <vnc-sdk>/lib/mac64/libvncsdk.<version>.dylib (SDK library)
* <vnc-sdk>/lib/mac64/vncannotator (if annotations are supported)

The sample app binary expects to find supporting files in the same directory.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or 
listen for direct TCP connections on a (known, static) IP address and 
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the 
Cloud address and Cloud password in basicServer.cxx before compiling.

To deploy to multiple devices, do not hard-code but instead instruct device
users to provide this information at run-time in the following format:

./Debug/basicServer <Cloud-addr> <Cloud-pwd>

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in basicServer.cxx and recompile. If the sample app will 
   run on a single device, optionally hard-code a listening port as well 
   (the default for VNC is 5900).
3) If deploying to multiple devices, instruct device users to provide this 
   information at run-time instead:

   ./Debug/basicServer <tcp-port>

Note the sample app will listen on all IPv4 and IPv6 addresses available to 
the device. To deter MITM attacks, inform Viewer app users of the device's 
unique, memorable catchphrase (printed to the console at run-time).

### Joining VNC Cloud *and* listening for direct TCP connections

With the exception of the direct TCP add-on code (which must always be 
hard-coded in basicServer.cxx), you can instruct device users to 
provide all the connectivity information required at the command line:

./Debug/basicServer <Cloud-addr> <Cloud-pwd> <tcp-port> 


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
