package com.example;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.commands.arguments.selector.EntitySelector;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.builder.RequiredArgumentBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.util.HashSet;

import com.mojang.brigadier.arguments.BoolArgumentType;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.chunk.LevelChunk;

public class PVP_KI implements ModInitializer {
	public static final String MOD_ID = "pvp_ki";
	public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);
	public static Process pythonProcess = null;

	@Override
	public void onInitialize() {
		LOGGER.info("Initializing PVP_KI Server Mod");
		KitManager.loadKits();
		SettingsManager.loadSettings();
		TeamManager.loadTeams();

		// Shutdown Hook for Python Process
		Runtime.getRuntime().addShutdownHook(new Thread(() -> {
			if (pythonProcess != null && pythonProcess.isAlive()) {
				LOGGER.info("Stopping Python process...");
				pythonProcess.destroy();
			}
		}));

		// Register Event Listeners
		registerEvents();

		// Register commands (single unified tree to avoid parsing conflicts)
		CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) -> {
			LOGGER.info("Registering /ki commands - Environment: " + environment);
	LiteralArgumentBuilder<CommandSourceStack> kiRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("ki")
		.requires(source -> true); // Allow all players

		// /ki start - Start reward tracking
			kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("start")
				.executes(context -> {
					try {
						ServerIPCClient.sendCommand("START", "Reward tracking started");
						context.getSource().sendSuccess(() -> Component.literal("Reward tracking started"), false);
					} catch (Exception e) {
						context.getSource().sendFailure(Component.literal("Error: " + e.getMessage()));
					}
					return 1;
				}));

			// /ki stop - Stop reward tracking
			kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("stop")
				.executes(context -> {
					try {
						ServerIPCClient.sendCommand("STOP", "Reward tracking stopped");
						context.getSource().sendSuccess(() -> Component.literal("Reward tracking stopped"), false);
					} catch (Exception e) {
						context.getSource().sendFailure(Component.literal("Error: " + e.getMessage()));
					}
					return 1;
				}));

		// Server-side /ki createkit <name> - creates kits for /ki reset command
		kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("createkit")
			.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("name", StringArgumentType.string())
				.executes(context -> {
					try {
						String name = StringArgumentType.getString(context, "name");
						LOGGER.info("Creating server kit: " + name);
						ServerPlayer player = context.getSource().getPlayerOrException();
						KitManager.createKit(name, player);
						context.getSource().sendSuccess(() -> Component.literal("Server kit '" + name + "' saved for /ki reset."), false);
						return 1;
					} catch (Exception e) {
						LOGGER.error("Error creating kit", e);
						context.getSource().sendFailure(Component.literal("Error: " + e.getMessage()));
						return 0;
					}
				})));
	// /ki clearkits - clears all server kits
	kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("clearkits")
		.executes(context -> {
			KitManager.clearAllKits();
			context.getSource().sendSuccess(() -> Component.literal("Cleared all server kits."), false);
			return 1;
		}));
		// /ki reset <p1> <p2> <kit> [shuffle]
			kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("reset")
				.then(RequiredArgumentBuilder.<CommandSourceStack, EntitySelector>argument("p1", EntityArgument.player())
					.then(RequiredArgumentBuilder.<CommandSourceStack, EntitySelector>argument("p2", EntityArgument.player())
						.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("kit", StringArgumentType.string())
							.executes(context -> resetCommand(context, false))
							.then(RequiredArgumentBuilder.<CommandSourceStack, Boolean>argument("shuffle", BoolArgumentType.bool())
								.executes(context -> resetCommand(context, true)))))));

			// /ki settings commands
			LiteralArgumentBuilder<CommandSourceStack> settingsRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("settings");
			
			// /ki settings show
			settingsRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("show")
				.executes(context -> {
					context.getSource().sendSuccess(() -> Component.literal("=== PVP KI Settings ==="), false);
					context.getSource().sendSuccess(() -> Component.literal("Nametags: " + (SettingsManager.showTeamNametags ? "ON" : "OFF")), false);
					context.getSource().sendSuccess(() -> Component.literal("Allowed Biomes: " + 
						(SettingsManager.allowedBiomes.isEmpty() ? "All" : String.join(", ", SettingsManager.allowedBiomes))), false);
					context.getSource().sendSuccess(() -> Component.literal("Blocked Biomes: " + 
						(SettingsManager.blockedBiomes.isEmpty() ? "None" : String.join(", ", SettingsManager.blockedBiomes))), false);
					return 1;
				}));
			
			// /ki settings nametags <on|off>
			settingsRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("nametags")
				.then(LiteralArgumentBuilder.<CommandSourceStack>literal("on")
					.executes(context -> {
						SettingsManager.showTeamNametags = true;
						SettingsManager.saveSettings();
						context.getSource().sendSuccess(() -> Component.literal("Team nametags enabled"), false);
						return 1;
					}))
				.then(LiteralArgumentBuilder.<CommandSourceStack>literal("off")
					.executes(context -> {
						SettingsManager.showTeamNametags = false;
						SettingsManager.saveSettings();
						context.getSource().sendSuccess(() -> Component.literal("Team nametags disabled"), false);
						return 1;
					})));
			
			// /ki settings biome commands
			LiteralArgumentBuilder<CommandSourceStack> biomeRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("biome");
			
			// /ki settings biome allow <biome>
			biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("allow")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("biome", StringArgumentType.string())
					.executes(context -> {
						String biome = StringArgumentType.getString(context, "biome");
						SettingsManager.allowedBiomes.add(biome);
						SettingsManager.saveSettings();
						context.getSource().sendSuccess(() -> Component.literal("Added '" + biome + "' to allowed biomes"), false);
						return 1;
					})));
			
			// /ki settings biome block <biome>
			biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("block")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("biome", StringArgumentType.string())
					.executes(context -> {
						String biome = StringArgumentType.getString(context, "biome");
						SettingsManager.blockedBiomes.add(biome);
						SettingsManager.saveSettings();
						context.getSource().sendSuccess(() -> Component.literal("Added '" + biome + "' to blocked biomes"), false);
						return 1;
					})));
			
			// /ki settings biome clear
			biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("clear")
				.executes(context -> {
					SettingsManager.allowedBiomes.clear();
					SettingsManager.blockedBiomes.clear();
					SettingsManager.saveSettings();
					context.getSource().sendSuccess(() -> Component.literal("Cleared all biome filters"), false);
					return 1;
				}));
			
			// /ki settings biome list
			biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("list")
				.executes(context -> {
					context.getSource().sendSuccess(() -> Component.literal("Allowed Biomes: " + 
						(SettingsManager.allowedBiomes.isEmpty() ? "All" : String.join(", ", SettingsManager.allowedBiomes))), false);
					context.getSource().sendSuccess(() -> Component.literal("Blocked Biomes: " + 
						(SettingsManager.blockedBiomes.isEmpty() ? "None" : String.join(", ", SettingsManager.blockedBiomes))), false);
					return 1;
				}));
			
			settingsRoot.then(biomeRoot);
			kiRoot.then(settingsRoot);

			// Server-side /team commands
			LiteralArgumentBuilder<CommandSourceStack> teamRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("team");

			// /team create <name>
			teamRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("create")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("name", StringArgumentType.string())
					.executes(context -> {
						String teamName = StringArgumentType.getString(context, "name");
						TeamManager.createTeam(teamName);
						broadcastTeamUpdate(context.getSource());
						context.getSource().sendSuccess(() -> Component.literal("Created team '" + teamName + "'"), true);
						return 1;
					})));

		// /team delete <name> - REMOVED (use /team remove instead)

		// /team add [team name] [player name]
			teamRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("add")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("team", StringArgumentType.string())
					.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("player", StringArgumentType.string())
						.executes(context -> {
							String teamName = StringArgumentType.getString(context, "team");
							String playerName = StringArgumentType.getString(context, "player");
							TeamManager.addPlayerToTeam(teamName, playerName);
							broadcastTeamUpdate(context.getSource());
							context.getSource().sendSuccess(() -> Component.literal("Added " + playerName + " to team '" + teamName + "'"), true);
							return 1;
						}))));

		// /team remove team [team name] - removes entire team
		// /team remove player [player name] - removes player from all teams
		teamRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("remove")
			.then(LiteralArgumentBuilder.<CommandSourceStack>literal("team")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("teamName", StringArgumentType.string())
					.executes(context -> {
						String teamName = StringArgumentType.getString(context, "teamName");
						boolean removed = TeamManager.deleteTeam(teamName);
						if (removed) {
						broadcastTeamUpdate(context.getSource());
							context.getSource().sendSuccess(() -> Component.literal("Removed team '" + teamName + "'"), true);
							return 1;
						} else {
							context.getSource().sendFailure(Component.literal("Team '" + teamName + "' not found"));
							return 0;
						}
					})))
			.then(LiteralArgumentBuilder.<CommandSourceStack>literal("player")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("playerName", StringArgumentType.string())
					.executes(context -> {
						String playerName = StringArgumentType.getString(context, "playerName");
						boolean removed = TeamManager.removePlayerByName(playerName);
						if (removed) {
						broadcastTeamUpdate(context.getSource());
							context.getSource().sendSuccess(() -> Component.literal("Removed player '" + playerName + "' from all teams"), true);
							return 1;
						} else {
							context.getSource().sendFailure(Component.literal("Player '" + playerName + "' not found in any team"));
							return 0;
						}
					}))));

		// /team list
			teamRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("list")
				.executes(context -> {
					var allTeams = TeamManager.getAllTeams();
					if (allTeams.isEmpty()) {
						context.getSource().sendSuccess(() -> Component.literal("No teams exist"), false);
					} else {
						context.getSource().sendSuccess(() -> Component.literal("=== Teams ==="), false);
						for (String teamName : allTeams.keySet()) {
							String members = String.join(", ", allTeams.get(teamName));
							context.getSource().sendSuccess(() -> Component.literal(teamName + ": " + members), false);
						}
					}
					return 1;
				}));

			// /team clear
			teamRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("clear")
				.executes(context -> {
					for (String teamName : new HashSet<>(TeamManager.getTeamNames())) {
						TeamManager.deleteTeam(teamName);
					}
					broadcastTeamUpdate(context.getSource());
					context.getSource().sendSuccess(() -> Component.literal("All teams cleared"), true);
					return 1;
				}));

			dispatcher.register(kiRoot);
			
			// Remove vanilla /team command and register our custom one
			dispatcher.getRoot().getChildren().removeIf(node -> node.getName().equals("team"));
			dispatcher.register(teamRoot);
		});
	}

	private int resetCommand(com.mojang.brigadier.context.CommandContext<CommandSourceStack> context, boolean hasShuffle) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
		ServerPlayer p1 = EntityArgument.getPlayer(context, "p1");
		ServerPlayer p2 = EntityArgument.getPlayer(context, "p2");
		String kitName = StringArgumentType.getString(context, "kit");
		boolean shuffle = hasShuffle && BoolArgumentType.getBool(context, "shuffle");

		if ("random".equalsIgnoreCase(kitName)) {
			kitName = KitManager.getRandomKit();
		}

		// Find fresh location with unmodified chunks and matching biome filters
		ServerLevel level = (ServerLevel) p1.level();
		double x, z;
		int attempts = 0;
		boolean foundSuitable = false;
		
		do {
			x = (Math.random() * 2000000) - 1000000;
			z = (Math.random() * 2000000) - 1000000;
			attempts++;
			
			LevelChunk chunk = level.getChunk((int)x >> 4, (int)z >> 4);
			
		// Check if chunk is unmodified: inhabited time == 0 AND no block entities
		if (chunk.getInhabitedTime() == 0 && chunk.getBlockEntities().isEmpty()) {
			// Check biome filtering - skip for now (1.21.11 API changes)
			String biomeName = "plains"; // Default to plains biome
			if (SettingsManager.isBiomeAllowed(biomeName)) {
				foundSuitable = true;
				break;
			}
		}
	} while (attempts < 100); // Increased attempts for biome filtering
	
	if (!foundSuitable) {
		context.getSource().sendFailure(Component.literal("Could not find suitable location after 100 attempts"));
		return 0;
	}

		// Find safe surface Y (first solid block from top)
		double y = 63; // Default to world height
		for (int checkY = 320; checkY >= 0; checkY--) {
			net.minecraft.world.level.block.state.BlockState state = level.getBlockState(new BlockPos((int)x, checkY, (int)z));
			if (!state.isAir()) {
				y = checkY + 1.8; // 1.8 blocks above solid ground (player eye height)
				break;
			}
		}

		// Find safe surface Y for p2 at offset position
		double y2 = 63;
		for (int checkY = 320; checkY >= 0; checkY--) {
			net.minecraft.world.level.block.state.BlockState state = level.getBlockState(new BlockPos((int)x + 10, checkY, (int)z));
			if (!state.isAir()) {
				y2 = checkY + 1.8;
				break;
			}
		}

		resetPlayer(p1, x, y, z, kitName, shuffle);
		resetPlayer(p2, x + 10, y2, z, kitName, shuffle);

		// Send RESET event to Python
		ServerIPCClient.sendCommand("RESET", p1.getName().getString() + "," + p2.getName().getString());

		String finalKit = kitName;
		double finalX = x;
		double finalZ = z;
		context.getSource().sendSuccess(() -> Component.literal("Reset to " + (int)finalX + ", " + (int)finalZ + " with kit " + finalKit), true);
		return 1;
	}

	private void resetPlayer(ServerPlayer player, double x, double y, double z, String kit, boolean shuffle) {
		player.setHealth(player.getMaxHealth());
		player.getFoodData().setFoodLevel(20);
		player.getInventory().clearContent();
		player.removeAllEffects();
		player.teleportTo(x, y, z);
		player.setYRot(0);
		player.setXRot(0);

		if (kit != null) {
			KitManager.applyKit(kit, player, shuffle);
		}
	}

	private void broadcastTeamUpdate(CommandSourceStack source) {
		// Broadcast team data to all connected clients via chat messages
		LOGGER.info("Team data updated and will be synced to clients");
		
		// Send team data as special chat messages that clients can parse
		var allTeams = TeamManager.getAllTeams();
		var server = source.getServer();
		
		for (String teamName : allTeams.keySet()) {
			String members = String.join(",", allTeams.get(teamName));
			String teamData = "TEAMDATA:" + teamName + ":" + members;
			Component message = Component.literal(teamData);
			
			// Send to all online players
			for (ServerPlayer player : server.getPlayerList().getPlayers()) {
				player.sendSystemMessage(message);
			}
		}
	}

	private void registerEvents() {
		// Attack Event - hits are tracked client-side via IPC only
		AttackEntityCallback.EVENT.register((player, world, hand, entity, hitResult) -> {
			if (player instanceof ServerPlayer && entity instanceof Player) {
				String attacker = player.getName().getString();
				String target = entity.getName().getString();
				// Only log server-side for debugging, client will send via IPC
				LOGGER.info("EVENT:HIT:" + attacker + ":" + target);
				// No displayClientMessage - hits are sent via IPC to Python for reward tracking
			}
			return InteractionResult.PASS;
		});

		// Death Event - server-side only for logging
		ServerLivingEntityEvents.AFTER_DEATH.register((entity, source) -> {
			if (entity instanceof ServerPlayer) {
				String victim = entity.getName().getString();
				String killer = source.getEntity() != null ? source.getEntity().getName().getString() : "Environment";
				LOGGER.info("EVENT:DEATH:" + victim + ":" + killer);
				// No hotbar message - death tracking handled client-side via health monitoring
			}
		});
	}
}