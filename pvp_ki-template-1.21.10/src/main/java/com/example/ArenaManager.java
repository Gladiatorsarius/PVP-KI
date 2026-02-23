package com.example;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

public class ArenaManager {
        // Cache for white wool pad locations per arena (reset on save/load)
        private static final Map<String, List<BlockPos>> padCache = new HashMap<>();
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Path CONFIG_DIR = Paths.get("config", "pvp_ki");
    private static final Path ARENAS_FILE = sanitizePath(CONFIG_DIR.resolve("arenas.json"));

    /**
     * Sanitize a path to prevent path traversal and ensure it is within the config directory.
     */
    private static Path sanitizePath(Path path) {
        Path absConfig = CONFIG_DIR.toAbsolutePath().normalize();
        Path absPath = path.toAbsolutePath().normalize();
        if (!absPath.startsWith(absConfig)) {
            throw new SecurityException("Attempted access outside config directory: " + absPath);
        }
        return absPath;
    }

    public static class ArenaConfig {
        public String name;
        public BlockPos pos1;
        public BlockPos pos2;
        public boolean enabled = true;

        public ArenaConfig() {}
        public ArenaConfig(String name) { this.name = name; }

        public BlockPos getMin() {
            if (pos1 == null || pos2 == null) return null;
            int minX = Math.min(pos1.getX(), pos2.getX());
            int minY = Math.min(pos1.getY(), pos2.getY());
            int minZ = Math.min(pos1.getZ(), pos2.getZ());
            return new BlockPos(minX, minY, minZ);
        }
        public BlockPos getMax() {
            if (pos1 == null || pos2 == null) return null;
            int maxX = Math.max(pos1.getX(), pos2.getX());
            int maxY = Math.max(pos1.getY(), pos2.getY());
            int maxZ = Math.max(pos1.getZ(), pos2.getZ());
            return new BlockPos(maxX, maxY, maxZ);
        }
        public int getHeight() {
            BlockPos min = getMin();
            BlockPos max = getMax();
            if (min == null || max == null) return 0;
            return (max.getY() - min.getY());
        }
    }

    private static final Map<String, ArenaConfig> arenas = new HashMap<>();

    public static void loadArenas() {
            padCache.clear();
        try {
            if (!Files.exists(ARENAS_FILE)) return;
            try (Reader reader = Files.newBufferedReader(ARENAS_FILE)) {
                Map<String, Map<String, Object>> raw = GSON.fromJson(reader, new TypeToken<Map<String, Map<String, Object>>>(){}.getType());
                arenas.clear();
                if (raw != null) {
                    for (String name : raw.keySet()) {
                        if (name == null || name.trim().isEmpty()) continue;
                        Map<String, Object> a = raw.get(name);
                        ArenaConfig cfg = new ArenaConfig(name);
                        cfg.enabled = a.getOrDefault("enabled", Boolean.TRUE) instanceof Boolean && (Boolean) a.get("enabled");
                        Map<String, Double> p1 = (Map<String, Double>) a.get("pos1");
                        Map<String, Double> p2 = (Map<String, Double>) a.get("pos2");
                        if (p1 != null && p1.get("x") != null && p1.get("y") != null && p1.get("z") != null) {
                            cfg.pos1 = new BlockPos(p1.get("x").intValue(), p1.get("y").intValue(), p1.get("z").intValue());
                        }
                        if (p2 != null && p2.get("x") != null && p2.get("y") != null && p2.get("z") != null) {
                            cfg.pos2 = new BlockPos(p2.get("x").intValue(), p2.get("y").intValue(), p2.get("z").intValue());
                        }
                        arenas.put(name, cfg);
                    }
                }
            }
        } catch (SecurityException se) {
            System.err.println("[ArenaManager] Security error: " + se.getMessage());
            se.printStackTrace();
        } catch (Exception e) {
            System.err.println("[ArenaManager] Error loading arenas: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public static void saveArenas() {
            padCache.clear();
        try {
            Files.createDirectories(CONFIG_DIR);
            Map<String, Object> out = new HashMap<>();
            for (String name : arenas.keySet()) {
                if (name == null || name.trim().isEmpty()) continue;
                ArenaConfig cfg = arenas.get(name);
                Map<String, Object> a = new HashMap<>();
                a.put("enabled", cfg.enabled);
                if (cfg.pos1 != null) {
                    a.put("pos1", Map.of("x", cfg.pos1.getX(), "y", cfg.pos1.getY(), "z", cfg.pos1.getZ()));
                }
                if (cfg.pos2 != null) {
                    a.put("pos2", Map.of("x", cfg.pos2.getX(), "y", cfg.pos2.getY(), "z", cfg.pos2.getZ()));
                }
                out.put(name, a);
            }
            try (Writer writer = Files.newBufferedWriter(ARENAS_FILE)) {
                GSON.toJson(out, writer);
            }
        } catch (SecurityException se) {
            System.err.println("[ArenaManager] Security error: " + se.getMessage());
            se.printStackTrace();
        } catch (Exception e) {
            System.err.println("[ArenaManager] Error saving arenas: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public static ArenaConfig getOrCreate(String name) {
        return arenas.computeIfAbsent(name, ArenaConfig::new);
    }

    public static boolean remove(String name) {
        boolean removed = arenas.remove(name) != null;
        if (removed) saveArenas();
        return removed;
    }

    public static void enable(String name, boolean value) {
        ArenaConfig cfg = getOrCreate(name);
        cfg.enabled = value;
        saveArenas();
    }

    public static List<ArenaConfig> getEnabled() {
        List<ArenaConfig> list = new ArrayList<>();
        for (ArenaConfig cfg : arenas.values()) {
            if (cfg.enabled && cfg.pos1 != null && cfg.pos2 != null) list.add(cfg);
        }
        return list;
    }

    public static void setPos(String name, BlockPos pos, boolean pos2) {
        ArenaConfig cfg = getOrCreate(name);
        if (pos2) cfg.pos2 = pos; else cfg.pos1 = pos;
        saveArenas();
    }

    public static List<BlockPos> findWhiteWoolPads(ServerLevel level, ArenaConfig cfg) {
        // Use cache if available
        if (padCache.containsKey(cfg.name)) {
            return new ArrayList<>(padCache.get(cfg.name));
        }
        List<BlockPos> pads = new ArrayList<>();
        BlockPos min = cfg.getMin();
        BlockPos max = cfg.getMax();
        if (min == null || max == null) return pads;
        // Restrict search bounds: only scan Y from minY to minY+10 (assume pads are near arena floor)
        int minY = min.getY();
        int maxY = Math.min(minY + 10, max.getY());
        for (int x = min.getX(); x <= max.getX(); x++) {
            for (int y = minY; y <= maxY; y++) {
                for (int z = min.getZ(); z <= max.getZ(); z++) {
                    BlockPos bp = new BlockPos(x, y, z);
                    BlockState state = level.getBlockState(bp);
                    if (state.getBlock() == Blocks.WHITE_WOOL) {
                        pads.add(bp);
                    }
                }
            }
        }
        pads.sort(Comparator.comparingInt((BlockPos p) -> p.getX())
                .thenComparingInt(p -> p.getY())
                .thenComparingInt(p -> p.getZ()));
        padCache.put(cfg.name, new ArrayList<>(pads));
        return pads;
    }
}
