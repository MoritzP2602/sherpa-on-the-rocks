set(libProc_fsrchannels2_la_SOURCES
C2_1.C
C2_0.C
CG.C
)
add_library(Proc_fsrchannels2 SHARED ${libProc_fsrchannels2_la_SOURCES})
amegic_handle_shared_library(Proc_fsrchannels2)
install(TARGETS Proc_fsrchannels2 DESTINATION ${CMAKE_INSTALL_PREFIX}/${CMAKE_INSTALL_LIBDIR})

