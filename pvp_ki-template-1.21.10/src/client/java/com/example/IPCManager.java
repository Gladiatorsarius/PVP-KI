package com.example;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;

import java.io.*;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

public class IPCManager implements Runnable {
    private final int port;
    private final Gson gson = new Gson();
    private volatile boolean running = true;
    private volatile boolean active = false;
    private DataOutputStream currentOut;

    public IPCManager(int port) {
        this.port = port;
    }

    @Override
    public void run() {
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println("IPC Server started on port " + port);
            while (running) {
                try (Socket clientSocket = serverSocket.accept();
                     DataOutputStream out = new DataOutputStream(clientSocket.getOutputStream());
                     DataInputStream in = new DataInputStream(clientSocket.getInputStream())) {

                    currentOut = out;
                    active = true;
                    System.out.println("Client connected");

                    while (running) {
                        // Read Length (2 bytes unsigned short)
                        int length = in.readUnsignedShort();
                        if (length == 0) continue;

                        // Read JSON bytes
                        byte[] jsonBytes = new byte[length];
                        in.readFully(jsonBytes);
                        String actionJson = new String(jsonBytes, StandardCharsets.UTF_8);

                        JsonObject actions = gson.fromJson(actionJson, JsonObject.class);

                        // Set pending action for Mixin to apply
                        PVP_KIClient.pendingAction = actions;

                        // Check for reset (handled immediately if possible, or via chat)
                        if (actions.has("reset")) {
                            // Handle reset logic if needed
                        }
                    }
                } catch (EOFException e) {
                    System.out.println("Client disconnected");
                } catch (Exception e) {
                    System.err.println("Error in IPC: " + e.getMessage());
                } finally {
                    active = false;
                    currentOut = null;
                }
            }
        } catch (Exception e) {
            System.err.println("IPC Server error: " + e.getMessage());
        }
    }

    public void sendFrame(byte[] frameBytes, Map<String, Object> state) {
        if (currentOut != null) {
            try {
                // Add Events
                synchronized (PVP_KIClient.eventQueue) {
                    state.put("events", new java.util.ArrayList<>(PVP_KIClient.eventQueue));
                    PVP_KIClient.eventQueue.clear();
                }

                // Check for pending server commands and inject into header
                CommandQueue.ServerCommand cmd = CommandQueue.dequeue();
                if (cmd != null) {
                    state.put("cmd_type", cmd.type);
                    state.put("cmd_data", cmd.data);
                }
                
                // Inject player_name and agent_id for agent mapping
                net.minecraft.client.Minecraft mc = net.minecraft.client.Minecraft.getInstance();
                if (mc.player != null) {
                    state.put("player_name", mc.player.getName().getString());
                    state.put("agent_id", PVP_KIClient.currentAgentId);
                }
                
                // Inject teams data (map of player names to team/enemy/null)
                Map<String, String> teams = new HashMap<>();
                synchronized (PVP_KIClient.teamMembers) {
                    // Mark team members as "team"
                    for (String teamMember : PVP_KIClient.teamMembers) {
                        teams.put(teamMember, "team");
                    }
                    
                    // Mark other visible players as "enemy"
                    if (mc.level != null) {
                        for (net.minecraft.world.entity.player.Player player : mc.level.players()) {
                            String playerName = player.getName().getString();
                            // Skip if already marked as team member
                            if (!teams.containsKey(playerName)) {
                                // Skip self
                                if (mc.player != null && !playerName.equals(mc.player.getName().getString())) {
                                    teams.put(playerName, "enemy");
                                }
                            }
                        }
                    }
                }
                state.put("teams", teams);

                // Add body length
                state.put("bodyLength", frameBytes.length);

                String stateJson = gson.toJson(state);
                byte[] jsonBytes = stateJson.getBytes(StandardCharsets.UTF_8);

                // Send Header Length (4 bytes)
                currentOut.writeInt(jsonBytes.length);
                // Send Header
                currentOut.write(jsonBytes);
                // Send Body
                currentOut.write(frameBytes);
                currentOut.flush();
            } catch (Exception e) {
                System.err.println("Error sending frame: " + e.getMessage());
                active = false; // Assume disconnected
            }
        }
    }

    public boolean isActive() {
        return active;
    }

    public void stop() {
        running = false;
    }
}
