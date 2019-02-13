# Building and running the basic Viewer sample app for Windows

This sample Viewer app can connect to any sample Server app. Note to send 
Ctrl+Alt+Del to a sample Server app*, press Shift+Ctrl+Alt+Del.

*You cannot send Ctrl+Alt+Del to a Windows computer running the 
<vnc-sdk>\samples\basicServer because it doesn't have sufficient permissions 
to inject the sequence. Try <vnc-sdk>\samples\serviceServerWin instead. 


## Requirements

* Visual Studio 2010/2013/2015 (Express for Windows *Desktop* is supported;
  Express for *Windows* is NOT supported.)
* CMake 2.8.11+ (make sure this is on your path). Note Visual Studio 
  2015 requires CMake 3.1.0 or above.


## Building the sample app

You can optionally hard-code connectivity information in main.cxx before 
compiling. This may be convenient if you are deploying to a single device. If 
you are deploying to multiple devices, instruct device users to provide this 
information at run-time instead. See the final section for more information.

1) Open the Developer Command Prompt for VS<version> app. This is likely to
   be in a Visual Studio Tools folder.
2) Navigate to the <vnc-sdk>\samples\basicViewerWin folder.
3) Run an appropriate CMake command to generate build files, for example:

   cmake .                                  # To build 32-bit project files
   cmake -G"Visual Studio 12 2013" .        # To build 32-bit project files
                                              for a particular generator
   cmake -G"Visual Studio 12 2013 Win64" .  # To build 64-bit project files
                                              for a particular generator
   Alternatively, you can use the CMake GUI.
4) To compile the sample app, either:
   * Open the solution in Visual Studio, set basicViewerWin as the startup
     project, and build and run in the normal way.
   * Run the following command, and check the current <configuration> folder
     (for example \Debug) for build output: msbuild.exe basicViewerWin.sln


## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the 
following files:

* basicViewerWin.exe (sample app binary)
* vncsdk.dll (SDK library)

The sample app binary expects to find the SDK library in the same directory
or on your PATH.


## Providing connectivity information and running the sample app

You can either join VNC Cloud and let it manage connectivity for you, or 
establish direct TCP connections to computers listening on known IP addresses 
and ports. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the
sample app to. Use <vnc-sdk>\tools\vnccloudaddresstool to freely obtain
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the Viewer 
Cloud address, Viewer Cloud password, and Server (peer) Cloud address to 
connect to in main.cxx before compiling.

To deploy to multiple devices, do not hard-code but instead instruct device 
users to provide this information at run-time in the following format:

<configuration>\basicViewerWin.exe
  <Viewer-Cloud-addr> <Viewer-Cloud-pwd> <Server-Cloud-addr>

### Establishing direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in main.cxx and recompile. If the sample app will run on a 
   single device, optionally hard-code the IP address and port of the 
   computer to connect to as well.
3) If deploying to multiple devices, instruct device users to provide this 
   information at run-time instead:

   <configuration>\basicViewerWin.exe <Server-ip-address> <Server-tcp-port>


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
