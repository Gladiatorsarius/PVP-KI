package com.example;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.reflect.TypeToken;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtOps;
import net.minecraft.world.item.Item;
import net.minecraft.nbt.Tag;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.resources.RegistryOps;

import java.io.*;
import java.lang.reflect.Type;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

public class ClientKitManager {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final Path CONFIG_DIR = Paths.get("config", "pvp_ki");
    private static final Path KITS_FILE = CONFIG_DIR.resolve("client_kits.json");
    
    // Map<KitName, List<ItemStack JSON Strings>>
    private static Map<String, List<JsonObject>> kits = new HashMap<>();

    static {
        loadKits();
    }

    public static void loadKits() {
        if (!Files.exists(KITS_FILE)) return;
        try (Reader reader = Files.newBufferedReader(KITS_FILE)) {
            Type type = new TypeToken<Map<String, List<Map<String, Object>>>>(){}.getType();
            Map<String, List<Map<String, Object>>> rawKits = GSON.fromJson(reader, type);
            kits = new HashMap<>();
            if (rawKits != null) {
                for (String kitName : rawKits.keySet()) {
                    List<JsonObject> itemList = new ArrayList<>();
                    for (Map<String, Object> itemMap : rawKits.get(kitName)) {
                        JsonObject obj = GSON.toJsonTree(itemMap).getAsJsonObject();
                        itemList.add(obj);
                    }
                    kits.put(kitName, itemList);
                }
            }
        } catch (IOException e) {
            System.err.println("Error loading client kits: " + e.getMessage());
        }
    }

    public static void saveKits() {
        try {
            Files.createDirectories(CONFIG_DIR);
            try (Writer writer = Files.newBufferedWriter(KITS_FILE)) {
                GSON.toJson(kits, writer);
            }
        } catch (IOException e) {
            System.err.println("Error saving client kits: " + e.getMessage());
        }
    }

    public static void createKit(String name, LocalPlayer player) {
        List<JsonObject> items = new ArrayList<>();
        RegistryOps<Tag> ops = RegistryOps.create(NbtOps.INSTANCE, player.registryAccess());
        
        // Save Inventory (Main + Armor + Offhand)
        for (int i = 0; i < player.getInventory().getContainerSize(); i++) {
            ItemStack stack = player.getInventory().getItem(i);
            if (!stack.isEmpty()) {
                try {
                    // Encode ItemStack to NBT Tag
                    Tag tag = ItemStack.CODEC.encodeStart(ops, stack).result().orElse(null);
                    
                    if (tag instanceof CompoundTag ct) {
                        // Write NBT to bytes
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();
                        net.minecraft.nbt.NbtIo.writeCompressed(ct, baos);
                        byte[] nbtBytes = baos.toByteArray();
                        
                        // Encode as base64 for JSON storage
                        String base64 = java.util.Base64.getEncoder().encodeToString(nbtBytes);
                        
                        JsonObject itemJson = new JsonObject();
                        itemJson.addProperty("data", base64);
                        itemJson.addProperty("Slot", i);
                        items.add(itemJson);
                    }
                } catch (Exception e) {
                    System.err.println("Error saving item: " + e.getMessage());
                }
            }
        }
        
        kits.put(name, items);
        saveKits();
    }

    public static void applyKit(String name, LocalPlayer player, boolean shuffle) {
        if (!kits.containsKey(name)) {
            System.out.println("Kit not found: " + name);
            return;
        }

        player.getInventory().clearContent();
        List<JsonObject> items = kits.get(name);
        List<ItemStack> mainInventoryItems = new ArrayList<>();
        List<Integer> mainInventorySlots = new ArrayList<>();
        RegistryOps<Tag> ops = RegistryOps.create(NbtOps.INSTANCE, player.registryAccess());

        for (JsonObject itemJson : items) {
            try {
                // Get slot
                int slot = 0;
                if (itemJson.has("Slot")) {
                    slot = itemJson.get("Slot").getAsInt();
                }

                // Reconstruct ItemStack from full NBT data
                ItemStack stack = ItemStack.EMPTY;
                
                try {
                    if (itemJson.has("data")) {
                        String base64 = itemJson.get("data").getAsString();
                        // Decode base64 to bytes
                        byte[] nbtBytes = java.util.Base64.getDecoder().decode(base64);
                        // Read NBT from bytes
                        ByteArrayInputStream bais = new ByteArrayInputStream(nbtBytes);
                        CompoundTag nbt = net.minecraft.nbt.NbtIo.readCompressed(bais, net.minecraft.nbt.NbtAccounter.unlimitedHeap());
                        // Decode the full ItemStack with all NBT data (count, enchantments, potions, etc.)
                        var result = ItemStack.CODEC.parse(ops, nbt);
                        if (result.result().isPresent()) {
                            stack = result.result().get();
                        }
                    } else {
                        // Old format not supported
                        System.out.println("[ClientKitManager] Skipping old format item");
                    }
                } catch (Exception e) {
                    System.err.println("Error parsing item data: " + e.getMessage());
                    e.printStackTrace();
                }
                
                if (stack.isEmpty()) continue;
                
                // Armor slots in Inventory: 36, 37, 38, 39. Offhand: 40.
                // Main inventory: 0-35.
                if (slot >= 36) {
                    // Armor or Offhand - set directly
                    player.getInventory().setItem(slot, stack);
                } else {
                    // Main inventory item
                    if (shuffle) {
                        mainInventoryItems.add(stack);
                        mainInventorySlots.add(slot);
                    } else {
                        player.getInventory().setItem(slot, stack);
                    }
                }
            } catch (Exception e) {
                System.err.println("Error applying kit item: " + e.getMessage());
                e.printStackTrace();
            }
        }

        if (shuffle && !mainInventoryItems.isEmpty()) {
            Collections.shuffle(mainInventoryItems);
            // Distribute randomly in main inventory (0-35)
            List<Integer> availableSlots = new ArrayList<>();
            for (int i = 0; i < 36; i++) availableSlots.add(i);
            Collections.shuffle(availableSlots);

            for (int i = 0; i < mainInventoryItems.size(); i++) {
                if (i < availableSlots.size()) {
                    player.getInventory().setItem(availableSlots.get(i), mainInventoryItems.get(i));
                }
            }
        }
    }

    public static Set<String> getKitNames() {
        return kits.keySet();
    }
    
    public static String getRandomKit() {
        if (kits.isEmpty()) return null;
        List<String> keys = new ArrayList<>(kits.keySet());
        return keys.get(new Random().nextInt(keys.size()));
    }

    public static boolean deleteKit(String name) {
        if (kits.containsKey(name)) {
            kits.remove(name);
            saveKits();
            return true;
        }
        return false;
    }
    
    public static Map<String, List<JsonObject>> getAllKits() {
        return new HashMap<>(kits);
    }
}
