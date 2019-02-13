# Building and running the service Server sample app for Linux

This persistent sample Server app maintains screen capture between switch and 
log outs, meaning the lock, login and other elevated screens can be remoted. 
It must, however, be integrated as a system service. For a single-shot sample 
app that does not need to run as root, see the cross-platform 
<vnc-sdk>/samples/basicServer.


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

You can optionally hard-code connectivity information and a VNC (Server) 
password in serviceServerLinux.cxx before compiling. This may be convenient 
if you are deploying to a single device. If you are deploying to multiple 
devices, provide this information when you run the service instead. See the 
final section for more information.

1) Navigate to the <vnc-sdk>/samples/serviceServerLinux directory.
2) Run the following command to generate build files (make sure to 
   include the space and period): cmake .
3) Run the following command to compile the sample app: make


## Deploying the sample app to a secure location

Choose a location writable only by an Administrator, to prevent ordinary 
users running arbitrary code as the root user:  

1) Copy the sample app binary, vncagent (handles screen capture and input 
   injection) and vncannotator (if required) to a suitable /bin directory:

   sudo cp serviceServerLinux vncagent vncannotator /usr/local/bin/

2) Copy the SDK library to a suitable /lib directory:

   sudo cp -d ../../lib/linux-<arch>/libvncsdk.so.* /usr/local/lib/

3) Update the system library cache: sudo ldconfig


## Running the sample app as a system service

### Linux distributions using systemd

1) Open the file systemd/vncsdkServer.service:
   * If you deployed serviceServerLinux to a different /bin directory, edit 
     the 'ExecStart' option appropriately.
   * If you did not hard-code connectivity information and a VNC password in 
     serviceServerLinux.cxx before compiling, append the appropriate 
     information to 'ExecStart' as follows:
   
     ExecStart=/usr/local/bin/serviceServerLinux 
        -cloud <Cloud-addr> <Cloud-pwd> -tcp <tcp-port> <VNC-pwd> 

2) Copy the service configuration file to the appropriate location:

   mkdir -p /usr/lib/systemd/system   #if dir not already created
   sudo cp systemd/vncsdkServer.service /usr/lib/systemd/system
   sudo systemctl daemon-reload

3) Start the service: sudo systemctl start vncsdkServer

   Note: To start the service automatically on boot, run the command:
   sudo systemctl enable vncsdkServer

### Linux distributions using upstart

1) Open the file upstart/vncsdkServer.conf:
   * If you deployed serviceServerLinux to a different /bin directory, edit 
     the 'exec' stanza appropriately.
   * If you want to prevent the sample app starting automatically on boot, and 
     you are using upstart 0.6.7 or later (initctl version), add the stanza 
     'manual' on a separate line following the 'stop' stanza.     
   * If you did not hard-code connectivity information and a VNC password in 
     serviceServerLinux.cxx before compiling, append the appropriate 
     information to the 'exec' stanza as follows:
   
     exec /usr/local/bin/serviceServerLinux 
        -cloud <Cloud-addr> <Cloud-pwd> -tcp <tcp-port> <VNC-pwd>

2) Copy the service configuration file to the appropriate location:
   
   sudo cp upstart/vncsdkServer.conf /etc/init

3) Start the service: sudo service vncsdkServer start 
   (on some systems, this may be: sudo initctl start vncsdkServer)

   Note: To start the service automatically on boot, run the command:
   sudo update-rc.d vncsdkServer defaults

### Linux distributions using SysV-style init (for example, Raspbian 7.8)

1) Open the file sysv/vncsdkServer:
   * If you deployed serviceServerLinux to a different /bin directory, 
     edit the 'EXE=' line appropriately.
   * If you did not hard-code connectivity information and a VNC password in
     serviceServerLinux.cxx before compiling, add the appropriate information 
     to the 'OPTS=' line as follows:
   
     OPTS="-cloud <Cloud-addr> <Cloud-pwd> -tcp <tcp-port> <VNC-pwd>"

2) Copy the service configuration file to the appropriate location:
   
   sudo cp sysv/vncsdkServer /etc/init.d

3) Start the service: sudo service vncsdkServer start 
   (on some systems, this may be: sudo /etc/init.d/vncsdkServer start)

   Note: To start the service automatically on boot, run the command:
   sudo update-rc.d vncsdkServer defaults
   Note: An X server must be running in order to capture the screen. On a Pi, 
   use raspi-config to Boot to Desktop so the sample app can survive a log out.


## Providing connectivity information

You can either join VNC Cloud and let it manage connectivity for you, or 
listen for direct TCP connections on a (known, static) IP address and 
(dedicated, open) port. Or enable the sample app to do both.

### Joining VNC Cloud

You must provide a separate Cloud address for each device you deploy the 
sample app to. Use <vnc-sdk>/tools/vnccloudaddresstool to freely obtain 
Cloud addresses in conjunction with your sandbox API key, or call the 
VNC Cloud API directly.

If the sample app will run on a single device, optionally hard-code the 
Cloud address and Cloud password in serviceServerLinux.cxx before compiling.

To deploy to multiple devices, do not hard-code but instead add this
information to the appropriate service configuration file.

### Listening for direct TCP connections

1) Sign in to your RealVNC account and follow the instructions on the 
   Add-on codes page to obtain a trial direct TCP add-on code.
2) Apply the code in serviceServerLinux.cxx and recompile. If the sample 
   app will run on a single device, optionally hard-code a listening port as 
   well (the default for VNC is 5900).
3) If deploying to multiple devices, do not hard code but instead add this 
   information to the appropriate service configuration file.

Note the sample app will listen on all IPv4 and IPv6 addresses available to the 
device. To deter MITM attacks, inform sample Viewer app users of the device's 
unique, memorable catchphrase; examine syslog to find out what this is: 
cat /var/log/syslog | grep catchphrase

### Joining VNC Cloud *and* listening for direct TCP connections

You can add all the connectivity information required (Cloud address 
and Cloud password, listening port, and VNC password) to the appropriate 
service configuration file. The exception is the direct TCP add-on code, 
which must always be hard-coded in serviceServerLinux.cxx.


## SELinux

To run the sample app, SELinux must either be temporarily disabled 
(sudo setenforce 0) or suitable policy module(s) put in place.

For example, to create and use a semodule for the vncannotator binary:

  ausearch -c 'vncannotator' --raw | audit2allow -M my-vncannotator
  semodule -i my-vncannotator.pp

(These commands assume you have already run the sample app and vncannotator 
has been blocked by SELinux, raising an audit event in the logs.)


## Logging

The sample app logs to /var/log/syslog by default.


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
