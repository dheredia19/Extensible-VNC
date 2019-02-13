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

#import "ConnectingViewController.h"
#import "AppDelegate.h"

@interface ConnectingViewController ()
@property (weak, nonatomic) IBOutlet UILabel *messageLabel;
@property (weak, nonatomic) IBOutlet UIActivityIndicatorView *spinner;
@property (weak, nonatomic) IBOutlet NSLayoutConstraint *constraintToLabel;
@property (weak, nonatomic) IBOutlet NSLayoutConstraint *constraintToSpinner;

@end

/**
 * ConnectingViewController is used to inform the different states of the Viewer Session.
 */
@implementation ConnectingViewController

-(void)viewDidLoad
{
  [super viewDidLoad];
  [self setMessage:@"Start Basic iOS Viewer" spinnerHidden:YES startButtonEnabled:YES];
}

/**
 * Setting the message to present in the connection label according to the sdk connection state.
 *
 * @param message is the message that will be presented in the connection status label
 * @param spinnerHidden Bool value controls the visibility of the spinner
 * @param enabled sets the Start Button state enabled/disabled.
 */
- (void)setMessage:(NSString *)message spinnerHidden:(BOOL)spinnerHidden startButtonEnabled:(BOOL)enabled
{
  /* Handling constraints to present the Start Button according to the spinner's visibility */
  if (spinnerHidden) {
    _constraintToLabel.priority = UILayoutPriorityDefaultHigh;
    _constraintToSpinner.priority = UILayoutPriorityDefaultLow;
    [_startBtn layoutIfNeeded];
  }else{
    _constraintToLabel.priority = UILayoutPriorityDefaultLow;
    _constraintToSpinner.priority = UILayoutPriorityDefaultHigh;
    [_startBtn layoutIfNeeded];
  }
  _messageLabel.text = message;
  _spinner.hidden = spinnerHidden;
  _startBtn.enabled = enabled;
  
  if (UI_USER_INTERFACE_IDIOM() == UIUserInterfaceIdiomPhone)
  {
    self.messageLabel.font = [UIFont systemFontOfSize:17];
    self.startBtn.titleLabel.font = [UIFont systemFontOfSize:15];
  } else {
    self.messageLabel.font = [UIFont systemFontOfSize:30];
    self.startBtn.titleLabel.font = [UIFont systemFontOfSize:25];
  }
}

/** 
 * Starting a new viewer session.
 */
- (IBAction)startBtnPressed:(id)sender
{
  [[AppDelegate instance] startViewerSession];
}

@end
