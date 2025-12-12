package com.example;

import java.util.*;

/**
 * Client-side team management.
 * Tracks which players are on the team vs enemies.
 * Works on any server (with or without mod).
 */
public class TeamManager {
    private static final Set<String> teamPlayers = new HashSet<>();
    private static final Set<String> enemyPlayers = new HashSet<>();
    
    /**
     * Add a player to the team
     */
    public static void addTeammate(String playerName) {
        teamPlayers.add(playerName);
        enemyPlayers.remove(playerName);
        System.out.println("[TeamManager] Added teammate: " + playerName);
    }
    
    /**
     * Add a player to enemies
     */
    public static void addEnemy(String playerName) {
        enemyPlayers.add(playerName);
        teamPlayers.remove(playerName);
        System.out.println("[TeamManager] Added enemy: " + playerName);
    }
    
    /**
     * Remove a player from team
     */
    public static void removeTeammate(String playerName) {
        teamPlayers.remove(playerName);
        System.out.println("[TeamManager] Removed teammate: " + playerName);
    }
    
    /**
     * Remove a player from enemies
     */
    public static void removeEnemy(String playerName) {
        enemyPlayers.remove(playerName);
        System.out.println("[TeamManager] Removed enemy: " + playerName);
    }
    
    /**
     * Clear all teams
     */
    public static void clearAll() {
        teamPlayers.clear();
        enemyPlayers.clear();
        System.out.println("[TeamManager] Cleared all teams");
    }
    
    /**
     * Get team status for a player
     * @return "team", "enemy", or null if not classified
     */
    public static String getPlayerStatus(String playerName) {
        if (teamPlayers.contains(playerName)) {
            return "team";
        } else if (enemyPlayers.contains(playerName)) {
            return "enemy";
        }
        return null;
    }
    
    /**
     * Check if player is a teammate
     */
    public static boolean isTeammate(String playerName) {
        return teamPlayers.contains(playerName);
    }
    
    /**
     * Check if player is an enemy
     */
    public static boolean isEnemy(String playerName) {
        return enemyPlayers.contains(playerName);
    }
    
    /**
     * Get all teammates
     */
    public static Set<String> getTeammates() {
        return new HashSet<>(teamPlayers);
    }
    
    /**
     * Get all enemies
     */
    public static Set<String> getEnemies() {
        return new HashSet<>(enemyPlayers);
    }
    
    /**
     * Get team data for all visible players as a map for IPC
     * Format: {"playerName": "team"|"enemy"|null}
     */
    public static Map<String, String> getTeamData() {
        Map<String, String> teams = new HashMap<>();
        for (String player : teamPlayers) {
            teams.put(player, "team");
        }
        for (String player : enemyPlayers) {
            teams.put(player, "enemy");
        }
        return teams;
    }
    
    /**
     * Get list of all team members for display
     */
    public static List<String> listTeam() {
        return new ArrayList<>(teamPlayers);
    }
    
    /**
     * Get list of all enemies for display
     */
    public static List<String> listEnemies() {
        return new ArrayList<>(enemyPlayers);
    }
}
