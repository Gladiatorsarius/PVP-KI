package com.example;

import com.google.gson.JsonObject;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandManager;
import net.fabricmc.fabric.api.client.message.v1.ClientReceiveMessageEvents;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ServerboundChatCommandPacket;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;

public class PVP_KIClient implements ClientModInitializer {
	public static IPCManager ipcManager;
	public static JsonObject pendingAction;
	public static final List<String> eventQueue = Collections.synchronizedList(new ArrayList<>());
	public static final List<String> teamMembers = Collections.synchronizedList(new ArrayList<>());
	public static int currentAgentId = 1; // Current agent this client is mapped to

	@Override
	public void onInitializeClient() {
		// Start default IPC (Agent 1)
		startIPC(9999);
		
		// Register nametag overlay renderer
		NametagOverlayRenderer.register();
		
		// Register client-side event detection
		registerClientEvents();		// Register commands
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

// Toggle nametag overlay with /name
		dispatcher.register(ClientCommandManager.literal("name")
				.executes(context -> {
					boolean newState = !NametagOverlayRenderer.isEnabled();
					NametagOverlayRenderer.setEnabled(newState);
					context.getSource().sendFeedback(Component.literal(
						"Nametag overlays: " + (newState ? "ON" : "OFF")
					));
					return 1;
				}));

		// Debug command /testframe to check IPC status and frame sending
		dispatcher.register(ClientCommandManager.literal("testframe")
				.executes(context -> {
					if (ipcManager != null && ipcManager.isActive()) {
						Minecraft mc = Minecraft.getInstance();
						if (mc.player != null) {
							context.getSource().sendFeedback(Component.literal("IPC Active - Python connected on port " + (9999 + currentAgentId - 1)));
							context.getSource().sendFeedback(Component.literal("Frames are being sent automatically"));
						} else {
							context.getSource().sendFeedback(Component.literal("No player - cannot send frames"));
						}
					} else {
						context.getSource().sendFeedback(Component.literal("IPC not active - Python not connected"));
					}
					return 1;
				}));

		// Client-side reward control (does not rely on server mod)
		dispatcher.register(ClientCommandManager.literal("reward")
			.then(ClientCommandManager.literal("start")
				.executes(context -> {
					ClientCommandQueue.enqueue("START", "Reward tracking started");
					context.getSource().sendFeedback(Component.literal("[reward] START sent to Python"));
					return 1;
				}))
			.then(ClientCommandManager.literal("stop")
				.executes(context -> {
					ClientCommandQueue.enqueue("STOP", "Reward tracking stopped");
					context.getSource().sendFeedback(Component.literal("[reward] STOP sent to Python"));
					return 1;
				}))
			.then(ClientCommandManager.literal("reset")
				.executes(context -> {
					ClientCommandQueue.enqueue("RESET", "Rewards reset to zero");
					context.getSource().sendFeedback(Component.literal("[reward] RESET sent to Python"));
					return 1;
				})));

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
						})))
				.then(ClientCommandManager.literal("sync")
					.executes(context -> {
						Minecraft mc = Minecraft.getInstance();
						if (mc.getConnection() == null) {
							context.getSource().sendFeedback(Component.literal("Not connected to a server."));
							return 0;
						}
						if (mc.player == null) {
							return 0;
						}
						
						var allKits = ClientKitManager.getAllKits();
						if (allKits.isEmpty()) {
							context.getSource().sendFeedback(Component.literal("No client kits to sync."));
							return 0;
						}
						
						// Clear all server kits first
						mc.getConnection().send(new ServerboundChatCommandPacket("ki clearkits"));
						
						// Sync each kit by loading it and creating it on server
						int synced = 0;
						for (String kitName : allKits.keySet()) {
							// Load the kit inventory
							ClientKitManager.applyKit(kitName, mc.player, false);
							// Send createkit command to save it on server
							String command = "ki createkit " + kitName;
							mc.getConnection().send(new ServerboundChatCommandPacket(command));
							synced++;
						}
						
						context.getSource().sendFeedback(Component.literal("Cleared server kits and synced " + synced + " kit(s) from client!"));
						return 1;
					})));

			// Client-side /agent <id> (switches IPC port locally, supports unlimited agents)
			dispatcher.register(ClientCommandManager.literal("agent")
				.then(ClientCommandManager.argument("id", IntegerArgumentType.integer(1, 100))
					.executes(context -> {
						int id = IntegerArgumentType.getInteger(context, "id");
						// Agent 1 = port 9999, Agent 2 = port 10001, Agent 3 = 10002, etc.
						// Command port is 9998 (no longer conflicts)
						int port = (id == 1) ? 9999 : (10000 + id - 1);
						
						currentAgentId = id;
						startIPC(port);
						
						// Send MAP command to Python (player_name, agent_id will be injected in headers)
						Minecraft mc = Minecraft.getInstance();
						if (mc.player != null) {
							// Headers will include player_name and agent_id automatically
						}
						
						context.getSource().sendFeedback(Component.literal("Switched to Agent " + id + " (Port " + port + ")"));
					return 1;
				})));			// Client-side /clientteam commands (only when NO server teams exist)
			if (!ClientTeamManager.hasServerTeams()) {
				dispatcher.register(ClientCommandManager.literal("clientteam")
					.then(ClientCommandManager.literal("add")
						.then(ClientCommandManager.argument("player", StringArgumentType.string())
							.executes(context -> {
								String playerName = StringArgumentType.getString(context, "player");
								if (!teamMembers.contains(playerName)) {
									teamMembers.add(playerName);
									context.getSource().sendFeedback(Component.literal("Added " + playerName + " to local team"));
								} else {
									context.getSource().sendFeedback(Component.literal(playerName + " is already in local team"));
								}
								return 1;
							})))
					.then(ClientCommandManager.literal("remove")
						.then(ClientCommandManager.argument("player", StringArgumentType.string())
							.executes(context -> {
								String playerName = StringArgumentType.getString(context, "player");
								if (teamMembers.remove(playerName)) {
									context.getSource().sendFeedback(Component.literal("Removed " + playerName + " from local team"));
								} else {
									context.getSource().sendFeedback(Component.literal(playerName + " is not in local team"));
								}
								return 1;
							})))
					.then(ClientCommandManager.literal("list")
						.executes(context -> {
							if (teamMembers.isEmpty()) {
								context.getSource().sendFeedback(Component.literal("Local team is empty"));
							} else {
								context.getSource().sendFeedback(Component.literal("Local team members: " + String.join(", ", teamMembers)));
							}
							return 1;
						}))
					.then(ClientCommandManager.literal("clear")
						.executes(context -> {
							teamMembers.clear();
							context.getSource().sendFeedback(Component.literal("Local team cleared"));
							return 1;
						})));
			} else {
				// Server teams exist - don't register clientteam, show message instead
				dispatcher.register(ClientCommandManager.literal("clientteam")
					.executes(context -> {
						context.getSource().sendFeedback(Component.literal("Server teams are active. Use /team instead."));
						return 1;
					}));
			}
		});

		// Register Chat Listener for Events, Team Data, and Death Messages
		ClientReceiveMessageEvents.GAME.register((message, overlay) -> {
			String text = message.getString();
			
			// Handle explicit EVENT: messages
			if (text.startsWith("EVENT:")) {
				eventQueue.add(text);
			}
			
			// Listen for team data from server
			if (text.startsWith("TEAMDATA:")) {
				String[] parts = text.split(":", 3);
				if (parts.length >= 3) {
					String teamName = parts[1];
					String members = parts[2];
					String[] playerNames = members.isEmpty() ? new String[0] : members.split(",");
					ClientTeamManager.updateTeam(teamName, playerNames);
				}
			}
			
			// Parse death messages from chat (works on any server!)
			// Common death message patterns:
			// "Player was slain by Killer"
			// "Player was shot by Killer"
			// "Player was killed by Killer"
			// "Player died"
			// "Player fell from a high place"
			// etc.
			parseChatDeathMessage(text);
		});
	}

	private void parseChatDeathMessage(String text) {
		// Death message patterns - Minecraft uses specific phrases
		String[] deathPhrases = {
			" was slain by ",
			" was shot by ",
			" was killed by ",
			" was blown up by ",
			" was squashed by ",
			" was fireballed by ",
			" was stung to death by ",
			" was obliterated by ",
			" was pummeled by ",
			" was impaled by ",
			" died",
			" drowned",
			" fell from a high place",
			" fell off a ladder",
			" fell while climbing",
			" was doomed to fall",
			" blew up",
			" burned to death",
			" went up in flames",
			" walked into fire",
			" suffocated in a wall",
			" was squished too much",
			" experienced kinetic energy",
			" removed an elytra while flying",
			" starved to death",
			" was pricked to death",
			" hit the ground too hard",
			" fell out of the world",
			" withered away"
		};
		
		for (String phrase : deathPhrases) {
			if (text.contains(phrase)) {
				// Extract victim and killer (if applicable)
				String victim = null;
				String killer = "Environment";
				
				// Check for PvP deaths (has "by" in phrase)
				if (phrase.contains(" by ")) {
					int byIndex = text.indexOf(phrase);
					if (byIndex > 0) {
						victim = text.substring(0, byIndex).trim();
						int killerStart = byIndex + phrase.length();
						String remaining = text.substring(killerStart);
						// Extract killer name (up to first space or special char)
						int spaceIndex = remaining.indexOf(" ");
						killer = spaceIndex > 0 ? remaining.substring(0, spaceIndex) : remaining.trim();
					}
				} else {
					// Environmental death
					int phraseIndex = text.indexOf(phrase);
					if (phraseIndex > 0) {
						victim = text.substring(0, phraseIndex).trim();
					}
				}
				
				if (victim != null && !victim.isEmpty()) {
					String event = "EVENT:DEATH:" + victim + ":" + killer;
					synchronized (eventQueue) {
						eventQueue.add(event);
					}
					System.out.println("[Client Death Detection] " + event);
				}
				break;
			}
		}
	}

	private void startIPC(int port) {
		if (ipcManager != null) {
			ipcManager.stop();
		}
		ipcManager = new IPCManager(port);
		new Thread(ipcManager).start();
	}
	
	private void registerClientEvents() {
		// Client-side attack detection
		AttackEntityCallback.EVENT.register((player, world, hand, entity, hitResult) -> {
			if (player instanceof Player && entity instanceof Player) {
				String attacker = player.getName().getString();
				String target = entity.getName().getString();
				String event = "EVENT:HIT:" + attacker + ":" + target;
				synchronized (eventQueue) {
					eventQueue.add(event);
				}
				System.out.println("[Client] " + event);
			}
			return InteractionResult.PASS;
		});
		
		// Note: Client-side death detection is handled via health monitoring in IPCManager
		// Full AFTER_DEATH event requires server-side mod, so we rely on health=0 detection
	}
}