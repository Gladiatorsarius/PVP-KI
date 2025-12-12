package com.example.mixin.client;

import com.example.PVP_KIClient;
import com.example.SettingsManager;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.network.chat.Style;
import net.minecraft.ChatFormatting;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Mixin to modify player nametags based on team membership
 */
@Mixin(Entity.class)
public class NameTagMixin {
    
    @Inject(method = "getDisplayName", at = @At("RETURN"), cancellable = true)
    private void modifyNameTag(CallbackInfoReturnable<Component> cir) {
        // Only modify for players
        Entity entity = (Entity) (Object) this;
        if (!(entity instanceof Player)) {
            return;
        }
        
        // Check if nametags are enabled
        if (!SettingsManager.showTeamNametags) {
            return;
        }
        
        Player player = (Player) entity;
        String playerName = player.getName().getString();
        
        // Check if this player is in our team
        boolean isTeamMember = false;
        synchronized (PVP_KIClient.teamMembers) {
            isTeamMember = PVP_KIClient.teamMembers.contains(playerName);
        }
        
        // Don't modify our own nametag
        Minecraft mc = Minecraft.getInstance();
        if (mc.player != null && playerName.equals(mc.player.getName().getString())) {
            return;
        }
        
        // Create modified nametag
        MutableComponent newName;
        if (isTeamMember) {
            // Green "Team" label for teammates
            newName = Component.literal("[Team]")
                    .setStyle(Style.EMPTY.withColor(ChatFormatting.GREEN).withBold(true));
        } else {
            // Red "Enemy" label for enemies
            newName = Component.literal("[Enemy]")
                    .setStyle(Style.EMPTY.withColor(ChatFormatting.RED).withBold(true));
        }
        
        cir.setReturnValue(newName);
    }
}
