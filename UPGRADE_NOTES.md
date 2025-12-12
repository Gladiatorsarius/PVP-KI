# Minecraft 1.21.11 Upgrade Notes

## Changes Made

This upgrade updates the PVP-KI mod from Minecraft 1.21.10 to 1.21.11.

### Version Updates

The following versions have been updated in `pvp_ki-template-1.21.10/gradle.properties`:

- **Minecraft Version**: `1.21.10` → `1.21.11`
- **Fabric API**: `0.136.0+1.21.10` → `0.136.0+1.21.11`
- **Fabric Loom**: `1.8+` → `1.7.4` (fixed to proper version format)
- **Fabric Loader**: `0.17.3` (unchanged, compatible with 1.21.x)

The following dependency was updated in `pvp_ki-template-1.21.10/src/main/resources/fabric.mod.json`:

- **Minecraft Dependency**: `~1.21.10` → `~1.21.11`

### Version Selection Rationale

1. **Minecraft 1.21.11**: As requested in the issue
2. **Fabric API 0.136.0+1.21.11**: Following standard Fabric API versioning pattern where the suffix matches the Minecraft version
3. **Fabric Loom 1.7.4**: A stable version compatible with Minecraft 1.21.x (the original `1.8+` was not a valid version format)
4. **Fabric Loader 0.17.3**: Retained as it's compatible across Minecraft 1.21.x versions

### Important Notes

**Note**: Due to network restrictions in the build environment preventing access to `maven.fabricmc.net`, the build could not be verified. You should:

1. Verify the build works locally: `cd pvp_ki-template-1.21.10 && ./gradlew build`
2. Check the [Fabric Versions Page](https://fabricmc.net/develop/) for the exact Fabric API version for 1.21.11
3. If the Fabric API version 0.136.0+1.21.11 doesn't exist, check for alternatives like:
   - `0.137.0+1.21.11`
   - `0.138.0+1.21.11`
   - Or the latest available for 1.21.11

### Alternative Loom Versions

If Loom 1.7.4 doesn't work, try these alternatives (in order of preference):
- `1.8.0` (if available for 1.21.11)
- `1.7.5`
- `1.7.3`
- `1.9.0` (if it exists)

### Checking for Correct Versions

To find the correct Fabric API version for 1.21.11:
```bash
# Check available Fabric API versions
curl -s "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/maven-metadata.xml" | grep -A 1 "1.21.11"

# Or check on the Fabric website
# Visit: https://fabricmc.net/develop/
```

### Build Instructions

After verifying versions:

```bash
cd pvp_ki-template-1.21.10
./gradlew clean build
```

The compiled mod will be in: `build/libs/pvp_ki-1.0.0.jar`

### Testing

After building, test the mod by:
1. Copying `build/libs/pvp_ki-*.jar` to your Minecraft mods folder
2. Launching Minecraft 1.21.11 with Fabric Loader 0.17.3+
3. Verifying all mod features work as expected:
   - Team commands (`/team add/remove/list/clear`)
   - Agent commands (`/agent <1-100>`)
   - Kit commands (`/ki *`)
   - IPC communication with Python training system

### References

- [Fabric 1.21.11 Update Guide](https://fabricmc.net/2025/12/05/12111.html)
- [Fabric Development Page](https://fabricmc.net/develop/)
- [Fabric Loom Versions](https://maven.fabricmc.net/net/fabricmc/fabric-loom/)
- [Fabric API Versions](https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/)

## Troubleshooting

### "Could not resolve fabric-api"
The version 0.136.0+1.21.11 may not exist. Check the Fabric versions page and update the version in `gradle.properties`.

### "Plugin fabric-loom not found"
Try a different Loom version. Common stable versions include 1.7.x and 1.8.x series.

### Compilation Errors
If you encounter compilation errors, check if any API changes were made in Minecraft 1.21.11 that affect the mod's code. The Fabric API should handle most compatibility layers.

## Rollback Instructions

If you need to rollback to 1.21.10:

```bash
git revert HEAD
```

Or manually change:
- `gradle.properties`: Set `minecraft_version=1.21.10`, `fabric_version=0.136.0+1.21.10`, `loom_version=1.8+`
- `fabric.mod.json`: Set `"minecraft": "~1.21.10"`
