package com.example.mixin.client;

import com.example.ClientTeamManager;
import com.example.PVP_KIClient;
import net.minecraft.client.Minecraft;
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
 * Shows bold labels: [Team] green, [Enemy] red, [Neutral] gray
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
        
        // Check if nametags are enabled (session toggle)
        if (!PVP_KIClient.nametagsEnabled) {
            return;
        }
        
        Player player = (Player) entity;
        String targetName = player.getName().getString();
        
        // Get local player
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null) {
            return;
        }
        
        String localName = mc.player.getName().getString();
        
        // Don't modify our own nametag
        if (targetName.equals(localName)) {
            return;
        }
        
        // Get relation using unified logic
        String relation = ClientTeamManager.getRelation(localName, targetName);
        
        // Create label-only nametag based on relation
        MutableComponent label;
        if ("team".equals(relation)) {
            label = Component.literal("[Team]")
                    .setStyle(Style.EMPTY.withColor(ChatFormatting.GREEN).withBold(true));
        } else if ("neutral".equals(relation)) {
            label = Component.literal("[Neutral]")
                    .setStyle(Style.EMPTY.withColor(ChatFormatting.GRAY).withBold(true));
        } else {
            label = Component.literal("[Enemy]")
                    .setStyle(Style.EMPTY.withColor(ChatFormatting.RED).withBold(true));
        }
        
        cir.setReturnValue(label);
    }
}
