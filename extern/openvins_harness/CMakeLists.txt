cmake_minimum_required(VERSION 3.14)
project(openvins_harness LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies
find_package(Eigen3 3.3 REQUIRED)
find_package(cppzmq REQUIRED)  # Header-only ZMQ C++ bindings
find_package(msgpack-cxx REQUIRED)  # msgpack C++ serialization
find_package(OpenCV REQUIRED COMPONENTS core imgcodecs)

# OpenVINS -- installed via `make install` from ov_msckf build
# Build OpenVINS: git clone https://github.com/rpng/open_vins.git
#   cd open_vins/ov_msckf && mkdir build && cd build
#   cmake -DENABLE_ROS=OFF -DCMAKE_BUILD_TYPE=Release ..
#   make -j$(nproc) && sudo make install
find_library(OV_MSCKF_LIB ov_msckf_lib REQUIRED)
find_path(OV_MSCKF_INCLUDE open_vins REQUIRED)

add_executable(openvins_harness main.cpp)

target_include_directories(openvins_harness
    PRIVATE
    ${OV_MSCKF_INCLUDE}
    ${OpenCV_INCLUDE_DIRS}
)

target_link_libraries(openvins_harness
    PRIVATE
    ${OV_MSCKF_LIB}
    Eigen3::Eigen
    cppzmq
    msgpack-cxx
    ${OpenCV_LIBS}
)
