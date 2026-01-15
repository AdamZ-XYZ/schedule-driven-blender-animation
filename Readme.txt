# Schedule-Driven Blender Animation

A command-line–driven Blender animation pipeline that visualises a schedule on a 3D blender model.
The animation highlights active activities over time based on a CSV-defined schedule aligned to object names in a Blender model.

---

## Usage

```bash
python3 main.py <Model.blend> <schedule_input> [--visual_type <type>]
```

### Arguments

* `Model.blend`
  Blender file containing the 3D model.

* `schedule_input`
  Path to:

  * a single schedule CSV file, **or**
  * a directory containing multiple schedule CSVs (batch mode).

* `--visual_type` *(optional)*
  Controls how activities are visually encoded.
  Defaults to `Simple`.

---

## Inputs

### 1. Schedule (CSV)

Each schedule CSV must contain the following columns:

| Column        | Type   | Required | Description                                            |
| --------------| ------ | -------- | ------------------------------------------------------ |
| Activity      | string | Yes      | Name of the activity; must match a Blender object name |
| Start         | int    | Yes      | Start time                                             |
| Finish        | int    | Yes      | Finish time                                            |
| WBS           | string | No       | Hierarchical work breakdown structure (e.g. `A.B.C`)   |
| Company       | string | No       | Comapny Name for optionl colour seperation.            |
| ActivityType  | string | No       | Activity type for optionl colour seperation.           |

#### Notes

* Schedules may contain **negative start or finish times**
* Activities may **overlap**
* WBS hierarchies may be arbitrarily deep

---

### 2. Blender Model

* Each **Activity** must correspond to a Blender object name
* The model **may include additional objects** not referenced in the schedule
* Objects not referenced in the schedule are ignored

---

## Outputs

For each schedule (and for each selected camera, if enabled):

* `output.mp4`
  A rendered animation showing:

  * activities appearing when they start
  * visual highlighting while active
  * persistence after completion (based on visual mode)

Outputs are written to a structured directory under the run output folder.

---

## Input Rules & Constraints

* The Blender model **must contain all scheduled activities**
* The Blender model **may contain surplus objects**
* `Start < Finish` is required for all activities
* Activities may overlap in time
* Negative time values are permitted
* WBS data is optional and ignored unless explicitly used by the selected visual mode

---

## Design Intent

* **Deterministic**: output depends only on schedule + model
* **Scriptable**: no UI interaction required
* **Scalable**: render cost scales with number of schedule events, not frame count
* **Extensible**: supports additional visual modes (company, WBS, heatmaps, etc.)
* **heatmaps** to be added next update

###  NOTE
Code is currently messy af with ad hoc fixed. Will be cleaned soon.