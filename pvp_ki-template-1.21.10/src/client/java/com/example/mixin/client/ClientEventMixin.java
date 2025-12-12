package com.example.mixin.client;

import com.example.PVP_KIClient;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Mixin to detect HIT and DEATH events on the client side
 */
@Mixin(Player.class)
public abstract class ClientEventMixin {
    
    /**
     * Detect when a player takes damage (gets hit)
     */
    @Inject(method = "hurt", at = @At("HEAD"))
    private void onPlayerHurt(DamageSource source, float amount, CallbackInfoReturnable<Boolean> cir) {
        Player victim = (Player)(Object)this;
        
        // Only track on client side
        if (victim.level().isClientSide) {
            Entity attacker = source.getEntity();
            
            // Only track player vs player hits
            if (attacker instanceof Player) {
                String attackerName = attacker.getName().getString();
                String victimName = victim.getName().getString();
                
                // Add event to queue
                String event = "EVENT:HIT:" + attackerName + ":" + victimName;
                PVP_KIClient.eventQueue.add(event);
                System.out.println("[ClientEvent] " + event);
            }
        }
    }
}
