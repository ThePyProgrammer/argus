/**
 * DSO (Direct Sparse Odometry) ZMQ harness.
 *
 * Wraps DSO's FullSystem as a subprocess that communicates with the
 * Python SubprocessSLAMBridge via ZMQ PAIR socket + msgpack headers.
 *
 * Protocol (same as OpenVINS harness):
 *   Request: [msgpack_header, rgb_bytes, depth_bytes]
 *     header: { ts, rgb_shape, rgb_dtype, depth_shape, depth_dtype, n_imu }
 *   Response: msgpack { pose: bytes(4x4 float64), status: "ok"|"lost", time_ms: float }
 *
 * DSO is monocular -- it uses only the grayscale conversion of the RGB
 * frame. Depth is ignored by DSO but sent by the bridge for consistency.
 * The harness converts RGB to grayscale float and feeds DSO.
 *
 * DSO outputs poses in camera-optical frame (x-right, y-down, z-forward).
 * The Python side applies T_MUJOCO_FROM_OPTICAL to convert to MuJoCo frame.
 *
 * Usage:
 *   ./dso_harness --zmq ipc:///tmp/slam_bridge_12345 [--config path/to/calib.txt]
 */

#include <chrono>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include <Eigen/Core>
#include <msgpack.hpp>
#include <zmq.hpp>

// DSO headers
#include "FullSystem/FullSystem.h"
#include "IOWrapper/ImageDisplay.h"
#include "util/NumType.h"
#include "util/settings.h"

namespace {

// Convert RGB uint8 (H*W*3) to grayscale float (H*W)
std::vector<float> rgb_to_grayscale(const uint8_t* rgb, int width, int height) {
    std::vector<float> gray(width * height);
    for (int i = 0; i < width * height; ++i) {
        // Standard luminance weights
        gray[i] = 0.299f * rgb[i * 3]
                 + 0.587f * rgb[i * 3 + 1]
                 + 0.114f * rgb[i * 3 + 2];
    }
    return gray;
}

// Pack a 4x4 Eigen matrix as raw bytes (column-major double)
std::string pack_pose(const Eigen::Matrix4d& mat) {
    std::string buf(128, '\0');  // 4*4*8 = 128 bytes
    std::memcpy(buf.data(), mat.data(), 128);
    return buf;
}

}  // namespace


int main(int argc, char** argv) {
    // --- Parse CLI args ---
    std::string zmq_endpoint;
    std::string config_path;

    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        if (arg == "--zmq" && i + 1 < argc) {
            zmq_endpoint = argv[++i];
        } else if (arg == "--config" && i + 1 < argc) {
            config_path = argv[++i];
        }
    }

    if (zmq_endpoint.empty()) {
        std::cerr << "Usage: dso_harness --zmq <ipc_endpoint> [--config <path>]"
                  << std::endl;
        return 1;
    }

    // --- DSO settings ---
    // Disable DSO GUI
    dso::setting_debugout_runquiet = true;
    dso::disableAllDisplay = true;

    // --- Initialize DSO FullSystem ---
    auto* fullSystem = new dso::FullSystem();
    fullSystem->setGammaFunction(nullptr);  // no photometric calibration
    fullSystem->linearizeOperation = false;

    // --- ZMQ setup ---
    zmq::context_t ctx(1);
    zmq::socket_t socket(ctx, zmq::socket_type::pair);
    socket.connect(zmq_endpoint);

    std::cout << "[dso_harness] Connected to " << zmq_endpoint << std::endl;

    int frame_id = 0;
    bool initialized = false;
    int width = 0;
    int height = 0;

    // --- Main loop ---
    while (true) {
        // Receive multipart message: [header, rgb_bytes, depth_bytes]
        std::vector<zmq::message_t> parts;
        zmq::recv_result_t result;

        // Receive all parts
        zmq::message_t part;
        int more = 1;
        while (more) {
            result = socket.recv(part, zmq::recv_flags::none);
            if (!result.has_value()) {
                std::cerr << "[dso_harness] recv failed" << std::endl;
                break;
            }
            parts.push_back(std::move(part));
            part = zmq::message_t();

            int more_size = sizeof(more);
            socket.getsockopt(ZMQ_RCVMORE, &more, &more_size);
        }

        if (parts.size() < 3) {
            std::cerr << "[dso_harness] Expected 3+ parts, got "
                      << parts.size() << std::endl;
            continue;
        }

        auto t_start = std::chrono::high_resolution_clock::now();

        // Unpack header
        msgpack::object_handle oh = msgpack::unpack(
            static_cast<const char*>(parts[0].data()),
            parts[0].size()
        );
        msgpack::object obj = oh.get();

        // Extract header fields
        std::map<std::string, msgpack::object> header;
        obj.convert(header);

        double timestamp = header["ts"].as<double>();

        // Extract image dimensions from rgb_shape [H, W, 3]
        std::vector<int> rgb_shape;
        header["rgb_shape"].convert(rgb_shape);
        height = rgb_shape[0];
        width = rgb_shape[1];

        // Convert RGB to grayscale float
        const auto* rgb_data = static_cast<const uint8_t*>(parts[1].data());
        auto grayscale = rgb_to_grayscale(rgb_data, width, height);

        // Create DSO ImageAndExposure
        auto* img = new dso::ImageAndExposure(width, height, timestamp);
        std::memcpy(img->image, grayscale.data(),
                     width * height * sizeof(float));
        img->exposure_time = 1.0;  // simulated -- no real exposure

        // Feed to DSO
        fullSystem->addActiveFrame(img, frame_id);
        frame_id++;

        // Get latest pose
        auto poses = fullSystem->getAllKFPoses();
        Eigen::Matrix4d pose = Eigen::Matrix4d::Identity();
        std::string status = "ok";

        if (poses.empty()) {
            status = "initializing";
        } else {
            // DSO returns SE3 objects; get the latest keyframe pose
            pose = poses.back().matrix();
        }

        auto t_end = std::chrono::high_resolution_clock::now();
        double time_ms = std::chrono::duration<double, std::milli>(
            t_end - t_start).count();

        // Pack response
        std::string pose_bytes = pack_pose(pose);

        msgpack::sbuffer sbuf;
        msgpack::packer<msgpack::sbuffer> pk(&sbuf);
        pk.pack_map(3);
        pk.pack("pose");
        pk.pack_bin(pose_bytes.size());
        pk.pack_bin_body(pose_bytes.data(), pose_bytes.size());
        pk.pack("status");
        pk.pack(status);
        pk.pack("time_ms");
        pk.pack(time_ms);

        zmq::message_t reply(sbuf.data(), sbuf.size());
        socket.send(reply, zmq::send_flags::none);
    }

    delete fullSystem;
    return 0;
}
