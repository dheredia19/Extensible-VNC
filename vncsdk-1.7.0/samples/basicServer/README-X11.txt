# Building and running the basic Server sample app for Linux

This single-shot sample Server app remotes the desktop of the currently 
logged-in user only. It cannot remote the login, lock, or any other elevated 
screen. Screen capture does not persist between log and switch outs. For a 
persistent sample app demonstrating this behavior, see 
<vnc-sdk>/samples/serviceServerLinux.


## Requirements

* CMake 2.8.4+
* Desktop computer:
  * gcc 4.8.2+ (already installed on Ubuntu)
  * g++ 4.8.2+ 
* Raspberry Pi:
  * gcc 4.6.3+ (already installed on Raspbian 7.8)
  * g++ 4.6.3+ (already installed on Raspbian 7.8)

Example installation commands (run as administrator):

* Ubuntu: apt-get install cmake g++ build-essential
* CentOS: yum install cmake gcc gcc-c++
* Raspberry Pi: apt-get install cmake 


## Building the sample app

You can optionally hard-code connectivity information in basicServer.cxx 
before compiling. This may be convenient if you are deploying to a single 
device. If you are deploying to multiple devices, instruct device users 
to provide this information at run-time instead. See the final section 
for more information.

1) Navigate to the <vnc-sdk>/samples/basicServer directory.
2) Run the following command to generate build files (make sure to 
   include the space and period): cmake .
3) Run the following command to compile the sample app: make


## Deploying the sample app to other devices

If you want to run this sample app on multiple devices, deploy the 
following files:

* basicServer (sample app binary)
* vncagent (handles screen capture and input injection)
* <vnc-sdk>/lib/<linux-plat>/libvncsdk.so.<version> (SDK library)
* <vnc-sdk>/lib/<linux-plat>/vncannotator (if annotations are supported)

The sample app binary expects to find vncagent in the same directory. You 
should locate the SDK library in an appropriate directory (such as 
/usr/local/lib) and run a suitable command to update the system library cache, 
for example: sudo ldconfig


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

./basicServer <Cloud-addr> <Cloud-pwd>

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in basicServer.cxx and recompile. If the sample app will 
   run on a single device, optionally hard-code a listening port as well 
   (the default for VNC is 5900).
3) If deploying to multiple devices, instruct device users to provide this 
   information at run-time instead:

   ./basicServer <tcp-port>

Note the sample app will listen on all IPv4 and IPv6 addresses available to 
the device. To deter MITM attacks, inform Viewer app users of the device's 
unique, memorable catchphrase (printed to the console at run-time).

### Joining VNC Cloud *and* listening for direct TCP connections

With the exception of the direct TCP add-on code (which must always be 
hard-coded in basicServer.cxx), you can instruct device users to 
provide all the connectivity information required at the command line:

./basicServer <Cloud-addr> <Cloud-pwd> <tcp-port>


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
