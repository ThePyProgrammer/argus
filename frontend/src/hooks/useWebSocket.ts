import { useEffect, useRef } from 'react';
import { useRobotStore } from '../stores/robotStore';
import { useControlStore } from '../stores/controlStore';
import { useSlamStore, fetchSlamState } from '../stores/slamStore';
import { useDetectorStore, fetchDetectorState } from '../stores/detectorStore';
import { useMetricsStore } from '../stores/metricsStore';
import { usePipelineStore } from '../stores/pipelineStore';
import type {
  WSMessage,
  RobotListPayload,
  PoseUpdatePayload,
  CloudDeltaPayload,
  CloudFullPayload,
  StatsPayload,
  TrajectoryPayload,
  SlamMetrics,
  MetricHistory,
  Detection3DEnvelope,
  DetectorRestartCompletePayload,
  DetectorParamAckPayload,
  DetectionMetrics,
  DetectionMetricHistory,
  DetectionGtMetrics,
} from '../utils/messageTypes';

/**
 * WebSocket hook that connects to the Argus backend and dispatches
 * incoming messages to the appropriate Zustand stores.
 */
export function useWebSocket(url: string = `ws://${window.location.host}/ws`): void {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(url);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        // Register sendCommand with controlStore
        const sendCommand = (cmd: { action: string; value?: number }) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'command', payload: cmd }));
          }
        };
        const sendRaw = (msg: Record<string, unknown>) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(msg));
          }
        };
        useControlStore.getState().setSendCommand(sendCommand);
        useControlStore.getState().setSendRaw(sendRaw);
      };

      ws.onmessage = (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          handleBinaryMessage(event.data);
        } else {
          handleTextMessage(event.data as string);
        }
      };

      ws.onclose = () => {
        // Reconnect after 2 second delay
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    function handleTextMessage(raw: string) {
      const msg: WSMessage = JSON.parse(raw);
      const store = useRobotStore.getState();

      switch (msg.type) {
        case 'robot_list': {
          const payload = msg.payload as RobotListPayload;
          store.setRobotList(payload.robots);
          break;
        }
        case 'pose_update': {
          const payload = msg.payload as PoseUpdatePayload;
          if (msg.robot_id) {
            store.updatePose(msg.robot_id, payload.position, payload.rotation, payload.tracking_status, payload.body_yaw);
            if (msg.robot_id === 'robot_a') {
              const p = payload.position;
              console.log(`[pose] robot_a: [${p[0].toFixed(2)}, ${p[1].toFixed(2)}, ${p[2].toFixed(2)}]`);
            }
          }
          break;
        }
        case 'cloud_delta': {
          const payload = msg.payload as CloudDeltaPayload;
          if (payload.positions.length > 0) {
            const first = payload.positions[0];
            const last = payload.positions[payload.positions.length - 1];
            console.log(`[cloud] ${payload.positions.length} pts, first=[${first[0].toFixed(2)},${first[1].toFixed(2)},${first[2].toFixed(2)}] last=[${last[0].toFixed(2)},${last[1].toFixed(2)},${last[2].toFixed(2)}]`);
          }
          store.appendCloudDelta(payload.positions, payload.colors);
          break;
        }
        case 'cloud_full': {
          const payload = msg.payload as CloudFullPayload;
          store.setCloudFull(payload.positions, payload.colors);
          break;
        }
        case 'stats': {
          const payload = msg.payload as StatsPayload;
          store.updateStats(payload);
          // Dispatch SLAM + detection metrics to metricsStore (single set()).
          if (payload.slam_metrics) {
            // Phase 6 DET-METRICS-01/02 — detection payload keys added by
            // streaming_viz.py (Plan 08/10) and SC#2 revision 2026-04-15.
            const detectionMetrics =
              ((payload as unknown as { detection_metrics?: Record<string, DetectionMetrics> }).detection_metrics) ?? {};
            const detectionHistory =
              ((payload as unknown as { detection_history?: Record<string, DetectionMetricHistory> }).detection_history) ?? {};
            const detectionGtMetrics =
              ((payload as unknown as { detection_gt_metrics?: Record<string, DetectionGtMetrics> }).detection_gt_metrics) ?? {};
            useMetricsStore.getState().updateAllMetrics(
              payload.slam_metrics as Record<string, SlamMetrics>,
              (payload.baseline as Record<string, SlamMetrics> | null) ?? null,
              (payload.metric_history as Record<string, MetricHistory>) ?? {},
              detectionMetrics,
              detectionHistory,
              detectionGtMetrics,
            );
          }
          break;
        }
        case 'trajectory': {
          const payload = msg.payload as TrajectoryPayload;
          if (msg.robot_id) {
            store.updateTrajectory(
              msg.robot_id,
              payload.positions,
              payload.alphas,
            );
          }
          break;
        }
        case 'detections_3d': {
          // Phase 2 D-18 cutover: envelope (Detection3DEnvelope) replaces legacy detections array
          const payload = msg.payload as Detection3DEnvelope;
          if (msg.robot_id) {
            store.updateDetections(msg.robot_id, payload);
          }
          break;
        }
        case 'detector_restart_complete': {
          const payload = msg.payload as DetectorRestartCompletePayload;
          useDetectorStore.getState().setRestarting(false);
          // Refresh backend + lifter state so activeDisplay/activeLifterDisplay match
          fetchDetectorState();
          const lifter = (payload as DetectorRestartCompletePayload & { lifter?: string }).lifter;
          console.log(`[detector] restart complete: ${payload.backend}${lifter ? ' / lifter=' + lifter : ''}`);
          break;
        }
        case 'detector_param_ack': {
          const payload = msg.payload as DetectorParamAckPayload;
          console.log(`[detector] param ${payload.param}: ${payload.status}`);
          break;
        }
        case 'scene_description': {
          const payload = msg.payload as { text: string; objects: string[] };
          if (msg.robot_id) {
            store.updateSceneDescription(msg.robot_id, payload.text, payload.objects);
          }
          break;
        }
        case 'cloud_configs': {
          const payload = msg.payload as { configs: Record<string, string>; active: string };
          useControlStore.getState().setCloudConfigs(payload.configs, payload.active);
          break;
        }
        case 'cloud_config_ack': {
          const payload = msg.payload as { config: string };
          useControlStore.getState().setActiveCloudConfig(payload.config);
          // Clear existing cloud so new config data replaces it
          store.setCloudFull([], []);
          break;
        }
        case 'slam_param_ack': {
          const payload = msg.payload as { param: string; status: string; value?: unknown };
          if (payload.status === 'unknown_parameter') {
            useSlamStore.getState().setError('Parameter update rejected by backend.');
          }
          console.log(`[slam] param ${payload.param}: ${payload.status}`);
          break;
        }
        case 'slam_restart_complete': {
          useSlamStore.getState().setRestarting(false);
          usePipelineStore.getState().setIsApplying(false);
          fetchSlamState();
          break;
        }
        case 'crash_fallback': {
          const payload = msg.payload as { subsystem?: string; crashed_backend: string; fallback_backend: string };
          const subsystem = payload.subsystem ?? 'slam'; // backward-compat default
          if (subsystem === 'slam') {
            const slamState = useSlamStore.getState();
            slamState.setCrashMessage(
              `Backend ${payload.crashed_backend} crashed, fell back to ICP`
            );
            slamState.setActive('icp', 'ICP Odometry', {});
          } else if (subsystem === 'detector') {
            // Phase 5 DET-MODELS-06 — populate detectorStore.crashMessage so CrashToast renders,
            // and mirror the SLAM pattern by setting active backend to the fallback (yolov11).
            const detectorState = useDetectorStore.getState();
            detectorState.setCrashMessage(
              `Backend ${payload.crashed_backend} crashed, fell back to ${payload.fallback_backend}`
            );
            detectorState.setActive(payload.fallback_backend, 'YOLOv11-nano', {});
          } else {
            console.warn(
              `[crash_fallback] unknown subsystem=${subsystem}: ${payload.crashed_backend} -> ${payload.fallback_backend}`
            );
          }
          break;
        }
        case 'pipeline_status': {
          const payload = msg.payload as {
            node_statuses?: Record<string, string>;
            edge_throughputs?: Record<string, number>;
          };
          const pipelineState = usePipelineStore.getState();
          if (payload.node_statuses) {
            for (const [nodeId, status] of Object.entries(payload.node_statuses)) {
              pipelineState.setNodeStatus(nodeId, status);
            }
          }
          if (payload.edge_throughputs) {
            for (const [edgeId, fps] of Object.entries(payload.edge_throughputs)) {
              pipelineState.setEdgeThroughput(edgeId, fps);
            }
          }
          break;
        }
      }
    }

    function handleBinaryMessage(data: ArrayBuffer) {
      const view = new DataView(data);
      const msgType = view.getUint8(0);

      if (msgType === 0x01 || msgType === 0x02) {
        // Camera frame: [type][id_len:1][robot_id ASCII][JPEG bytes]
        // 0x01 = RGB, 0x02 = depth (colorized)
        const idLen = view.getUint8(1);
        const robotId = new TextDecoder().decode(
          new Uint8Array(data, 2, idLen),
        );
        const jpegData = new Uint8Array(data, 2 + idLen);
        const blob = new Blob([jpegData], { type: 'image/jpeg' });
        const blobUrl = URL.createObjectURL(blob);
        if (msgType === 0x01) {
          useRobotStore.getState().setCameraUrl(robotId, blobUrl);
        } else {
          useRobotStore.getState().setDepthUrl(robotId, blobUrl);
        }
      }
    }

    connect();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [url]);
}
