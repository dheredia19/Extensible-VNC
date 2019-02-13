# Building and running the basic Viewer sample app for HTML 5

This sample Viewer app can run in any *desktop* web browser and connect to any
sample Server app. Note, to send Ctrl+Alt+Del to a sample Server app*, press
the button on the web page.

* You cannot send Ctrl+Alt+Del to a Windows computer running the
<vnc-sdk>/samples/basicServer because it doesn't have sufficient permissions
to inject the sequence. Try <vnc-sdk>/samples/serviceServerWin instead.


## Requirements

* A desktop with a supported web browser (mobile browsers are not supported)
* A web server (if you want to access the sample app from elsewhere)
* Python 2.7.x (if you want to run the Python HTTP web server)


## Providing Cloud addresses and running the sample app

You must provide a separate Cloud address for each device you deploy the
sample app to, and hard-code:

* this Cloud address
* the associated Cloud password
* the Cloud address of the device (peer) to connect to

...in viewer.js before compiling. Use <vnc-sdk>/tools/vnccloudaddresstool to 
freely obtain Cloud addresses in conjunction with your sandbox API key, or 
call the VNC Cloud API directly.

To access the sample app from the current desktop only:

1) Navigate to the <vnc-sdk>/samples/basicViewerHTML5 directory.
2) Double-click viewer.html.

Note: For IE 11/MS Edge, you may need to first right-click each of viewer.html, 
vncsdk.js, viewer.css and viewer.js and select Properties > General > Unblock.
For Chrome browser versions from 65 onwards, serving the viewer from the
desktop may be blocked - follow the instructions below for SimpleHTTPServer to
serve to a local Chrome browser.

To enable others to access the sample app over the web:

1) Navigate to the <vnc-sdk>/samples/basicViewerHTML5 directory.
2) Copy the VNC SDK library to this directory, for example under Linux:
   cp ../../lib/html5/vncsdk.js .
2) If your users will use:
   * Firefox, IE, Edge or Safari, start an HTTP web server (for example, the
     Python HTTP web server: python -m SimpleHTTPServer) and instruct them to 
     navigate to http://<your-ip-address>:8000/viewer.html.
   * Chrome, start an HTTPS web server and instruct users to navigate to
     https://<your-ip-address>:8000/viewer.html.
     
Note: For IE 11, you may need to configure browser settings as follows if 
users in the local domain report an 'Access is denied' error:
* Enable Tools > Internet options > Security > Local intranet > Custom level >
  Miscellaneous > Access data sources across domains
* Add vnc.com and the local web server address using Tools > Internet options >
  Security > Local intranet > Sites > Advanced > Add


Copyright (C) 2016-2018 RealVNC Limited. All rights reserved.
