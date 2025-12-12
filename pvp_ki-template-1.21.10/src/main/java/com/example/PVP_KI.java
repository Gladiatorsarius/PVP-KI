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
				.requires(source -> source.hasPermission(0)); // Allow all players

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

		// /ki reset <p1> <p2> <kit> [shuffle]
			kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("reset")
				.then(RequiredArgumentBuilder.<CommandSourceStack, EntitySelector>argument("p1", EntityArgument.player())
					.then(RequiredArgumentBuilder.<CommandSourceStack, EntitySelector>argument("p2", EntityArgument.player())
						.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("kit", StringArgumentType.string())
							.executes(context -> resetCommand(context, false))
							.then(RequiredArgumentBuilder.<CommandSourceStack, Boolean>argument("shuffle", BoolArgumentType.bool())
								.executes(context -> resetCommand(context, true)))))));
			
			// /ki settings - Settings management
			LiteralArgumentBuilder<CommandSourceStack> settingsRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("settings");
			
			// /ki settings show
			settingsRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("show")
				.executes(context -> {
					context.getSource().sendSuccess(() -> Component.literal("=== PVP KI Settings ==="), false);
					context.getSource().sendSuccess(() -> Component.literal("Nametags: " + (SettingsManager.showTeamNametags ? "ON" : "OFF")), false);
					context.getSource().sendSuccess(() -> Component.literal("Allowed Biomes: " + 
						(SettingsManager.allowedBiomes.isEmpty() ? "none" : String.join(", ", SettingsManager.allowedBiomes))), false);
					context.getSource().sendSuccess(() -> Component.literal("Blocked Biomes: " + 
						(SettingsManager.blockedBiomes.isEmpty() ? "none" : String.join(", ", SettingsManager.blockedBiomes))), false);
					return 1;
				}));
			
			// /ki settings nametags <on|off>
			settingsRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("nametags")
				.then(RequiredArgumentBuilder.<CommandSourceStack, Boolean>argument("enabled", BoolArgumentType.bool())
					.executes(context -> {
						boolean enabled = BoolArgumentType.getBool(context, "enabled");
						SettingsManager.showTeamNametags = enabled;
						SettingsManager.saveSettings();
						context.getSource().sendSuccess(() -> Component.literal("Nametags " + (enabled ? "enabled" : "disabled")), true);
						return 1;
					})));
			
			// /ki settings biome allow <biome>
			LiteralArgumentBuilder<CommandSourceStack> biomeRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("biome");
			biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("allow")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("biome", StringArgumentType.word())
					.executes(context -> {
						String biome = StringArgumentType.getString(context, "biome");
						SettingsManager.allowedBiomes.add(biome);
						SettingsManager.saveSettings();
						context.getSource().sendSuccess(() -> Component.literal("Added " + biome + " to allowed biomes"), false);
						return 1;
					})));
			
			// /ki settings biome block <biome>
			biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("block")
				.then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("biome", StringArgumentType.word())
					.executes(context -> {
						String biome = StringArgumentType.getString(context, "biome");
						SettingsManager.blockedBiomes.add(biome);
						SettingsManager.saveSettings();
						context.getSource().sendSuccess(() -> Component.literal("Added " + biome + " to blocked biomes"), false);
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
					context.getSource().sendSuccess(() -> Component.literal("Allowed: " + 
						(SettingsManager.allowedBiomes.isEmpty() ? "none" : String.join(", ", SettingsManager.allowedBiomes))), false);
					context.getSource().sendSuccess(() -> Component.literal("Blocked: " + 
						(SettingsManager.blockedBiomes.isEmpty() ? "none" : String.join(", ", SettingsManager.blockedBiomes))), false);
					return 1;
				}));
			
			settingsRoot.then(biomeRoot);
			kiRoot.then(settingsRoot);

			dispatcher.register(kiRoot);
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

		// Find fresh location with unmodified chunks and allowed biome
		ServerLevel level = (ServerLevel) p1.level();
		double x, z;
		int attempts = 0;
		boolean foundValidLocation = false;
		
		do {
			x = (Math.random() * 2000000) - 1000000;
			z = (Math.random() * 2000000) - 1000000;
			attempts++;
			
			LevelChunk chunk = level.getChunk((int)x >> 4, (int)z >> 4);
			
			// Check if chunk is unmodified: inhabited time == 0 AND no block entities
			if (chunk.getInhabitedTime() == 0 && chunk.getBlockEntities().isEmpty()) {
				// Check biome filtering
				BlockPos pos = new BlockPos((int)x, 64, (int)z);
				net.minecraft.world.level.biome.Biome biome = level.getBiome(pos).value();
				String biomeName = level.registryAccess()
					.registryOrThrow(net.minecraft.core.registries.Registries.BIOME)
					.getKey(biome).getPath();
				
				if (SettingsManager.isBiomeAllowed(biomeName)) {
					foundValidLocation = true;
					break;
				}
			}
			
			// Warn if taking too many attempts
			if (attempts % 50 == 0) {
				LOGGER.warn("Biome search taking long: {} attempts", attempts);
			}
		} while (attempts < 200); // Increased from 10 to 200 for biome filtering
		
		if (!foundValidLocation) {
			LOGGER.warn("Could not find valid location after {} attempts, using last attempt", attempts);
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

	private void registerEvents() {
		// Attack Event
		AttackEntityCallback.EVENT.register((player, world, hand, entity, hitResult) -> {
			if (player instanceof ServerPlayer && entity instanceof Player) {
				String attacker = player.getName().getString();
				String target = entity.getName().getString();
				LOGGER.info("EVENT:HIT:" + attacker + ":" + target);
				// Send attack event to action queue
				if (player instanceof ServerPlayer) {
					((ServerPlayer)player).displayClientMessage(Component.literal("EVENT:HIT:" + attacker + ":" + target), true);
				}
			}
			return InteractionResult.PASS;
		});

		// Death Event
		ServerLivingEntityEvents.AFTER_DEATH.register((entity, source) -> {
			if (entity instanceof ServerPlayer) {
				String victim = entity.getName().getString();
				String killer = source.getEntity() != null ? source.getEntity().getName().getString() : "Environment";
				LOGGER.info("EVENT:DEATH:" + victim + ":" + killer);
				// Send death event to action queue
				ServerPlayer serverPlayer = (ServerPlayer) entity;
				serverPlayer.displayClientMessage(Component.literal("EVENT:DEATH:" + victim + ":" + killer), true);
			}
		});
	}
}