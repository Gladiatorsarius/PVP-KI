package com.example;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

/**
 * Server-side team management
 * Teams are persistent, synced to clients via CustomPayload packets
 */
public class TeamManager {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Path CONFIG_DIR = Paths.get("config", "pvp_ki");
    private static final Path TEAMS_FILE = CONFIG_DIR.resolve("teams.json");
    
    // Map<TeamName, Set<PlayerNames>>
    private static Map<String, Set<String>> teams = new HashMap<>();
    
    public static void loadTeams() {
        try {
            if (Files.exists(TEAMS_FILE)) {
                String json = Files.readString(TEAMS_FILE);
                JsonObject obj = GSON.fromJson(json, JsonObject.class);
                teams.clear();
                
                for (String teamName : obj.keySet()) {
                    Set<String> members = new HashSet<>();
                    var memberArray = obj.getAsJsonArray(teamName);
                    for (var elem : memberArray) {
                        members.add(elem.getAsString());
                    }
                    teams.put(teamName, members);
                }
            }
        } catch (IOException e) {
            PVP_KI.LOGGER.warn("Failed to load teams: " + e.getMessage());
        }
    }
    
    public static void saveTeams() {
        try {
            Files.createDirectories(CONFIG_DIR);
            JsonObject obj = new JsonObject();
            
            for (String teamName : teams.keySet()) {
                com.google.gson.JsonArray arr = new com.google.gson.JsonArray();
                for (String member : teams.get(teamName)) {
                    arr.add(member);
                }
                obj.add(teamName, arr);
            }
            
            Files.writeString(TEAMS_FILE, GSON.toJson(obj));
        } catch (IOException e) {
            PVP_KI.LOGGER.warn("Failed to save teams: " + e.getMessage());
        }
    }
    
    public static void createTeam(String teamName) {
        if (!teams.containsKey(teamName)) {
            teams.put(teamName, new HashSet<>());
            saveTeams();
        }
    }
    
    public static boolean deleteTeam(String teamName) {
        if (teams.remove(teamName) != null) {
            saveTeams();
            return true;
        }
        return false;
    }
    
    public static void addPlayerToTeam(String teamName, String playerName) {
        if (!teams.containsKey(teamName)) {
            createTeam(teamName);
        }
        teams.get(teamName).add(playerName);
        saveTeams();
    }
    
    public static void removePlayerFromTeam(String teamName, String playerName) {
        if (teams.containsKey(teamName)) {
            teams.get(teamName).remove(playerName);
            if (teams.get(teamName).isEmpty()) {
                teams.remove(teamName);
            }
            saveTeams();
        }
    }
    
    public static Set<String> getTeamMembers(String teamName) {
        return teams.getOrDefault(teamName, new HashSet<>());
    }
    
    public static String getPlayerTeam(String playerName) {
        for (String teamName : teams.keySet()) {
            if (teams.get(teamName).contains(playerName)) {
                return teamName;
            }
        }
        return null;
    }
    
    public static Set<String> getTeamNames() {
        return new HashSet<>(teams.keySet());
    }
    
    public static Map<String, Set<String>> getAllTeams() {
        return new HashMap<>(teams);
    }
    
    public static boolean removePlayerByName(String playerName) {
        for (String teamName : new HashSet<>(teams.keySet())) {
            if (teams.get(teamName).contains(playerName)) {
                teams.get(teamName).remove(playerName);
                if (teams.get(teamName).isEmpty()) {
                    teams.remove(teamName);
                }
                saveTeams();
                return true;
            }
        }
        return false;
    }
}
