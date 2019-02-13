# Copyright (C) 2016-2017 RealVNC Limited. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

cmake_minimum_required(VERSION 2.8.12.2)
project(basicViewerMac)
include("../common/common.cmake")
include_directories("${PROJECT_SOURCE_DIR}/../../include")

set(VNC_LIB_DIR "${PROJECT_SOURCE_DIR}/../../lib")
find_vnc_viewer_libs(${VNC_LIB_DIR} VNC_LIBS PLATFORM_LIBS)

set(SRCS
  AppDelegate.mm
  BasicViewerView.mm
  main.mm
)

set(HDRS
  AppDelegate.h
  BasicViewerView.h
)

set(RESOURCES
  Info.plist
)

file(GLOB SDK_HDRS "${PROJECT_SOURCE_DIR}/../../include/vnc/*.h")
source_group("SDK Header Files" FILES ${SDK_HDRS})
source_group("Sample Header Files" FILES ${HDRS})
source_group("Sample Source Files" FILES ${SRCS})

add_executable(BasicViewerMac MACOSX_BUNDLE ${SRCS} ${HDRS} ${SDK_HDRS})
target_link_libraries(BasicViewerMac ${VNC_LIBS} ${PLATFORM_LIBS})

set_target_properties(BasicViewerMac PROPERTIES
  RESOURCE "${RESOURCES}"
  COMPILE_FLAGS "-fobjc-arc"
  MACOSX_BUNDLE_INFO_PLIST "${PROJECT_SOURCE_DIR}/Info.plist"
)

vnc_viewer_post_build(BasicViewerMac ${VNC_LIB_DIR})

