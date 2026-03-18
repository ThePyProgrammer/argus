import { useEffect, useRef } from 'react';
import { useRobotStore } from '../stores/robotStore';
import { useControlStore } from '../stores/controlStore';
import type {
  WSMessage,
  RobotListPayload,
  PoseUpdatePayload,
  CloudDeltaPayload,
  CloudFullPayload,
  StatsPayload,
  TrajectoryPayload,
} from '../utils/messageTypes';

/**
 * WebSocket hook that connects to the C2 backend and dispatches
 * incoming messages to the appropriate Zustand stores.
 */
export function useWebSocket(url: string = 'ws://localhost:8000/ws'): void {
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
        useControlStore.getState().setSendCommand(sendCommand);
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
            store.updatePose(msg.robot_id, payload.position, payload.rotation);
          }
          break;
        }
        case 'cloud_delta': {
          const payload = msg.payload as CloudDeltaPayload;
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
      }
    }

    function handleBinaryMessage(data: ArrayBuffer) {
      const view = new DataView(data);
      const msgType = view.getUint8(0);

      if (msgType === 0x01) {
        // Camera frame: [0x01][id_len:1][robot_id ASCII][JPEG bytes]
        const idLen = view.getUint8(1);
        const robotId = new TextDecoder().decode(
          new Uint8Array(data, 2, idLen),
        );
        const jpegData = new Uint8Array(data, 2 + idLen);
        const blob = new Blob([jpegData], { type: 'image/jpeg' });
        const blobUrl = URL.createObjectURL(blob);
        useRobotStore.getState().setCameraUrl(robotId, blobUrl);
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
