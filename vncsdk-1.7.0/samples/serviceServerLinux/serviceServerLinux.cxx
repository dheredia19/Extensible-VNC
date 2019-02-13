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

#include <iostream>
#include <sstream>
#include <assert.h>
#include <string.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <time.h>
#include <syslog.h>
#include <unistd.h>

#include <vnc/Vnc.h>
#include "SignalHandler.h"

/*
 * serviceServerLinux sample
 *
 * This sample demonstrates how to implement a VNC server as a Linux service.
 * The code itself is very simple, and similar to the basicServer sample,
 * the main differences being that it uses vnc_Server_createService to create
 * the server, and the server password is no longer automatically generated,
 * but specified on the command line (ideally this would be stored in a more
 * secure manner).
 *
 * This sample can be run as a background (daemon) process, by calling it with
 * the "-d" argument, which can be used for systems using SysV-style init.
 */

/* You can specify the server password here, which is used instead of
   specifying it on the command line: */
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
   Either specify the port number below OR provide the port number via the service's
   command line.
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

/* Timeout (in seconds) after which any connected viewers should be disconnected
   if the vncagent is not ready. This usually indicates that the X server has
   shut down and the screen can no longer be captured. */
#define DISCONNECT_TIMEOUT 15

/* Globals */
vnc_Server* server = 0;
vnc_CloudListener* cloudListener = 0;
vnc_DirectTcpListener* directTcpListener = 0;
time_t cloudListenRetryTime = -1;
time_t disconnectTime = -1;
bool running = true;
int exitCode = 0;
SignalHandler signalHandler;
bool runAsDaemon = false;

/* Flag to indicate the service server may have been shutdown by the OS. */
static bool systemShutdown = false;

/* Flag to indicate that we will wait until all viewers have disconnected. */
static bool waitForDisconnections = false;

/* Function prototypes */

bool parseCommandLine(int argc, const char** argv);
bool daemonize();
vnc_Server* createAndInitServer();
void setupSecurity(vnc_Server* server);
vnc_CloudListener* createCloudListener(vnc_Server* server, const char* cloudAddress,
                                  const char* cloudPassword);
vnc_DirectTcpListener* createDirectTcpListener(vnc_Server* server, int port);
bool disconnectViewers();
void handleTimers(int& nextExpiry);
void runLoop();

/*
 * EventLoop callbacks
 * We maintain three sets of file descriptors for which we require notifications
 * of readability, writability and exception status. The eventUpdated callback
 * tells us which notifications are needed for a particular descriptor, so we
 * can update the sets accordingly. We also keep track of the maximum file
 * descriptor value, which, along with the three fd_sets, are used by the select()
 * system call in our event loop.
 */
fd_set fdsRead;
fd_set fdsWrite;
fd_set fdsExcept;
int maxFd = -1;

static void eventUpdated(void* userData, int fd, int eventMask)
{
  if (fd > maxFd) maxFd = fd;
  FD_CLR(fd, &fdsRead);
  if (eventMask & vnc_EventLoopFd_Read) FD_SET(fd, &fdsRead);
  FD_CLR(fd, &fdsWrite);
  if (eventMask & vnc_EventLoopFd_Write) FD_SET(fd, &fdsWrite);
  FD_CLR(fd, &fdsExcept);
  if (eventMask & vnc_EventLoopFd_Except) FD_SET(fd, &fdsExcept);
}

/* Connection callbacks */

void connectionStarted(void* userData,
                       vnc_Server* server,
                       vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);

  /* Disallow connections if the vncagent isn't running, since the display
     cannot be remoted at this point. This probably means that the X server
     isn't running. */
  if (!vnc_Server_isAgentReady(server)) {
    syslog(LOG_NOTICE, "Disallowing viewer %s - agent not ready", peerAddress);
    vnc_Server_disconnect(server, connection, "Not available",
                          vnc_Server_DisconnectAlert);
    return;
  }

  syslog(LOG_NOTICE, "Viewer %s connected", peerAddress);
}

void connectionEnded(void* userData,
                     vnc_Server* server,
                     vnc_Connection* connection)
{
  const char* peerAddress = vnc_Server_getPeerAddress(server, connection);
  syslog(LOG_NOTICE, "Viewer %s disconnected", peerAddress);
  if (waitForDisconnections && vnc_Server_getConnectionCount(server) == 1) {
    /* The server can exit now as this is the last viewer to be disconnected. */
    running = false;
  }
}

/* Security callbacks */

static vnc_bool_t isUserNameRequired(void* userData,
                                     vnc_Server* server,
                                     vnc_Connection* connection)
{ return vnc_false; }

static int authenticateUser(void* userData,
                            vnc_Server* server,
                            vnc_Connection* connection,
                            const char* username,
                            const char* password)
{
  if (strcmp(password, serverPassword) == 0) {
    return vnc_Server_PermAll;
  }
  return 0;
}

/* Agent callbacks */

static void agentStarted(void* userData, vnc_Server* server)
{
  syslog(LOG_NOTICE, "agent started");
  disconnectTime = -1; /* Cancel pending disconnect */
}

static void agentStopped(void* userData, vnc_Server* server)
{
  syslog(LOG_NOTICE, "agent stopped");
  /* Disconnect viewers if the agent hasn't restarted within a certain time. */
  struct timespec now;
  clock_gettime(CLOCK_MONOTONIC, &now);
  disconnectTime = now.tv_sec + DISCONNECT_TIMEOUT;
}

/* Cloud callbacks */

static void listeningFailed(void* userData, vnc_CloudListener* listener_,
                            const char* cloudError, int suggestedRetryTime)
{
  std::ostringstream logBuf;
  logBuf << "The listener is disconnected from VNC Cloud: " << cloudError;
  if (suggestedRetryTime < 0) {
    /* Quit immediately if we don't have any connections. */
    if (!disconnectViewers()) {
      running = false;
    }
  } else {
    vnc_CloudListener_destroy(cloudListener);
    cloudListener = 0;
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    cloudListenRetryTime = now.tv_sec + suggestedRetryTime;
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
  } else {
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
  exitCode = 1;

  /* Check whether we already have any hardcoded values */
  if (cloudAddress && cloudPassword) usingCloud = true;
  if (directTcpPort) usingDirectTcp = true;

  if (!parseCommandLine(argc, argv)) {
    return exitCode;
  }

  /* Become a daemon process if required */
  if (runAsDaemon && !daemonize()) {
    return exitCode;
  }

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

  cloudListenRetryTime = 0; /* Try listening immediately */

  if (usingDirectTcp) {
    directTcpListener = createDirectTcpListener(server, directTcpPort);
    if (!directTcpListener) goto cleanup;
  }

  /* Server setup complete, now run the EventLoop */
  exitCode = 0;
  runLoop();

  syslog(LOG_NOTICE, "Service server is shutting down");

cleanup:
  if (cloudListener) vnc_CloudListener_destroy(cloudListener);
  if (directTcpListener) vnc_DirectTcpListener_destroy(directTcpListener);
  if (server) vnc_Server_destroy(server);
  syslog(LOG_NOTICE, "Service server exiting");
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
    else if (argv[i] && strcmp(argv[i], "-d") == 0) {
      runAsDaemon = true;
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
 * Become a daemon process - this is required when starting from a SysV init script.
 */
bool daemonize()
{
  pid_t pid;
  pid = fork();
  if (pid < 0) return false;
  if (pid > 0) exit(0);

  if (setsid() < 0) return false;

  pid = fork();
  if (pid < 0) return false;
  if (pid > 0) exit(0);

  /* Close any open file descriptors */
  for (int i=0; i<64; ++i) close(i);

  /* Reopen standard file descriptors pointing to /dev/null */
  open("/dev/null",O_RDONLY);
  open("/dev/null",O_RDWR);
  open("/dev/null",O_RDWR);

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
    running = false;
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

  /* Initialize descriptor sets and event loop callbacks */
  FD_ZERO(&fdsRead);
  FD_ZERO(&fdsWrite);
  FD_ZERO(&fdsExcept);
  const vnc_EventLoopFd_Callback eventLoopCallback = {
    eventUpdated,
    0 /* timerUpdated not used here */
  };

  if (!vnc_EventLoopFd_setCallback(&eventLoopCallback, 0))
  {
    syslog(LOG_ERR, "Call to vnc_EventLoopFd_setCallback failed: %s",
           vnc_getLastError());
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

  /* Setup agent callbacks */
  vnc_Server_AgentCallback agentCallback = {
    agentStarted,
    agentStopped,
  };
  vnc_Server_setAgentCallback(server, &agentCallback, 0);

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

/*
 * Checks and handles any timers we have set
 */
void handleTimers(int& nextExpiry)
{
  struct timespec now;
  clock_gettime(CLOCK_MONOTONIC, &now);

  /* Check if it's time to try or retry listening */
  if (cloudListenRetryTime >= 0) {
    if (now.tv_sec > cloudListenRetryTime) {
      cloudListenRetryTime = -1;
      if (usingCloud) {
        cloudListener = createCloudListener(server,
              cloudAddress,
              cloudPassword);
      }

      /* Poll the event loop, as vnc_CloudListener_create may have updated
      the expiry time */
      nextExpiry = 0;
    } else {
      int expiry = cloudListenRetryTime - now.tv_sec;
      if (nextExpiry < 0 || expiry < nextExpiry) {
        nextExpiry = expiry;
      }
    }
  }

  /* Check if it's time to disconnect viewers */
  if (disconnectTime >= 0) {
    if (now.tv_sec > disconnectTime) {
      disconnectTime = -1;
      vnc_Server_disconnectAll(server, "Not available",
                               vnc_Server_DisconnectAlert);
    } else {
      int expiry = disconnectTime - now.tv_sec;
      if (nextExpiry < 0 || expiry < nextExpiry) {
        nextExpiry = expiry;
      }
    }
  }
}

/*
 * Run the SDK event loop
 */
void runLoop()
{
  running = true;
  int nextExpiry = 0;

  while (running) {
    /* Handle any timers */
    handleTimers(nextExpiry);

    /* Calculate timeout if timer is active */
    timeval* timeout = 0;
    timeval delta;
    if (nextExpiry >= 0) {
      delta.tv_sec = nextExpiry / 1000;
      delta.tv_usec = 1000 * (nextExpiry % 1000);
      timeout = &delta;
    }

    /* Make a copy of the fd sets since these get updated by select */
    fd_set selRead = fdsRead;
    fd_set selWrite = fdsWrite;
    fd_set selExcept = fdsExcept;

    /* Add signal file descriptor to the read set if we're not shutting down */
    if (!systemShutdown) {
      maxFd = std::max(signalHandler.addFd(&selRead), maxFd);
    }

    /* Wait for events or timeout */
    int ready = select(maxFd+1, &selRead, &selWrite, &selExcept, timeout);

    if (ready > 0) {
      for (int fd=0; fd<=maxFd; ++fd) {
        if (!signalHandler.handleEvent(fd, &selRead)) {
          /* Mark any SDK fd events that occurred */
          if (FD_ISSET(fd, &selRead)) {
            vnc_EventLoopFd_markEvents(fd, vnc_EventLoopFd_Read);
          }
          if (FD_ISSET(fd, &selWrite)) {
            vnc_EventLoopFd_markEvents(fd, vnc_EventLoopFd_Write);
          }
          if (FD_ISSET(fd, &selExcept)) {
            vnc_EventLoopFd_markEvents(fd, vnc_EventLoopFd_Except);
          }
        }
      }
    }

    /* Handle fd events or timers */
    nextExpiry = vnc_EventLoopFd_handleEvents();
  }
}
