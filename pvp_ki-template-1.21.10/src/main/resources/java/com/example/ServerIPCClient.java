package com.example;

import com.google.gson.Gson;
import com.google.gson.JsonObject;

import java.io.DataOutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * Server-side IPC client for authoritative Protocol v1 event/reset signaling
 * from the Minecraft server mod to the training side command bridge.
 */
public class ServerIPCClient {
    private static final int COMMAND_PORT = 9998; // Dedicated command channel (moved from 10001)
    private static final Gson GSON = new Gson();

    /**
     * Send a server-authoritative event/reset command to the bridge socket.
     */
    public static void sendCommand(String eventType, String details) {
        try (Socket socket = new Socket("127.0.0.1", COMMAND_PORT);
             DataOutputStream out = new DataOutputStream(socket.getOutputStream())) {

            JsonObject msg = new JsonObject();
            msg.addProperty("type", eventType);
            msg.addProperty("data", details);

            byte[] payload = GSON.toJson(msg).getBytes(StandardCharsets.UTF_8);
            out.writeInt(payload.length);
            out.write(payload);
            out.flush();
            System.out.println("[ServerIPC] Sent command: " + eventType + " - " + details);
        } catch (Exception e) {
            System.err.println("[ServerIPC] Failed to send command: " + e.getMessage());
        }
    }

    public static boolean isConnected() {
        return true; // fire-and-forget per command
    }
}
