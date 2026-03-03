package com.example;

/**
 * Manages the enabled state for 3D nametag overlays
 * Actual rendering is handled by NametagRenderMixin
 */
public class NametagOverlayRenderer {
    private static boolean enabled = true;
    
    public static void register() {
        // Registration happens via mixin injection
    }
    
    public static void setEnabled(boolean enable) {
        enabled = enable;
    }
    
    public static boolean isEnabled() {
        return enabled;
    }
}
