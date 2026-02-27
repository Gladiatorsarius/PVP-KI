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
import net.minecraft.world.entity.player.Player;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.builder.RequiredArgumentBuilder;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

import com.mojang.brigadier.arguments.BoolArgumentType;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.scores.PlayerTeam;
import net.minecraft.world.scores.Scoreboard;
import net.minecraft.network.protocol.game.ClientboundSetPlayerTeamPacket;

public class PVP_KI implements ModInitializer {
        // Broadcast teams and nametag flag to all players
        public static void broadcastTeams(ServerLevel server) {
                List<ServerPlayer> players = server.getServer().getPlayerList().getPlayers();
                // Use Minecraft's built-in team packet to notify clients about teams.
                Scoreboard sb = server.getServer().getScoreboard();
                for (String teamName : SettingsManager.teams.keySet()) {
                    PlayerTeam team = sb.getPlayersTeam(teamName);
                    if (team == null) continue;
                    ClientboundSetPlayerTeamPacket pkt = ClientboundSetPlayerTeamPacket.createAddOrModifyPacket(team, true);
                    for (ServerPlayer p : players) {
                        try {
                            p.connection.send(pkt);
                        } catch (Throwable t) {
                            // best-effort send; ignore per-player failures
                        }
                    }
                }
        }
    public static final String MOD_ID = "pvp_ki";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);
    public static Process pythonProcess = null;
    // Snapshot of scoreboard teams to detect changes when a mapped listener isn't available
    private static volatile Map<String, Set<String>> lastTeamSnapshot = new HashMap<>();

    @Override
    public void onInitialize() {
                // Scoreboard listener removed to match current Mojang mappings.
                // Broadcasts still occur when SettingsManager modifies teams.
        LOGGER.info("Initializing PVP_KI Server Mod");
        KitManager.loadKits();
        SettingsManager.loadSettings();
        ArenaManager.loadArenas();

        // Shutdown Hook for Python Process
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            if (pythonProcess != null && pythonProcess.isAlive()) {
                LOGGER.info("Stopping Python process...");
                pythonProcess.destroy();
            }
        }));

        // Register Event Listeners
        registerEvents();

        // Register commands (single unified tree)
        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) -> {
            LOGGER.info("Registering /ki commands - Environment: " + environment);
            // Only allow server operators (permission level 2+) to use /ki commands
            LiteralArgumentBuilder<CommandSourceStack> kiRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("ki")
                .requires(source -> true);

            // /ki createkit <name>
            kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("createkit")
                .requires(source -> true)
                .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("name", StringArgumentType.string())
                    .executes(context -> {
                        try {
                            String name = StringArgumentType.getString(context, "name");
                            ServerPlayer player = context.getSource().getPlayerOrException();
                            KitManager.createKit(name, player);
                            context.getSource().sendSuccess(() -> Component.literal("Server kit '" + name + "' saved."), false);
                            return 1;
                        } catch (Exception e) {
                            context.getSource().sendFailure(Component.literal("Error: " + e.getMessage()));
                            return 0;
                        }
                    })));

            // /ki clearkits
            kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("clearkits")
                .requires(source -> true)
                .executes(context -> {
                    KitManager.clearAllKits();
                    context.getSource().sendSuccess(() -> Component.literal("Cleared all server kits."), false);
                    return 1;
                }));

            // /ki reset <p1> <p2> <kit> [shuffle]
            kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("reset")
                .requires(source -> true)
                .then(RequiredArgumentBuilder.<CommandSourceStack, EntitySelector>argument("p1", EntityArgument.player())
                    .then(RequiredArgumentBuilder.<CommandSourceStack, EntitySelector>argument("p2", EntityArgument.player())
                        .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("kit", StringArgumentType.string())
                            .executes(context -> resetCommand(context, false))
                            .then(RequiredArgumentBuilder.<CommandSourceStack, Boolean>argument("shuffle", BoolArgumentType.bool())
                                .executes(context -> resetCommand(context, true)))))));

            // /ki settings ...
            LiteralArgumentBuilder<CommandSourceStack> settingsRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("settings").requires(source -> true);
            // show
            settingsRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("show")
                .executes(context -> {
                    context.getSource().sendSuccess(() -> Component.literal("=== PVP KI Settings ==="), false);
                    context.getSource().sendSuccess(() -> Component.literal("Nametags: " + (SettingsManager.showTeamNametags ? "ON" : "OFF")), false);
                    context.getSource().sendSuccess(() -> Component.literal("Reset Mode: " + SettingsManager.resetMode), false);
                    context.getSource().sendSuccess(() -> Component.literal("Allowed Biomes: " + (SettingsManager.allowedBiomes.isEmpty() ? "All" : String.join(", ", SettingsManager.allowedBiomes))), false);
                    context.getSource().sendSuccess(() -> Component.literal("Blocked Biomes: " + (SettingsManager.blockedBiomes.isEmpty() ? "None" : String.join(", ", SettingsManager.blockedBiomes))), false);
                    return 1;
                }));
            // nametags on/off
            settingsRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("nametags")
                .then(LiteralArgumentBuilder.<CommandSourceStack>literal("on")
                    .executes(context -> {
                        SettingsManager.showTeamNametags = true;
                        SettingsManager.saveSettings();
                        PVP_KI.broadcastTeams(context.getSource().getLevel());
                        context.getSource().sendSuccess(() -> Component.literal("Team nametags enabled"), false);
                        return 1;
                    }))
                .then(LiteralArgumentBuilder.<CommandSourceStack>literal("off")
                    .executes(context -> {
                        SettingsManager.showTeamNametags = false;
                        SettingsManager.saveSettings();
                        PVP_KI.broadcastTeams(context.getSource().getLevel());
                        context.getSource().sendSuccess(() -> Component.literal("Team nametags disabled"), false);
                        return 1;
                    })));
            // biome allow/block/clear/list
            LiteralArgumentBuilder<CommandSourceStack> biomeRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("biome");
            biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("allow")
                .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("biome", StringArgumentType.string())
                    .executes(context -> { String biome = StringArgumentType.getString(context, "biome"); SettingsManager.allowedBiomes.add(biome); SettingsManager.saveSettings(); context.getSource().sendSuccess(() -> Component.literal("Allowed '" + biome + "'"), false); return 1; })));
            biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("block")
                .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("biome", StringArgumentType.string())
                    .executes(context -> { String biome = StringArgumentType.getString(context, "biome"); SettingsManager.blockedBiomes.add(biome); SettingsManager.saveSettings(); context.getSource().sendSuccess(() -> Component.literal("Blocked '" + biome + "'"), false); return 1; })));
            biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("clear")
                .executes(context -> { SettingsManager.allowedBiomes.clear(); SettingsManager.blockedBiomes.clear(); SettingsManager.saveSettings(); context.getSource().sendSuccess(() -> Component.literal("Cleared biome filters"), false); return 1; }));
            biomeRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("list")
                .executes(context -> { context.getSource().sendSuccess(() -> Component.literal("Allowed: " + (SettingsManager.allowedBiomes.isEmpty()?"All":String.join(", ", SettingsManager.allowedBiomes))), false); context.getSource().sendSuccess(() -> Component.literal("Blocked: " + (SettingsManager.blockedBiomes.isEmpty()?"None":String.join(", ", SettingsManager.blockedBiomes))), false); return 1; }));
            settingsRoot.then(biomeRoot);
            // resetmode
            settingsRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("resetmode")
                .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("mode", StringArgumentType.string())
                    .executes(context -> { String mode = StringArgumentType.getString(context, "mode"); if (!mode.equalsIgnoreCase("world") && !mode.equalsIgnoreCase("arena")) { context.getSource().sendFailure(Component.literal("Invalid mode. Use 'world' or 'arena'.")); return 0; } SettingsManager.resetMode = mode.toLowerCase(Locale.ROOT); SettingsManager.saveSettings(); context.getSource().sendSuccess(() -> Component.literal("Reset mode set to " + SettingsManager.resetMode), false); return 1; })));            
            kiRoot.then(settingsRoot);

            // /ki neutral <teamName> - mark scoreboard team as neutral
            LiteralArgumentBuilder<CommandSourceStack> neutralRoot = LiteralArgumentBuilder.<CommandSourceStack>literal("neutral")
                .requires(source -> source.getEntity() != null);

            // Suggest existing scoreboard team names for the add/remove subcommands
            SuggestionProvider<CommandSourceStack> teamSuggestionNonNeutral = (context, builder) -> {
                try {
                    ServerLevel lvl = (ServerLevel) context.getSource().getLevel();
                    Scoreboard sb = lvl.getScoreboard();
                    for (PlayerTeam t : sb.getPlayerTeams()) {
                        if (!SettingsManager.neutralTeams.contains(t.getName())) builder.suggest(t.getName());
                    }
                } catch (Throwable ignored) {
                }
                return builder.buildFuture();
            };

            SuggestionProvider<CommandSourceStack> teamSuggestionNeutral = (context, builder) -> {
                try {
                    ServerLevel lvl = (ServerLevel) context.getSource().getLevel();
                    Scoreboard sb = lvl.getScoreboard();
                    for (PlayerTeam t : sb.getPlayerTeams()) {
                        if (SettingsManager.neutralTeams.contains(t.getName())) builder.suggest(t.getName());
                    }
                } catch (Throwable ignored) {
                }
                return builder.buildFuture();
            };

            // /ki neutral add <teamName> (suggest only non-neutral teams)
            neutralRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("add")
                .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("teamName", StringArgumentType.string())
                    .suggests(teamSuggestionNonNeutral)
                    .executes(context -> {
                        String teamName = StringArgumentType.getString(context, "teamName");
                        if (SettingsManager.neutralTeams.contains(teamName)) {
                            // team already neutral — benign message
                            context.getSource().sendSuccess(() -> Component.literal(teamName + " is already neutral"), false);
                        } else {
                            SettingsManager.neutralTeams.add(teamName);
                            SettingsManager.saveSettings();
                            PVP_KI.broadcastTeams(context.getSource().getLevel());
                            context.getSource().sendSuccess(() -> Component.literal("Added '" + teamName + "' to neutral teams"), false);
                        }
                        return 1;
                    })));

            // /ki neutral remove <teamName> (suggest only neutral teams)
            neutralRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("remove")
                .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("teamName", StringArgumentType.string())
                    .suggests(teamSuggestionNeutral)
                    .executes(context -> {
                        String teamName = StringArgumentType.getString(context, "teamName");
                        if (SettingsManager.neutralTeams.contains(teamName)) {
                            SettingsManager.neutralTeams.remove(teamName);
                            SettingsManager.saveSettings();
                            PVP_KI.broadcastTeams(context.getSource().getLevel());
                            context.getSource().sendSuccess(() -> Component.literal("Removed '" + teamName + "' from neutral teams"), false);
                        } else {
                            context.getSource().sendSuccess(() -> Component.literal(teamName + " is not neutral"), false);
                        }
                        return 1;
                    })));

            // /ki neutral list - show all configured neutral teams
            neutralRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("list")
                .executes(context -> {
                    String msg = SettingsManager.neutralTeams.isEmpty() ? "No neutral teams configured" : String.join(", ", SettingsManager.neutralTeams);
                    context.getSource().sendSuccess(() -> Component.literal("Neutral teams: " + msg), false);
                    return 1;
                }));

            kiRoot.then(neutralRoot);

            // /ki arena admin commands
            kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("arena")
                .requires(source -> true)
                .then(LiteralArgumentBuilder.<CommandSourceStack>literal("add")
                    .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("name", StringArgumentType.string())
                        .then(LiteralArgumentBuilder.<CommandSourceStack>literal("pos1")
                            .executes(ctx -> {
                                ServerPlayer p = ctx.getSource().getPlayerOrException();
                                BlockPos hit = rayTraceBlock(p, 64);
                                if (hit == null) {
                                    ctx.getSource().sendFailure(Component.literal("No block targeted"));
                                    return 0;
                                }
                                ArenaManager.setPos(StringArgumentType.getString(ctx, "name"), hit, false);
                                // Example: add player to team after pos1 set
                                SettingsManager.addToTeam(StringArgumentType.getString(ctx, "name"), p.getName().getString(), ctx.getSource().getLevel());
                                ctx.getSource().sendSuccess(() -> Component.literal("Set pos1 for '" + StringArgumentType.getString(ctx, "name") + "' to " + hit.toShortString()), true);
                                return 1;
                            }))
                        .then(LiteralArgumentBuilder.<CommandSourceStack>literal("pos2")
                            .executes(ctx -> {
                                ServerPlayer p = ctx.getSource().getPlayerOrException();
                                BlockPos hit = rayTraceBlock(p, 64);
                                if (hit == null) {
                                    ctx.getSource().sendFailure(Component.literal("No block targeted"));
                                    return 0;
                                }
                                ArenaManager.setPos(StringArgumentType.getString(ctx, "name"), hit, true);
                                SettingsManager.addToTeam(StringArgumentType.getString(ctx, "name"), p.getName().getString(), ctx.getSource().getLevel());
                                ctx.getSource().sendSuccess(() -> Component.literal("Set pos2 for '" + StringArgumentType.getString(ctx, "name") + "' to " + hit.toShortString()), true);
                                return 1;
                            }))
                    ))
                .then(LiteralArgumentBuilder.<CommandSourceStack>literal("enable")
                    .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("name", StringArgumentType.string())
                        .executes(ctx -> { ArenaManager.enable(StringArgumentType.getString(ctx, "name"), true); ctx.getSource().sendSuccess(() -> Component.literal("Enabled arena"), true); return 1; })))
                .then(LiteralArgumentBuilder.<CommandSourceStack>literal("disable")
                    .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("name", StringArgumentType.string())
                        .executes(ctx -> { ArenaManager.enable(StringArgumentType.getString(ctx, "name"), false); ctx.getSource().sendSuccess(() -> Component.literal("Disabled arena"), true); return 1; })))
                .then(LiteralArgumentBuilder.<CommandSourceStack>literal("remove")
                    .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("name", StringArgumentType.string())
                        .executes(ctx -> { boolean ok = ArenaManager.remove(StringArgumentType.getString(ctx, "name")); if (ok) ctx.getSource().sendSuccess(() -> Component.literal("Removed arena"), true); else ctx.getSource().sendFailure(Component.literal("Arena not found")); return ok?1:0; })))
                .then(LiteralArgumentBuilder.<CommandSourceStack>literal("list")
                    .executes(ctx -> { var enabled = ArenaManager.getEnabled(); if (enabled.isEmpty()) { ctx.getSource().sendSuccess(() -> Component.literal("No enabled arenas"), false); } else { ctx.getSource().sendSuccess(() -> Component.literal("Enabled arenas:"), false); for (ArenaManager.ArenaConfig a : enabled) { ctx.getSource().sendSuccess(() -> Component.literal("- " + a.name + " [" + (a.pos1!=null?a.pos1.toShortString():"?") + ", " + (a.pos2!=null?a.pos2.toShortString():"?") + "]"), false); } } return 1; }))
            );

            // /ki resetteams <numTeams> <kit> <shuffle> <teams...>
            kiRoot.then(LiteralArgumentBuilder.<CommandSourceStack>literal("resetteams")
                .requires(source -> true)
                .then(RequiredArgumentBuilder.<CommandSourceStack, Integer>argument("numTeams", com.mojang.brigadier.arguments.IntegerArgumentType.integer(2))
                    .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("kit", StringArgumentType.string())
                        .then(RequiredArgumentBuilder.<CommandSourceStack, Boolean>argument("shuffle", BoolArgumentType.bool())
                            .then(RequiredArgumentBuilder.<CommandSourceStack, String>argument("teams", StringArgumentType.greedyString())
                                .executes(ctx -> resetteams(ctx))))))
            );

            dispatcher.register(kiRoot);
        });
    }

    // Server-side raytrace to get targeted block
    private BlockPos rayTraceBlock(ServerPlayer player, int maxDistance) {
        Vec3 start = player.getEyePosition(1.0f);
        Vec3 look = player.getLookAngle();
        Vec3 end = start.add(look.x * maxDistance, look.y * maxDistance, look.z * maxDistance);
        ClipContext ctx = new ClipContext(start, end, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player);
        BlockHitResult result = player.level().clip(ctx);
        if (result.getType() == HitResult.Type.BLOCK) {
            return result.getBlockPos();
        }
        return null;
    }

    // /ki resetteams handler
    private int resetteams(com.mojang.brigadier.context.CommandContext<CommandSourceStack> ctx) {
        try {
            int numTeams = com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "numTeams");
            String kitName = StringArgumentType.getString(ctx, "kit");
            boolean shuffle = BoolArgumentType.getBool(ctx, "shuffle");
            String teamsStr = StringArgumentType.getString(ctx, "teams");
            List<String> teamNames = new ArrayList<>();
            for (String t : teamsStr.split("\\s+")) if (!t.isBlank()) teamNames.add(t);

            // Validate team count against mode
            boolean arenaMode = "arena".equalsIgnoreCase(SettingsManager.resetMode);
            if (arenaMode && (numTeams < 2 || numTeams > 4)) {
                ctx.getSource().sendFailure(Component.literal("Arena mode supports 2-4 teams"));
                return 0;
            }
            if (!arenaMode && (numTeams < 2 || numTeams > 10)) {
                ctx.getSource().sendFailure(Component.literal("World mode supports 2-10 teams"));
                return 0;
            }
            if (teamNames.size() != numTeams) {
                ctx.getSource().sendFailure(Component.literal("Expected " + numTeams + " team names, got " + teamNames.size()));
                return 0;
            }

            // Resolve kit
            if ("random".equalsIgnoreCase(kitName)) {
                String rnd = KitManager.getRandomKit();
                if (rnd == null) { ctx.getSource().sendFailure(Component.literal("No kits available for 'random'")); return 0; }
                kitName = rnd;
            }

            // Validate teams exist and all members online
            Scoreboard sb = ctx.getSource().getServer().getScoreboard();
            List<List<ServerPlayer>> teamPlayers = new ArrayList<>();
            for (String name : teamNames) {
                PlayerTeam team = sb.getPlayersTeam(name);
                if (team == null) {
                    ctx.getSource().sendFailure(Component.literal("Team '" + name + "' not found in scoreboard"));
                    return 0;
                }
                List<ServerPlayer> online = new ArrayList<>();
                for (String pn : team.getPlayers()) {
                    ServerPlayer sp = ctx.getSource().getServer().getPlayerList().getPlayerByName(pn);
                    if (sp == null) {
                        ctx.getSource().sendFailure(Component.literal("Player '" + pn + "' (Team '" + name + "') is offline — aborting reset"));
                        return 0;
                    }
                    online.add(sp);
                }
                if (online.isEmpty()) {
                    ctx.getSource().sendFailure(Component.literal("Team '" + name + "' has no online players"));
                    return 0;
                }
                teamPlayers.add(online);
            }

            // Dispatch by mode
            ServerLevel level = ctx.getSource().getLevel();
            if (!arenaMode) {
                return resetteamsWorld(ctx.getSource(), level, teamNames, teamPlayers, kitName, shuffle);
            } else {
                return resetteamsArena(ctx.getSource(), level, teamNames, teamPlayers, kitName, shuffle);
            }
        } catch (Exception e) {
            ctx.getSource().sendFailure(Component.literal("Error: " + e.getMessage()));
            return 0;
        }
    }

    private int resetteamsWorld(CommandSourceStack src, ServerLevel level, List<String> teamNames, List<List<ServerPlayer>> teamPlayers, String kitName, boolean shuffle) {
        // Find suitable base location like existing resetCommand
        double x = 0, z = 0;
        int attempts = 0;
        boolean found = false;
        // Restrict search area to within 100,000 blocks of spawn (performance)
        int SEARCH_RADIUS = 100000;
        while (attempts < 25) { // Reduce attempts for performance
            x = (Math.random() * 2 * SEARCH_RADIUS) - SEARCH_RADIUS;
            z = (Math.random() * 2 * SEARCH_RADIUS) - SEARCH_RADIUS;
            attempts++;
            LevelChunk chunk = level.getChunk((int)x >> 4, (int)z >> 4);
            if (chunk.getInhabitedTime() == 0 && chunk.getBlockEntities().isEmpty()) {
                String biomeName = "plains"; // placeholder until biome API update
                if (SettingsManager.isBiomeAllowed(biomeName)) { found = true; break; }
            }
        }
        if (!found) { src.sendFailure(Component.literal("Could not find suitable location after 25 attempts")); return 0; }

        // Surface Y
        double baseY = 63;
        for (int checkY = 320; checkY >= 0; checkY--) {
            if (!level.getBlockState(new BlockPos((int)x, checkY, (int)z)).isAir()) { baseY = checkY + 1.0; break; }
        }

        int n = teamNames.size();
        double radius = 20.0;
        for (int i = 0; i < n; i++) {
            double angle = (2 * Math.PI * i) / n;
            double tx = x + radius * Math.cos(angle);
            double tz = z + radius * Math.sin(angle);
            // small per-player offset within team
            for (ServerPlayer sp : teamPlayers.get(i)) {
                double ox = (Math.random() - 0.5) * 4.0; // ±2
                double oz = (Math.random() - 0.5) * 4.0; // ±2
                teleportAndApply(sp, tx + ox, baseY, tz + oz, kitName, shuffle);
            }
        }

        ServerIPCClient.sendCommand("RESET", String.join(",", teamNames));
        src.sendSuccess(() -> Component.literal("Resetted " + n + " teams in world mode with kit '" + kitName + "'"), true);
        return 1;
    }

    private int resetteamsArena(CommandSourceStack src, ServerLevel level, List<String> teamNames, List<List<ServerPlayer>> teamPlayers, String kitName, boolean shuffle) {
        List<ArenaManager.ArenaConfig> enabled = ArenaManager.getEnabled();
        if (enabled.isEmpty()) { src.sendFailure(Component.literal("No enabled arenas")); return 0; }
        ArenaManager.ArenaConfig arena = enabled.get(new java.util.Random().nextInt(enabled.size()));
        BlockPos min = arena.getMin(); BlockPos max = arena.getMax();
        if (min == null || max == null) { src.sendFailure(Component.literal("Arena '" + arena.name + "' is incomplete")); return 0; }
        int height = arena.getHeight();
        int destY = min.getY() + height + 10;
        BlockPos destMin = new BlockPos(min.getX(), destY, min.getZ());

        // Execute /clone with replace
        String cmd = String.format(Locale.ROOT,
            "/clone %d %d %d %d %d %d %d %d %d replace",
            min.getX(), min.getY(), min.getZ(), max.getX(), max.getY(), max.getZ(), destMin.getX(), destMin.getY(), destMin.getZ());
        src.getServer().getCommands().performPrefixedCommand(src, cmd);

        // Find pads in source then map to destination by Y offset
        List<BlockPos> pads = ArenaManager.findWhiteWoolPads(level, arena);
        if (pads.size() < teamNames.size()) {
            src.sendFailure(Component.literal("Arena '" + arena.name + "' has only " + pads.size() + " pads; " + teamNames.size() + " teams requested"));
            return 0;
        }
        // Randomly pick distinct pads from sorted list
        List<BlockPos> shuffled = new ArrayList<>(pads);
        Collections.shuffle(shuffled);
        List<BlockPos> chosen = shuffled.subList(0, teamNames.size());

        int yOffset = destMin.getY() - min.getY();
        for (int i = 0; i < teamNames.size(); i++) {
            BlockPos srcPad = chosen.get(i);
            BlockPos dstPad = new BlockPos(srcPad.getX(), srcPad.getY() + yOffset, srcPad.getZ());
            double ty = dstPad.getY() + 1.0; // feet on top of block
            for (ServerPlayer sp : teamPlayers.get(i)) {
                teleportAndApply(sp, dstPad.getX() + 0.5, ty, dstPad.getZ() + 0.5, kitName, shuffle);
            }
        }

        ServerIPCClient.sendCommand("RESET", String.join(",", teamNames));
        src.sendSuccess(() -> Component.literal("Resetted " + teamNames.size() + " teams in arena '" + arena.name + "' with kit '" + kitName + "'"), true);
        return 1;
    }

    private int resetCommand(com.mojang.brigadier.context.CommandContext<CommandSourceStack> context, boolean hasShuffle) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p1 = EntityArgument.getPlayer(context, "p1");
        ServerPlayer p2 = EntityArgument.getPlayer(context, "p2");
        String kitName = StringArgumentType.getString(context, "kit");
        boolean shuffle = hasShuffle && BoolArgumentType.getBool(context, "shuffle");
        if ("random".equalsIgnoreCase(kitName)) {
            kitName = KitManager.getRandomKit();
        }

        ServerLevel level = (ServerLevel) p1.level();

        // If reset mode is arena, place both players on arena pads
        boolean arenaMode = "arena".equalsIgnoreCase(SettingsManager.resetMode);
        if (arenaMode) {
            List<ArenaManager.ArenaConfig> enabled = ArenaManager.getEnabled();
            if (enabled.isEmpty()) {
                context.getSource().sendFailure(Component.literal("No enabled arenas"));
                return 0;
            }
            ArenaManager.ArenaConfig arena = enabled.get(new java.util.Random().nextInt(enabled.size()));
            List<BlockPos> pads = ArenaManager.findWhiteWoolPads(level, arena);
            if (pads.size() < 2) {
                context.getSource().sendFailure(Component.literal("Arena '" + arena.name + "' does not have enough pads"));
                return 0;
            }
            Collections.shuffle(pads);
            BlockPos pad1 = pads.get(0);
            BlockPos pad2 = pads.get(1);
            double ty1 = pad1.getY() + 1.0;
            double ty2 = pad2.getY() + 1.0;
            teleportAndApply(p1, pad1.getX() + 0.5, ty1, pad1.getZ() + 0.5, kitName, shuffle);
            teleportAndApply(p2, pad2.getX() + 0.5, ty2, pad2.getZ() + 0.5, kitName, shuffle);
            ServerIPCClient.sendCommand("RESET", p1.getName().getString() + "," + p2.getName().getString());
            context.getSource().sendSuccess(() -> Component.literal("Reset to arena '" + arena.name + "' with kit '" + kitName + "'"), true);
            return 1;
        }

        // World mode (fallback)
        double x = 0, z = 0;
        int attempts = 0;
        boolean foundSuitable = false;
        int SEARCH_RADIUS = 100000;
        while (attempts < 25) {
            x = (Math.random() * 2 * SEARCH_RADIUS) - SEARCH_RADIUS;
            z = (Math.random() * 2 * SEARCH_RADIUS) - SEARCH_RADIUS;
            attempts++;
            LevelChunk chunk = level.getChunk((int)x >> 4, (int)z >> 4);
            if (chunk.getInhabitedTime() == 0 && chunk.getBlockEntities().isEmpty()) {
                String biomeName = "plains"; // Default to plains biome
                if (SettingsManager.isBiomeAllowed(biomeName)) {
                    foundSuitable = true;
                    break;
                }
            }
        }
        if (!foundSuitable) {
            context.getSource().sendFailure(Component.literal("Could not find suitable location after 25 attempts"));
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

    private void teleportAndApply(ServerPlayer player, double x, double y, double z, String kit, boolean shuffle) {
        resetPlayer(player, x, y, z, kit, shuffle);
    }

    private void registerEvents() {
        // Attack Event - compute relation and send to IPC with damage info
        AttackEntityCallback.EVENT.register((player, world, hand, entity, hitResult) -> {
            if (player instanceof ServerPlayer attacker && entity instanceof ServerPlayer target) {
                String attackerName = attacker.getName().getString();
                String targetName = target.getName().getString();
                
                // Compute relation
                String relation = computeRelation(attacker, target);
                
                // Log for Python IPC to pick up (damage will be computed from health delta)
                LOGGER.info("EVENT:HIT:" + attackerName + ":" + targetName + ":" + relation);
            }
            return InteractionResult.PASS;
        });

        // Death Event - server-side only for logging
        ServerLivingEntityEvents.AFTER_DEATH.register((entity, source) -> {
            if (entity instanceof ServerPlayer) {
                String victim = entity.getName().getString();
                String killer = source.getEntity() != null ? source.getEntity().getName().getString() : "Environment";
                LOGGER.info("EVENT:DEATH:" + victim + ":" + killer);
            }
        });

        // Broadcast teams when players join or disconnect so clients receive up-to-date team state immediately
        ServerPlayConnectionEvents.JOIN.register((handler, sender, server) -> {
            try {
                server.execute(() -> {
                    try { PVP_KI.broadcastTeams(server.overworld()); } catch (Throwable t) { }
                });
            } catch (Throwable t) { }
        });
        ServerPlayConnectionEvents.DISCONNECT.register((handler, server) -> {
            try {
                server.execute(() -> {
                    try { PVP_KI.broadcastTeams(server.overworld()); } catch (Throwable t) { }
                });
            } catch (Throwable t) { }
        });

        // Try to register a native scoreboard listener on server start; fall back to polling if unavailable.
        ServerLifecycleEvents.SERVER_STARTED.register(server -> {
            boolean registered = false;
            try {
                Scoreboard sb = server.getScoreboard();
                // Find an "addListener" method that accepts an interface type
                Method addListener = null;
                for (Method m : sb.getClass().getMethods()) {
                    if (m.getName().equals("addListener") && m.getParameterCount() == 1 && m.getParameterTypes()[0].isInterface()) {
                        addListener = m;
                        break;
                    }
                }
                if (addListener != null) {
                    Class<?> listenerType = addListener.getParameterTypes()[0];
                    final java.util.Set<String> seenMethods = ConcurrentHashMap.newKeySet();
                    InvocationHandler handler = (proxy, method, args) -> {
                        try {
                            String methodName = method.getName();
                            if (seenMethods.add(methodName)) {
                                LOGGER.debug("Scoreboard listener method: {}", methodName);
                            }
                            String lower = methodName.toLowerCase(Locale.ROOT);
                            boolean isTeamCallback = lower.contains("team") || lower.contains("teams") || lower.contains("playerteam") || lower.contains("teamchange") || lower.contains("teamadded") || lower.contains("teamremoved") || lower.contains("jointeam") || lower.contains("leaveteam") || lower.contains("playerjoin") || lower.contains("playerleave");
                            if (isTeamCallback) {
                                try { broadcastTeams(server.overworld()); } catch (Throwable t) { }
                            }
                        } catch (Throwable t) {
                        }
                        return null;
                    };
                    Object proxy = Proxy.newProxyInstance(listenerType.getClassLoader(), new Class<?>[]{listenerType}, handler);
                    addListener.invoke(sb, proxy);
                    registered = true;
                    LOGGER.info("Registered scoreboard listener via reflection: " + addListener);
                }
            } catch (Throwable t) {
                LOGGER.debug("Scoreboard listener reflection failed, will fall back to tick poller", t);
            }

            if (!registered) {
                // Fall back: poll at end of server tick
                try {
                    ServerTickEvents.END_SERVER_TICK.register(s -> {
                        ServerLevel lvl = s.overworld();
                        if (lvl == null) return;
                        Map<String, Set<String>> snap = captureTeamsSnapshot(lvl);
                        if (!snap.equals(lastTeamSnapshot)) {
                            lastTeamSnapshot = snap;
                            broadcastTeams(lvl);
                        }
                    });
                    LOGGER.info("Scoreboard listener not found; using tick poller fallback.");
                } catch (Throwable t) {
                    LOGGER.warn("Failed to register scoreboard poller fallback", t);
                }
            }
        });
    }

    private static Map<String, Set<String>> captureTeamsSnapshot(ServerLevel level) {
        Map<String, Set<String>> out = new HashMap<>();
        try {
            Scoreboard sb = level.getScoreboard();
            for (String teamName : sb.getTeamNames()) {
                PlayerTeam team = sb.getPlayersTeam(teamName);
                if (team == null) continue;
                Set<String> members = new HashSet<>(team.getPlayers());
                out.put(teamName, members);
            }
        } catch (Throwable t) {
            // ignore reflection/mapping issues
        }
        return out;
    }

    private String computeRelation(ServerPlayer attacker, ServerPlayer target) {
        ServerLevel level = (ServerLevel) attacker.level();
        Scoreboard scoreboard = level.getScoreboard();
        PlayerTeam attackerTeam = scoreboard.getPlayersTeam(attacker.getScoreboardName());
        PlayerTeam targetTeam = scoreboard.getPlayersTeam(target.getScoreboardName());
        
        if (attackerTeam != null && targetTeam != null && attackerTeam == targetTeam) {
            return "team";
        }
        
        if (attackerTeam != null && SettingsManager.neutralTeams.contains(attackerTeam.getName())) {
            return "neutral";
        }
        if (targetTeam != null && SettingsManager.neutralTeams.contains(targetTeam.getName())) {
            return "neutral";
        }
        
        return "enemy";
    }
}
