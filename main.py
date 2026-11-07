import argparse
import json


def main():
    parser = argparse.ArgumentParser(description='Exam behavior review - phones and head movement')
    parser.add_argument('--video',help='Run headless on a selected video')
    parser.add_argument('--output',help='Output folder for headless execution')
    parser.add_argument('--config',help='Threshold YAML for headless execution')
    args = parser.parse_args()
    if args.video:
        from src.pipeline import process_video
        print(json.dumps(process_video(args.video,args.output,args.config),indent=2))
    else:
        import sys
        if sys.platform == 'win32':
            import ctypes
            # Give Windows a distinct taskbar identity before creating a window.
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Instant.ExamBehaviorReview')
        import tkinter as tk
        from app.tkinter_app import CheatingAlertApp
        root = tk.Tk()
        CheatingAlertApp(root)
        root.mainloop()


if __name__ == '__main__':
    main()
