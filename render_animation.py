import bpy
import sys
import os
import csv
import subprocess
import shutil
import time
import argparse


raw_argv = sys.argv
script_argv = raw_argv[raw_argv.index("--") + 1:] if "--" in raw_argv else []

def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Blender render orchestration"
    )

    parser.add_argument(
        "schedule_csv",
        help="Processed schedule CSV"
    )

    parser.add_argument(
        "run_dir",
        help="Output directory for this run"
    )

    parser.add_argument(
        "--cam_select",
        default="all",
        help="Camera selection: all | first:N | CamA,CamB"
    )

    parser.add_argument(
        "--cam_exclude",
        default="",
        help="Comma-separated camera names to exclude"
    )

    return parser.parse_args(argv)

args = parse_args(script_argv)


schedule_csv = args.schedule_csv
run_dir = args.run_dir

os.makedirs(run_dir, exist_ok=True)

#Scene Setup
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.fps = 10
scene.render.image_settings.file_format = "PNG"
scene.render.use_motion_blur = False

# render
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
            "Color_R": float(row.get("Color_R", 1.0)),
            "Color_G": float(row.get("Color_G", 0.0)),
            "Color_B": float(row.get("Color_B", 0.0)),
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

# Camera Select Handling
all_cameras = sorted(
    [obj for obj in bpy.data.objects if obj.type == "CAMERA"],
    key=lambda o: o.name
)

arg = args.cam_select

if arg == "all":
    selected = all_cameras

elif arg.startswith("first:"):
    n = int(arg.split(":")[1])
    selected = all_cameras[:n]

else:
    names = set(arg.split(","))
    selected = [c for c in all_cameras if c.name in names]

if args.cam_exclude:
    exclude = set(args.cam_exclude.split(","))
    selected = [c for c in selected if c.name not in exclude    ]

if not selected:
    raise RuntimeError(
        f"No cameras selected. "
        f"Available cameras: {[c.name for c in all_cameras]}"
    )

if arg not in ("all",) and not arg.startswith("first:"):
    requested = set(arg.split(","))
    found = {c.name for c in selected}
    missing = requested - found

    if missing:
        raise RuntimeError(
            f"Unknown camera(s): {', '.join(sorted(missing))}"
        )


#Apply Animation logic per row - Now included Camera Loop



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


for cam in selected:
    scene.camera = cam
    cam_run_dir = os.path.join(run_dir, cam.name)
    frames_dir = os.path.join(cam_run_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)




    for frame in event_frames:
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(
            frames_dir, f"frame_{frame:04d}.png"
        )
        bpy.ops.render.render(write_still=True)

    #FFMPEG 

    fps = scene.render.fps
    concat_path = os.path.join(cam_run_dir, "frames.txt")

    with open(concat_path, "w") as f:
        for i, frame in enumerate(event_frames):
            png_path = os.path.abspath(
                os.path.join(frames_dir, f"frame_{frame:04d}.png")
            )
            f.write(f"file '{png_path}'\n")

            if i < len(event_frames) - 1:
                duration = (event_frames[i + 1] - frame) / fps
                f.write(f"duration {duration}\n")

        f.write(f"file '{png_path}'\n")



    output_mp4 = os.path.join(cam_run_dir, "output.mp4")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_path,
        "-fps_mode", "vfr",
        "-pix_fmt", "yuv420p",
        output_mp4
    ], check=True)

    shutil.rmtree(frames_dir) #Delte using shutil library recursive tree ver
    os.remove(concat_path) #frames.txt is kept elsewhere and deleted this way



