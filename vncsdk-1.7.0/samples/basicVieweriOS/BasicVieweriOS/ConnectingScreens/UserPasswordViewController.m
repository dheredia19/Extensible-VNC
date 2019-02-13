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

#import "UserPasswordViewController.h"

/**
 * UserPasswordViewController used to receive user authentication input
 */
@interface UserPasswordViewController ()

@property (weak, nonatomic) IBOutlet UILabel *usernameLabel;
@property (weak, nonatomic) IBOutlet UILabel *passwordLabel;

@property (nonatomic, weak) IBOutlet UITextField *usernameField;
@property (nonatomic, weak) IBOutlet UITextField *passwordField;

- (IBAction)cancelTapped:(id)sender;
- (IBAction)acceptTapped:(id)sender;

@end


@implementation UserPasswordViewController

- (void)viewWillAppear:(BOOL)animated
{
  [super viewWillAppear:animated];
  self.usernameField.enabled = self.usernameRequired;
  self.passwordField.enabled = self.passwordRequired;
  if (self.usernameRequired) {
    [self.usernameField becomeFirstResponder];
  } else if (self.passwordRequired) {
    [self.passwordField becomeFirstResponder];
  }
}

- (void)viewDidLoad
{
  [super viewDidLoad];
  
  if (UI_USER_INTERFACE_IDIOM() == UIUserInterfaceIdiomPhone)
  {
    self.usernameLabel.font = [UIFont systemFontOfSize:17];
    self.passwordLabel.font = [UIFont systemFontOfSize:17];
  } else {
    self.usernameLabel.font = [UIFont systemFontOfSize:25];
    self.passwordLabel.font = [UIFont systemFontOfSize:25];
  }
}

- (IBAction)cancelTapped:(id)sender
{
  [self.delegate userPasswordPromptCancelled];
}

- (IBAction)acceptTapped:(id)sender
{
  [self.delegate userPasswordPromptAcceptedWithUsername:self.usernameField.text
                                               password:self.passwordField.text];
}

- (BOOL)textFieldShouldReturn:(UITextField *)textField
{
  if (textField == self.usernameField) {
    [self.passwordField becomeFirstResponder];
  } else if (textField == self.passwordField) {
    [self acceptTapped:nil];
  }
  return YES;
}

@end
