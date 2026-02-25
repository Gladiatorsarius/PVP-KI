# 🤖 GitHub Copilot - Projekt: Minecraft 1.21.10 PvP KI (Self-Play / Offline)

# 🎯 Ziel: Implementierung eines vollständigen DRL-Systems zur Beherrschung des modernen 1.21.10 PvP.

# --- TECHNISCHES SETUP ---
# Server: PaperMC 1.21.10 (lokal, offline-mode=false).
# Clients: Zwei Minecraft 1.21.10 Clients mit Custom Fabric Mod.
# IPC-Methode: TCP/IP Sockets auf localhost (Java Server, Python Client).
# Datenfluss: Bidirektional (Frame-Bytes/Zustand -> KI) und (Aktionen <- KI).

# --- MODUL 1: JAVA FABRIC MOD (1.21.10) ---
# Aufgabe: I/O-Bridge zur Spiel-Engine.
# 1. Bildschirm-Capture: Fängt Frame-Daten direkt von der Render-Pipeline ab.
# 2. Eingabe-Injektion: Empfängt Aktionsbefehle (JSON) und injiziert sie präzise in die Spiel-Engine.
# 3. Belohnungsdaten: Liest interne Werte (eigene/Gegner-HP, Events) aus und sendet sie numerisch.
# 4. IPC-Server: Verwaltet TCP-Verbindung zur Python-KI.

# --- MODUL 2: PYTHON KI (DRL AGENT) ---
# Aufgabe: Denker, Lerner und Orchestrator.
# 1. IPC-Client: Stellt TCP-Verbindung zur Mod her, empfängt kontinuierlich Daten.
# 2. DRL-Architektur: CNN-basiertes Netz zur Verarbeitung von visuellen Inputs und numerischen Zuständen.
# 3. RL-Algorithmus: Implementiert Self-Play-Trainings-Loop (z.B. PPO/SAC).
# 4. Belohnungsfunktion: Nutzt die präzisen HP/Event-Daten zur Maximierung des PvP-Erfolgs.

# --- AKTUELLER AUFGABENFOKUS ---
# ❗️ Wir konzentrieren uns auf die Implementierung der IPC-Schnittstelle und des Kern-RL-Agenten.

# 💡 ANWEISUNG AN COPILOT
# 1. Beginne mit einem detaillierten technischen Plan für die TCP/IP Socket-Kommunikation.
# 2. Beschreibe die ersten 3 Implementierungsschritte für Modul 1 (Java Mod) und Modul 2 (Python KI).
# 3. Beantworte am Ende die Frage zur Datenstruktur des JSON-Strings für Belohnungsdaten.

# 🟢 STARTE MIT DER ÜBERSCHRIFT: ✅ Technischer Gesamtplan