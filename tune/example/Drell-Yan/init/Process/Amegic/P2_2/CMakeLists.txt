
cmake_minimum_required(VERSION 3.11.0)
project(Proc_P2_2 LANGUAGES C CXX)
find_package(SHERPA-MC PATHS /home/moritz.pabst/Programs/sherpa-ue/install/share/SHERPA-MC REQUIRED NO_DEFAULT_PATH)
message(STATUS SHERPA-MC_DIR=${SHERPA-MC_DIR})
include("GNUInstallDirs")
set(libProc_P2_2_la_SOURCES  ./2_2__d__db__mum__mup__O0_2/V_Z.C ./2_2__d__db__mum__mup__O0_2/V.C ./2_2__u__ub__mum__mup__O0_2/V_Z.C ./2_2__u__ub__mum__mup__O0_2/V.C ./2_2__d__db__mum__mup__O0_1__1_2/V_Z.C ./2_2__d__db__mum__mup__O0_1__1_2/V.C ./2_2__u__ub__mum__mup__O0_1__1_2/V_Z.C ./2_2__u__ub__mum__mup__O0_1__1_2/V.C ./2_2__d__db__mum__mup__O0_2__E0/V_Z.C ./2_2__d__db__mum__mup__O0_2__E0/V.C ./2_2__d__db__mum__mup__O0_2__E1/V_Z.C ./2_2__d__db__mum__mup__O0_2__E1/V.C ./2_2__u__ub__mum__mup__O0_2__E0/V_Z.C ./2_2__u__ub__mum__mup__O0_2__E0/V.C ./2_2__u__ub__mum__mup__O0_2__E1/V_Z.C ./2_2__u__ub__mum__mup__O0_2__E1/V.C ./2_2__d__db__em__ep__O0_2/V_Z.C ./2_2__d__db__em__ep__O0_2/V.C ./2_2__u__ub__em__ep__O0_2/V_Z.C ./2_2__u__ub__em__ep__O0_2/V.C ./2_2__d__db__em__ep__O0_1__1_2/V_Z.C ./2_2__d__db__em__ep__O0_1__1_2/V.C ./2_2__u__ub__em__ep__O0_1__1_2/V_Z.C ./2_2__u__ub__em__ep__O0_1__1_2/V.C ./2_2__d__db__em__ep__O0_2__E0/V_Z.C ./2_2__d__db__em__ep__O0_2__E0/V.C ./2_2__d__db__em__ep__O0_2__E1/V_Z.C ./2_2__d__db__em__ep__O0_2__E1/V.C ./2_2__u__ub__em__ep__O0_2__E0/V_Z.C ./2_2__u__ub__em__ep__O0_2__E0/V.C ./2_2__u__ub__em__ep__O0_2__E1/V_Z.C ./2_2__u__ub__em__ep__O0_2__E1/V.C )
add_library( Proc_P2_2 SHARED ${libProc_P2_2_la_SOURCES})
amegic_handle_shared_library(Proc_P2_2)
set(CMAKE_INSTALL_PREFIX ${PROJECT_SOURCE_DIR}/../)
install(TARGETS Proc_P2_2 DESTINATION ${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR})

add_subdirectory(./fsrchannels2)
