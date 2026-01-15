import tempfile 
import pandas as pd
import argparse
import os
import subprocess
import sys

def parse_args():
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
        choices=["Simple","WBS","Company","ActivityType"],
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
        default = "Camera",
        help="Camera Selection: Comma-separated camera names to include, first:N"
    )

    parser.add_argument(
    "--cam_exclude",
    default="",
    help="Comma-separated camera names to exclude"
)

    return parser


def main():
    parser = parse_args()
    args = parser.parse_args()

    if args.visual_type == "WBS" and not args.top_wbs:
        parser.error("--top_wbs is required when --visual-type=WBS")


    blend_file = os.path.abspath(args.blend_file)

    if not os.path.isfile(blend_file):
        raise FileNotFoundError(f"Blend file not found: {blend_file}")

    schedule_input = os.path.abspath(args.schedule_input)

    if not os.path.exists(schedule_input):
        raise FileNotFoundError(f"Schedule input not found: {schedule_input}")

    if os.path.isfile(schedule_input):
        schedule_files = [schedule_input]

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
    
    for schedule_csv in schedule_files:

        schedule_name = os.path.splitext(os.path.basename(schedule_csv))[0]
        run_dir = os.path.join("outputs", schedule_name)
        os.makedirs(run_dir, exist_ok=True)

        schedule = pd.read_csv(schedule_csv)

        # WBS Filtering - Re Rooting Approach
        if args.top_wbs:
            top_wbs = args.top_wbs
            mask = schedule["WBS"].astype(str).apply(
                lambda wbs: top_wbs in wbs.split(".")
            )
            schedule = schedule[mask]
            
            def reroot_wbs(wbs, root):
                parts = wbs.split(".")
                idx = parts.index(root)
                return ".".join(parts[idx:])
            
            schedule["WBS"] = schedule["WBS"].apply(
                lambda wbs: reroot_wbs(wbs, top_wbs)
            )

        # Company/Activity Filtering
        if args.visual_type == "Company" or args.visual_type == "ActivityType":
            values = sorted(schedule[args.visual_type].unique())

            import colorsys

            def generate_palette(n, s=0.8, v=0.9):
                colors = []
                for i in range(n):
                    h = i / n
                    r, g, b = colorsys.hsv_to_rgb(h, s, v)
                    colors.append((r, g, b, 1.0))
                    print(r, g, b)
                return colors
            
            palette = generate_palette(len(values))

            ColorDictionary = {
                group: palette[i]
                for i, group in enumerate(values)
            }


        for row in schedule.to_dict(orient="records"):
            
            start = row["Start"]
            end   = row["End"]
            if end < start:
                raise ValueError(
                    f"Critical Error for {row['Activity']}: "
                    f"End < Start ({end} < {start})"
                )

        true_start = schedule["Start"].min()
        fps = 1

        if args.visual_type == "Company" or args.visual_type == "ActivityType": #Quick Fix
            processed = pd.DataFrame({
                "Activity": schedule["Activity"],
                "Start Frame": ((schedule["Start"] - true_start) * fps).astype(int),
                "End Frame": ((schedule["End"] - true_start) * fps).astype(int),
                "Color_R": schedule[args.visual_type].map(lambda c: ColorDictionary[c][0]),
                "Color_G": schedule[args.visual_type].map(lambda c: ColorDictionary[c][1]),
                "Color_B": schedule[args.visual_type].map(lambda c: ColorDictionary[c][2]),
            })
        else: 
            processed = pd.DataFrame({
                "Activity": schedule["Activity"],
                "Start Frame": ((schedule["Start"] - true_start) * fps).astype(int),
                "End Frame": ((schedule["End"] - true_start) * fps).astype(int),
            })



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


if __name__ == "__main__":
    main()
