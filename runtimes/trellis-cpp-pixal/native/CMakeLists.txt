cmake_minimum_required(VERSION 3.20)
project(mediaforge_pixal_projection LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(TRELLIS_SOURCE_DIR "" CACHE PATH "Pinned trellis.cpp source checkout")
set(TRELLIS_BUILD_DIR "" CACHE PATH "Matching trellis.cpp build with GGML libraries")
if(NOT EXISTS "${TRELLIS_SOURCE_DIR}/thirdparty/ggml/include/ggml.h")
  message(FATAL_ERROR "TRELLIS_SOURCE_DIR must contain the pinned GGML checkout")
endif()
execute_process(COMMAND git -C "${TRELLIS_SOURCE_DIR}" rev-parse HEAD
  OUTPUT_VARIABLE TRELLIS_REV OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND git -C "${TRELLIS_SOURCE_DIR}/thirdparty/ggml" rev-parse HEAD
  OUTPUT_VARIABLE GGML_REV OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
if(NOT TRELLIS_REV STREQUAL "2516c48b677050c570f47eba2e68dc8a5bc918b0" OR
   NOT GGML_REV STREQUAL "737e88f25d4f62254f3b7a726fd9663036cc94da")
  message(FATAL_ERROR "trellis.cpp/GGML source revisions differ from the projection port pins")
endif()
foreach(component base cpu vulkan)
  find_library(GGML_${component} NAMES ggml-${component}
               PATHS "${TRELLIS_BUILD_DIR}" NO_DEFAULT_PATH REQUIRED)
endforeach()
add_library(pixal_projection STATIC projection.cpp)
target_include_directories(pixal_projection PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}" "${TRELLIS_SOURCE_DIR}/thirdparty/ggml/include")
target_compile_options(pixal_projection PRIVATE -Wall -Wextra -Werror)
target_link_libraries(pixal_projection PUBLIC "${GGML_base}")
add_executable(pixal-projection-check projection_check.cpp)
target_include_directories(pixal-projection-check PRIVATE "${TRELLIS_SOURCE_DIR}/include")
target_link_libraries(pixal-projection-check PRIVATE pixal_projection "${GGML_cpu}" "${GGML_vulkan}")
set_target_properties(pixal-projection-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")

find_package(Python3 COMPONENTS Interpreter REQUIRED)
find_library(GGML_registry NAMES ggml PATHS "${TRELLIS_BUILD_DIR}" NO_DEFAULT_PATH REQUIRED)
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../patches/projected-dit.patch" DIT_PATCH_SHA)
set(DIT_OVERLAY "${CMAKE_CURRENT_BINARY_DIR}/dit-${DIT_PATCH_SHA}")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/../prepare_trellis.py"
  --source "${TRELLIS_SOURCE_DIR}" --destination "${DIT_OVERLAY}"
  COMMAND_ERROR_IS_FATAL ANY)
add_library(pixal_dit STATIC flow_checkpoint.cpp flow_runner.cpp "${DIT_OVERLAY}/src/dit.cpp" "${TRELLIS_SOURCE_DIR}/src/trellis_model.cpp")
set_source_files_properties(flow_checkpoint.cpp flow_runner.cpp flow_check.cpp
  PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra;-Werror")
target_include_directories(pixal_dit PUBLIC "${DIT_OVERLAY}/include" "${TRELLIS_SOURCE_DIR}/include"
  "${TRELLIS_SOURCE_DIR}/thirdparty/ggml/include")
target_link_libraries(pixal_dit PUBLIC "${GGML_base}" "${GGML_cpu}" "${GGML_registry}")
add_executable(pixal-dit-check dit_check.cpp)
target_link_libraries(pixal-dit-check PRIVATE pixal_dit pixal_projection "${GGML_vulkan}")
set_target_properties(pixal-dit-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
add_executable(pixal-flow-check flow_check.cpp)
target_link_libraries(pixal-flow-check PRIVATE pixal_dit "${GGML_vulkan}")
set_target_properties(pixal-flow-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
add_library(pixal_image STATIC image_features.cpp naf.cpp vision_checkpoint.cpp stage_bridge.cpp ss_decoder.cpp ss_decoder_checkpoint.cpp sparse_decoder.cpp sparse_decoder_checkpoint.cpp mesh_decode.cpp)
target_link_libraries(pixal_image PUBLIC pixal_dit pixal_projection)
target_compile_options(pixal_image PRIVATE -Wall -Wextra -Werror)
add_executable(pixal-image-check image_check.cpp)
target_link_libraries(pixal-image-check PRIVATE pixal_image "${GGML_vulkan}")
target_compile_options(pixal-image-check PRIVATE -Wall -Wextra -Werror)
set_target_properties(pixal-image-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
add_executable(pixal-naf-check naf_check.cpp)
target_link_libraries(pixal-naf-check PRIVATE pixal_image "${GGML_vulkan}")
target_compile_options(pixal-naf-check PRIVATE -Wall -Wextra -Werror)
set_target_properties(pixal-naf-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
add_executable(pixal-vision-check vision_check.cpp)
target_link_libraries(pixal-vision-check PRIVATE pixal_image "${GGML_vulkan}")
target_compile_options(pixal-vision-check PRIVATE -Wall -Wextra -Werror)
set_target_properties(pixal-vision-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
set_source_files_properties(stage_bridge.cpp PROPERTIES COMPILE_OPTIONS "-ffp-contract=off")
set_source_files_properties(mesh_decode.cpp PROPERTIES COMPILE_OPTIONS "-ffp-contract=off")
add_executable(pixal-stages-check stages_check.cpp)
target_link_libraries(pixal-stages-check PRIVATE pixal_image "${GGML_vulkan}")
target_compile_options(pixal-stages-check PRIVATE -Wall -Wextra -Werror)
set_target_properties(pixal-stages-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
add_executable(pixal-ss-decoder-check ss_decoder_check.cpp)
target_link_libraries(pixal-ss-decoder-check PRIVATE pixal_image "${GGML_vulkan}")
target_compile_options(pixal-ss-decoder-check PRIVATE -Wall -Wextra -Werror)
set_target_properties(pixal-ss-decoder-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
add_executable(pixal-sparse-decoder-check sparse_decoder_check.cpp)
target_link_libraries(pixal-sparse-decoder-check PRIVATE pixal_image "${GGML_vulkan}")
target_compile_options(pixal-sparse-decoder-check PRIVATE -Wall -Wextra -Werror)
set_target_properties(pixal-sparse-decoder-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
add_executable(pixal-mesh-check mesh_decode_check.cpp "${TRELLIS_SOURCE_DIR}/src/dual_grid.cpp")
target_link_libraries(pixal-mesh-check PRIVATE pixal_image "${GGML_vulkan}")
target_compile_options(pixal-mesh-check PRIVATE -Wall -Wextra -Werror)
set_target_properties(pixal-mesh-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")

# CPU postprocessing overlay; never compile the optional QEM GPU backends.
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/../patches/surface-export.patch" SURFACE_PATCH_SHA)
set(SURFACE_OVERLAY "${CMAKE_CURRENT_BINARY_DIR}/surface-${SURFACE_PATCH_SHA}")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/../prepare_trellis.py"
  --source "${TRELLIS_SOURCE_DIR}" --destination "${SURFACE_OVERLAY}" --component surface
  COMMAND_ERROR_IS_FATAL ANY)
find_library(PIXAL_WEBP NAMES webp PATHS "${TRELLIS_BUILD_DIR}/_deps/libwebp-build" NO_DEFAULT_PATH REQUIRED)
find_library(PIXAL_SHARPYUV NAMES sharpyuv PATHS "${TRELLIS_BUILD_DIR}/_deps/libwebp-build" NO_DEFAULT_PATH REQUIRED)
add_library(pixal_surface STATIC surface_export.cpp pipeline.cpp
  "${SURFACE_OVERLAY}/src/uv_bake.cpp" "${SURFACE_OVERLAY}/src/mesh_glb.cpp" "${SURFACE_OVERLAY}/src/remesh_dc.cpp"
  "${TRELLIS_SOURCE_DIR}/src/tri_bvh.cpp" "${TRELLIS_SOURCE_DIR}/src/decimate_qem.cpp"
  "${TRELLIS_SOURCE_DIR}/thirdparty/xatlas/xatlas.cpp" "${TRELLIS_SOURCE_DIR}/thirdparty/meshoptimizer/simplifier.cpp")
target_include_directories(pixal_surface BEFORE PUBLIC "${SURFACE_OVERLAY}/include")
target_include_directories(pixal_surface PRIVATE "${TRELLIS_SOURCE_DIR}/thirdparty/stb" "${TRELLIS_SOURCE_DIR}/thirdparty/fqms"
  "${TRELLIS_SOURCE_DIR}/thirdparty/xatlas" "${TRELLIS_SOURCE_DIR}/thirdparty/meshoptimizer" "${TRELLIS_BUILD_DIR}/_deps/libwebp-src/src")
target_compile_definitions(pixal_surface PRIVATE TRELLIS_HAVE_WEBP XA_MULTITHREADED=0)
set_source_files_properties(surface_export.cpp surface_export_cli.cpp pipeline.cpp pipeline_check.cpp PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra;-Werror;-ffp-contract=off")
target_link_libraries(pixal_surface PUBLIC pixal_image "${PIXAL_WEBP}" "${PIXAL_SHARPYUV}")
add_executable(pixal-surface-export surface_export_cli.cpp)
target_link_libraries(pixal-surface-export PRIVATE pixal_surface)
set_target_properties(pixal-surface-export PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")

# Compile the unchanged upstream graph as a separate binary for exact regression
# comparison of the legacy mode, including its default GELU implementation.
add_executable(pixal-dit-baseline-check dit_check.cpp "${TRELLIS_SOURCE_DIR}/src/dit.cpp"
  "${TRELLIS_SOURCE_DIR}/src/trellis_model.cpp")
target_compile_definitions(pixal-dit-baseline-check PRIVATE MEDIAFORGE_UNPATCHED_DIT=1)
target_include_directories(pixal-dit-baseline-check PRIVATE "${TRELLIS_SOURCE_DIR}/include"
  "${TRELLIS_SOURCE_DIR}/thirdparty/ggml/include")
target_link_libraries(pixal-dit-baseline-check PRIVATE pixal_projection "${GGML_base}" "${GGML_cpu}" "${GGML_registry}" "${GGML_vulkan}")
set_target_properties(pixal-dit-baseline-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")

add_executable(pixal-pipeline-check pipeline_check.cpp)
target_link_libraries(pixal-pipeline-check PRIVATE pixal_surface "${GGML_vulkan}")
set_target_properties(pixal-pipeline-check PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")

add_executable(pixal-generate worker_cli.cpp)
target_link_libraries(pixal-generate PRIVATE pixal_surface "${GGML_vulkan}")
target_compile_options(pixal-generate PRIVATE -Wall -Wextra -Werror -ffp-contract=off)
set_target_properties(pixal-generate PROPERTIES BUILD_RPATH "${TRELLIS_BUILD_DIR}")
