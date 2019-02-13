# Building and running the basic Server sample app for Windows

This single-shot sample Server app remotes the desktop of the currently 
logged-in user only. It cannot remote the login, lock, and User Account 
Control screens, nor inject Ctrl+Alt+Delete on Windows Vista+ computers. 
Screen capture does not persist between log and switch outs. For a 
persistent sample app demonstrating this behavior, see 
<vnc-sdk>\samples\serviceServerWin.


## Requirements

* Visual Studio 2010/2013/2015 (Express for Windows *Desktop* is supported;
  Express for *Windows* is NOT supported.)
* CMake 2.8.11+ (make sure this is on your path). Note Visual Studio 
  2015 requires CMake 3.1.0 or above. 


## Building the sample app

You can optionally hard-code connectivity information in basicServer.cxx 
before compiling. This may be convenient if you are deploying to a single 
device. If you are deploying to multiple devices, instruct device users 
to provide this information at run-time instead. See the final section 
for more information.

1) Open the Developer Command Prompt for VS<version> app. This is likely to
   be in a Visual Studio Tools folder.
2) Navigate to the <vnc-sdk>\samples\basicServer folder.
3) Run an appropriate CMake command to generate build files, for example:   

   cmake .                                  # To build 32-bit project files
   cmake -G"Visual Studio 12 2013" .        # To build 32-bit project files
                                              for a particular generator
   cmake -G"Visual Studio 12 2013 Win64" .  # To build 64-bit project files
                                              for a particular generator
   Alternatively, you can use the CMake GUI.
4) To compile the sample app, either:
   * Open the solution in Visual Studio, set basicServer as the startup
     project, and build and run in the normal way.
   * Run the following command, and check the current <configuration> folder
     (for example \Debug) for output: msbuild.exe basicServer.sln


## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the 
following files:

* basicServer.exe (sample app binary)
* vncagent.exe (handles screen capture and input injection)
* vncsdk.dll (SDK library)
* vncannotator.exe (if annotations are supported)

The sample app binary expects to find supporting files in the same directory 
or on your PATH.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or 
listen for direct TCP connections on a (known, static) IP address and 
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>\tools\vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the 
Cloud address and Cloud password in basicServer.cxx before compiling.

To deploy to multiple devices, do not hard-code but instead instruct device
users to provide this information at run-time in the following format:

<configuration>\basicServer.exe <Cloud-addr> <Cloud-pwd>

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in basicServer.cxx and recompile. If the sample app will 
   run on a single device, optionally hard-code a listening port as well 
   (the default for VNC is 5900).
3) If deploying to multiple devices, instruct device users to provide this 
   information at run-time instead:

   <configuration>\basicServer.exe <tcp-port>

Note the sample app will listen on all IPv4 and IPv6 addresses available to 
the device. To deter MITM attacks, inform Viewer app users of the device's 
unique, memorable catchphrase (printed to the console at run-time).

### Joining VNC Cloud *and* listening for direct TCP connections

With the exception of the direct TCP add-on code (which must always be 
hard-coded in basicServer.cxx), you can instruct device users to 
provide all the connectivity information required at the command line:

<configuration>\basicServer.exe <Cloud-addr> <Cloud-pwd> <tcp-port>
 

Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
