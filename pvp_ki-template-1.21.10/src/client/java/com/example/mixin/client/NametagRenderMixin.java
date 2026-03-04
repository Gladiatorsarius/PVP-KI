package com.example.mixin.client;

import com.example.NametagOverlayRenderer;
import com.example.PVP_KIClient;
import com.example.ClientTeamManager;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.resource.GraphicsResourceAllocator;
import com.mojang.blaze3d.buffers.GpuBufferSlice;
import org.joml.Vector4f;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Mixin to render 3D nametag overlays above player heads
 */
@Mixin(LevelRenderer.class)
public class NametagRenderMixin {
    
    // Inject at the start of renderLevel to avoid fragile INVOKE targets
    @Inject(method = "renderLevel", at = @At("HEAD"))
    private void onRenderLevel(GraphicsResourceAllocator allocator, net.minecraft.client.DeltaTracker deltaTracker, boolean bl, Camera camera, 
                               org.joml.Matrix4f matrix4f, org.joml.Matrix4f matrix4f2, org.joml.Matrix4f matrix4f3,
                               GpuBufferSlice gpuBufferSlice, Vector4f vector4f, boolean bl2, CallbackInfo ci) {
        if (!NametagOverlayRenderer.isEnabled()) return;
        
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.level == null) return;
        
        PoseStack poseStack = new PoseStack();
        MultiBufferSource.BufferSource bufferSource = mc.renderBuffers().bufferSource();
        
        // Get camera position via reflection
        Vec3 cameraPos;
        try {
            java.lang.reflect.Field posField = Camera.class.getDeclaredField("position");
            posField.setAccessible(true);
            org.joml.Vector3d camPosVec = (org.joml.Vector3d) posField.get(camera);
            cameraPos = new Vec3(camPosVec.x, camPosVec.y, camPosVec.z);
        } catch (Exception e) {
            return; // Can't get camera position, abort
        }
        float tickDelta = deltaTracker.getGameTimeDeltaPartialTick(true);
        
        // Iterate through all players
        for (Player player : mc.level.players()) {
            if (player == mc.player) continue;
            if (player.isInvisible()) continue;
            
            Vec3 playerPos = player.getPosition(tickDelta);
            double distance = cameraPos.distanceTo(playerPos);
            
            if (distance > 64.0) continue;
            
            String playerName = player.getName().getString();
            String localPlayerName = mc.player.getName().getString();
            
            // Check if they're in the SAME server team
            boolean isTeam = false;
            String localPlayerTeam = ClientTeamManager.getPlayerTeam(localPlayerName);
            String otherPlayerTeam = ClientTeamManager.getPlayerTeam(playerName);
            
            if (localPlayerTeam != null && otherPlayerTeam != null) {
                // Both are in server teams - only team if SAME team
                isTeam = localPlayerTeam.equals(otherPlayerTeam);
            } else {
                // Fall back to local client team list (client-side only mode)
                isTeam = PVP_KIClient.teamMembers.contains(playerName);
            }
            
            String label = isTeam ? "§a[TEAM]" : "§c[ENEMY]";
            double labelY = playerPos.y + player.getBbHeight() + 0.5;
            
            poseStack.pushPose();
            poseStack.translate(
                playerPos.x - cameraPos.x,
                labelY - cameraPos.y,
                playerPos.z - cameraPos.z
            );
            
            // Billboard to face camera
            poseStack.mulPose(camera.rotation());
            
            float scale = 0.025f;
            poseStack.scale(-scale, -scale, scale);
            
            Matrix4f matrix = poseStack.last().pose();
            int textWidth = mc.font.width(label);
            float xOffset = -textWidth / 2.0f;
            
            // Draw with semi-transparent background
            int bgColor = 0x40000000;
            mc.font.drawInBatch(label, xOffset, 0, 0xFFFFFFFF, false, matrix, bufferSource, 
                net.minecraft.client.gui.Font.DisplayMode.NORMAL, bgColor, 15728880);
            
            poseStack.popPose();
        }
        
        bufferSource.endBatch();
    }
}
