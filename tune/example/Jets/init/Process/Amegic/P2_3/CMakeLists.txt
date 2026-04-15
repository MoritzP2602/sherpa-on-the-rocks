
cmake_minimum_required(VERSION 3.11.0)
project(Proc_P2_3 LANGUAGES C CXX)
find_package(SHERPA-MC PATHS /home/moritz.pabst/Programs/sherpa-ue/install/share/SHERPA-MC REQUIRED NO_DEFAULT_PATH)
message(STATUS SHERPA-MC_DIR=${SHERPA-MC_DIR})
include("GNUInstallDirs")
set(libProc_P2_3_la_SOURCES  ./2_3__d__d__G__d__d__O3_0/V_Z.C ./2_3__d__d__G__d__d__O3_0/V.C ./2_3__d__d__G__d__d__O3_0/V_1.C ./2_3__d__db__G__d__db__O3_0/V_Z.C ./2_3__d__db__G__d__db__O3_0/V.C ./2_3__d__db__G__d__db__O3_0/V_1.C ./2_3__d__db__G__u__ub__O3_0/V_Z.C ./2_3__d__db__G__u__ub__O3_0/V.C ./2_3__d__db__G__u__ub__O3_0/V_1.C ./2_3__d__u__G__d__u__O3_0/V_Z.C ./2_3__d__u__G__d__u__O3_0/V.C ./2_3__d__u__G__d__u__O3_0/V_1.C ./2_3__d__ub__G__d__ub__O3_0/V_Z.C ./2_3__d__ub__G__d__ub__O3_0/V.C ./2_3__d__ub__G__d__ub__O3_0/V_1.C ./2_3__G__d__d__d__db__O3_0/V_Z.C ./2_3__G__d__d__d__db__O3_0/V.C ./2_3__G__d__d__d__db__O3_0/V_1.C ./2_3__G__d__d__u__ub__O3_0/V_Z.C ./2_3__G__d__d__u__ub__O3_0/V.C ./2_3__G__d__d__u__ub__O3_0/V_1.C ./2_3__db__db__G__db__db__O3_0/V_Z.C ./2_3__db__db__G__db__db__O3_0/V.C ./2_3__db__db__G__db__db__O3_0/V_1.C ./2_3__db__ub__G__db__ub__O3_0/V_Z.C ./2_3__db__ub__G__db__ub__O3_0/V.C ./2_3__db__ub__G__db__ub__O3_0/V_1.C ./2_3__G__db__d__db__db__O3_0/V_Z.C ./2_3__G__db__d__db__db__O3_0/V.C ./2_3__G__db__d__db__db__O3_0/V_1.C ./2_3__G__db__u__db__ub__O3_0/V_Z.C ./2_3__G__db__u__db__ub__O3_0/V.C ./2_3__G__db__u__db__ub__O3_0/V_1.C ./2_3__G__u__d__u__db__O3_0/V_Z.C ./2_3__G__u__d__u__db__O3_0/V.C ./2_3__G__u__d__u__db__O3_0/V_1.C ./2_3__G__ub__d__db__ub__O3_0/V_Z.C ./2_3__G__ub__d__db__ub__O3_0/V.C ./2_3__G__ub__d__db__ub__O3_0/V_1.C )
add_library( Proc_P2_3 SHARED ${libProc_P2_3_la_SOURCES})
amegic_handle_shared_library(Proc_P2_3)
set(CMAKE_INSTALL_PREFIX ${PROJECT_SOURCE_DIR}/../)
install(TARGETS Proc_P2_3 DESTINATION ${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR})

add_subdirectory(./fsrchannels3)
