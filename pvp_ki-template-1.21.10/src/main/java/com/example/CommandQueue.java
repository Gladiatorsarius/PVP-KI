package com.example;

import java.util.LinkedList;
import java.util.Queue;

/**
 * Queue for server commands to be injected into IPC headers
 */
public class CommandQueue {
    private static final Queue<ServerCommand> queue = new LinkedList<>();

    public static class ServerCommand {
        public String type;
        public String data;

        public ServerCommand(String type, String data) {
            this.type = type;
            this.data = data;
        }
    }

    public static void enqueue(String type, String data) {
        synchronized (queue) {
            queue.add(new ServerCommand(type, data));
        }
    }

    public static ServerCommand dequeue() {
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
