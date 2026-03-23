cmake_minimum_required(VERSION 3.14)
project(dso_harness LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)

find_package(Eigen3 3.3 REQUIRED)
find_package(cppzmq REQUIRED)
find_package(msgpack-cxx REQUIRED)

# DSO -- built from source, typically in extern/dso/build
find_library(DSO_LIB dso PATHS ${CMAKE_SOURCE_DIR}/../dso/build/lib REQUIRED)
find_path(DSO_INCLUDE dso PATHS ${CMAKE_SOURCE_DIR}/../dso/src REQUIRED)

add_executable(dso_harness main.cpp)
target_include_directories(dso_harness PRIVATE ${DSO_INCLUDE})
target_link_libraries(dso_harness
    PRIVATE
    ${DSO_LIB}
    Eigen3::Eigen
    cppzmq
    msgpack-cxx
)
