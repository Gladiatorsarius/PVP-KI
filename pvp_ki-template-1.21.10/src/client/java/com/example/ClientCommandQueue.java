package com.example;

import java.util.LinkedList;
import java.util.Queue;

/**
 * Legacy queue for client-side IPC command headers.
 * Protocol v1 keeps reset/combat authority server-side and disables this path by default.
 */
public class ClientCommandQueue {
    private static final Queue<IPCCommand> queue = new LinkedList<>();

    public static class IPCCommand {
        public String type;
        public String data;

        public IPCCommand(String type, String data) {
            this.type = type;
            this.data = data;
        }
    }

    public static void enqueue(String type, String data) {
        if (!PVP_KIClient.ENABLE_LEGACY_CLIENT_IPC) {
            return;
        }
        synchronized (queue) {
            queue.add(new IPCCommand(type, data));
        }
    }

    public static IPCCommand dequeue() {
        synchronized (queue) {
            return queue.poll();
        }
    }

    public static boolean isEmpty() {
        synchronized (queue) {
            return queue.isEmpty();
        }
    }
}
