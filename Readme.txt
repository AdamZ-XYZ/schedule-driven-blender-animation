Schedule Driven Blender Animation Script
Command Line
main.py {Model.blend} {schedule_input} {--visual_type}

Inputs:
Schedule CSV or directory of CSV's for Batch.
    Schedule Format : Activity (String), Start (int), Finish (int), WBS (Level.Level1.Level2 String) [OPTIONAL]
Blender Model: Activity - Object corresponding names.

Outputs:
Output.mp4 of schedule driven highlight of currently active activities

Input rules:
Model MUST contain ALL Schedule activities as objects.
Model MAY contain EXTRA objects.
Schedule MAY have negative star/end times.
Schedule MAY include WBS hierachies
Activity MUST start before it ends.
Activities MAY overlap

