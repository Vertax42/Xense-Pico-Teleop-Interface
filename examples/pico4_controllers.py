import sys
import time

import xensevr_pc_service_sdk as xrt


def clear_screen():
    """Clear terminal and move cursor to top"""
    print("\033[2J\033[H", end="")


def run_tests():
    print("Starting Python binding test...")

    try:
        print("Initializing SDK...")
        xrt.init()
        print("SDK Initialized successfully.")
        time.sleep(1)

        i = 0
        while True:
            clear_screen()

            print("=" * 60)
            print(f"  XenseVR Controller Data  |  Iteration: {i+1}")
            print("=" * 60)

            # Controller Poses
            left_pose = xrt.get_left_controller_pose()
            right_pose = xrt.get_right_controller_pose()
            print(f"\n[Left Controller Pose]")
            print(f"  Position:    x={left_pose[0]:8.4f}  y={left_pose[1]:8.4f}  z={left_pose[2]:8.4f}")
            print(f"  Quaternion: qx={left_pose[3]:8.4f} qy={left_pose[4]:8.4f} qz={left_pose[5]:8.4f} qw={left_pose[6]:8.4f}")

            print(f"\n[Right Controller Pose]")
            print(f"  Position:    x={right_pose[0]:8.4f}  y={right_pose[1]:8.4f}  z={right_pose[2]:8.4f}")
            print(f"  Quaternion: qx={right_pose[3]:8.4f} qy={right_pose[4]:8.4f} qz={right_pose[5]:8.4f} qw={right_pose[6]:8.4f}")

            # Headset Pose
            headset_pose = xrt.get_headset_pose()
            print(f"\n[Headset Pose]")
            print(f"  Position:    x={headset_pose[0]:8.4f}  y={headset_pose[1]:8.4f}  z={headset_pose[2]:8.4f}")
            print(f"  Quaternion: qx={headset_pose[3]:8.4f} qy={headset_pose[4]:8.4f} qz={headset_pose[5]:8.4f} qw={headset_pose[6]:8.4f}")

            # Triggers & Grips
            left_trigger = xrt.get_left_trigger()
            right_trigger = xrt.get_right_trigger()
            left_grip = xrt.get_left_grip()
            right_grip = xrt.get_right_grip()

            print(f"\n[Inputs]")
            print(f"  Left  Trigger: {left_trigger:6.3f}    Grip: {left_grip:6.3f}")
            print(f"  Right Trigger: {right_trigger:6.3f}    Grip: {right_grip:6.3f}")

            print("\n" + "=" * 60)
            print("  Press Ctrl+C to exit")
            print("=" * 60)

            sys.stdout.flush()
            time.sleep(0.02)
            i += 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except RuntimeError as e:
        print(f"Runtime Error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
    finally:
        print("\nClosing SDK...")
        xrt.close()
        print("SDK closed.")
        print("Test finished.")


if __name__ == "__main__":
    run_tests()
