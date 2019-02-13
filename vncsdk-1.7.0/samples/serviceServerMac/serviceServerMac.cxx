/*
Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software without
specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/


#include <CoreFoundation/CoreFoundation.h>
#include <iostream>
#include <sstream>
#include <assert.h>
#include <string.h>
#include <stdlib.h>
#include <syslog.h>
#include <sys/stat.h>
#include <unistd.h>

#include <vnc/Vnc.h>
#include "SignalHandler.h"


/*
 * serviceServerMac sample
 *
 * This sample demonstrates how to implement a VNC server as a Mac OS daemon.
 * The code itself is very simple, and similar to the basicServer sample,
 * the main differences being that it uses vnc_Server_createService to create
 * the server, and the server password is no longer automatically generated,
 * but specified on the command line (ideally this would be stored in a more
 * secure manner).
 *
 * The daemon requires an instance of vncagent.app to be running in each
 * graphical session.  See the README.txt for details of how to ensure this.
 */

/* You can specify the server password here, which is used instead of
   specifying it on the command line or in the com.realvnc.serviceServerMac.plist
   file: */
const char* serverPassword = 0;

/* For Cloud connections, either hard-code the Cloud address for the Server OR
 * specify it at the command line. Example Cloud address:
 * LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm
 */
const char* cloudAddress = 0;

/* Either hard-code the Cloud password associated with this Cloud address OR
 * specify it at the command line. Example Cloud password: KMDgGgELSvAdvscgGfk2
 */
const char* cloudPassword = 0;

/* To enable direct TCP connectivity you need to copy the content of your
   add-on code (available from your RealVNC account) into the string below. */
static const char* directTcpAddOnCode = "";

/* For direct TCP connections you must provide a TCP listening port number.
   Either specify the port number below OR provide the port number via the command
   line or in the com.realvnc.serviceServerMac.plist file.
   The default direct TCP port number can be specified below by using:
   int directTcpPort = VNC_DIRECT_TCP_DEFAULT_PORT
   Ignore this if you are not using the Direct TCP add-on */
int directTcpPort = 0;

/* The following flags indicate the type of connection(s) being used and they
   are set automatically according to user-supplied command line arguments and
   the parameters above. Each type of connection is optional.
   If you set any flag to true below then that makes that type of connection
   mandatory i.e. connectivity details MUST be provided via the command line or
   using the parameters above. */
bool usingCloud = false;
bool usingDirectTcp = false;


/* Location of private directory to contain server file store */
#define STORE_DIR "/var/run/vncsdkServer"

/* Globals */
vnc_Server* server = 0;
vnc_CloudListener* cloudListener = 0;
vnc_DirectTcpListener* directTcpListener = 0;
CFRunLoopTimerRef cloudListenRetryTimer = 0;
SignalHandler signalHandler;

/* Flag to indicate that the launch daemon may have been shutdown by the OS. */
bool systemShutdown = false;

/* Flag to indicate that we will wait until all viewers have disconnected. */
static bool waitForDisconnections = false;


/* Function prototypes */
bool parseCommandLine(int argc, const char** argv);
vnc_Server* createAndInitServer();
void setupSecurity(vnc_Server* server);
vnc_CloudListener* createCloudListener(vnc_Server* server, const char* cloudAddress,
                                  const char* cloudPassword);
vnc_DirectTcpListener* createDirectTcpListener(vnc_Server* server, int port);
bool disconnectViewers();


/* Connection callbacks */

void connectionStarted(void* userData,
                       vnc_Server* server,
                       vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);
  syslog(LOG_NOTICE, "Viewer %s connected", peerAddress);
}

void connectionEnded(void* userData,
                     vnc_Server* server,
                     vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);
  syslog(LOG_NOTICE, "Viewer %s disconnected", peerAddress);
  if (waitForDisconnections && vnc_Server_getConnectionCount(server) == 1) {
    /* The daemon can exit now as this is the last viewer to be disconnected.
       All viewers should have disconnected within the 5 second period after we
       have received the SIGTERM signal otherwise launchd will send a SIGKILL
       signal. */
    vnc_EventLoop_stop();
  }
}

/* Security callbacks */

static vnc_bool_t isUserNameRequired(void* userData, vnc_Server* server,
                                     vnc_Connection* connection)
{
  /* Don't prompt for a username when accessing this server, just a password
     is required */
  return vnc_false;
}

static int authenticateUser(void* userData, vnc_Server* server,
                            vnc_Connection* connection, const char* username,
                            const char* password)
{
  /* Check that the password supplied by the connecting viewer is the same as
     the server password. If so, allow the connection with all permissions,
     otherwise do not allow the connection. */
  if (strcmp(password, serverPassword) == 0) {
    return vnc_Server_PermAll;
  }
  return 0;
}

/* Cloud callbacks */

static void cloudListenRetryTimerCallback(CFRunLoopTimerRef timer, void* info)
{
  if (!cloudListener) {
    cloudListener = createCloudListener(server, cloudAddress, cloudPassword);
  }
  /* Quit if we cannot create the Cloud listener and we don't have any
     connections. */
  if (!cloudListener && !disconnectViewers()) {
    vnc_EventLoop_stop();
  }
}

static void listeningFailed(void* userData, vnc_CloudListener* listener_,
                            const char* cloudError, int suggestedRetryTime)
{
  std::ostringstream logBuf;
  logBuf << "The listener is disconnected from VNC Cloud: " << cloudError;
  if (suggestedRetryTime < 0) {
    /* Quit immediately if we don't have any connections. */
    if (!disconnectViewers()) {
      vnc_EventLoop_stop();
    }
  } else {
    vnc_CloudListener_destroy(cloudListener);
    cloudListener = 0;
    if (cloudListenRetryTimer) {
      CFRunLoopRemoveTimer(CFRunLoopGetCurrent(), cloudListenRetryTimer,
                           kCFRunLoopDefaultMode);
      CFRelease(cloudListenRetryTimer);
    }
    CFAbsoluteTime fireTime = CFAbsoluteTimeGetCurrent() + suggestedRetryTime;
    cloudListenRetryTimer = CFRunLoopTimerCreate(NULL, fireTime, 0, 0, 0,
                                        cloudListenRetryTimerCallback, NULL);
    CFRunLoopAddTimer(CFRunLoopGetCurrent(), cloudListenRetryTimer,
                      kCFRunLoopDefaultMode);
    logBuf << " (retrying in " << suggestedRetryTime << "s)";
  }
  syslog(LOG_ERR, "%s", logBuf.str().c_str());
}

static void listeningStatusChanged(void* userData, vnc_CloudListener* listener,
                                   vnc_CloudListener_Status status)
{
  if(status == vnc_CloudListener_StatusSearching) {
    syslog(LOG_NOTICE, "The listener is in the process of establishing an "
           "association with VNC Cloud");
  }
  else {
    syslog(LOG_NOTICE, "Listening for connections");
  }
}

/* RsaKey callback */

static void rsaKeyDetailsReady(void* userData,
             const vnc_DataBuffer* rsaPublic,
             const char* hexFingerprint,
             const char* catchphraseFingerprint)
{
  syslog(LOG_NOTICE,
   "Server id is: %s\n"
   "Server catchphrase is: %s\n",
   hexFingerprint, catchphraseFingerprint);
}

/* Logger callback */

static void logToSyslog(void*, vnc_Logger_Level level, const char* message)
{
  syslog(LOG_NOTICE, "%s", message);
}

/*
 * main function - validates cloud addresses, initializes server, creates
 * connection listeners
 */
int main(int argc, const char** argv)
{
  int exitCode = 1;

  /* Check whether we already have any hardcoded values */
  if (cloudAddress && cloudPassword) usingCloud = true;
  if (directTcpPort) usingDirectTcp = true;

  if (!parseCommandLine(argc, argv))
    return exitCode;

  /* Create a logger which outputs to syslog.
     This is created before initializing the server so we receive logging
     as soon as the server starts up. */
  vnc_Logger_Callback lcb = { logToSyslog };
  vnc_Logger_createCustomLogger(&lcb, 0);

  /* Create a private directory containing a file DataStore for storing
     persistent data for the server. */
  mkdir(STORE_DIR, 0600);
  vnc_DataStore_createFileStore(STORE_DIR "/fileStore.txt");

  server = createAndInitServer();
  if (!server) goto cleanup;

  setupSecurity(server);

  if (usingCloud) {
    cloudListener = createCloudListener(server, cloudAddress, cloudPassword);
    if (!cloudListener) goto cleanup;
  }

  if (usingDirectTcp) {
    directTcpListener = createDirectTcpListener(server, directTcpPort);
    if (!directTcpListener) goto cleanup;
  }

  /* Server setup complete, now run the EventLoop */
  syslog(LOG_NOTICE, "Running service server daemon");
  exitCode = 0;
  vnc_EventLoop_run();

  syslog(LOG_NOTICE, "Service server is shutting down");

cleanup:
  if (cloudListener) vnc_CloudListener_destroy(cloudListener);
  if (directTcpListener) vnc_DirectTcpListener_destroy(directTcpListener);
  if (server) vnc_Server_destroy(server);
  if (cloudListenRetryTimer) {
    CFRunLoopRemoveTimer(CFRunLoopGetCurrent(), cloudListenRetryTimer,
                         kCFRunLoopDefaultMode);
    CFRelease(cloudListenRetryTimer);
  }
  syslog(LOG_NOTICE, "Service server daemon exiting");
  vnc_shutdown();
  return exitCode;
}

/*
* Extract port number from command line argument.
*/
int extractPortNum(const char* arg)
{
  char* tailPtr;
  int port = strtol(arg, &tailPtr, 10);
  if (*tailPtr) return 0; /* tailPtr should point to null */
  return port;
}

/*
* Parse the command line to obtain connectivity details to be used when
* listening for incoming connections.
*
* For Cloud connectivity, specify the cloudAddress and cloudPassword after
* a -cloud argument:
*
*   -cloud [cloudAddress cloudPassword]
*
* For Direct TCP connectivity, specify the listening port number after a
* -tcp argument:
*
*   -tcp [port]
*
* The server password can also be specified on the command line as a separate
* parameter:
*
*   [password]
*
*/
bool parseCommandLine(int argc, const char** argv)
{
  bool badArgs = false;

  /* Parse any supplied command line arguments */
  for (int i = 1; i<argc; ++i) {
    if (argv[i] && strcmp(argv[i], "-cloud") == 0) {
      if (argc > i+2) {
        cloudAddress = argv[++i];
        cloudPassword = argv[++i];
      }
      usingCloud = true;
    }
    else if (argv[i] && strcmp(argv[i], "-tcp") == 0) {
      if (argc > i+1) {
        directTcpPort = extractPortNum(argv[++i]);
      }
      usingDirectTcp = true;
    }
    else serverPassword = argv[i];
  }

  /* Check if all required connectivity details are provided */
  if (usingCloud && (!cloudAddress || !cloudPassword)) {
    syslog(LOG_ERR, "You must provide a valid Cloud address and password");
    badArgs = true;
  }
  if (usingDirectTcp && !directTcpPort) {
    syslog(LOG_ERR, "You must provide a valid TCP port number");
    badArgs = true;
  }
  if (!serverPassword) {
    syslog(LOG_ERR, "You must provide a server password");
    badArgs = true;
  }

  if (!usingCloud && !usingDirectTcp) {
    syslog(LOG_ERR, "No connection details provided");
    badArgs = true;
  }

  if (badArgs) {
    syslog(LOG_ERR, "You must provide a Cloud address, Cloud password, "
      "and/or Direct TCP port, and a server password");
    return false;
  }
  return true;
}

/*
 * Cleanup viewer connections if we have received the SIGTERM signal.
 */
void shutdownServer()
{
  syslog(LOG_NOTICE, "Got SIGTERM, shutting down.");
  systemShutdown = true;
  /* Quit immediately if we don't have any connections. */
  if (!disconnectViewers()) {
    vnc_EventLoop_stop();
  }
}

/*
 * Initializes SDK and Server, setting up connection callbacks
 */
vnc_Server* createAndInitServer()
{
  /* Initialize the SDK */
  if (!vnc_init()) {
    syslog(LOG_ERR, "Failed to initialize VNC SDK: %s", vnc_getLastError());
    return 0;
  }

  /* Enable Direct TCP Add-On */
  if (usingDirectTcp && !vnc_enableAddOn(directTcpAddOnCode)) {
    syslog(LOG_ERR, "Failed to enable Direct TCP add-on: %s", vnc_getLastError());
    return 0;
  }

  /* Hook up function to handle SIGTERM. */
  signalHandler.init(shutdownServer);

  /* Initialise the server. Note that the vncagent path is not specified, so it
     should be found in the same directory as the main program */
  vnc_Server* server = vnc_Server_createService(0);
  if (!server) {
    syslog(LOG_ERR, "Failed to initialize server: %s", vnc_getLastError());
    return 0;
  }

  /* Setup connection callbacks */
  vnc_Server_ConnectionCallback connectionCallback = {
    connectionStarted,
    connectionEnded,
  };
  vnc_Server_setConnectionCallback(server, &connectionCallback, 0);

  return server;
}

/*
 * Initialize security-related settings for the server
 */
void setupSecurity(vnc_Server* server)
{
  /* Setup security callback */
  vnc_Server_SecurityCallback securityCallback = {
    0, /* verifyPeer not required */
    isUserNameRequired,
    0, /* isPasswordRequired always returns true if not specified */
    authenticateUser
  };
  vnc_Server_setSecurityCallback(server, &securityCallback, 0);
}


/*
 * Starts the server listening for connections made via VNC Cloud
 */
vnc_CloudListener* createCloudListener(vnc_Server* server, const char* cloudAddress,
                                  const char* cloudPassword)
{
  vnc_CloudListener_Callback listenerCallback = {
    listeningFailed,
    0, /* filterConnection not required here */
    listeningStatusChanged
  };
  vnc_CloudListener* listener =
      vnc_CloudListener_create(cloudAddress, cloudPassword,
                               vnc_Server_getConnectionHandler(server),
                               &listenerCallback, 0);

  if (!listener) {
    syslog(LOG_ERR, "Could not create VNC Cloud listener: %s",
           vnc_getLastError());
    return 0;
  }
  return listener;
}

/*
 * Start listening for connections made via direct TCP
 * Ignore this if you do not intend to use the Direct TCP add-on
 */
vnc_DirectTcpListener* createDirectTcpListener(vnc_Server* server, int port)
{
  /* This listens on ALL addresses and does not employ callbacks */
  vnc_DirectTcpListener* listener =
    vnc_DirectTcpListener_create(port, 0,
      vnc_Server_getConnectionHandler(server),
      0, 0);

  if (!listener) {
    syslog(LOG_ERR, "Could not create DirectTcp listener: %s",
     vnc_getLastError());
    return 0;
  } else {
    /* If DirectTcp is being used, request the RSA key details to write to
       the log so that viewers can verify they are connecting to this server. */
    vnc_RsaKey_Callback keyCallback = {
      rsaKeyDetailsReady
    };
    vnc_RsaKey_getDetails(&keyCallback, 0, true);
  }
  return listener;
}

/*
 * Disconnect all viewers connected to the server if the service has been told
 * to stop or we can no longer maintain a connection to VNC Cloud
 */
bool disconnectViewers()
{
  if (vnc_Server_getConnectionCount(server) == 0) {
    return false;
  }
  if (cloudListener) {
    vnc_CloudListener_destroy(cloudListener);
    cloudListener = 0;
  }

  if (directTcpListener) {
    vnc_DirectTcpListener_destroy(directTcpListener);
    directTcpListener = 0;
  }

  /* Set flag to wait until all viewers have disconnected from the server. */
  waitForDisconnections = true;
  int disconnectFlags = vnc_Server_DisconnectAlert;
  /* Tell all viewers to reconnect if we have received a SIGTERM in case the
     server comes back automatically after a reboot. */
  if (systemShutdown) disconnectFlags |= vnc_Server_DisconnectReconnect;
  vnc_Server_disconnectAll(server, "The server has been stopped",
                           disconnectFlags);
  return true;
}
