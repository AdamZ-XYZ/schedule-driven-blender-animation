import bpy
import sys
import os
import csv
import subprocess
import shutil
import time

t0 = time.perf_counter()



argv = sys.argv
argv = argv[argv.index("--") + 1:]

if len(argv) != 2:
    raise RuntimeError("Expected arguments: <processed_schedule.csv> <output_dir>")

schedule_csv = argv[0]
print("CSV BEING READ:", schedule_csv)
run_dir = argv[1]

os.makedirs(run_dir, exist_ok=True)

frames_dir = os.path.join(run_dir, "frames")
os.makedirs(frames_dir, exist_ok=True)





#Scene Setup
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.fps = 10
scene.render.image_settings.file_format = "PNG"
scene.render.use_motion_blur = False


# render
scene.camera = bpy.data.objects["Camera"]
scene.render.resolution_x =  1280
scene.render.resolution_y =  720



# Load Processed Schedule
rows = []
with open(schedule_csv, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append({
            "Activity": row["Activity"],
            "Start Frame": int(row["Start Frame"]),
            "End Frame": int(row["End Frame"]),
            "Color_R": float(row["Color_R"]),
            "Color_G": float(row["Color_G"]),
            "Color_B": float(row["Color_B"]),
        })

#Resolve Animated Objects
animated_objects = []

for row in rows:
    name = row["Activity"]  # or WBS column
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise RuntimeError(f"Object '{name}' not found in Blender file")
    animated_objects.append(obj)

animated_objects = list({obj.name: obj for obj in animated_objects}.values())

#Initial Global Hide

for obj in animated_objects:
    obj.hide_render = True
    obj.hide_viewport = True
    obj.keyframe_insert("hide_render", frame=0)
    obj.keyframe_insert("hide_viewport", frame=0)


#Apply Animation logic per row


for row in rows:
    obj = bpy.data.objects[row["Activity"]]


    # material
    if not obj.data.materials:
        mat = bpy.data.materials.new(name=f"{obj.name}_mat")
        mat.use_nodes = True
        obj.data.materials.append(mat)
    else:
        mat = obj.data.materials[0]

    # CRITICAL: make it unique
    if mat.users > 1:
        mat = mat.copy()
        obj.data.materials[0] = mat


    bsdf = mat.node_tree.nodes["Principled BSDF"]

    r = float(row["Color_R"])
    g = float(row["Color_G"])
    b = float(row["Color_B"])

    print("BLENDER: ,")
    print(r, g, b)

    #Pre Start
    bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
    if row["Start Frame"] > 2:
        bsdf.inputs["Base Color"].keyframe_insert(
            "default_value", frame=row["Start Frame"]-1
        )

    # start
    obj.hide_render = False
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
    obj.keyframe_insert("hide_render", frame=row["Start Frame"])
    bsdf.inputs["Base Color"].keyframe_insert(
        "default_value", frame=row["Start Frame"]
    )


    #Pre End
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
    bsdf.inputs["Base Color"].keyframe_insert(
        "default_value", frame=row["End Frame"]-1
    )

    # end
    bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
    bsdf.inputs["Base Color"].keyframe_insert(
        "default_value", frame=row["End Frame"]
    )

event_frames = set()

for row in rows:
    event_frames.add(row["Start Frame"])
    event_frames.add(row["End Frame"])


event_frames = sorted(event_frames)

for frame in event_frames:
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(frames_dir, f"frame_{frame:04d}.png")
    bpy.ops.render.render(write_still=True)

t1 = time.perf_counter()
print(f"Rendered {len(event_frames)} frames in {t1 - t0:.2f}s")

#FFMPEG 

fps = scene.render.fps
concat_path = os.path.join(run_dir, "frames.txt")

with open(concat_path, "w") as f:
    for i, frame in enumerate(event_frames):
        f.write(f"file 'frames/frame_{frame:04d}.png'\n")

        if i < len(event_frames) - 1:
            duration = (event_frames[i + 1] - frame) / fps
            f.write(f"duration {duration}\n")

    # repeat last frame (ffmpeg requirement)
    f.write(f"file 'frames/frame_{event_frames[-1]:04d}.png'\n")



output_mp4 = os.path.join(run_dir, "output.mp4")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", "frames.txt",
    "-fps_mode", "vfr",
    "-pix_fmt", "yuv420p",
    "output.mp4"
], check=True, cwd=run_dir)

shutil.rmtree(frames_dir) #Delte using shutil library recursive tree ver
os.remove(concat_path) #frames.txt is kept elsewhere and deleted this way



