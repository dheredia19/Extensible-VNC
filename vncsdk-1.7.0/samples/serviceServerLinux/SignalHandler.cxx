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


#include <syslog.h>
#include <unistd.h>
#include <signal.h>
#include <sys/signalfd.h>
#include <vnc/Vnc.h>
#include "SignalHandler.h"


SignalHandler::SignalHandler() : signalFd(-1), handleSignal(0)
{
}

void SignalHandler::init(HandleSignalFunc handleSignal_)
{
  /* Create the file descriptor using signalfd() to handle SIGTERM signal. */
  sigset_t mask;
  sigemptyset(&mask);
  sigaddset(&mask, SIGTERM);
  if (sigprocmask(SIG_BLOCK, &mask, 0) == -1) {
    syslog(LOG_ERR, "Call to sigprocmask() failed");
  }
  signalFd = signalfd(-1, &mask, 0);
  if (signalFd == -1) {
    syslog(LOG_ERR, "Call to signalfd() failed");
  }
  handleSignal = handleSignal_;
}

int SignalHandler::addFd(fd_set* readFds)
{
  FD_SET(signalFd, readFds);
  return signalFd;
}

bool SignalHandler::handleEvent(int fd, fd_set* readFds)
{
  if (fd != signalFd) return false;
  if (FD_ISSET(signalFd, readFds)) {
    /* Check if we got SIGTERM and handle this signal. */
    struct signalfd_siginfo fdsi;
    read(signalFd, &fdsi, sizeof(struct signalfd_siginfo));
    if (fdsi.ssi_signo == SIGTERM && handleSignal) {
      handleSignal();
    }
  }
  return true;
}
