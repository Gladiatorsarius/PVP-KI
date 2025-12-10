package com.example;

import com.google.gson.Gson;
import com.google.gson.JsonObject;

import java.io.*;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * Server-side IPC client to send commands to Python training loop
 */
public class ServerIPCClient {
    private static final Gson GSON = new Gson();
    private static Socket socket = null;
    private static DataOutputStream out = null;
    private static DataInputStream in = null;
    private static final Object lock = new Object();

    /**
     * Send a command to Python via IPC
     */
    public static void sendCommand(String eventType, String details) {
        synchronized (lock) {
            try {
                // If not connected, try to connect
                if (socket == null || socket.isClosed()) {
                    connect();
                }

                if (out != null && socket != null && !socket.isClosed()) {
                    JsonObject msg = new JsonObject();
                    msg.addProperty("type", eventType);
                    msg.addProperty("data", details);

                    String json = GSON.toJson(msg);
                    byte[] jsonBytes = json.getBytes(StandardCharsets.UTF_8);

                    // Send Length (4 bytes int)
                    out.writeInt(jsonBytes.length);
                    // Send JSON
                    out.write(jsonBytes);
                    out.flush();

                    System.out.println("[ServerIPC] Sent: " + eventType + " - " + details);
                }
            } catch (IOException e) {
                System.err.println("[ServerIPC] Error sending command: " + e.getMessage());
                disconnect();
            }
        }
    }

    /**
     * Connect to Python IPC server (port 9999 or 10000 depending on active agent)
     */
    private static void connect() {
        try {
            // Try port 9999 first (Agent 1), then 10000 (Agent 2)
            int[] ports = {9999, 10000};
            for (int port : ports) {
                try {
                    socket = new Socket("localhost", port);
                    out = new DataOutputStream(socket.getOutputStream());
                    in = new DataInputStream(socket.getInputStream());
                    System.out.println("[ServerIPC] Connected to Python on port " + port);
                    return;
                } catch (IOException e) {
                    // Try next port
                }
            }
            System.err.println("[ServerIPC] Could not connect to Python on ports 9999 or 10000");
        } catch (Exception e) {
            System.err.println("[ServerIPC] Connection failed: " + e.getMessage());
        }
    }

    /**
     * Disconnect from Python
     */
    public static void disconnect() {
        synchronized (lock) {
            try {
                if (socket != null && !socket.isClosed()) socket.close();
                if (out != null) out.close();
                if (in != null) in.close();
            } catch (IOException e) {
                System.err.println("[ServerIPC] Error disconnecting: " + e.getMessage());
            }
            socket = null;
            out = null;
            in = null;
        }
    }

    /**
     * Check if connected
     */
    public static boolean isConnected() {
        return socket != null && !socket.isClosed() && out != null;
    }
}
