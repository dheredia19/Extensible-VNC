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

#import "AppDelegate.h"
#import "ConnectingViewController.h"
#import "UserPasswordViewController.h"
#import "DesktopViewController.h"
#import "ViewerAdapter.h"

#include <vncsdk/Vnc.h>

/* For Cloud connections, hard-code the Cloud address for the Viewer. Example address:
 LxygGgSrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRsVnXoDoue4Xqm */
#define LOCAL_CLOUD_ADDRESS ""

/* Hard-code the Cloud password associated with this Cloud address. Example password:
 KMDgGgELSvAdvscgGfk2 */
#define LOCAL_CLOUD_PASSWORD ""

/* Hard-code the Cloud address of the Server (peer) to connect to. Example address:
 LxyDgGgrhXQFiLj5M4M.LxyPXzA9sGLkB6pCtJv.devEX1Sg2Txs1CgVuW4.LxyPRydf9ZczNo13BcD */
#define PEER_CLOUD_ADDRESS ""

/* Set this to NO if you want to use Direct TCP connectivity. */
#define USE_CLOUD_CONNECTIVITY true

/* To enable direct TCP connectivity you need to copy the content of your
 add-on code (available from your RealVNC account) into the string below. */
#define DIRECT_TCP_ADDON_CODE ""

/* For direct TCP connections you must provide the server's TCP host address
 and port number. Either edit the macros below OR provide these connection
 details via an alert view which will pop up when you click start.
 The default direct TCP port number can be specified below by using:
 #define TCP_PORT VNC_DIRECT_TCP_DEFAULT_PORT
 Ignore these macros if you are not using the Direct TCP add-on */
#define TCP_ADDRESS ""
#define TCP_PORT 0

#pragma mark - App Delegate

@interface AppDelegate () <UserPasswordPromptDelegate>
{
  vnc_CloudConnector* _cloud;
  vnc_DirectTcpConnector* _tcpConnector;
}

@property (strong, nonatomic) ViewerAdapter *viewer;
@property (strong, nonatomic) DesktopViewController *desktopViewController;
@property (strong, nonatomic) ConnectingViewController *connectingViewController;

@property (assign) BOOL usingDirectTCP;

@end


@implementation AppDelegate

/**
 * Class method to retrieve the AppDelegate's instance
 * 
 * @return AppDelegate instance
 */
+ (AppDelegate*)instance
{
  return (AppDelegate*)[[UIApplication sharedApplication] delegate];
}

/**
 * It's recommended that all the SDK calls are handled in a separate thread so we don't lock the UI Main Thread
 * whilst doing SDK operations and for that it's required to create a custom SDK thread.
 * We use the NSThread approach because synchronous calls done with GCD may be called on the main thread.
 * So we need to guarantee that all SDK calls are handled in the SDK thread.
 * To make these operations more straight forward we've added Blocks functionality as an NSThread Category.
 */

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions
{
  self.window = [[UIWindow alloc] initWithFrame:[[UIScreen mainScreen] bounds]];
  
  /* The ConnectingViewController will inform the state of the Viewer Session */
  _connectingViewController = [[ConnectingViewController alloc] init];
  
  /* Initializing the SDK thread */
  _sdkThread = [[NSThread alloc] initWithTarget: self selector:@selector(sdkThreadMain) object:nil];
  [_sdkThread start];
  
  /* Initializes the SDK synchronously in the sdkThread. This must be called before any other SDK functions are called. */
  
  [_sdkThread performBlockSync:^{
    
    vnc_Logger_createStderrLogger();
    
    if (!vnc_init()) {
      [self displayMessage:[NSString stringWithFormat: @"Failed to initialise VNC SDK: %s\n", vnc_getLastError()] startButtonEnabled:NO];
    }
    
    self.usingDirectTCP = !USE_CLOUD_CONNECTIVITY;
    
    if (self.usingDirectTCP) {
      NSString *directTCPCode = [NSString stringWithUTF8String:DIRECT_TCP_ADDON_CODE];
      if ([directTCPCode length] > 0) {
        if (!vnc_enableAddOn(DIRECT_TCP_ADDON_CODE)) {
          [self displayMessage:[NSString stringWithFormat: @"Failed to enable Direct TCP add-on: %s\n", vnc_getLastError()] startButtonEnabled:NO];
        }
      } else {
        [self displayMessage:@"You must enter a valid Direct TCP add-on code to use the Direct TCP module." startButtonEnabled:NO];
      }
    }
  }];
  
  self.window.rootViewController = self.connectingViewController;
  [self.window makeKeyAndVisible];
  
  return YES;
}

- (void)applicationWillTerminate:(UIApplication *)application
{
  [self cleanup];
}

/** 
 * Method used to start a viewer session
 */
-(void)startViewerSession
{
  /* Clean up the previous state if we have any objects persisting from a prior connection attempt
     (e.g. startViewerSession is called twice without cleanly closing a connection) */
  [self cleanup];
  
  NSString* localCloudAddress = [[NSString alloc] initWithUTF8String:LOCAL_CLOUD_ADDRESS];
  NSString* localCloudPassword = [[NSString alloc] initWithUTF8String:LOCAL_CLOUD_PASSWORD];
  NSString* peerCloudAddress = [[NSString alloc] initWithUTF8String:PEER_CLOUD_ADDRESS];
  
  NSString* tcpAddress = [[NSString alloc] initWithUTF8String:TCP_ADDRESS];
  
  NSArray* arguments = [[NSProcessInfo processInfo] arguments];
  if (arguments.count == 4) {
    localCloudAddress = arguments[1];
    localCloudPassword = arguments[2];
    peerCloudAddress = arguments[3];
  }
  
  /* Check that the local cloud address, password and peer cloud address have been provided.*/
  if (!self.usingDirectTCP) {
    if (0 == [localCloudAddress length] ||
        0 == [localCloudPassword length] ||
        0 == [peerCloudAddress length]) {
      [self displayMessage:@"No connectivity information provided." startButtonEnabled:NO];
      return;
    }
  }
  
  /* Start connections */
  [self.connectingViewController setMessage:@"Connecting..." spinnerHidden:NO startButtonEnabled:NO];
  
  /* Initializing the viewer for SDK cloud connections */
  [_sdkThread performBlockSync:^{
   
    [self createDataStore];
    
    /* Create the viewer */
    self.viewer = [[ViewerAdapter alloc] init];
    if (nil == self.viewer) {
      [self displayMessage:[NSString stringWithFormat:@"Failed to create viewer: %s", vnc_getLastError()] startButtonEnabled:YES];
      return;
    }
    
    /* Create desktop view controller with a custom initializer to run the viewer SDK methods to handle callback connections */
    _desktopViewController = [[DesktopViewController alloc] initWithViewer:self.viewer];
    if (nil == _desktopViewController) {
      [self displayMessage:[NSString stringWithFormat:@"Failed to create viewer: %s", vnc_getLastError()] startButtonEnabled:YES];
      return;
    }
    
    /* Register our username/password callback functions */
    vnc_Viewer_AuthenticationCallback authCallback;
    memset(&authCallback, 0, sizeof(vnc_Viewer_AuthenticationCallback));
    authCallback.requestUserCredentials = userCredentialsRequest;
    authCallback.cancelUserCredentialsRequest = userCredentialsCancel;
    if (!vnc_Viewer_setAuthenticationCallback(self.viewer.desktopViewer, &authCallback, 0)) {
      [self displayMessage:[NSString stringWithFormat:@"Failed to set Authentication Callbacks: %s\n", vnc_getLastError()]
        startButtonEnabled:YES];
      return;
    }
    
    /* Register connection state callbacks */
    vnc_Viewer_ConnectionCallback connectionCallback;
    memset(&connectionCallback, 0, sizeof(vnc_Viewer_ConnectionCallback));
    connectionCallback.connecting = &connecting;
    connectionCallback.connected = &connected;
    connectionCallback.disconnected = &disconnected;
    if (!vnc_Viewer_setConnectionCallback(self.viewer.desktopViewer, &connectionCallback, 0)) {
      [self displayMessage:[NSString stringWithFormat:@"Failed to set Connection State Callbacks: %s\n", vnc_getLastError()]
        startButtonEnabled:YES];
      return;
    }
    
    if (!self.usingDirectTCP) {
      [self createCloudConnectorTo:peerCloudAddress
                 localCloudAddress:localCloudAddress
                localCloudPassword:localCloudPassword];
    } else {
      /* Register peer verification callbacks */
      vnc_Viewer_PeerVerificationCallback peerVerificationCallback;
      memset(&peerVerificationCallback, 0, sizeof(vnc_Viewer_PeerVerificationCallback));
      peerVerificationCallback.verifyPeer = &verifyPeer;
      peerVerificationCallback.cancelPeerVerification = &cancelPeerVerification;
      if (!vnc_Viewer_setPeerVerificationCallback(self.viewer.desktopViewer, &peerVerificationCallback, 0)) {
        [self displayMessage:[NSString stringWithFormat:@"Failed to set Peer Verification Callbacks: %s\n", vnc_getLastError()]
          startButtonEnabled:YES];
        return;
      }
      
      if ([tcpAddress length] == 0) {
        dispatch_async(dispatch_get_main_queue(), ^{
          NSString *alertTitle = @"Connect to Server";
          
          UIAlertController *alertController = [UIAlertController
                                                alertControllerWithTitle:alertTitle
                                                message:@""
                                                preferredStyle:UIAlertControllerStyleAlert];
          
          [alertController addTextFieldWithConfigurationHandler:^(UITextField * textField) {
            textField.placeholder = @"Address";
          }];
          [alertController addTextFieldWithConfigurationHandler:^(UITextField * textField) {
            textField.placeholder = @"Port";
          }];
          
          UIAlertAction *connectAction = [UIAlertAction
                                         actionWithTitle:@"Connect"
                                         style:UIAlertActionStyleDefault
                                         handler:^(UIAlertAction *action) {
                                           NSString *address = [alertController.textFields[0] text];
                                           NSString *port = [alertController.textFields[1] text];
                                           int portValue = [port intValue] ? : VNC_DIRECT_TCP_DEFAULT_PORT;
                                           if (address.length > 0) {
                                             [_sdkThread performBlockAsync:^{
                                               [self createDirectTCPConnectorTo:address
                                                                           port:portValue];
                                             }];
                                           } else {
                                             [[AppDelegate instance] displayMessage:@"Unable to connect, no network address specified" startButtonEnabled:YES];
                                           }
                                         }];
          UIAlertAction *cancelAction = [UIAlertAction
                                         actionWithTitle:@"Cancel"
                                         style:UIAlertActionStyleCancel
                                         handler:^(UIAlertAction *action) {
                                           [alertController dismissViewControllerAnimated:YES
                                                                               completion:nil];
                                           [[AppDelegate instance] displayMessage:@"Connection cancelled" startButtonEnabled:YES];
                                         }];
          [alertController addAction:cancelAction];
          [alertController addAction:connectAction];
          [[[[AppDelegate instance] window] rootViewController] presentViewController:alertController
                                                                             animated:YES
                                                                           completion:nil];
        });
      } else {
        [self createDirectTCPConnectorTo:tcpAddress
                                    port:TCP_PORT];
      }
    }
    
  }];
}

- (void)createCloudConnectorTo:(NSString *)peerCloudAddress
             localCloudAddress:(NSString *)localCloudAddress
            localCloudPassword:(NSString *)localCloudPassword
{
  NSLog(@"Connecting via VNC Cloud, local address: %@, peer cloud address: %@", localCloudAddress, peerCloudAddress);
  
  _cloud = vnc_CloudConnector_create([localCloudAddress UTF8String], [localCloudPassword UTF8String]);
  if (NULL != _cloud) {
    /* Begin an outgoing connection to the given Cloud address. The connection will be handled by the connectionHandler. */
    if (!vnc_CloudConnector_connect(_cloud, [peerCloudAddress UTF8String], self.viewer.connectionHandler)) {
      [self displayMessage:[NSString stringWithFormat: @"Failed to make VNC Cloud connection: %s\n", vnc_getLastError()]
        startButtonEnabled:YES];
    }
  } else {
    /* Unable to create a CloudConnector, check and display what the error was: */
    [self displayMessage:[NSString stringWithFormat: @"Failed to make VNC Cloud connection: %s\n", vnc_getLastError()]
      startButtonEnabled:NO];
  }
}

- (void)createDirectTCPConnectorTo:(NSString *)tcpAddress
                              port:(int)tcpPort
{
  NSLog(@"Connecting via Direct TCP to address: %@:%d", tcpAddress, tcpPort);
  
  _tcpConnector = vnc_DirectTcpConnector_create();
  if (NULL != _tcpConnector) {
    /* Begin an outgoing connection to the given address. The connection will be handled by the connectionHandler. */
    if (!vnc_DirectTcpConnector_connect(_tcpConnector, [tcpAddress UTF8String], tcpPort, self.viewer.connectionHandler)) {
      [self displayMessage:[NSString stringWithFormat: @"Failed to make direct TCP connection: %s\n", vnc_getLastError()]
        startButtonEnabled:YES];
    }
  } else {
    /* Unable to create a DirectTcpConnector, check and display what the error was: */
    [self displayMessage:[NSString stringWithFormat: @"Failed to create direct TCP connector: %s\n", vnc_getLastError()]
      startButtonEnabled:NO];
  }
  vnc_DirectTcpConnector_destroy(_tcpConnector);
}

- (void)createDataStore
{
  /* Create data store under "Application Support" */
  NSError* err = nil;
  NSFileManager* fm = [NSFileManager defaultManager];
  NSURL* appSupportDir = [fm URLForDirectory:NSApplicationSupportDirectory
                                    inDomain:NSUserDomainMask appropriateForURL:nil create:YES error:&err];
  if (err) {
    [self displayMessage:[NSString stringWithFormat:@"Failed to find or create application support directory: %@", err] startButtonEnabled:NO];
    return;
  }
  NSString* bundleID = [[NSBundle mainBundle] bundleIdentifier];
  NSURL* dirPath = [appSupportDir URLByAppendingPathComponent:bundleID];
  if (![fm createDirectoryAtURL:dirPath withIntermediateDirectories:YES attributes:nil error:&err]) {
    [self displayMessage:[NSString stringWithFormat:@"Failed to create data store directory: %@", err] startButtonEnabled:NO];
    return;
  }
  
  dirPath = [dirPath URLByAppendingPathComponent:@"dataStore.txt"];
  if (!vnc_DataStore_createFileStore([[dirPath path] UTF8String])) {
    [self displayMessage:[NSString stringWithFormat:@"Failed to create data store directory: %s", vnc_getLastError()] startButtonEnabled:NO];
    return;
  }
}

/**
 * Function called to present the ConnectingViewController cleaning up the connection and viewer
 */
- (void)stopViewerSession
{
  [self cleanup];
  [self displayMessage:@"Connection was terminated, please press Start to begin a new connection" 
startButtonEnabled:YES];
}

/**
 * Destroys the viewer and cloudConnector synchronously in the sdkThread
 */
- (void)cleanup
{
  [_sdkThread performBlockSync:^{
    _desktopViewController = nil;
    if (nil != _cloud) {
      vnc_CloudConnector_destroy(_cloud); _cloud = nil;
    }
    self.viewer = nil;
  }];
}

/**
 * Thread main function to keep the thread alive during the currentRunLoop
 */
- (void)sdkThreadMain
{
  /* We need the NSPort here because a runloop with no sources or ports registered with it
     will simply exit immediately instead of running forever. */
  NSPort* keepAlive = [NSPort port];
  NSRunLoop* rl = [NSRunLoop currentRunLoop];
  [keepAlive scheduleInRunLoop: rl forMode: NSRunLoopCommonModes];
  [rl run];
}

#pragma mark - Connection callbacks

/**
 * C connection handler for when the SDK is connecting to the server
 */
void connecting(void* userData, vnc_Viewer *viewer)
{
  /* Calls the objc connecting counterpart */
  [[AppDelegate instance] connecting];
}

/**
 * C connection handler for when the SDK is connected to the server
 */
void connected(void* userData, vnc_Viewer *viewer)
{
  /* Calls the ObjC connecting counterpart */
  [[AppDelegate instance] connected];
}

/**
 * C connection handler for when the SDK is disconnected to the server
 */
void disconnected(void* userData, vnc_Viewer *viewer, const char* reason, int flags)
{
  NSString* reasonText = reason? [NSString stringWithCString:reason encoding:NSUTF8StringEncoding] : @"";
  [[AppDelegate instance] disconnected:reasonText flags:flags];
}

#pragma mark - Authentication prompt

/** 
 * C username and password handler for when the SDK needs authentication with the server
 */
void userCredentialsRequest(void* userData, vnc_Viewer *viewer, vnc_bool_t needUser,
                            vnc_bool_t needPasswd)
{
  dispatch_async(dispatch_get_main_queue(), ^{
    /* Show prompt */
    UserPasswordViewController *upvc = [[UserPasswordViewController alloc] init];
    upvc.usernameRequired = needUser;
    upvc.passwordRequired = needPasswd;
    upvc.delegate = [AppDelegate instance];
    [[[[AppDelegate instance] window] rootViewController] presentViewController:upvc
                                                                       animated:YES completion:nil];
  });
  
}

/** 
 * C username and password handler for when the user cancels the authentication with the server
 */
void userCredentialsCancel(void* userData, vnc_Viewer* session)
{
  [[AppDelegate instance] displayMessage:@"Authentication check cancelled" startButtonEnabled:YES];
}

#pragma mark - Peer Verification callbacks

void verifyPeer(void* userData,
              vnc_Viewer* viewer,
              const char* hexFingerprint,
              const char* catchphraseFingerprint,
                const vnc_DataBuffer* serverRsaPublic) {
  NSString *fingerprintString = [NSString stringWithUTF8String:hexFingerprint];
  NSString *catchphraseString = [NSString stringWithUTF8String:catchphraseFingerprint];
  dispatch_async(dispatch_get_main_queue(), ^{
    NSString *alertTitle = @"Verify peer identity";
    NSString *alertMessage = [NSString stringWithFormat:@"Connecting to %s\n\nServer Id: %@\nCatchphrase: %@", vnc_Viewer_getPeerAddress(viewer), fingerprintString, catchphraseString];
    
    UIAlertController *alertController = [UIAlertController
                                          alertControllerWithTitle:alertTitle
                                          message:alertMessage
                                          preferredStyle:UIAlertControllerStyleAlert];
    UIAlertAction *acceptAction = [UIAlertAction
                                   actionWithTitle:@"Accept"
                                   style:UIAlertActionStyleDefault
                                   handler:^(UIAlertAction *action) {
                                     [[AppDelegate instance] sendPeerIdentityResponse:true];
                                   }];
    UIAlertAction *cancelAction = [UIAlertAction
                                   actionWithTitle:@"Cancel"
                                   style:UIAlertActionStyleCancel
                                   handler:^(UIAlertAction *action) {
                                     [[AppDelegate instance] sendPeerIdentityResponse:false];
                                   }];
    [alertController addAction:cancelAction];
    [alertController addAction:acceptAction];
    [[[[AppDelegate instance] window] rootViewController] presentViewController:alertController
                                                                       animated:YES
                                                                     completion:nil];
  });
}

/**
 * Notification to cancel a prior request for peer verification.  This can
 * happen if the server closes the connection while peer verification is in
 * progress.  This callback is optional.
 */
void cancelPeerVerification(void* userData,
                          vnc_Viewer* viewer) {
  [[AppDelegate instance] displayMessage:@"Peer verification cancelled by server"
                      startButtonEnabled:YES];
}

#pragma mark - Connection callbacks

/**
 * ObjC connection handler (Called from the C callback)
 */
- (void)connecting
{
  NSLog(@"Session connecting");
  dispatch_async(dispatch_get_main_queue(), ^{
    [self.connectingViewController setMessage:@"Connecting..." spinnerHidden:NO startButtonEnabled:NO];
  });
}

/**
 * ObjC connection handler (Called from the C callback)
 */
- (void)connected
{
  NSLog(@"Session connected");
  /* We guarantee that the calls to load the view are done in the main thread */
  dispatch_async(dispatch_get_main_queue(), ^{
    self.window.rootViewController = self.desktopViewController;
  });
}

/**
 * ObjC connection handler (called from the C callback)
 */
- (void)disconnected:(NSString *)reason flags:(int)flags
{
  NSString *message = [NSString stringWithFormat:@"Disconnected: %@", reason];
  if (nil != self.connectingViewController.presentedViewController) {
    /**
     * Disconnection occurred while authenticating - close the authentication view controller:
     */
    [self.connectingViewController.presentedViewController dismissViewControllerAnimated:NO
                                                                              completion:nil];
    message = [NSString stringWithFormat:@"Disconnected whilst authenticating: %@", reason];
  }
  [self displayMessage:message startButtonEnabled:YES];
}

/**
 * Function that informs connection changes and presents the ConnectingViewController
 * Enable/Disable the Start Button depending on the connection state callbacks.
 */
- (void)displayMessage:(NSString*)message startButtonEnabled:(BOOL)enabled
{
  /* We guarantee that all messages are presented asynchronously in the main thread */
  dispatch_async(dispatch_get_main_queue(), ^{
    [self.connectingViewController setMessage:message spinnerHidden:YES startButtonEnabled:enabled];
    self.window.rootViewController = self.connectingViewController;
  });
}

#pragma mark - Peer identity callbacks

/**
 * Delegate method for when the user has chosen to accept a peer identity
 * or reject it.
 *
 * @param userAccepted set to yes if the user accepted the peer identity, or 
 * to no if they decline.
 */
- (void)sendPeerIdentityResponse:(BOOL)userAccepted
{
  [self.window.rootViewController dismissViewControllerAnimated:YES completion:nil];
  
  /* Calling the SDK thread to make sure the SDK knows the user's decision: */
  [_sdkThread performBlockAsync:^{
    if (!vnc_Viewer_sendPeerVerificationResponse([AppDelegate instance].viewer.desktopViewer, userAccepted)) {
      [self displayMessage:[NSString stringWithFormat:@"Failed to send peer verification response: %s\n", vnc_getLastError()]
        startButtonEnabled:YES];
      return;
    }
  }];
}

#pragma mark - Authentication prompt callbacks

/** 
 * Delegate method for when the username and password has been inserted
 */
- (void)userPasswordPromptAcceptedWithUsername:(NSString *)username
                                      password:(NSString *)password
{
  [self.window.rootViewController dismissViewControllerAnimated:YES completion:nil];
  __block const char* c_username = [username cStringUsingEncoding:NSUTF8StringEncoding];
  __block const char* c_password = [password cStringUsingEncoding:NSUTF8StringEncoding];
  
  /* Calling the SDK thread to propagate the username and password to the SDK: */
  [_sdkThread performBlockAsync:^{
    if (!vnc_Viewer_sendAuthenticationResponse(self.viewer.desktopViewer, true, c_username, c_password)) {
      [self displayMessage:[NSString stringWithFormat:@"Failed to send authentication response: %s\n", vnc_getLastError()]
        startButtonEnabled:YES];
      return;
    }
  }];
}

/**
 * Delegate method for when the username and password is cancelled by the user
 */
- (void)userPasswordPromptCancelled
{
  [self.window.rootViewController dismissViewControllerAnimated:YES completion:nil];
  
  [_sdkThread performBlockAsync:^{
    vnc_Viewer_sendAuthenticationResponse(self.viewer.desktopViewer, false, 0, 0);
  }];
  
  [[AppDelegate instance] displayMessage:@"Authentication cancelled" startButtonEnabled:YES];
}

@end
