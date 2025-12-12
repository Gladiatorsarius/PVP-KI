package com.example.mixin.client;

import com.example.ClientTeamManager;
import com.example.SettingsManager;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Mixin to override nametag rendering for team members and enemies
 */
@Mixin(EntityRenderer.class)
public abstract class NametagRenderMixin<T extends Entity> {
    
    /**
     * Override the display name for players when team nametags are enabled
     */
    @Inject(method = "getNameTag", at = @At("HEAD"), cancellable = true)
    protected void onGetNameTag(T entity, CallbackInfoReturnable<Component> cir) {
        // Only apply to players when nametags are enabled
        if (SettingsManager.showTeamNametags && entity instanceof Player) {
            Player player = (Player)entity;
            String playerName = player.getName().getString();
            
            // Check relationship
            String relationship = ClientTeamManager.getRelationship(playerName);
            
            if ("team".equals(relationship)) {
                // Show green "Team" label
                cir.setReturnValue(Component.literal("Team").withStyle(style -> 
                    style.withColor(net.minecraft.ChatFormatting.GREEN)));
            } else if ("enemy".equals(relationship)) {
                // Show red "Enemy" label
                cir.setReturnValue(Component.literal("Enemy").withStyle(style -> 
                    style.withColor(net.minecraft.ChatFormatting.RED)));
            }
            // If no relationship or nametags disabled, use default behavior (don't cancel)
        }
    }
}
