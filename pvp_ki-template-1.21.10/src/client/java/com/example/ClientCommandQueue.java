package com.example;

import java.util.LinkedList;
import java.util.Queue;

/**
 * Client-side queue for IPC commands to be injected into frame headers
 * Commands like START, STOP, RESET are queued here and sent with the next frame to Python
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
