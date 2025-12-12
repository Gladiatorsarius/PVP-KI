package com.example;

import com.google.gson.Gson;
import com.google.gson.JsonObject;

import java.io.DataOutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * Server-side IPC client to send commands to Python training loop on a dedicated command port.
 */
public class ServerIPCClient {
    private static final int COMMAND_PORT = 10001; // Dedicated command channel
    private static final Gson GSON = new Gson();

    /**
     * Send a command to Python via command socket.
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
