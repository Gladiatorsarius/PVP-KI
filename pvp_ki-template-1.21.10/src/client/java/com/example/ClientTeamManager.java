package com.example;

import java.util.*;

/**
 * Client-side team management for tracking team/enemy relationships
 */
public class ClientTeamManager {
    private static final Set<String> teamMembers = new HashSet<>();
    private static final Set<String> enemies = new HashSet<>();
    private static int currentAgentId = 1;
    
    /**
     * Add a player to the team
     */
    public static void addTeamMember(String playerName) {
        teamMembers.add(playerName);
        enemies.remove(playerName); // Remove from enemies if present
        System.out.println("[ClientTeam] Added to team: " + playerName);
    }
    
    /**
     * Remove a player from the team
     */
    public static void removeTeamMember(String playerName) {
        teamMembers.remove(playerName);
        System.out.println("[ClientTeam] Removed from team: " + playerName);
    }
    
    /**
     * Mark a player as enemy
     */
    public static void addEnemy(String playerName) {
        enemies.add(playerName);
        teamMembers.remove(playerName); // Remove from team if present
        System.out.println("[ClientTeam] Added to enemies: " + playerName);
    }
    
    /**
     * Remove a player from enemies
     */
    public static void removeEnemy(String playerName) {
        enemies.remove(playerName);
        System.out.println("[ClientTeam] Removed from enemies: " + playerName);
    }
    
    /**
     * Clear all team and enemy lists
     */
    public static void clearAll() {
        teamMembers.clear();
        enemies.clear();
        System.out.println("[ClientTeam] Cleared all teams and enemies");
    }
    
    /**
     * Get all team members
     */
    public static Set<String> getTeamMembers() {
        return new HashSet<>(teamMembers);
    }
    
    /**
     * Get all enemies
     */
    public static Set<String> getEnemies() {
        return new HashSet<>(enemies);
    }
    
    /**
     * Check if a player is a team member
     */
    public static boolean isTeamMember(String playerName) {
        return teamMembers.contains(playerName);
    }
    
    /**
     * Check if a player is an enemy
     */
    public static boolean isEnemy(String playerName) {
        return enemies.contains(playerName);
    }
    
    /**
     * Get the relationship status for a player
     * @return "team", "enemy", or null
     */
    public static String getRelationship(String playerName) {
        if (isTeamMember(playerName)) {
            return "team";
        } else if (isEnemy(playerName)) {
            return "enemy";
        }
        return null;
    }
    
    /**
     * Build a map of all known players and their relationships
     * Format: {"playerName": "team"|"enemy"|null}
     */
    public static Map<String, String> getAllRelationships() {
        Map<String, String> relationships = new HashMap<>();
        for (String player : teamMembers) {
            relationships.put(player, "team");
        }
        for (String player : enemies) {
            relationships.put(player, "enemy");
        }
        return relationships;
    }
    
    /**
     * Set the current agent ID for this client
     */
    public static void setCurrentAgentId(int agentId) {
        currentAgentId = agentId;
        System.out.println("[ClientTeam] Current agent ID: " + agentId);
    }
    
    /**
     * Get the current agent ID
     */
    public static int getCurrentAgentId() {
        return currentAgentId;
    }
}
