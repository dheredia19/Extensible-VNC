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

if(APPLE)
  cmake_minimum_required(VERSION 2.8.12.2)

  execute_process(COMMAND xcodebuild -version -sdk macosx
                  COMMAND grep ^SDKVersion:
                  COMMAND cut -d " " -f 2
                  OUTPUT_VARIABLE MACOSX_SDK_VERSION
                  RESULT_VARIABLE RESULT)
  string(STRIP "${MACOSX_SDK_VERSION}" MACOSX_SDK_VERSION)
  if (MACOSX_SDK_VERSION VERSION_LESS "10.10")
    message(FATAL_ERROR "Mac OS X 10.10 SDK and above is required")
  endif()
  execute_process(COMMAND xcodebuild -version -sdk macosx
                  COMMAND grep ^Path:
                  COMMAND cut -d " " -f 2
                  OUTPUT_VARIABLE MACOSX_SDK_PATH
                  RESULT_VARIABLE RESULT)
  string(STRIP "${MACOSX_SDK_PATH}" MACOSX_SDK_PATH)
  set(CMAKE_OSX_SYSROOT "${MACOSX_SDK_PATH}")
  set(CMAKE_OSX_DEPLOYMENT_TARGET "10.9")
  message(STATUS "Using SDK ${CMAKE_OSX_SYSROOT}")
endif()

function(get_lib_arch LIBARCH_VAR)
  set(ARCH "x86")
  if(" ${CMAKE_SYSTEM_PROCESSOR}" STREQUAL " armv6l" OR
     " ${CMAKE_SYSTEM_PROCESSOR}" STREQUAL " armv7l")
    set(ARCH "armhf-raspi")
  elseif (CMAKE_SIZEOF_VOID_P EQUAL 8)
    set(ARCH "x64")
  endif()
  if (WIN32)
    set(PLATFORM "win-${ARCH}")
  elseif (APPLE)
    set(PLATFORM "mac-${ARCH}")
  else()
    set(PLATFORM "linux-${ARCH}")
  endif()

  set(${LIBARCH_VAR} ${PLATFORM} PARENT_SCOPE)
endfunction()

function(expand_vnc_libs VNC_LIB_DIR VNC_LIBS_VAR EXPANDED_VNC_LIBS_VAR)
  foreach(lib_name ${VNC_LIBS})
    find_library(VNC_${lib_name}_LIB ${lib_name} ${VNC_LIB_DIR})
    list(APPEND VNC_EXPANDED_LIBS ${VNC_${lib_name}_LIB})
  endforeach()
  set(${EXPANDED_VNC_LIBS_VAR} ${VNC_EXPANDED_LIBS} PARENT_SCOPE)
endfunction()

function(find_vnc_server_libs VNC_LIB_DIR VNC_LIBS_VAR PLATFORM_LIBS_VAR)
  set(VNC_LIBS vncsdk)
  get_lib_arch(LIBARCH)
  expand_vnc_libs("${VNC_LIB_DIR}/${LIBARCH}" VNC_LIBS VNC_EXPANDED_LIBS)

  if(UNIX)
    if(APPLE)
      find_library(FRAMEWORK_FOUNDATION Foundation)
      find_library(FRAMEWORK_COREFOUNDATION CoreFoundation)
      list(APPEND EXTRA_LIBS ${FRAMEWORK_FOUNDATION} ${FRAMEWORK_COREFOUNDATION})
    else()
      list(APPEND EXTRA_LIBS ${X11_XTest_LIB} ${CRYPT_LIB})
    endif()
  elseif(WIN32)
    list(APPEND EXTRA_LIBS comctl32 crypt32 ws2_32 shlwapi)
  endif()

  set(${VNC_LIBS_VAR} ${VNC_EXPANDED_LIBS} PARENT_SCOPE)
  set(${PLATFORM_LIBS_VAR} ${EXTRA_LIBS} PARENT_SCOPE)
endfunction()

function(find_vnc_viewer_libs VNC_LIB_DIR VNC_LIBS_VAR PLATFORM_LIBS_VAR)
  set(VNC_LIBS vncsdk)
  get_lib_arch(LIBARCH)
  expand_vnc_libs("${VNC_LIB_DIR}/${LIBARCH}" VNC_LIBS VNC_EXPANDED_LIBS)

  if(APPLE)
    find_library(APPKIT_LIBRARY AppKit)
    find_library(CARBON_LIBRARY Carbon)
    find_library(FOUNDATION_LIBRARY Foundation)
    find_library(SYSTEMCONFIGURATION_LIBRARY SystemConfiguration)
    set(EXTRA_LIBS ${APPKIT_LIBRARY} ${CARBON_LIBRARY} ${FOUNDATION_LIBRARY} ${SYSTEMCONFIGURATION_LIBRARY})
  endif()

  set(${VNC_LIBS_VAR} ${VNC_EXPANDED_LIBS} PARENT_SCOPE)
  set(${PLATFORM_LIBS_VAR} ${EXTRA_LIBS} PARENT_SCOPE)
endfunction()

function(vnc_copyfile TARGET BUILD_TARGET)
  add_custom_command(TARGET ${BUILD_TARGET} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${VNC_LIB_DIR}/${LIBARCH}/${TARGET}"
    $<TARGET_FILE_DIR:${BUILD_TARGET}>)
endfunction()

function(vnc_server_post_build BUILD_TARGET VNC_LIB_DIR)
  get_lib_arch(LIBARCH)
  if(WIN32)
    set(VNC_BINARIES "vncsdk.dll" "vncagent.exe" "vncannotator.exe")
  elseif(APPLE)
    set(VNC_BINARIES "vncagent" "vncannotator")
    set_target_properties(${BUILD_TARGET} PROPERTIES
      INSTALL_RPATH "${VNC_LIB_DIR}/${LIBARCH};@executable_path/"
      BUILD_WITH_INSTALL_RPATH TRUE)
  else()
    set(VNC_BINARIES "vncagent" "vncannotator")
  endif()
  
  foreach (FILE ${VNC_BINARIES})
    vnc_copyfile(${FILE} ${BUILD_TARGET})
  endforeach()
endfunction()

function(vnc_copy_sdk_libs BUILD_TARGET LOCATION)
  if(APPLE)
    add_custom_command(TARGET ${BUILD_TARGET} POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E make_directory ${LOCATION})
    
    file(GLOB FILES "${VNC_LIB_DIR}/${LIBARCH}/libvncsdk.*.dylib")
    foreach(FILE ${FILES})
      add_custom_command(TARGET ${BUILD_TARGET} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy ${FILE} ${LOCATION})    
    endforeach()
  endif()
endfunction()

function(vnc_viewer_post_build BUILD_TARGET VNC_LIB_DIR)
  get_lib_arch(LIBARCH)
  if(APPLE)
    set_target_properties(${BUILD_TARGET} PROPERTIES
      INSTALL_RPATH "@executable_path/../Frameworks/"
      BUILD_WITH_INSTALL_RPATH TRUE)
    vnc_copy_sdk_libs(${BUILD_TARGET} "$<TARGET_FILE_DIR:${BUILD_TARGET}>/../Frameworks")
  elseif(WIN32)
    add_custom_command(TARGET ${BUILD_TARGET} POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${VNC_LIB_DIR}/${LIBARCH}/vncsdk.dll"
        $<TARGET_FILE_DIR:${BUILD_TARGET}>)
  endif()
endfunction()
