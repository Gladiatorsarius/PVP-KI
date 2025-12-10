Deep Reinforcement Learning (DRL) Trainingsplan für PvP-Agenten
Dieser Plan beschreibt die schrittweise Einführung und Anpassung des Belohnungsschemas, um einen KI-Agenten vom Erlernen der Grundlagen bis hin zur Entwicklung komplexer PvP-Strategien zu führen.
Phase 1: Bootstrapping (Initiale Lernphase)
Diese Phase dient dazu, dem unerfahrenen Agenten die grundlegenden Mechanismen des Spiels (Bewegung, Angreifen, Zielen) so schnell wie möglich beizubringen. Dies geschieht durch Training gegen einen menschlichen Spieler.
Ziel
* Erwerb grundlegender Fähigkeiten (Attackieren, Ausweichen).
* Schaffung eines stabilen Verhaltens, bevor der Agent komplexeren Strategien im Self-Play ausgesetzt wird.
Belohnungsschema (Aktiv während des Bootstrappings)


Komponente
	Belohnungswert
	Zweck
	Terminaler Sieg
	+500 Punkte (Moderat)
	Etabliert den Sieg als Hauptziel, ohne eine zu starke Risikoscheu zu erzeugen.
	Terminaler Verlust
	-500 Punkte (Moderat)
	Minimiert die Bestrafung, damit der Agent bereit ist, risikoreichere Aktionen auszuführen, um zu lernen.
	Kontinuierliches HP-Delta (Gegner verliert HP)
	+10 Punkte pro 0.5 Herz
	Dichtes positives Feedback für erfolgreiche Treffer.
	Kontinuierliches HP-Delta (Agent verliert HP)
	-10 Punkte pro 0.5 Herz
	Dichtes negatives Feedback, das Überleben und Ausweichen fördert.
	Zeitstrafe
	0 (Entfernt)
	Die Bestrafung für Ineffizienz wird durch den menschlichen Gegner übernommen, der einen zögernden Agenten besiegt.
	Phase 2: Self-Play (Fortgeschrittene Strategie-Entwicklung)
Nachdem der Agent die Grundlagen beherrscht, wird das Training auf Self-Play (Agent gegen Agent) umgestellt. Hierbei werden das Belohnungsschema und die Bestrafungen geschärft, um hochoptimierte und effiziente Verhaltensweisen zu erzwingen.
Ziel
* Entwicklung komplexer Strategien (z. B. optimales Timing, Block-Einsatz, Positionierung).
* Maximale Effizienz und Aggressivität.
Belohnungsschema (Aktiv während des Self-Plays)
Komponente
	Belohnungswert
	Zweck
	Terminaler Sieg
	+1000 Punkte (Hoch)
	Priorisiert den Sieg maximal als das einzig wahre Ziel.
	Terminaler Verlust
	-1000 Punkte (Hoch)
	Starke Strafe, um schlechte Gesamtstrategien zu eliminieren.
	Kontinuierliches HP-Delta (Gegner verliert HP)
	+10 Punkte pro 0.5 Herz
	Bleibt die wichtigste Quelle für dichtes Feedback.
	Kontinuierliches HP-Delta (Agent verliert HP)
	-10 Punkte pro 0.5 Herz
	Bleibt die wichtigste Quelle für dichtes Feedback.
	Zeitstrafe
	-1 Punkt pro Frame (Hinzugefügt)