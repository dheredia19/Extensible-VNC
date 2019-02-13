# Building and running the basic Viewer sample app for Linux

This sample Viewer app can connect to any sample Server app. Note to send 
Ctrl+Alt+Del to a sample Server app*, first disable the local shortcut action.

*You cannot send Ctrl+Alt+Del to a Windows computer running the 
<vnc-sdk>/samples/basicServer because it doesn't have sufficient permissions 
to inject the sequence. Try <vnc-sdk>/samples/serviceServerWin instead. 


## Requirements

* CMake 2.8.4+
* X11 libraries (libX11, libXext, libXtst, libxcb, libXau, libXdmcp)
* Desktop computer:
  * gcc 4.8.2+ (already installed on Ubuntu)
  * g++ 4.8.2+
* Raspberry Pi:
  * gcc 4.6.3+ (already installed on Raspbian 7.8)
  * g++ 4.6.3+ (already installed on Raspbian 7.8)

Example installation commands (run as administrator):

* Ubuntu: apt-get install cmake g++ libx11-dev build-essential
* CentOS: yum install cmake gcc gcc-c++ libX11-devel
* Raspberry Pi: apt-get install cmake libx11-dev


## Building the sample app

You can optionally hard-code connectivity information in main.cxx before 
compiling. This may be convenient if you are deploying to a single device. If 
you are deploying to multiple devices, instruct device users to provide this 
information at run-time instead. See the final section for more information.

1) Navigate to the <vnc-sdk>/samples/basicViewerX11 directory.
2) Run the following command to generate build files (make sure to 
   include the space and period): cmake .
3) Run the following command to compile the sample app: make


## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the 
following files:

* basicViewerX11 (sample app binary)
* <vnc-sdk>/lib/<linux-plat>/libvncsdk.so.<version> (SDK library)

Locate the SDK library in an appropriate directory (such as /usr/local/lib) 
and run a suitable command to update the system, for example: sudo ldconfig


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
connect to in main.cxx before compiling.

To deploy to multiple devices, do not hard-code but instead instruct device 
users to provide this information at run-time in the following format:

./basicViewerX11 <Viewer-Cloud-addr>  <Viewer-Cloud-pwd>  <Server-Cloud-addr>

### Establishing direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in main.cxx and recompile. If the sample app will run on a 
   single device, optionally hard-code the IP address and port of the 
   computer to connect to as well.
3) If deploying to multiple devices, instruct device users to provide this 
   information at run-time instead:

   ./basicViewerX11 <Server-ip-address> <Server-tcp-port>


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
