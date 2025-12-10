package com.example;

import com.google.gson.JsonObject;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandManager;
import net.fabricmc.fabric.api.client.message.v1.ClientReceiveMessageEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ServerboundChatCommandPacket;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;

public class PVP_KIClient implements ClientModInitializer {
	public static IPCManager ipcManager;
	public static JsonObject pendingAction;
	public static final List<String> eventQueue = Collections.synchronizedList(new ArrayList<>());

	@Override
	public void onInitializeClient() {
		// Start default IPC (Agent 1)
		startIPC(9999);

		// Register commands
		ClientCommandRegistrationCallback.EVENT.register((dispatcher, registryAccess) -> {
			// Forward /ki ... to the server
			dispatcher.register(ClientCommandManager.literal("ki")
				.then(ClientCommandManager.argument("args", StringArgumentType.greedyString())
					.executes(context -> {
						String args = StringArgumentType.getString(context, "args");
						Minecraft mc = Minecraft.getInstance();
						if (mc.getConnection() != null) {
							mc.getConnection().send(new ServerboundChatCommandPacket("ki " + args));
							context.getSource().sendFeedback(Component.literal("Sent /ki " + args + " to server"));
						}
						return 1;
					}))
				.executes(context -> {
					Minecraft mc = Minecraft.getInstance();
					if (mc.getConnection() != null) {
						mc.getConnection().send(new ServerboundChatCommandPacket("ki"));
						context.getSource().sendFeedback(Component.literal("Sent /ki to server"));
					}
					return 1;
				}));

			// Client-side /kit create <name> (saves locally without sending to server)
			dispatcher.register(ClientCommandManager.literal("kit")
				.then(ClientCommandManager.literal("create")
					.then(ClientCommandManager.argument("name", StringArgumentType.string())
						.executes(context -> {
							String kitName = StringArgumentType.getString(context, "name");
							Minecraft mc = Minecraft.getInstance();
							if (mc.player != null) {
								ClientKitManager.createKit(kitName, mc.player);
								context.getSource().sendFeedback(Component.literal("Kit '" + kitName + "' saved locally."));
							}
							return 1;
						})))
				.then(ClientCommandManager.literal("list")
					.executes(context -> {
						String kits = String.join(", ", ClientKitManager.getKitNames());
						context.getSource().sendFeedback(Component.literal("Local Kits: " + kits));
						return 1;
					}))
				.then(ClientCommandManager.literal("load")
					.then(ClientCommandManager.argument("name", StringArgumentType.string())
						.executes(context -> {
							String kitName = StringArgumentType.getString(context, "name");
							Minecraft mc = Minecraft.getInstance();
							if (mc.player != null) {
								ClientKitManager.applyKit(kitName, mc.player, false);
								context.getSource().sendFeedback(Component.literal("Kit '" + kitName + "' loaded."));
							}
							return 1;
						})))
				.then(ClientCommandManager.literal("delete")
					.then(ClientCommandManager.argument("name", StringArgumentType.string())
						.executes(context -> {
							String kitName = StringArgumentType.getString(context, "name");
							if (ClientKitManager.deleteKit(kitName)) {
								context.getSource().sendFeedback(Component.literal("Kit '" + kitName + "' deleted."));
							} else {
								context.getSource().sendFeedback(Component.literal("Kit '" + kitName + "' not found."));
							}
							return 1;
						})))
				.then(ClientCommandManager.literal("edit")
					.then(ClientCommandManager.argument("name", StringArgumentType.string())
						.executes(context -> {
							String kitName = StringArgumentType.getString(context, "name");
							Minecraft mc = Minecraft.getInstance();
							if (mc.player != null) {
								ClientKitManager.deleteKit(kitName);
								ClientKitManager.createKit(kitName, mc.player);
								context.getSource().sendFeedback(Component.literal("Kit '" + kitName + "' updated with current inventory."));
							}
							return 1;
						}))));

			// Client-side /agent <1|2> (switches IPC port locally)
			dispatcher.register(ClientCommandManager.literal("agent")
				.then(ClientCommandManager.argument("id", IntegerArgumentType.integer(1, 2))
					.executes(context -> {
						int id = IntegerArgumentType.getInteger(context, "id");
						int port = (id == 1) ? 9999 : 10000;
						
						startIPC(port);
						
						context.getSource().sendFeedback(Component.literal("Switched to Agent " + id + " (Port " + port + ")"));
						return 1;
					})));
		});

		// Register Chat Listener for Events
		ClientReceiveMessageEvents.GAME.register((message, overlay) -> {
			String text = message.getString();
			if (text.startsWith("EVENT:")) {
				eventQueue.add(text);
			}
		});
	}

	private void startIPC(int port) {
		if (ipcManager != null) {
			ipcManager.stop();
		}
		ipcManager = new IPCManager(port);
		new Thread(ipcManager).start();
	}
}