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
