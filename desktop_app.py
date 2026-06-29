from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import cv2
from PIL import Image, ImageTk

from config import COLOR_GREEN, COLOR_RED, COLOR_WHITE, COLOR_YELLOW
from main import (
    DEFAULT_REFERENCE_VIDEO,
    MATCH_LABELS,
    build_match_checks,
    draw_user_angles,
)
from pose_engine import (
    create_pose_detector,
    get_landmarks,
    get_world_landmarks,
    open_webcam,
    process_frame,
)
from pose_features import extract_pose_features
from reference_video import (
    ReferenceVideoGuide,
    draw_reference_overlay,
)
from template_correction import evaluate_against_reference
from utils import (
    FPSCounter,
    draw_coordinates,
    draw_feedback_banner,
    draw_status_panel,
)


APP_TITLE = "Yoga Pose Coach"
DISPLAY_WIDTH = 1120


class YogaPoseCoachApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1380x820")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#171717")
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

        self.reference_video_path = Path(DEFAULT_REFERENCE_VIDEO)
        self.cap = None
        self.user_detector = None
        self.reference_guide = None
        self.fps_counter = FPSCounter()
        self.running = False
        self.after_id = None
        self.photo = None

        self.score_var = tk.StringVar(value="Score: --")
        self.feedback_var = tk.StringVar(value="Click Start to begin.")
        self.video_var = tk.StringVar(
            value=f"Reference: {self.reference_video_path.name}"
        )
        self.state_var = tk.StringVar(value="Stopped")
        self.pause_button_text = tk.StringVar(value="Pause Reference")

        self._build_ui()

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)
        self.root.rowconfigure(0, weight=1)

        video_frame = tk.Frame(
            self.root,
            bg="#0f0f0f",
            padx=10,
            pady=10,
        )
        video_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(0, weight=1)

        self.video_label = tk.Label(
            video_frame,
            bg="#050505",
            fg="#d4d4d4",
            text="Yoga Pose Coach",
            font=("Helvetica", 22, "bold"),
        )
        self.video_label.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        control = tk.Frame(
            self.root,
            bg="#202020",
            width=240,
            padx=16,
            pady=18,
        )
        control.grid(
            row=0,
            column=1,
            sticky="ns",
        )
        control.grid_propagate(False)

        tk.Label(
            control,
            text=APP_TITLE,
            bg="#202020",
            fg="#f7f7f7",
            font=("Helvetica", 18, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        self._button(control, "Start", self.start).pack(fill="x", pady=5)
        self._button(control, "Stop", self.stop).pack(fill="x", pady=5)
        self._button(
            control,
            textvariable=self.pause_button_text,
            command=self.toggle_reference,
        ).pack(fill="x", pady=5)
        self._button(
            control,
            "Restart Reference",
            self.restart_reference,
        ).pack(fill="x", pady=5)
        self._button(
            control,
            "Choose Video",
            self.choose_reference_video,
        ).pack(fill="x", pady=5)
        self._button(control, "Quit", self.quit_app).pack(fill="x", pady=5)

        tk.Frame(
            control,
            height=1,
            bg="#3a3a3a",
        ).pack(fill="x", pady=18)

        self._info_label(
            control,
            self.state_var,
            fg="#d8d8d8",
        ).pack(anchor="w", pady=(0, 10))
        self._info_label(
            control,
            self.score_var,
            fg="#f8d75c",
            font=("Helvetica", 15, "bold"),
        ).pack(anchor="w", pady=(0, 10))
        self._info_label(
            control,
            self.feedback_var,
            fg="#ffffff",
            wraplength=205,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))
        self._info_label(
            control,
            self.video_var,
            fg="#bdbdbd",
            wraplength=205,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(
            control,
            text=(
                "Tip: macOS may ask for camera permission "
                "the first time the app starts."
            ),
            bg="#202020",
            fg="#8f8f8f",
            font=("Helvetica", 11),
            wraplength=205,
            justify="left",
        ).pack(side="bottom", anchor="w")

    def _button(
        self,
        parent,
        text=None,
        command=None,
        textvariable=None,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            textvariable=textvariable,
            command=command,
            bg="#2f6fed",
            fg="white",
            activebackground="#3d7cff",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=10,
            font=("Helvetica", 13, "bold"),
            cursor="hand2",
        )

    def _info_label(
        self,
        parent,
        textvariable,
        *,
        fg,
        font=("Helvetica", 12),
        wraplength=None,
        justify=None,
    ) -> tk.Label:
        return tk.Label(
            parent,
            textvariable=textvariable,
            bg="#202020",
            fg=fg,
            font=font,
            wraplength=wraplength,
            justify=justify,
        )

    def start(self) -> None:
        if self.running:
            return

        self.state_var.set("Starting camera and pose model...")
        self.root.update_idletasks()

        try:
            self.cap = open_webcam(
                cam_index=0,
                width=1280,
                height=720,
            )
            self.user_detector = create_pose_detector()
            self.reference_guide = ReferenceVideoGuide(
                self.reference_video_path,
                mirror=True,
            )
        except Exception as exc:
            self._release_resources()
            self.state_var.set("Stopped")
            messagebox.showerror(
                APP_TITLE,
                f"Could not start the app:\n{exc}",
            )
            return

        self.running = True
        self.fps_counter = FPSCounter()
        self.state_var.set("Running")
        self._schedule_next_frame()

    def stop(self) -> None:
        if not self.running and self.cap is None:
            return

        self.running = False

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self._release_resources()
        self.state_var.set("Stopped")
        self.score_var.set("Score: --")
        self.feedback_var.set("Click Start to begin.")
        self.pause_button_text.set("Pause Reference")

    def toggle_reference(self) -> None:
        if self.reference_guide is None:
            return

        self.reference_guide.toggle_pause()
        self.pause_button_text.set(
            "Play Reference"
            if self.reference_guide.paused
            else "Pause Reference"
        )

    def restart_reference(self) -> None:
        if self.reference_guide is not None:
            self.reference_guide.reset()
            self.pause_button_text.set("Pause Reference")

    def choose_reference_video(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Choose reference video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.m4v *.avi"),
                ("All files", "*.*"),
            ],
        )

        if not file_path:
            return

        if self.reference_guide is None:
            new_path = Path(file_path)
            self.reference_video_path = new_path
            self.video_var.set(f"Reference: {new_path.name}")
            return

        try:
            new_path = Path(file_path)
            old_guide = self.reference_guide
            new_guide = ReferenceVideoGuide(
                new_path,
                mirror=True,
            )
            self.reference_guide = new_guide
            self.reference_video_path = new_path
            self.video_var.set(f"Reference: {new_path.name}")
            old_guide.close()
            self.pause_button_text.set("Pause Reference")
        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Could not open reference video:\n{exc}",
            )

    def quit_app(self) -> None:
        self.stop()
        self.root.destroy()

    def _schedule_next_frame(self) -> None:
        self.after_id = self.root.after(
            1,
            self._update_frame,
        )

    def _update_frame(self) -> None:
        if not self.running:
            return

        try:
            display_frame = self._process_frame()
        except Exception as exc:
            self.stop()
            messagebox.showerror(
                APP_TITLE,
                f"Processing stopped:\n{exc}",
            )
            return

        if display_frame is not None:
            self._show_frame(display_frame)

        self._schedule_next_frame()

    def _process_frame(self):
        if (
            self.cap is None
            or self.user_detector is None
            or self.reference_guide is None
        ):
            return None

        reference = self.reference_guide.read()
        success, frame = self.cap.read()

        if not success or frame is None:
            return None

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        fps = self.fps_counter.update()

        results = process_frame(
            self.user_detector,
            frame,
        )
        landmarks = get_landmarks(results)
        world_landmarks = get_world_landmarks(results)
        user_visible = landmarks is not None
        evaluation = None
        match_score = 0.0
        banner_message = "Stand in front of camera"
        banner_color = COLOR_YELLOW

        if landmarks:
            features = extract_pose_features(
                landmarks,
                world_landmarks,
            )
            evaluation = evaluate_against_reference(
                features,
                reference.features,
            )
            match_score = evaluation.score
            banner_message = evaluation.primary_feedback

            if not reference.features:
                banner_color = COLOR_YELLOW
            elif not reference.pose_detected:
                banner_message = "Waiting for a clear reference pose."
                banner_color = COLOR_YELLOW
            elif evaluation.is_correct:
                banner_color = COLOR_GREEN
            elif evaluation.score >= 65:
                banner_color = COLOR_YELLOW
            else:
                banner_color = COLOR_RED

            draw_user_angles(
                frame,
                landmarks,
            )
            draw_coordinates(
                frame,
                landmarks,
                w,
                h,
            )

        checks = build_match_checks(
            evaluation,
            user_visible=user_visible,
            reference_visible=reference.pose_detected,
        )
        draw_status_panel(
            frame,
            checks,
            hold_timer=0.0,
            rest_timer=0.0,
            phase="FOLLOW VIDEO",
            fps=fps,
            labels=MATCH_LABELS,
            score=match_score,
        )
        draw_reference_overlay(
            frame,
            reference,
        )
        draw_feedback_banner(
            frame,
            banner_message,
            banner_color,
        )
        cv2.putText(
            frame,
            f"Reference: {self.reference_video_path.name}",
            (20, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            COLOR_WHITE,
            1,
            cv2.LINE_AA,
        )

        self.score_var.set(f"Score: {match_score:.0f}/100")
        self.feedback_var.set(banner_message)

        return frame

    def _show_frame(self, frame) -> None:
        frame = self._resize_for_display(frame)
        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )
        image = Image.fromarray(rgb_frame)
        self.photo = ImageTk.PhotoImage(image=image)
        self.video_label.configure(
            image=self.photo,
            text="",
        )

    def _resize_for_display(self, frame):
        h, w = frame.shape[:2]

        if w <= DISPLAY_WIDTH:
            return frame

        scale = DISPLAY_WIDTH / w
        return cv2.resize(
            frame,
            (DISPLAY_WIDTH, int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )

    def _release_resources(self) -> None:
        if self.reference_guide is not None:
            self.reference_guide.close()
            self.reference_guide = None

        if self.user_detector is not None:
            self.user_detector.close()
            self.user_detector = None

        if self.cap is not None:
            self.cap.release()
            self.cap = None


def main() -> None:
    YogaPoseCoachApp().run()


if __name__ == "__main__":
    main()
