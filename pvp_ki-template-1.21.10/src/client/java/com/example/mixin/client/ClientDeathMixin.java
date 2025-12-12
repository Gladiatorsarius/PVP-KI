package com.example.mixin.client;

import com.example.PVP_KIClient;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Mixin to detect death events on the client side
 */
@Mixin(LivingEntity.class)
public abstract class ClientDeathMixin {
    
    /**
     * Detect when an entity dies
     */
    @Inject(method = "die", at = @At("HEAD"))
    private void onEntityDeath(DamageSource source, CallbackInfo ci) {
        LivingEntity entity = (LivingEntity)(Object)this;
        
        // Only track on client side and for players
        if (entity.level().isClientSide && entity instanceof Player) {
            Player victim = (Player)entity;
            Entity killer = source.getEntity();
            
            String victimName = victim.getName().getString();
            String killerName = (killer != null) ? killer.getName().getString() : "Environment";
            
            // Add event to queue
            String event = "EVENT:DEATH:" + victimName + ":" + killerName;
            PVP_KIClient.eventQueue.add(event);
            System.out.println("[ClientEvent] " + event);
        }
    }
}
