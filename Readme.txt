Schedule Driven Blender Animation Script

Inputs:
Schedule Format : Activity (String), Start (int), Finish (int).
Blender Model: Activity - Object corresponding names.

Outputs:
Output.mp4 of schedule driven highlight of currently active activities

Input rules:
Model MUST contain ALL Schedule activities as objects.
Model MAY contain EXTRA objects.
Schedule MAY have negative star/end times.
Activity MUST start before it ends.
Activities MAY overlap

