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

cmake_minimum_required(VERSION 2.8)
project(serviceServerLinux)
include("../common/common.cmake")
include_directories("${PROJECT_SOURCE_DIR}/../../include")
include(CheckLibraryExists)

set(VNC_LIB_DIR "${PROJECT_SOURCE_DIR}/../../lib")
find_vnc_server_libs(${VNC_LIB_DIR} VNC_LIBS PLATFORM_LIBS)

set(SRCS serviceServerLinux.cxx SignalHandler.cxx)
file(GLOB SDK_HDRS "${PROJECT_SOURCE_DIR}/../../include/vnc/*.h")
source_group("SDK Header Files" FILES ${SDK_HDRS})
source_group("Sample Source Files" FILES ${SRCS})

CHECK_LIBRARY_EXISTS(rt clock_gettime "time.h" HAVE_CLOCK_GETTIME)
if(HAVE_CLOCK_GETTIME)
  list(APPEND PLATFORM_LIBS "-lrt")
endif()

add_executable(serviceServerLinux ${SRCS} ${HDRS})
target_link_libraries(serviceServerLinux ${VNC_LIBS} ${PLATFORM_LIBS})

vnc_server_post_build(serviceServerLinux ${VNC_LIB_DIR})
