import shutil
import tempfile 
import pandas as pd
import argparse
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta


def create_parser(): 
    parser = argparse.ArgumentParser(
        description="Schedule-driven Blender assembly animation"
    )

    parser.add_argument(
        "blend_file",
        help="Path to Blender .blend file",
    )

    parser.add_argument(
        "schedule_input",
        help="Path to schedule CSV file",
    )

    parser.add_argument(
        "--visual_type",
        choices=["Simple","WBS","Company","ActivityType","Heatmap"],
        default="Simple",
        help="default: 'Simple', else: 'WBS'",
        required = False
    )

    parser.add_argument(
        "--top_wbs",
        help="Top-level WBS to filter from (required if visual-type=WBS)"
    )

    parser.add_argument(
        "--cam_select",
        default = "Camera", #Default to be determined
        help="Camera Selection: Comma-separated camera names to include, first:N"
    )

    parser.add_argument(
    "--cam_exclude",
    default="",
    help="Comma-separated camera names to exclude"
)

    return parser

def main():
    parser = create_parser()           
    args = parser.parse_args()

    #CLI optional argument validation
    if args.visual_type == "WBS" and not args.top_wbs:
        parser.error("--top_wbs is required when --visual-type=WBS")

    #File existence checks
    blend_file = os.path.abspath(args.blend_file)
    if not os.path.isfile(blend_file):
        raise FileNotFoundError(f"Blend file not found: {blend_file}")

    schedule_input = os.path.abspath(args.schedule_input)
    if not os.path.exists(schedule_input):
        raise FileNotFoundError(f"Schedule input not found: {schedule_input}")

    # Determine Schedule file vs directory
    if os.path.isfile(schedule_input):
        if schedule_input.lower().endswith(".csv"):
            schedule_files = [schedule_input]
        else: 
            raise RuntimeError("Schedule input must be a CSV file or directory")

    elif os.path.isdir(schedule_input):
        schedule_files = sorted(
            os.path.join(schedule_input, f)
            for f in os.listdir(schedule_input)
            if f.lower().endswith(".csv") 
        )

        if not schedule_files:
            raise RuntimeError("No CSV files found in schedule directory")

    else:
        raise RuntimeError("Schedule input must be a CSV file or directory")
    

    #CSV Handling
    for schedule_csv in schedule_files:

        #Create Outputs\{Schedule_name}
        schedule_name = os.path.splitext(os.path.basename(schedule_csv))[0]
        run_dir = os.path.join("outputs", schedule_name)
        os.makedirs(run_dir, exist_ok=True)

        #CSV Transformation for Blender 
        schedule = pd.read_csv(schedule_csv)

        # WBS Filtering
        if args.top_wbs:
            top_wbs = args.top_wbs
            
            #Mask out anything not containing top_wbs
            mask = schedule["WBS"].astype(str).apply(
                lambda wbs: top_wbs in wbs.split(".")
            )
            schedule = schedule[mask]
            
            #Currently Reroot is not necessary
            #Supports future WBS features i.e Level filtering etc.
            def reroot_wbs(wbs, root):
                parts = wbs.split(".")
                idx = parts.index(root)
                return ".".join(parts[idx:]) #From Index -> End
            
            schedule["WBS"] = schedule["WBS"].apply(
                lambda wbs: reroot_wbs(wbs, top_wbs) #replace w new root
            )

        # Company/Activity Filtering
        if args.visual_type in ("Company", "ActivityType"):
            filterValue = sorted(schedule[args.visual_type].unique())

            import colorsys
            def generate_palette(n, s=0.8, v=0.9):
                colors = []
                for i in range(n):
                    h = i / n
                    r, g, b = colorsys.hsv_to_rgb(h, s, v)
                    colors.append((r, g, b))
                    print(r, g, b)
                return colors
            
            palette = generate_palette(len(filterValue))

            ColorDictionary = {
                group: palette[i]
                for i, group in enumerate(filterValue)
            }

        #Resource normalisation
        if args.visual_type == "Heatmap":
           

            day_span = schedule["End"] - schedule["Start"]
            schedule["Resources"] = schedule["Resources"] / day_span

            max_daily = schedule["Resources"].max()
            preserveMinResource = schedule["Resources"].min()
            preserveMaxResource = max_daily

            schedule["Resources"] = schedule["Resources"] / max_daily
        

        #Evaluate schedule chronology logic
        for row in schedule.to_dict(orient="records"):
            
            start = row["Start"]
            end   = row["End"]
            if end < start:
                raise ValueError(
                    f"Critical Error for {row['Activity']}: "
                    f"End < Start ({end} < {start})"
                )

        #Converting times to keyframe values]
        true_start = schedule["Start"].min() #First frame - Lowest frame = 0
        fps = 1

        processed = pd.DataFrame({
            "Activity": schedule["Activity"],
            "Start Frame": ((schedule["Start"] - true_start) * fps).astype(int),
            "End Frame": ((schedule["End"] - true_start) * fps).astype(int),
            "Daily Resource":schedule["Resources"]
        })

        # Optional Color implementation
        if args.visual_type in ("Company", "ActivityType"):
            processed[["Color_R", "Color_G", "Color_B"]] = (
                schedule[args.visual_type]
                .map(ColorDictionary)
                .apply(pd.Series)
            )

        
        if args.visual_type in ("Heatmap"):
            processed["Color_R"] = processed["Daily Resource"]
            processed["Color_G"] = 0
            processed["Color_B"] = 1 - processed["Daily Resource"]


     
        # Creating temp.csv for blender
        tmp = tempfile.NamedTemporaryFile(
            suffix=".csv",
            delete=False
        )
        processed.to_csv(tmp.name, index=False)
        tmp.close()

        temp_csv_path = tmp.name
        blender_exe = "/Applications/Blender.app/Contents/MacOS/Blender"
        blender_script = os.path.abspath("render_animation.py")
       
    
        subprocess.run([
            blender_exe,
            "--background",
            blend_file,
            "--python",
            blender_script,
            "--",
            temp_csv_path,
            run_dir
        ], check=True)


        #Legend Generation
        def overlay_legend(
            image_path,
            *,
            date,
            visual_type,
            heatmap_range=None,
            category_colors=None
        ):
            img = Image.open(image_path).convert("RGBA")
            draw = ImageDraw.Draw(img)

            W, H = img.size
            pad = 20
            x = pad
            y = pad

            # Date
            draw.text(
                (x, y),
                f"Date: {date.strftime('%d-%b-%Y')}",
                fill=(255, 255, 255, 255)
            )
            y += 30

            # Heatmap Legend
            if visual_type == "Heatmap" and heatmap_range:
                min_v, max_v = heatmap_range

                bar_w = 200
                bar_h = 20

                for i in range(bar_w):
                    t = i / bar_w
                    r = int(255 * t)
                    b = int(255 * (1 - t))
                    draw.line(
                        [(x + i, y), (x + i, y + bar_h)],
                        fill=(r, 0, b, 255)
                    )

                draw.text((x, y + bar_h + 5), f"Min: {min_v}", fill=(255, 255, 255, 255))
                draw.text((x + bar_w - 60, y + bar_h + 5), f"Max: {max_v}", fill=(255, 255, 255, 255))
                y += bar_h + 30

            # Company/Activity Legend
            if visual_type in ("Company", "ActivityType") and category_colors:
                for name, (r, g, b) in category_colors.items():
                    draw.rectangle(
                        [x, y, x + 20, y + 20],
                        fill=(int(r * 255), int(g * 255), int(b * 255), 255)
                    )
                    draw.text((x + 30, y), name, fill=(255, 255, 255, 255))
                    y += 25

            img.save(image_path)



        #FFMPEG Needs to be Moved Here
        for cam in os.listdir(run_dir):
                cam_dir = os.path.join(run_dir, cam)
                frames_dir = os.path.join(cam_dir, "frames")
                if not os.path.isdir(frames_dir):
                    continue

                frames = sorted(
                    f for f in os.listdir(frames_dir) if f.endswith(".png")
                )

                epoch = datetime(1970, 1, 1)

                # Example values — already known in main.py
                heatmap_range = (
                    round(preserveMinResource,1),
                    round(preserveMaxResource,1)
                ) if args.visual_type == "Heatmap" else None

                category_colors = ColorDictionary if args.visual_type in ("Company", "ActivityType") else None

                for frame_file in frames:
                    frame_index = int(frame_file.split("_")[1].split(".")[0])
                    frame_date = epoch + timedelta(days=frame_index)

                    overlay_legend(
                        image_path=os.path.join(frames_dir, frame_file),
                        date=frame_date,
                        visual_type=args.visual_type,
                        heatmap_range=heatmap_range,
                        category_colors=category_colors
                    )

                concat_path = os.path.join(cam_dir, "frames.txt")
                with open(concat_path, "w") as f:
                    for frame in frames:
                        f.write(f"file '{os.path.abspath(os.path.join(frames_dir, frame))}'\n")
                        f.write(f"duration {1 / fps}\n")
                    f.write(f"file '{os.path.abspath(os.path.join(frames_dir, frames[-1]))}'\n")

                output_mp4 = os.path.join(cam_dir, "output.mp4")

                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_path,
                    "-fps_mode", "vfr",
                    "-pix_fmt", "yuv420p",
                    output_mp4
                ], check=True)

                shutil.rmtree(frames_dir)
                os.remove(concat_path)

        os.remove(tmp.name)



if __name__ == "__main__":
    main()
