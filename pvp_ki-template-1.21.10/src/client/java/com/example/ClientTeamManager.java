package com.example;

import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Player;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Client-side team tracking
 * Syncs with server-side teams and displays them on nametag overlays
 */
public class ClientTeamManager {
    // Map<TeamName, Set<PlayerNames>>
    private static final Map<String, Set<String>> serverTeams = new ConcurrentHashMap<>();
    // Map<PlayerName, TeamName>
    private static final Map<String, String> playerToTeam = new ConcurrentHashMap<>();
    // Set of team names that are neutral
    private static final Set<String> neutralTeams = ConcurrentHashMap.newKeySet();
    // Client-side fallback teams and neutrals when no server teams
    private static final Set<String> clientTeamMembers = ConcurrentHashMap.newKeySet();
    private static final Set<String> clientNeutralMembers = ConcurrentHashMap.newKeySet();
    
    public static void updateServerTeams(String teamName, Set<String> members) {
        if (members.isEmpty()) {
            serverTeams.remove(teamName);
        } else {
            serverTeams.put(teamName, new HashSet<>(members));
        }
        rebuildPlayerToTeamMap();
    }
    
    public static void updateTeam(String teamName, String[] memberNames) {
        Set<String> members = new HashSet<>();
        for (String name : memberNames) {
            if (!name.isEmpty()) {
                members.add(name);
            }
        }
        updateServerTeams(teamName, members);
        System.out.println("[ClientTeamManager] Updated team " + teamName + " with " + members.size() + " members");
    }
    
    public static void clearTeams() {
        serverTeams.clear();
        playerToTeam.clear();
        neutralTeams.clear();
    }
    
    public static void markTeamAsNeutral(String teamName, boolean isNeutral) {
        if (isNeutral) {
            neutralTeams.add(teamName);
        } else {
            neutralTeams.remove(teamName);
        }
    }
    
    public static boolean isNeutralTeam(String teamName) {
        return neutralTeams.contains(teamName);
    }
    
    // Client-side fallback team management
    public static void addToClientTeam(String playerName) {
        clientTeamMembers.add(playerName);
    }
    
    public static void removeFromClientTeam(String playerName) {
        clientTeamMembers.remove(playerName);
    }
    
    public static void addToClientNeutral(String playerName) {
        clientNeutralMembers.add(playerName);
    }
    
    public static void removeFromClientNeutral(String playerName) {
        clientNeutralMembers.remove(playerName);
    }
    
    public static void clearClientTeams() {
        clientTeamMembers.clear();
        clientNeutralMembers.clear();
    }
    
    public static Set<String> getClientTeamMembers() {
        return new HashSet<>(clientTeamMembers);
    }
    
    public static Set<String> getClientNeutralMembers() {
        return new HashSet<>(clientNeutralMembers);
    }
    
    // Relation computation: team, enemy, or neutral
    public static String getRelation(String localPlayer, String targetPlayer) {
        // Server teams take priority if available
        if (hasServerTeams()) {
            String localTeam = playerToTeam.get(localPlayer);
            String targetTeam = playerToTeam.get(targetPlayer);
            
            if (localTeam != null && targetTeam != null && localTeam.equals(targetTeam)) {
                return "team";
            }
            if (targetTeam != null && neutralTeams.contains(targetTeam)) {
                return "neutral";
            }
            return "enemy";
        } else {
            // Fallback to client-side team lists
            if (clientTeamMembers.contains(targetPlayer)) {
                return "team";
            }
            if (clientNeutralMembers.contains(targetPlayer)) {
                return "neutral";
            }
            return "enemy";
        }
    }
    
    private static void rebuildPlayerToTeamMap() {
        playerToTeam.clear();
        for (String teamName : serverTeams.keySet()) {
            for (String playerName : serverTeams.get(teamName)) {
                playerToTeam.put(playerName, teamName);
            }
        }
    }
    
    public static boolean isTeamMember(String playerName) {
        return playerToTeam.containsKey(playerName);
    }
    
    public static String getPlayerTeam(String playerName) {
        return playerToTeam.get(playerName);
    }
    
    public static boolean isTeammate(String player1, String player2) {
        String team1 = playerToTeam.get(player1);
        String team2 = playerToTeam.get(player2);
        return team1 != null && team1.equals(team2);
    }
    
    public static Map<String, Set<String>> getServerTeams() {
        return new HashMap<>(serverTeams);
    }
	
	public static boolean hasServerTeams() {
		return !serverTeams.isEmpty();
	}
}
