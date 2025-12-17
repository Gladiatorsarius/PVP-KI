package com.example.mixin.client;

import com.example.PVP_KIClient;
import com.google.gson.JsonObject;
import com.mojang.blaze3d.pipeline.RenderTarget;
import com.mojang.blaze3d.pipeline.TextureTarget;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.HashMap;
import java.util.Map;

import static org.lwjgl.opengl.GL11.*;
import static org.lwjgl.opengl.GL30.*;

@Mixin(net.minecraft.client.renderer.GameRenderer.class)
public class ExampleClientMixin {
	private TextureTarget smallTarget;
	private static final int TARGET_WIDTH = 64;
	private static final int TARGET_HEIGHT = 64;

	@Inject(at = @At("TAIL"), method = "render")
	private void onRender(net.minecraft.client.DeltaTracker deltaTracker, boolean bl, CallbackInfo ci) {
		if (PVP_KIClient.ipcManager != null && PVP_KIClient.ipcManager.isActive()) {
			captureFrame();
			applyActions();
		}
	}

	private void captureFrame() {
		Minecraft client = Minecraft.getInstance();
		int windowWidth = client.getWindow().getWidth();
		int windowHeight = client.getWindow().getHeight();

		if (windowWidth <= 0 || windowHeight <= 0) return;

		// Initialize small target if needed
		if (smallTarget == null) {
			// TextureTarget(String name, int width, int height, boolean useDepth)
			smallTarget = new TextureTarget("pvp_ki_small", TARGET_WIDTH, TARGET_HEIGHT, true);
			// Note: setClearColor not available in 1.21.11
		}

		try {
			// Get IDs via reflection
			int mainFboId = -1;
			int smallFboId = -1;
			
			try {
				// Try to find "frameBufferId" or "id" or "field_4493"
				java.lang.reflect.Field idField = null;
				Class<?> rtClass = RenderTarget.class;
				
				try { idField = rtClass.getDeclaredField("frameBufferId"); } catch (Exception e) {}
				if (idField == null) try { idField = rtClass.getDeclaredField("id"); } catch (Exception e) {}
				if (idField == null) try { idField = rtClass.getDeclaredField("field_4493"); } catch (Exception e) {} // Intermediary
				
				if (idField != null) {
					idField.setAccessible(true);
					mainFboId = idField.getInt(client.getMainRenderTarget());
					smallFboId = idField.getInt(smallTarget);
				}
			} catch (Exception e) {
				System.out.println("Failed to get FBO IDs: " + e.getMessage());
			}

			if (mainFboId != -1 && smallFboId != -1) {
				glBindFramebuffer(GL_READ_FRAMEBUFFER, mainFboId);
				glBindFramebuffer(GL_DRAW_FRAMEBUFFER, smallFboId);
				glBlitFramebuffer(0, 0, windowWidth, windowHeight, 0, 0, TARGET_WIDTH, TARGET_HEIGHT, GL_COLOR_BUFFER_BIT, GL_LINEAR);
				glBindFramebuffer(GL_FRAMEBUFFER, smallFboId);
			} else {
				// Fallback: Read from current buffer (likely main)
				return;
			}

			glReadBuffer(GL_COLOR_ATTACHMENT0);

			// Read Pixels
			ByteBuffer buffer = ByteBuffer.allocateDirect(TARGET_WIDTH * TARGET_HEIGHT * 4).order(ByteOrder.nativeOrder());
			glReadPixels(0, 0, TARGET_WIDTH, TARGET_HEIGHT, GL_BGRA, GL_UNSIGNED_BYTE, buffer);

			// Restore
			glBindFramebuffer(GL_FRAMEBUFFER, 0);

			// Flip
			// buffer.flip(); // Not needed if we read directly into allocated buffer? 
			// Actually glReadPixels writes from position 0. We need to read from it.
			// But we need to flip the image vertically because OpenGL is bottom-left origin.
			// We can do this in Python or here. Doing it here is cleaner but slower.
			// Let's just send it and let Python handle it or just learn upside down.
			// Actually, `buffer.get(bytes)` reads from position.
			
			byte[] frameBytes = new byte[TARGET_WIDTH * TARGET_HEIGHT * 4];
			buffer.get(frameBytes); // Reads from 0 to limit

			if (PVP_KIClient.ipcManager != null) {
				Map<String, Object> state = new HashMap<>();
				LocalPlayer player = client.player;
				if (player != null) {
					state.put("x", player.getX());
					state.put("y", player.getY());
					state.put("z", player.getZ());
					state.put("health", player.getHealth());
					state.put("hunger", player.getFoodData().getFoodLevel());
					state.put("pitch", player.getXRot());
					state.put("yaw", player.getYRot());
					state.put("width", TARGET_WIDTH);
					state.put("height", TARGET_HEIGHT);
				}
				PVP_KIClient.ipcManager.sendFrame(frameBytes, state);
			}
		} catch (Exception e) {
			System.out.println("Error in captureFrame: " + e.getMessage());
		}
	}

	private void applyActions() {
		JsonObject action = PVP_KIClient.pendingAction;
		if (action != null) {
			Minecraft client = Minecraft.getInstance();
			LocalPlayer player = client.player;
			
			if (action.has("forward")) client.options.keyUp.setDown(action.get("forward").getAsBoolean());
			if (action.has("left")) client.options.keyLeft.setDown(action.get("left").getAsBoolean());
			if (action.has("back")) client.options.keyDown.setDown(action.get("back").getAsBoolean());
			if (action.has("right")) client.options.keyRight.setDown(action.get("right").getAsBoolean());
			if (action.has("jump")) client.options.keyJump.setDown(action.get("jump").getAsBoolean());
			if (action.has("attack")) client.options.keyAttack.setDown(action.get("attack").getAsBoolean());
			
			if (player != null) {
				if (action.has("yaw")) player.setYRot(player.getYRot() + action.get("yaw").getAsFloat());
				if (action.has("pitch")) player.setXRot(player.getXRot() + action.get("pitch").getAsFloat());
			}
			
			PVP_KIClient.pendingAction = null;
		}
	}
}