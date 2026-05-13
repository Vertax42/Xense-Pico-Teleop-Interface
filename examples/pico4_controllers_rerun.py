"""
Pico4 Controller Visualization with Rerun

Visualizes:
- World coordinate system origin
- Headset pose
- Left/Right controller poses
- Motion trackers (if available)

Pico Coordinate System (Left-handed):
- X: Right (向右)
- Y: Up (向上)
- Z: Forward/In (向前，远离用户，进入场景)
- World origin: Headset position when VR app starts (app启动时headset的位置)

Note: Despite Pico docs saying "right-handed", the actual axis convention
(X right, Y up, Z in) is LEFT-HANDED.
"""

import sys
import time
import math

import numpy as np
import rerun as rr
import xensevr_pc_service_sdk as xrt


TRACKER_TRAIL_MAX_POINTS = 50


def quaternion_to_rotation_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    """Convert quaternion to 3x3 rotation matrix."""
    # Normalize quaternion
    norm = np.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if norm < 1e-10:
        return np.eye(3)
    qx, qy, qz, qw = qx/norm, qy/norm, qz/norm, qw/norm

    return np.array([
        [1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
        [2*(qx*qy + qz*qw), 1 - 2*(qx*qx + qz*qz), 2*(qy*qz - qx*qw)],
        [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx*qx + qy*qy)]
    ])


def quaternion_to_euler_degrees(qx: float, qy: float, qz: float, qw: float) -> tuple[float, float, float]:
    """Convert quaternion to roll/pitch/yaw angles in degrees."""
    norm = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if norm < 1e-10:
        return 0.0, 0.0, 0.0

    qx, qy, qz, qw = qx/norm, qy/norm, qz/norm, qw/norm

    roll = math.atan2(
        2.0 * (qw*qx + qy*qz),
        1.0 - 2.0 * (qx*qx + qy*qy),
    )
    pitch_sin = 2.0 * (qw*qy - qz*qx)
    pitch = math.asin(max(-1.0, min(1.0, pitch_sin)))
    yaw = math.atan2(
        2.0 * (qw*qz + qx*qy),
        1.0 - 2.0 * (qy*qy + qz*qz),
    )

    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


def safe_entity_name(value: object) -> str:
    """Return a path-safe ASCII name for a Rerun entity segment."""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)

    safe = "".join(
        ch if ch.isascii() and (ch.isalnum() or ch in "_-") else "_"
        for ch in text
    ).strip("_")
    return safe or "tracker"


def log_pose_arrows(
    entity_path: str,
    position: tuple,
    quaternion: tuple,
    length: float = 0.08,
    radius: float = 0.005
):
    """Log pose axes as RGB arrows (X=red, Y=green, Z=blue).

    Arrows are drawn in world coordinates with rotation applied.
    """
    x, y, z = position
    qx, qy, qz, qw = quaternion

    # Calculate rotation matrix from quaternion
    rot_mat = quaternion_to_rotation_matrix(qx, qy, qz, qw)
    origin = np.array([x, y, z])

    # Rotate local axes by the quaternion
    x_dir = rot_mat @ np.array([length, 0, 0])
    y_dir = rot_mat @ np.array([0, length, 0])
    z_dir = rot_mat @ np.array([0, 0, length])

    rr.log(
        f"{entity_path}/axes",
        rr.Arrows3D(
            origins=[origin, origin, origin],
            vectors=[x_dir, y_dir, z_dir],
            colors=[[255, 80, 80], [80, 255, 80], [80, 80, 255]],
            radii=radius,
        )
    )


def log_controller_mesh(entity_path: str, position: tuple, quaternion: tuple, color: tuple):
    """Log a simple box mesh to represent the controller in world coordinates."""
    x, y, z = position
    qx, qy, qz, qw = quaternion
    # Simple box representing controller grip
    half_extents = [0.03, 0.02, 0.06]  # width, height, depth

    rr.log(
        f"{entity_path}/mesh",
        rr.Boxes3D(
            centers=[[x, y, z]],
            half_sizes=[half_extents],
            quaternions=[rr.Quaternion(xyzw=[qx, qy, qz, qw])],
            colors=[color],
        )
    )


def log_headset_mesh(entity_path: str, position: tuple, quaternion: tuple):
    """Log a simple mesh to represent the headset in world coordinates."""
    x, y, z = position
    qx, qy, qz, qw = quaternion
    # Box representing headset
    half_extents = [0.08, 0.05, 0.05]

    rr.log(
        f"{entity_path}/mesh",
        rr.Boxes3D(
            centers=[[x, y, z]],
            half_sizes=[half_extents],
            quaternions=[rr.Quaternion(xyzw=[qx, qy, qz, qw])],
            colors=[[60, 60, 60, 200]],
        )
    )


def log_tracker_mesh(entity_path: str, position: tuple, quaternion: tuple, color: tuple):
    """Log a simple ellipsoid to represent a tracker in world coordinates."""
    x, y, z = position
    qx, qy, qz, qw = quaternion

    rr.log(
        f"{entity_path}/mesh",
        rr.Ellipsoids3D(
            centers=[[x, y, z]],
            half_sizes=[[0.025, 0.025, 0.015]],
            quaternions=[rr.Quaternion(xyzw=[qx, qy, qz, qw])],
            colors=[color],
        )
    )


def log_tracker_pose(
    entity_path: str,
    serial_number: str,
    position: tuple,
    quaternion: tuple,
    color: tuple,
    trail_points: list,
):
    """Log tracker position, rotation, trail, and numeric pose values."""
    x, y, z = (float(position[0]), float(position[1]), float(position[2]))
    qx, qy, qz, qw = (
        float(quaternion[0]),
        float(quaternion[1]),
        float(quaternion[2]),
        float(quaternion[3]),
    )
    roll, pitch, yaw = quaternion_to_euler_degrees(qx, qy, qz, qw)
    safe_name = entity_path.rsplit("/", 1)[-1]

    rr.log(
        f"world/tracker_frames/{safe_name}",
        rr.Transform3D(
            translation=[x, y, z],
            quaternion=rr.Quaternion(xyzw=[qx, qy, qz, qw]),
            axis_length=0.12,
        )
    )

    log_pose_arrows(
        entity_path,
        position=(x, y, z),
        quaternion=(qx, qy, qz, qw),
        length=0.12,
        radius=0.006,
    )
    log_tracker_mesh(
        entity_path,
        position=(x, y, z),
        quaternion=(qx, qy, qz, qw),
        color=color,
    )

    rr.log(
        f"{entity_path}/position",
        rr.Points3D(
            [[x, y, z]],
            labels=[f"{serial_number}\nxyz=({x:.3f}, {y:.3f}, {z:.3f})\nrpy=({roll:.1f}, {pitch:.1f}, {yaw:.1f})"],
            show_labels=True,
            colors=[color],
            radii=0.018,
        )
    )

    if len(trail_points) >= 2:
        rr.log(
            f"{entity_path}/trail",
            rr.LineStrips3D(
                [trail_points],
                colors=[color],
                radii=0.004,
            )
        )

    rr.log(f"tracker_values/{safe_name}/position/x", rr.Scalars(x))
    rr.log(f"tracker_values/{safe_name}/position/y", rr.Scalars(y))
    rr.log(f"tracker_values/{safe_name}/position/z", rr.Scalars(z))
    rr.log(f"tracker_values/{safe_name}/quaternion/x", rr.Scalars(qx))
    rr.log(f"tracker_values/{safe_name}/quaternion/y", rr.Scalars(qy))
    rr.log(f"tracker_values/{safe_name}/quaternion/z", rr.Scalars(qz))
    rr.log(f"tracker_values/{safe_name}/quaternion/w", rr.Scalars(qw))
    rr.log(f"tracker_values/{safe_name}/euler_deg/roll", rr.Scalars(roll))
    rr.log(f"tracker_values/{safe_name}/euler_deg/pitch", rr.Scalars(pitch))
    rr.log(f"tracker_values/{safe_name}/euler_deg/yaw", rr.Scalars(yaw))

    rr.log(
        f"tracker_status/{safe_name}",
        rr.TextDocument(
            f"Tracker: {serial_number}\n"
            f"Position xyz (m): {x:.4f}, {y:.4f}, {z:.4f}\n"
            f"Quaternion xyzw: {qx:.5f}, {qy:.5f}, {qz:.5f}, {qw:.5f}\n"
            f"Euler rpy (deg): {roll:.2f}, {pitch:.2f}, {yaw:.2f}"
        )
    )


def setup_rerun():
    """Initialize Rerun and set up the scene."""
    rr.init("Pico4 Controller Visualization", spawn=True)

    # Pico coordinate system: X=Right, Y=Up, Z=Forward/In (away from user)
    # This is LEFT-HANDED coordinate system (despite docs saying "right-handed")
    # World origin = Headset position when VR app starts
    rr.log("world", rr.ViewCoordinates.LEFT_HAND_Y_UP, static=True)

    # === World Origin - Large Coordinate Axes ===
    # X (Red)   = Right  向右
    # Y (Green) = Up     向上
    # Z (Blue)  = Forward/In 向前 (用户面对的方向)
    origin = np.array([0, 0, 0])
    axis_length = 0.8  # 80cm axes
    axis_radius = 0.015  # Thick arrows

    rr.log(
        "world/origin/axes",
        rr.Arrows3D(
            origins=[origin, origin, origin],
            vectors=[
                [axis_length, 0, 0],  # X axis (Right)
                [0, axis_length, 0],  # Y axis (Up)
                [0, 0, axis_length],  # Z axis (Forward)
            ],
            colors=[
                [255, 50, 50],    # X = Red (Right)
                [50, 255, 50],    # Y = Green (Up)
                [50, 50, 255],    # Z = Blue (Forward)
            ],
            radii=axis_radius,
        ),
        static=True
    )

    # Add axis labels (text annotations at end of each axis)
    label_offset = axis_length + 0.1
    rr.log(
        "world/origin/label_x",
        rr.Points3D([[label_offset, 0, 0]], colors=[[255, 50, 50]], radii=0.03),
        static=True
    )
    rr.log(
        "world/origin/label_y",
        rr.Points3D([[0, label_offset, 0]], colors=[[50, 255, 50]], radii=0.03),
        static=True
    )
    rr.log(
        "world/origin/label_z",
        rr.Points3D([[0, 0, label_offset]], colors=[[50, 50, 255]], radii=0.03),
        static=True
    )

    # Add a ground grid for reference
    grid_size = 3.0
    grid_lines = 31
    grid_points = []

    for i in range(grid_lines):
        t = -grid_size / 2 + i * grid_size / (grid_lines - 1)
        # Lines parallel to X axis
        grid_points.append([[t, 0, -grid_size/2], [t, 0, grid_size/2]])
        # Lines parallel to Z axis
        grid_points.append([[-grid_size/2, 0, t], [grid_size/2, 0, t]])

    rr.log(
        "world/grid",
        rr.LineStrips3D(
            grid_points,
            colors=[[100, 100, 100, 60]],
        ),
        static=True
    )


def run_visualization():
    print("Starting Pico4 Controller Visualization with Rerun...")

    try:
        print("Initializing SDK...")
        xrt.init()
        print("SDK initialized successfully.")

        print("Setting up Rerun visualization...")
        setup_rerun()
        print("Rerun visualization ready.")

        time.sleep(1)

        start_time = time.monotonic()
        tracker_trails = {}
        tracker_colors = [
            [255, 165, 0, 200],
            [138, 43, 226, 200],
            [0, 206, 209, 200],
            [255, 20, 147, 200],
        ]
        iteration = 0
        while True:
            rr.set_time("frame", sequence=iteration)
            rr.set_time("time", duration=time.monotonic() - start_time)

            # Get poses
            left_pose = xrt.get_left_controller_pose()
            right_pose = xrt.get_right_controller_pose()
            headset_pose = xrt.get_headset_pose()

            # Get inputs
            left_trigger = xrt.get_left_trigger()
            right_trigger = xrt.get_right_trigger()
            left_grip = xrt.get_left_grip()
            right_grip = xrt.get_right_grip()

            # === Log Headset ===
            log_pose_arrows(
                "world/headset",
                position=(headset_pose[0], headset_pose[1], headset_pose[2]),
                quaternion=(headset_pose[3], headset_pose[4], headset_pose[5], headset_pose[6]),
                length=0.12,
                radius=0.008
            )
            log_headset_mesh(
                "world/headset",
                position=(headset_pose[0], headset_pose[1], headset_pose[2]),
                quaternion=(headset_pose[3], headset_pose[4], headset_pose[5], headset_pose[6]),
            )
            # Label above headset (world coords, Y=up)
            rr.log(
                "world/headset/label",
                rr.Points3D(
                    [[headset_pose[0], headset_pose[1] + 0.12, headset_pose[2]]],
                    labels=["Headset"],
                    colors=[[200, 200, 200]],
                    radii=0.005,
                )
            )

            # === Log Left Controller ===
            # Color based on trigger/grip state
            left_color = [
                int(100 + 155 * left_trigger),  # Red increases with trigger
                int(100 + 155 * left_grip),      # Green increases with grip
                200,
                230
            ]

            log_pose_arrows(
                "world/left_controller",
                position=(left_pose[0], left_pose[1], left_pose[2]),
                quaternion=(left_pose[3], left_pose[4], left_pose[5], left_pose[6]),
            )
            log_controller_mesh(
                "world/left_controller",
                position=(left_pose[0], left_pose[1], left_pose[2]),
                quaternion=(left_pose[3], left_pose[4], left_pose[5], left_pose[6]),
                color=left_color,
            )
            # Label above controller (world coords, Y=up)
            rr.log(
                "world/left_controller/label",
                rr.Points3D(
                    [[left_pose[0], left_pose[1] + 0.12, left_pose[2]]],
                    labels=["Left"],
                    colors=[[100, 200, 255]],
                    radii=0.005,
                )
            )

            # === Log Right Controller ===
            right_color = [
                int(100 + 155 * right_trigger),
                int(100 + 155 * right_grip),
                200,
                230
            ]

            log_pose_arrows(
                "world/right_controller",
                position=(right_pose[0], right_pose[1], right_pose[2]),
                quaternion=(right_pose[3], right_pose[4], right_pose[5], right_pose[6]),
            )
            log_controller_mesh(
                "world/right_controller",
                position=(right_pose[0], right_pose[1], right_pose[2]),
                quaternion=(right_pose[3], right_pose[4], right_pose[5], right_pose[6]),
                color=right_color,
            )
            # Label above controller (world coords, Y=up)
            rr.log(
                "world/right_controller/label",
                rr.Points3D(
                    [[right_pose[0], right_pose[1] + 0.12, right_pose[2]]],
                    labels=["Right"],
                    colors=[[255, 200, 100]],
                    radii=0.005,
                )
            )

            # === Log Motion Trackers ===
            num_trackers = xrt.num_motion_data_available()
            if num_trackers > 0:
                tracker_poses = xrt.get_motion_tracker_pose()
                tracker_serial_numbers = xrt.get_motion_tracker_serial_numbers()

                for idx in range(num_trackers):
                    pose = tracker_poses[idx]
                    sn = tracker_serial_numbers[idx] if idx < len(tracker_serial_numbers) else f"tracker_{idx}"
                    sn_text = sn.decode("utf-8", errors="replace") if isinstance(sn, bytes) else str(sn)
                    sn_safe = safe_entity_name(sn_text)
                    color = tracker_colors[idx % len(tracker_colors)]

                    entity_path = f"world/trackers/{sn_safe}"
                    position = (pose[0], pose[1], pose[2])
                    quaternion = (pose[3], pose[4], pose[5], pose[6])
                    trail = tracker_trails.setdefault(sn_safe, [])
                    trail.append([float(position[0]), float(position[1]), float(position[2])])
                    if len(trail) > TRACKER_TRAIL_MAX_POINTS:
                        del trail[:-TRACKER_TRAIL_MAX_POINTS]

                    log_tracker_pose(
                        entity_path,
                        serial_number=sn_text,
                        position=position,
                        quaternion=quaternion,
                        color=color,
                        trail_points=trail,
                    )

            # === Log scalar values ===
            rr.log("inputs/left_trigger", rr.Scalars(left_trigger))
            rr.log("inputs/right_trigger", rr.Scalars(right_trigger))
            rr.log("inputs/left_grip", rr.Scalars(left_grip))
            rr.log("inputs/right_grip", rr.Scalars(right_grip))

            # === Log text annotation ===
            rr.log(
                "status",
                rr.TextDocument(
                    f"Iteration: {iteration + 1}\n"
                    f"Trackers: {num_trackers}\n"
                    f"L Trigger: {left_trigger:.2f} | Grip: {left_grip:.2f}\n"
                    f"R Trigger: {right_trigger:.2f} | Grip: {right_grip:.2f}"
                )
            )

            # Print status to console periodically
            if iteration % 50 == 0:
                print(f"[{iteration}] Headset: ({headset_pose[0]:.2f}, {headset_pose[1]:.2f}, {headset_pose[2]:.2f}) | Trackers: {num_trackers}")

            time.sleep(0.02)  # ~50 Hz
            iteration += 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except RuntimeError as e:
        print(f"Runtime Error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        print("\nClosing SDK...")
        xrt.close()
        print("SDK closed.")
        print("Visualization finished.")


if __name__ == "__main__":
    run_visualization()
