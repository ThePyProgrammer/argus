/**
 * OpenVINS ZMQ harness -- subprocess that wraps OpenVINS VioManager
 * and speaks the project's ZMQ wire protocol.
 *
 * Wire protocol (recv multipart):
 *   Part 0: msgpack header {ts, rgb_shape, rgb_dtype, depth_shape, depth_dtype, n_imu}
 *   Part 1: raw RGB bytes (H*W*3 uint8)
 *   Part 2: raw depth bytes (H*W float32)
 *   Part 3: raw IMU bytes (n_imu * 7 float64: [ts, ax, ay, az, gx, gy, gz])
 *
 * Wire protocol (send):
 *   Part 0: msgpack {pose: bytes(4x4 float64), status: "ok"|"lost"|"initializing", time_ms: float}
 *
 * Build: mkdir build && cd build && cmake .. && make
 * Requires: OpenVINS (ov_msckf), Eigen3, cppzmq, msgpack-cxx, OpenCV
 *
 * NOTE: This is a reference implementation. The exact OpenVINS API calls
 * (header paths, method signatures) should be verified against the installed
 * OpenVINS version. Comments mark sections that may need adjustment.
 */

#include <chrono>
#include <csignal>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include <Eigen/Dense>
#include <msgpack.hpp>
#include <opencv2/core.hpp>
#include <zmq.hpp>

// OpenVINS headers -- verify paths match your installed version
#include "ov_msckf/VioManager.h"
#include "ov_msckf/VioManagerOptions.h"
#include "ov_core/sensor_data.h"  // For ImuData, CameraData

static volatile bool g_running = true;

static void signal_handler(int /*sig*/) {
    g_running = false;
}

/**
 * Parse command-line arguments.
 * Expected: openvins_harness --zmq <endpoint> --config <path>
 */
struct Args {
    std::string zmq_endpoint;
    std::string config_path;
};

static Args parse_args(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        if (arg == "--zmq" && i + 1 < argc) {
            args.zmq_endpoint = argv[++i];
        } else if (arg == "--config" && i + 1 < argc) {
            args.config_path = argv[++i];
        }
    }
    if (args.zmq_endpoint.empty()) {
        std::cerr << "Usage: openvins_harness --zmq <endpoint> --config <path>\n";
        std::exit(1);
    }
    return args;
}

/**
 * Build a 4x4 homogeneous transform from rotation matrix and position.
 */
static void build_pose_matrix(const Eigen::Matrix3d& rot,
                               const Eigen::Vector3d& pos,
                               double* out_16) {
    // Row-major 4x4: [R | t; 0 0 0 1]
    for (int r = 0; r < 3; ++r) {
        for (int c = 0; c < 3; ++c) {
            out_16[r * 4 + c] = rot(r, c);
        }
        out_16[r * 4 + 3] = pos(r);
    }
    out_16[12] = 0.0;
    out_16[13] = 0.0;
    out_16[14] = 0.0;
    out_16[15] = 1.0;
}

/**
 * Pack a response as msgpack with pose bytes, status string, and timing.
 */
static zmq::message_t pack_response(const double* pose_16,
                                     const std::string& status,
                                     double time_ms) {
    msgpack::sbuffer buf;
    msgpack::packer<msgpack::sbuffer> pk(&buf);
    pk.pack_map(3);

    // "pose" -> raw bytes (4x4 float64 = 128 bytes)
    pk.pack(std::string("pose"));
    pk.pack_bin(128);
    pk.pack_bin_body(reinterpret_cast<const char*>(pose_16), 128);

    // "status" -> string
    pk.pack(std::string("status"));
    pk.pack(status);

    // "time_ms" -> float
    pk.pack(std::string("time_ms"));
    pk.pack(time_ms);

    return zmq::message_t(buf.data(), buf.size());
}

int main(int argc, char** argv) {
    // Signal handling for clean shutdown
    std::signal(SIGTERM, signal_handler);
    std::signal(SIGINT, signal_handler);

    Args args = parse_args(argc, argv);

    // ---------------------------------------------------------------
    // Initialize ZMQ PAIR socket
    // ---------------------------------------------------------------
    zmq::context_t ctx(1);
    zmq::socket_t sock(ctx, zmq::socket_type::pair);
    sock.connect(args.zmq_endpoint);

    std::cout << "[openvins_harness] Connected to " << args.zmq_endpoint << "\n";

    // ---------------------------------------------------------------
    // Initialize OpenVINS VioManager
    // NOTE: The exact initialization API may vary by OpenVINS version.
    //       Verify VioManagerOptions loading method with your build.
    // ---------------------------------------------------------------
    auto params = ov_msckf::VioManagerOptions();
    // Load parameters from YAML config file
    // NOTE: This method name may differ. Alternatives:
    //   params.load_print_simulation(args.config_path);
    //   params.load(args.config_path);
    params.load_print_simulation(args.config_path);
    auto vio = std::make_shared<ov_msckf::VioManager>(params);

    std::cout << "[openvins_harness] OpenVINS initialized from " << args.config_path << "\n";

    bool initialized = false;

    // ---------------------------------------------------------------
    // Main processing loop
    // ---------------------------------------------------------------
    while (g_running) {
        try {
            // Receive multipart message: [header, rgb, depth, imu?]
            std::vector<zmq::message_t> parts;
            auto result = zmq::recv_multipart(sock, std::back_inserter(parts));
            if (!result || parts.size() < 3) {
                continue;
            }

            auto t_start = std::chrono::high_resolution_clock::now();

            // -------------------------------------------------------
            // Unpack msgpack header
            // -------------------------------------------------------
            auto header_handle = msgpack::unpack(
                static_cast<const char*>(parts[0].data()),
                parts[0].size()
            );
            auto header = header_handle.get();
            auto header_map = header.via.map;

            double timestamp = 0.0;
            int rgb_h = 0, rgb_w = 0;
            int depth_h = 0, depth_w = 0;
            int n_imu = 0;

            // Extract header fields
            for (uint32_t i = 0; i < header_map.size; ++i) {
                auto& kv = header_map.ptr[i];
                std::string key;
                kv.key.convert(key);

                if (key == "ts") {
                    kv.val.convert(timestamp);
                } else if (key == "rgb_shape") {
                    auto shape = kv.val.as<std::vector<int>>();
                    rgb_h = shape[0];
                    rgb_w = shape[1];
                } else if (key == "depth_shape") {
                    auto shape = kv.val.as<std::vector<int>>();
                    depth_h = shape[0];
                    depth_w = shape[1];
                } else if (key == "n_imu") {
                    kv.val.convert(n_imu);
                }
            }

            // -------------------------------------------------------
            // Feed IMU readings to OpenVINS (each reading individually)
            // IMU data format: n_imu rows of 7 doubles [ts, ax, ay, az, gx, gy, gz]
            // -------------------------------------------------------
            if (n_imu > 0 && parts.size() >= 4) {
                const auto* imu_data = reinterpret_cast<const double*>(parts[3].data());
                for (int i = 0; i < n_imu; ++i) {
                    // NOTE: The exact ImuData struct and method name may
                    // differ between OpenVINS versions. Verify with your build.
                    ov_core::ImuData imu;
                    imu.timestamp = imu_data[i * 7 + 0];
                    // Accelerometer: ax, ay, az
                    imu.am = Eigen::Vector3d(
                        imu_data[i * 7 + 1],
                        imu_data[i * 7 + 2],
                        imu_data[i * 7 + 3]
                    );
                    // Gyroscope: gx, gy, gz
                    imu.wm = Eigen::Vector3d(
                        imu_data[i * 7 + 4],
                        imu_data[i * 7 + 5],
                        imu_data[i * 7 + 6]
                    );
                    vio->feed_measurement_imu(imu);
                }
            }

            // -------------------------------------------------------
            // Convert RGB bytes to OpenCV Mat and feed to OpenVINS
            // -------------------------------------------------------
            cv::Mat rgb_image(rgb_h, rgb_w, CV_8UC3,
                              const_cast<void*>(parts[1].data()));

            // NOTE: feed_measurement_camera / feed_measurement_monocular
            // API may vary. Verify with your OpenVINS version.
            ov_core::CameraData cam;
            cam.timestamp = timestamp;
            cam.sensor_ids.push_back(0);
            cam.images.push_back(rgb_image.clone());
            // For grayscale conversion if needed:
            // cv::Mat gray;
            // cv::cvtColor(rgb_image, gray, cv::COLOR_BGR2GRAY);
            // cam.images.push_back(gray);
            vio->feed_measurement_camera(cam);

            // -------------------------------------------------------
            // Get state estimate from OpenVINS
            // NOTE: The state access API may vary. Common alternatives:
            //   auto state = vio->get_state();
            //   Eigen::Vector3d pos = state->_imu->pos();
            //   Eigen::Matrix3d rot = state->_imu->Rot();
            // -------------------------------------------------------
            double pose_matrix[16];
            std::string status;

            auto state = vio->get_state();
            if (state == nullptr || !vio->initialized()) {
                // Not yet initialized -- send identity pose with "initializing" status
                Eigen::Matrix3d eye3 = Eigen::Matrix3d::Identity();
                Eigen::Vector3d zero3 = Eigen::Vector3d::Zero();
                build_pose_matrix(eye3, zero3, pose_matrix);
                status = "initializing";
            } else {
                try {
                    // Extract position and rotation from IMU state
                    // NOTE: Accessor names may differ by version
                    Eigen::Vector3d pos = state->_imu->pos();
                    Eigen::Matrix3d rot = state->_imu->Rot();

                    build_pose_matrix(rot, pos, pose_matrix);
                    status = "ok";
                    initialized = true;
                } catch (const std::exception& e) {
                    std::cerr << "[openvins_harness] State extraction error: "
                              << e.what() << "\n";
                    // Send last known or identity pose with "lost"
                    Eigen::Matrix3d eye3 = Eigen::Matrix3d::Identity();
                    Eigen::Vector3d zero3 = Eigen::Vector3d::Zero();
                    build_pose_matrix(eye3, zero3, pose_matrix);
                    status = "lost";
                }
            }

            auto t_end = std::chrono::high_resolution_clock::now();
            double elapsed_ms = std::chrono::duration<double, std::milli>(
                t_end - t_start).count();

            // -------------------------------------------------------
            // Send response
            // -------------------------------------------------------
            auto reply = pack_response(pose_matrix, status, elapsed_ms);
            sock.send(reply, zmq::send_flags::none);

        } catch (const zmq::error_t& e) {
            if (e.num() == ETERM || e.num() == EINTR) {
                break;  // Context terminated or interrupted
            }
            std::cerr << "[openvins_harness] ZMQ error: " << e.what() << "\n";
        } catch (const std::exception& e) {
            std::cerr << "[openvins_harness] Error: " << e.what() << "\n";
            // Try to send error response
            try {
                double identity[16] = {
                    1, 0, 0, 0,
                    0, 1, 0, 0,
                    0, 0, 1, 0,
                    0, 0, 0, 1
                };
                auto reply = pack_response(identity, "lost", 0.0);
                sock.send(reply, zmq::send_flags::none);
            } catch (...) {
                // Cannot recover, will be caught by Python-side timeout
            }
        }
    }

    std::cout << "[openvins_harness] Shutting down.\n";
    sock.close();
    ctx.close();
    return 0;
}
