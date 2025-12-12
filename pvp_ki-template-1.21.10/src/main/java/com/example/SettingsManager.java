package com.example;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

/**
 * Manages global settings for PVP KI system
 */
public class SettingsManager {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Path CONFIG_DIR = Paths.get("config", "pvp_ki");
    private static final Path SETTINGS_FILE = CONFIG_DIR.resolve("settings.json");
    
    // Settings
    public static boolean showTeamNametags = true;
    public static Set<String> allowedBiomes = new HashSet<>();
    public static Set<String> blockedBiomes = new HashSet<>();
    
    // Teams (temporary, per session)
    public static Map<String, Set<String>> teams = new HashMap<>();
    
    public static void loadSettings() {
        if (!Files.exists(SETTINGS_FILE)) {
            System.out.println("[Settings] No settings file found, using defaults");
            return;
        }
        
        try (Reader reader = Files.newBufferedReader(SETTINGS_FILE)) {
            Map<String, Object> data = GSON.fromJson(reader, new TypeToken<Map<String, Object>>(){}.getType());
            
            if (data != null) {
                showTeamNametags = data.getOrDefault("showTeamNametags", true) instanceof Boolean 
                    ? (Boolean) data.get("showTeamNametags") : true;
                
                allowedBiomes = new HashSet<>((List<String>) data.getOrDefault("allowedBiomes", new ArrayList<>()));
                blockedBiomes = new HashSet<>((List<String>) data.getOrDefault("blockedBiomes", new ArrayList<>()));
                
                System.out.println("[Settings] Loaded settings");
            }
        } catch (Exception e) {
            System.err.println("[Settings] Error loading: " + e.getMessage());
        }
    }
    
    public static void saveSettings() {
        try {
            Files.createDirectories(CONFIG_DIR);
            
            Map<String, Object> data = new HashMap<>();
            data.put("showTeamNametags", showTeamNametags);
            data.put("allowedBiomes", new ArrayList<>(allowedBiomes));
            data.put("blockedBiomes", new ArrayList<>(blockedBiomes));
            
            try (Writer writer = Files.newBufferedWriter(SETTINGS_FILE)) {
                GSON.toJson(data, writer);
            }
            
            System.out.println("[Settings] Saved settings");
        } catch (Exception e) {
            System.err.println("[Settings] Error saving: " + e.getMessage());
        }
    }
    
    // Team management
    public static void createTeam(String teamName, List<String> players) {
        teams.put(teamName, new HashSet<>(players));
        System.out.println("[Teams] Created team '" + teamName + "' with " + players.size() + " players");
    }
    
    public static void addToTeam(String teamName, String player) {
        teams.computeIfAbsent(teamName, k -> new HashSet<>()).add(player);
    }
    
    public static void removeFromTeam(String teamName, String player) {
        Set<String> team = teams.get(teamName);
        if (team != null) {
            team.remove(player);
            if (team.isEmpty()) {
                teams.remove(teamName);
            }
        }
    }
    
    public static String getPlayerTeam(String playerName) {
        for (Map.Entry<String, Set<String>> entry : teams.entrySet()) {
            if (entry.getValue().contains(playerName)) {
                return entry.getKey();
            }
        }
        return null;
    }
    
    public static boolean areTeammates(String player1, String player2) {
        String team1 = getPlayerTeam(player1);
        String team2 = getPlayerTeam(player2);
        return team1 != null && team1.equals(team2);
    }
    
    public static void clearTeams() {
        teams.clear();
        System.out.println("[Teams] Cleared all teams");
    }
    
    // Biome filtering
    public static boolean isBiomeAllowed(String biome) {
        if (!allowedBiomes.isEmpty()) {
            return allowedBiomes.contains(biome);
        }
        return !blockedBiomes.contains(biome);
    }
}
