set(libProc_fsrchannels3_la_SOURCES
C3_20.C
C3_19.C
C3_18.C
C3_17.C
C3_16.C
C3_15.C
C3_14.C
C3_13.C
C3_12.C
C3_11.C
C3_10.C
C3_9.C
C3_8.C
C3_7.C
C3_6.C
C3_5.C
C3_4.C
C3_3.C
C3_2.C
C3_1.C
C3_0.C
CG.C
)
add_library(Proc_fsrchannels3 SHARED ${libProc_fsrchannels3_la_SOURCES})
amegic_handle_shared_library(Proc_fsrchannels3)
install(TARGETS Proc_fsrchannels3 DESTINATION ${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR})




















