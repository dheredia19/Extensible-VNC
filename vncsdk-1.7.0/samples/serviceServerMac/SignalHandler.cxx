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
#include <sys/event.h>
#include "SignalHandler.h"


/* Stop the event loop in response to SIGTERM signal sent by launchd.
   This signal will get sent when the launch daemon is unloaded or when the
   machine is shutting down/restarted.
   Calling vnc_EventLoop_stop() directly from a signal handler is not
   guaranteed to be safe in the SDK so we will use a safe approach. See Apple's
   Technical Note TN2050 Observing Process Lifetimes Without Polling
   https://developer.apple.com/library/mac/technotes/tn2050/_index.html
   for details. */
static void handleSIGTERM(CFFileDescriptorRef f, CFOptionFlags callBackTypes,
                          void *info)
{
  if (info && ((SignalHandler*)info)->handleSignal) {
    ((SignalHandler*)info)->handleSignal();
  }
}

void SignalHandler::init(HandleSignalFunc handleSignal_)
{
  handleSignal = handleSignal_;

  /* Ignore SIGTERM signal as we want to use a kqueue to listen for this. */
  sig_t sigErr = signal(SIGTERM, SIG_IGN);
  assert(sigErr != SIG_ERR);

  /* Create a kernel event queue to listen for SIGTERM signal. */
  int kq = kqueue();
  assert(kq >= 0);
  struct kevent event;
  EV_SET(&event, SIGTERM, EVFILT_SIGNAL, EV_ADD | EV_RECEIPT, 0, 0, NULL);
  int numEvents = kevent(kq, &event, 1, &event, 1, NULL);
  assert(numEvents == 1);
  assert(event.flags & EV_ERROR);
  assert(event.data == 0);

  /* Use the runloop to monitor for read activity from kqueue file descriptor. */
  CFFileDescriptorContext context = {0, (void*)(this), NULL, NULL, NULL};
  CFFileDescriptorRef kqRef = CFFileDescriptorCreate(NULL, kq, true,
                                                     handleSIGTERM, &context);
  assert(kqRef != NULL);
  CFRunLoopSourceRef source = CFFileDescriptorCreateRunLoopSource(NULL, kqRef, 0);
  assert(source != NULL);
  CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopDefaultMode);
  CFFileDescriptorEnableCallBacks(kqRef, kCFFileDescriptorReadCallBack);
  CFRelease(source);
  CFRelease(kqRef);
}
