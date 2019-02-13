@echo off
goto comment

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

:comment

set VIRTENV=%~dp0\env

echo Checking for virtualenv.exe ...
"%SystemRoot%\System32\where.exe" /q virtualenv.exe
if errorlevel 1 goto QUIT

goto CONTINUE

:QUIT
  echo Aborting. 'virtualenv.exe' is not found on path.
  pause
  exit /B 1

:CONTINUE

echo Running VNC Cloud Address Tool ....

rem Get Python version
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set VERS=%%I

for /f "tokens=1 delims=." %%I in ("%VERS%") do set /a major=%%I
for /f "tokens=2 delims=." %%I in ("%VERS%") do set /a minor=%%I
for /f "tokens=3 delims=." %%I in ("%VERS%") do set /a build=%%I

if not %major% == 2 goto WARNING1
if %minor% lss 7 goto WARNING2
if %minor% == 7 (
  if %build% lss 9 (
    goto WARNING
  )
)
goto RUN

:WARNING1
echo.
echo You are running %VERS%.
echo This version is not supported, fully-secure Python 2.7.9 is recommended.
echo.
goto RUN

:WARNING2
echo.
echo You are running Python %VERS%.
echo You can still use the tool, but upgrading to fully-secure Python 2.7.9 is recommended.
echo.

:RUN

if exist "%VIRTENV%\created" (
  echo Using existing virtual environment "%VIRTENV%"
) else (
  echo Creating virtual environment
  virtualenv.exe -q "%VIRTENV%"
  TYPE nul >"%VIRTENV%\created"
)

echo Installing requirements ...
"%VIRTENV%\Scripts\pip.exe" install -r "%~dp0\requirements.txt" -vvvv > "%VIRTENV%\install.log"

"%VIRTENV%\Scripts\python.exe" "%~dp0\run.py" %*