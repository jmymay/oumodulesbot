cmake_minimum_required(VERSION 3.24)

project(OUBotInteractions)

find_package(functions_framework_cpp REQUIRED)
find_package(nlohmann_json 3.11.2 REQUIRED)
find_package(OpenSSL REQUIRED)

add_library(interaction_lib interaction_lib.cc verify_ed25519.cc)
target_compile_features(interaction_lib PRIVATE cxx_std_17)
target_link_libraries(
    interaction_lib
    functions-framework-cpp::framework
    nlohmann_json::nlohmann_json
    OpenSSL::Crypto)

add_executable(interaction interaction.cc)
target_link_libraries(interaction interaction_lib)
include(GNUInstallDirs)
install(TARGETS interaction RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/03597a01ee50ed33e9dfd640b249b4be3799d395.zip
)
FetchContent_MakeAvailable(googletest)

enable_testing()

add_executable(
    interaction_lib_test interaction_lib_test.cc
)
target_link_libraries(
    interaction_lib_test interaction_lib GTest::gtest_main nlohmann_json::nlohmann_json
)

add_executable(
    verify_ed25519_test verify_ed25519_test.cc verify_ed25519.cc
)
target_link_libraries(
    verify_ed25519_test GTest::gtest_main OpenSSL::Crypto
)

include(GoogleTest)
gtest_discover_tests(interaction_lib_test verify_ed25519_test)
