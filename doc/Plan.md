## PROMPT START: MINECRAFT PVP KI (1.21.10 - LAN-SETUP)

# 🎯 ZIEL: Training einer KI durch permanentes 1-gegen-1 Self-Play in einer lokalen, zu 100% offline-fähigen Umgebung.

# ///////////////////////////////////////////////////////////////////////////////
# // ALLGEMEINE SPEZIFIKATIONEN
# ///////////////////////////////////////////////////////////////////////////////

# VERSION: Minecraft Java Edition Version 1.21.10.

# ARCHITEKTUR:
# - Spielwelt: LAN-Gehostete Welt (Host-Client mit Modul 1).
# - Clients: Zwei Fabric Mods 1.21.10 (Client A / Port 9999 & Client B / Port 9998).
# - KI: Zentraler Trainer (GPU) und zwei asynchrone Collector-Prozesse (CPU).
# - IPC: TCP/IP Sockets über localhost.

# ///////////////////////////////////////////////////////////////////////////////
# // MODUL 1: JAVA SERVER-LOGIK-MODUL (FABRIC SERVER-SIDE MOD)
# ///////////////////////////////////////////////////////////////////////////////

# FOKUS: Game-Autorität & Synchronisation in der LAN-Host-Instanz.
# Typ: Fabric Server-Side Mod (KEIN Plugin).

# 1. KIT-SYSTEM: Speichert und wendet 1.21.10 PvP-Kits an.
# 2. SYNCHRONISIERTER RESET: Implementierung des Befehls /ki_reset <p1> <p2> <kit> über das Fabric Server Command API. Der Befehl muss beide Spieler heilen, das Inventar zurücksetzen und zu festen Startkoordinaten teleportieren.
# 3. EVENT-BROADCAST: Stellt sicher, dass Kills und Treffer von den Client-Mods abgefangen werden können.

# ///////////////////////////////////////////////////////////////////////////////
# // MODUL 2: JAVA FABRIC CLIENT MOD (I/O-BRIDGE)
# ///////////////////////////////////////////////////////////////////////////////

# FOKUS: Low-Latency IPC & 1.21.10 Game Hooks. (Läuft in beiden Clients).

# 1. DYNAMISCHES IPC-SETUP: Liest den Port aus der System Property ki.ipc.port (Fallback 9999). Startet den IPCManager (TCP Server) Thread.
# 2. HYBRID-SENDEN (Output): Kontinuierliches Senden von:
#    - JSON-Header (Zustand, HP, frame_size) + Newline.
#    - Binäre Frame-Bytes (Viewport-Capture) mit 1.21.10 Rendering-Hooks.
# [cite_start]3. AKTIONS-INJEKTION (Input): Empfängt Aktions-JSON und injiziert die relativen Bewegungs- und Blickrichtungsbefehle (Delta-Aiming)[cite: 10, 23].
# 4. RESET-AUSLÖSUNG: Führt den Server-Befehl /ki_reset ... über die Chat-Schnittstelle aus, wenn der Python-Agent einen Reset signalisiert.

# ///////////////////////////////////////////////////////////////////////////////
# // MODUL 3: PYTHON KI (DRL Agent & Orchestrator)
# ///////////////////////////////////////////////////////////////////////////////

# FOKUS: Lernen & Steuerung.

# [cite_start]1. ASYNCHRONE ARCHITEKTUR: Zentraler Trainer (GPU) und zwei Collector-Prozesse (CPU)[cite: 27]. Datenaustausch über multiprocessing.Queue.
# [cite_start]2. DATEN-PIPELINE: IPC-Client-Logik liest JSON-Header, extrahiert frame_size und liest die binären Frame-Bytes in ein NumPy-Array[cite: 25, 29, 30].
# 3. BELOHNUNGSFUNKTION: Berechnet Belohnungen aus HP-Differenzen, Treffern und Duell-Abschluss.
# [cite_start]4. DRL-CORE: Implementierung von CNN-Architektur und PPO/SAC-Algorithmus[cite: 26].

# ///////////////////////////////////////////////////////////////////////////////
# // 💡 ANWEISUNG AN COPILOT (AKTUELLER FOKUS)
# ///////////////////////////////////////////////////////////////////////////////

# Wir implementieren zuerst das IPC-Gerüst der Client-Mod (Modul 2).
# Schreibe den Java-Code für die ClientModInitializer Klasse und die IPCManager Klasse, die für Minecraft 1.21.10 geeignet sind und folgende Punkte erfüllen:
# 1. Dynamische Port-Lesung (ki.ipc.port oder Fallback 9999).
# 2. IPC-Thread-Start.
# 3. Reset-Auslösung: Die Methode handleReset() im IPCManager muss den synchronisierten Server-Befehl /ki_reset ... über die Chat-Schnittstelle des Clients senden.

## PROMPT ENDE