import tempfile 
import pandas as pd
import argparse
import os
import subprocess

def parse_args():
    parser = argparse.ArgumentParser(
        description="Schedule-driven Blender assembly animation"
    )

    parser.add_argument(
        "blend_file",
        help="Path to Blender .blend file"
    )

    parser.add_argument(
        "schedule_input",
        help="Path to schedule CSV file"
    )

    return parser.parse_args()


def main():
    args = parse_args()

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
