"""
동영상 관절 스켈레톤 GUI (tkinter) - 변환 + 뷰어

설치:
    pip install ultralytics opencv-python pillow lapx

실행:
    python pose_skeleton_gui.py

뷰어 단축키 (뷰어 탭에서):
    Space      재생 / 일시정지
    ← / →      1프레임 뒤로 / 앞으로
    A / B      구간 시작(A) / 끝(B) 지정
"""
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import cv2
from PIL import Image, ImageTk

# COCO 17 keypoints
SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 11), (6, 12), (11, 12),
    (5, 7), (7, 9), (6, 8), (8, 10),
    (11, 13), (13, 15), (12, 14), (14, 16),
]
COLORS = [
    (0, 255, 255), (0, 255, 0), (255, 128, 0), (255, 0, 255),
    (0, 128, 255), (255, 255, 0), (128, 0, 255), (0, 0, 255),
]
MODELS = {
    "n - 가장 빠름": "yolo11n-pose.pt",
    "s - 빠름": "yolo11s-pose.pt",
    "m - 균형 (추천)": "yolo11m-pose.pt",
    "l - 정확": "yolo11l-pose.pt",
    "x - 가장 정확": "yolo11x-pose.pt",
}
PREVIEW_W, PREVIEW_H = 720, 405


def draw_person(img, kpts, conf, color, min_conf, line_w, dot_r):
    for a, b in SKELETON:
        if conf[a] >= min_conf and conf[b] >= min_conf:
            pa = (int(kpts[a][0]), int(kpts[a][1]))
            pb = (int(kpts[b][0]), int(kpts[b][1]))
            cv2.line(img, pa, pb, color, line_w, cv2.LINE_AA)
    for i, (x, y) in enumerate(kpts):
        if conf[i] >= min_conf:
            cv2.circle(img, (int(x), int(y)), dot_r, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(img, (int(x), int(y)), dot_r, color, 2, cv2.LINE_AA)


def fmt_time(t):
    t = max(0.0, t)
    m = int(t // 60)
    return f"{m:02d}:{t - m * 60:05.2f}"


def bgr_to_photo(bgr, box_w, box_h):
    h, w = bgr.shape[:2]
    scale = min(box_w / w, box_h / h)
    img = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))))
    return ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))


# =====================================================================
# 뷰어: 재생 / 속도 조절 / 구간 반복
# =====================================================================
class Viewer(ttk.Frame):
    TL_H = 30
    TL_PAD = 8

    def __init__(self, master):
        super().__init__(master)
        self.cap = None
        self.total = 0
        self.fps = 30.0
        self.cur = 0            # 현재 화면에 표시된 프레임 번호
        self.playing = False
        self.a = None           # 구간 시작 프레임
        self.b = None           # 구간 끝 프레임
        self.speed = 1.0
        self._photo = None
        self._job = None

        self.loop_var = tk.BooleanVar(value=True)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.path_var = tk.StringVar(value="열린 동영상 없음")
        self.time_var = tk.StringVar(value="00:00.00 / 00:00.00")
        self.ab_var = tk.StringVar(value="구간: 지정 안 됨")
        self.speed_lbl_var = tk.StringVar(value="1.00x")

        self._build()

    # ---------- UI ----------
    def _build(self):
        pad = {"padx": 6, "pady": 3}

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Button(top, text="동영상 열기", command=self.open_dialog,
                   takefocus=False).pack(side="left")
        ttk.Label(top, textvariable=self.path_var, foreground="#555").pack(
            side="left", padx=10)

        self.canvas = tk.Canvas(self, width=PREVIEW_W, height=PREVIEW_H, bg="#111",
                                highlightthickness=0)
        self.canvas.pack(padx=8, pady=4)

        # 타임라인 (클릭/드래그로 이동, A-B 구간 표시)
        self.tl = tk.Canvas(self, width=PREVIEW_W, height=self.TL_H, bg="#222",
                            highlightthickness=0, cursor="hand2")
        self.tl.pack(padx=8, pady=(0, 4))
        self.tl.bind("<Button-1>", self._on_timeline)
        self.tl.bind("<B1-Motion>", self._on_timeline)

        # 재생 컨트롤
        ctl = ttk.Frame(self)
        ctl.pack(fill="x", padx=8)
        ttk.Button(ctl, text="⏮", width=4, command=lambda: self.seek(self.a or 0),
                   takefocus=False).pack(side="left", **pad)
        ttk.Button(ctl, text="◀|", width=4, command=lambda: self.step(-1),
                   takefocus=False).pack(side="left", **pad)
        self.play_btn = ttk.Button(ctl, text="▶ 재생", width=10,
                                   command=self.toggle_play, takefocus=False)
        self.play_btn.pack(side="left", **pad)
        ttk.Button(ctl, text="|▶", width=4, command=lambda: self.step(1),
                   takefocus=False).pack(side="left", **pad)
        ttk.Label(ctl, textvariable=self.time_var, width=24).pack(side="right", **pad)

        # 속도
        spd = ttk.Frame(self)
        spd.pack(fill="x", padx=8)
        ttk.Label(spd, text="재생 속도").pack(side="left", **pad)
        ttk.Scale(spd, from_=0.1, to=3.0, variable=self.speed_var, length=220,
                  command=self._on_speed, takefocus=False).pack(side="left", **pad)
        ttk.Label(spd, textvariable=self.speed_lbl_var, width=6).pack(side="left")
        for s in (0.25, 0.5, 1.0, 1.5, 2.0):
            ttk.Button(spd, text=f"{s:g}x", width=5, takefocus=False,
                       command=lambda v=s: self.set_speed(v)).pack(side="left", padx=2)

        # 구간 반복
        lp = ttk.Frame(self)
        lp.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(lp, text="A 지정", width=8, command=self.set_a,
                   takefocus=False).pack(side="left", **pad)
        ttk.Button(lp, text="B 지정", width=8, command=self.set_b,
                   takefocus=False).pack(side="left", **pad)
        ttk.Button(lp, text="구간 해제", width=9, command=self.clear_ab,
                   takefocus=False).pack(side="left", **pad)
        ttk.Checkbutton(lp, text="구간 반복", variable=self.loop_var,
                        takefocus=False).pack(side="left", padx=10)
        ttk.Label(lp, textvariable=self.ab_var).pack(side="left", padx=6)

        self._draw_timeline()

    # ---------- 파일 ----------
    def open_dialog(self):
        path = filedialog.askopenfilename(
            title="동영상 선택",
            filetypes=[("동영상", "*.mp4 *.mov *.avi *.mkv *.m4v"), ("모든 파일", "*.*")])
        if path:
            self.load(path)

    def load(self, path):
        self.pause()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            messagebox.showerror("오류", f"동영상을 열 수 없습니다.\n{path}")
            return
        self.cap = cap
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        self.a = self.b = None
        self.cur = 0
        self.path_var.set(str(path))
        self._update_ab_label()
        self.seek(0)

    def close(self):
        self.pause()
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    # ---------- 재생 제어 ----------
    def toggle_play(self):
        if self.cap is None:
            return
        if self.playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if self.cap is None or self.playing:
            return
        if self.cur >= self.total - 1 and not self._loop_active():
            self.seek(0)
        self.playing = True
        self.play_btn.config(text="⏸ 일시정지")
        self._tick()

    def pause(self):
        self.playing = False
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self.play_btn.config(text="▶ 재생")

    def _loop_active(self):
        return (self.loop_var.get() and self.a is not None and self.b is not None
                and self.b > self.a)

    def _tick(self):
        if not self.playing or self.cap is None:
            return
        t0 = time.perf_counter()

        if self._loop_active() and self.cur >= self.b:
            self.seek(self.a)
        else:
            ok, frame = self.cap.read()
            if not ok:
                if self._loop_active():
                    self.seek(self.a)
                else:
                    self.pause()
                    return
            else:
                self.cur += 1
                self._show(frame)
                self._update_labels()
                self._draw_timeline()

        interval = 1.0 / (self.fps * self.speed)
        delay = max(1, int((interval - (time.perf_counter() - t0)) * 1000))
        self._job = self.after(delay, self._tick)

    def seek(self, idx):
        if self.cap is None:
            return
        idx = int(min(max(0, idx), self.total - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self.cap.read()
        if ok:
            self.cur = idx
            self._show(frame)
        self._update_labels()
        self._draw_timeline()

    def step(self, delta):
        if self.cap is None:
            return
        self.pause()
        self.seek(self.cur + delta)

    # ---------- 속도 ----------
    def _on_speed(self, value):
        self.speed = max(0.1, round(float(value) / 0.05) * 0.05)
        self.speed_lbl_var.set(f"{self.speed:.2f}x")

    def set_speed(self, v):
        self.speed_var.set(v)
        self._on_speed(v)

    # ---------- 구간 반복 ----------
    def set_a(self):
        if self.cap is None:
            return
        self.a = self.cur
        if self.b is not None and self.b <= self.a:
            self.b = None
        self._update_ab_label()
        self._draw_timeline()

    def set_b(self):
        if self.cap is None:
            return
        if self.a is not None and self.cur <= self.a:
            messagebox.showinfo("알림", "B는 A보다 뒤 위치여야 합니다.")
            return
        self.b = self.cur
        if self.a is None:
            self.a = 0
        self._update_ab_label()
        self._draw_timeline()

    def clear_ab(self):
        self.a = self.b = None
        self._update_ab_label()
        self._draw_timeline()

    def _update_ab_label(self):
        if self.a is None and self.b is None:
            self.ab_var.set("구간: 지정 안 됨")
            return
        a = fmt_time(self.a / self.fps) if self.a is not None else "--"
        b = fmt_time(self.b / self.fps) if self.b is not None else "--"
        self.ab_var.set(f"구간  A {a}  ~  B {b}")

    # ---------- 그리기 ----------
    def _show(self, frame):
        self._photo = bgr_to_photo(frame, PREVIEW_W, PREVIEW_H)
        self.canvas.delete("all")
        self.canvas.create_image(PREVIEW_W // 2, PREVIEW_H // 2, image=self._photo)

    def _update_labels(self):
        self.time_var.set(
            f"{fmt_time(self.cur / self.fps)} / {fmt_time(self.total / self.fps)}"
            f"   ({self.cur + 1}/{self.total})")

    def _x(self, idx):
        span = PREVIEW_W - 2 * self.TL_PAD
        return self.TL_PAD + idx / max(1, self.total - 1) * span

    def _draw_timeline(self):
        c = self.tl
        c.delete("all")
        y = self.TL_H // 2 + 4
        c.create_rectangle(self.TL_PAD, y - 3, PREVIEW_W - self.TL_PAD, y + 3,
                           fill="#555", outline="")
        if self.cap is None:
            return
        if self.a is not None and self.b is not None:
            c.create_rectangle(self._x(self.a), y - 5, self._x(self.b), y + 5,
                               fill="#3b82f6", outline="")
        for idx, label in ((self.a, "A"), (self.b, "B")):
            if idx is not None:
                x = self._x(idx)
                c.create_line(x, 2, x, self.TL_H - 2, fill="#fbbf24", width=2)
                c.create_text(x + 6, 7, text=label, fill="#fbbf24",
                              font=("TkDefaultFont", 8, "bold"))
        x = self._x(self.cur)
        c.create_line(x, 4, x, self.TL_H - 2, fill="#ffffff", width=2)
        c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#ffffff", outline="")

    def _on_timeline(self, event):
        if self.cap is None:
            return
        span = PREVIEW_W - 2 * self.TL_PAD
        ratio = min(max((event.x - self.TL_PAD) / span, 0.0), 1.0)
        self.seek(round(ratio * (self.total - 1)))


# =====================================================================
# 메인 앱
# =====================================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("동영상 관절 스켈레톤")
        self.resizable(False, False)

        self.q = queue.Queue(maxsize=4)
        self.stop_event = threading.Event()
        self.thread = None
        self._photo = None

        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.model_var = tk.StringVar(value="m - 균형 (추천)")
        self.model_path_var = tk.StringVar()
        self.conf_var = tk.DoubleVar(value=0.4)
        self.line_var = tk.IntVar(value=3)
        self.black_var = tk.BooleanVar(value=False)
        self.separate_var = tk.BooleanVar(value=True)
        self.preview_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="동영상을 선택하세요.")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)
        self.convert_tab = ttk.Frame(self.nb)
        self.viewer = Viewer(self.nb)
        self.nb.add(self.convert_tab, text="  변환  ")
        self.nb.add(self.viewer, text="  뷰어  ")

        self._build_convert(self.convert_tab)
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 변환 탭 UI ----------
    def _build_convert(self, root):
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(root)
        frm.pack(padx=10, pady=10)

        ttk.Label(frm, text="입력 동영상").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.in_var, width=60).grid(row=0, column=1, **pad)
        ttk.Button(frm, text="찾기", command=self.pick_input).grid(row=0, column=2, **pad)

        ttk.Label(frm, text="저장 위치").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.out_var, width=60).grid(row=1, column=1, **pad)
        ttk.Button(frm, text="변경", command=self.pick_output).grid(row=1, column=2, **pad)

        opt = ttk.LabelFrame(frm, text="옵션")
        opt.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=8)

        ttk.Label(opt, text="모델").grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(opt, textvariable=self.model_var, values=list(MODELS),
                     state="readonly", width=18).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(opt, text="최소 신뢰도").grid(row=0, column=2, sticky="e", **pad)
        ttk.Scale(opt, from_=0.1, to=0.9, variable=self.conf_var, length=140,
                  command=lambda v: self.conf_lbl.config(text=f"{float(v):.2f}")
                  ).grid(row=0, column=3, **pad)
        self.conf_lbl = ttk.Label(opt, text="0.40", width=5)
        self.conf_lbl.grid(row=0, column=4, **pad)

        ttk.Label(opt, text="선 굵기").grid(row=1, column=0, sticky="w", **pad)
        ttk.Spinbox(opt, from_=1, to=10, textvariable=self.line_var, width=5
                    ).grid(row=1, column=1, sticky="w", **pad)
        ttk.Checkbutton(opt, text="검은 배경에 뼈대만", variable=self.black_var
                        ).grid(row=1, column=2, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(opt, text="미리보기 (끄면 더 빠름)", variable=self.preview_var
                ).grid(row=1, column=4, sticky="w", **pad)
        ttk.Checkbutton(opt, text="사람별 개별 포즈 추출 (정확도↑, 느림↑)",
                variable=self.separate_var).grid(row=2, column=4, sticky="w", **pad)

        ttk.Label(opt, text="모델 파일(.pt)").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(opt, textvariable=self.model_path_var, width=42
                  ).grid(row=2, column=1, columnspan=3, sticky="w", **pad)
        ttk.Button(opt, text="찾기", command=self.pick_model).grid(
            row=2, column=4, sticky="w", **pad)
        ttk.Label(opt, text="※ 비워두면 위에서 고른 모델을 자동 다운로드합니다.",
                  foreground="#666").grid(row=3, column=0, columnspan=5, sticky="w", **pad)

        self.canvas = tk.Canvas(frm, width=PREVIEW_W, height=PREVIEW_H, bg="#111",
                                highlightthickness=0)
        self.canvas.grid(row=3, column=0, columnspan=3, padx=8, pady=6)

        self.progress = ttk.Progressbar(frm, length=PREVIEW_W, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=3, padx=8, pady=4)
        ttk.Label(frm, textvariable=self.status_var).grid(
            row=5, column=0, columnspan=3, sticky="w", padx=8)

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=3, pady=8)
        self.start_btn = ttk.Button(btns, text="시작", command=self.start, width=12)
        self.start_btn.pack(side="left", padx=6)
        self.stop_btn = ttk.Button(btns, text="중지", command=self.stop, width=12,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=6)

    # ---------- 단축키 (뷰어 탭에서만) ----------
    def _bind_keys(self):
        def on_viewer(fn):
            def handler(event):
                if self.nb.select() == str(self.viewer):
                    fn()
                    return "break"
            return handler

        self.bind_all("<space>", on_viewer(self.viewer.toggle_play))
        self.bind_all("<Left>", on_viewer(lambda: self.viewer.step(-1)))
        self.bind_all("<Right>", on_viewer(lambda: self.viewer.step(1)))
        self.bind_all("<KeyPress-a>", on_viewer(self.viewer.set_a))
        self.bind_all("<KeyPress-b>", on_viewer(self.viewer.set_b))

    def _on_close(self):
        self.stop_event.set()
        self.viewer.close()
        self.destroy()

    # ---------- 파일 선택 ----------
    def pick_input(self):
        path = filedialog.askopenfilename(
            title="동영상 선택",
            filetypes=[("동영상", "*.mp4 *.mov *.avi *.mkv *.m4v"), ("모든 파일", "*.*")])
        if path:
            self.in_var.set(path)
            p = Path(path)
            self.out_var.set(str(p.with_name(p.stem + "_skeleton.mp4")))
            self.status_var.set("준비 완료. [시작]을 눌러주세요.")

    def pick_model(self):
        path = filedialog.askopenfilename(
            title="모델 파일 선택", filetypes=[("PyTorch 모델", "*.pt"), ("모든 파일", "*.*")])
        if path:
            self.model_path_var.set(path)

    def pick_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4", filetypes=[("MP4", "*.mp4")])
        if path:
            self.out_var.set(path)

    # ---------- 실행 제어 ----------
    def start(self):
        if not self.in_var.get() or not Path(self.in_var.get()).exists():
            messagebox.showwarning("알림", "입력 동영상을 선택하세요.")
            return
        if not self.out_var.get():
            messagebox.showwarning("알림", "저장 위치를 지정하세요.")
            return

        model_path = self.model_path_var.get().strip()
        if model_path and not Path(model_path).exists():
            messagebox.showwarning("알림", "모델 파일 경로가 올바르지 않습니다.")
            return

        # 같은 파일이 뷰어에서 열려 있으면 덮어쓰기 전에 닫기
        self.viewer.close()

        params = dict(
            input=self.in_var.get(),
            output=self.out_var.get(),
            model=model_path or MODELS[self.model_var.get()],
            separate=bool(self.separate_var.get()),
            min_conf=float(self.conf_var.get()),
            line_w=int(self.line_var.get()),
            black=self.black_var.get(),
            preview=self.preview_var.get(),
        )
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress["value"] = 0
        self.thread = threading.Thread(target=self.worker, args=(params,), daemon=True)
        self.thread.start()
        self.after(30, self.poll)

    def stop(self):
        self.stop_event.set()
        self.status_var.set("중지하는 중...")

    # ---------- 작업 스레드 ----------
    def _put(self, item, block=True):
        try:
            if block:
                self.q.put(item)
            else:
                self.q.put_nowait(item)
        except queue.Full:
            pass

    def worker(self, p):
        try:
            self._put(("status", "모델 로딩 중... (처음에는 다운로드로 시간이 걸립니다)"))
            from ultralytics import YOLO
            pose_model = YOLO(p["model"])
            detector = None
            if p.get("separate"):
                # Use a lightweight person detector to split overlapping people before pose estimation
                try:
                    detector = YOLO("yolov8n.pt")
                except Exception:
                    detector = None

            cap = cv2.VideoCapture(p["input"])
            if not cap.isOpened():
                raise RuntimeError("동영상을 열 수 없습니다.")
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            writer = cv2.VideoWriter(p["output"], cv2.VideoWriter_fourcc(*"mp4v"),
                                     fps, (w, h))
            dot_r = max(3, p["line_w"] + 2)
            n = 0
            cancelled = False

            while True:
                if self.stop_event.is_set():
                    cancelled = True
                    break
                ok, frame = cap.read()
                if not ok:
                    break

                canvas = frame * 0 if p["black"] else frame

                if detector is not None:
                    # Detect persons first, then run pose on each crop to separate close/overlapping people
                    dets = detector(frame, conf=p["min_conf"], classes=[0], verbose=False)[0]
                    boxes = []
                    if hasattr(dets, "boxes") and dets.boxes is not None:
                        xyxy = dets.boxes.xyxy.cpu().numpy()
                        for b in xyxy:
                            x1, y1, x2, y2 = [int(v) for v in b]
                            # ensure valid box
                            x1 = max(0, min(x1, frame.shape[1] - 1))
                            x2 = max(0, min(x2, frame.shape[1] - 1))
                            y1 = max(0, min(y1, frame.shape[0] - 1))
                            y2 = max(0, min(y2, frame.shape[0] - 1))
                            if x2 > x1 and y2 > y1:
                                boxes.append((x1, y1, x2, y2))

                    ids = list(range(len(boxes)))
                    for pid, (x1, y1, x2, y2) in zip(ids, boxes):
                        crop = frame[y1:y2, x1:x2]
                        if crop.size == 0:
                            continue
                        try:
                            cres = pose_model(crop, conf=p["min_conf"], verbose=False)[0]
                        except Exception:
                            continue
                        if cres.keypoints is None or len(cres.keypoints) == 0:
                            continue
                        # take first detected pose in the crop
                        k = cres.keypoints.xy.cpu().numpy()[0]
                        c = cres.keypoints.conf.cpu().numpy()[0]
                        # offset to original frame coords
                        k[:, 0] += x1
                        k[:, 1] += y1
                        draw_person(canvas, k, c, COLORS[pid % len(COLORS)],
                                    p["min_conf"], p["line_w"], dot_r)
                else:
                    # Fallback: use single pose model with tracking as before
                    res = pose_model.track(frame, persist=True, verbose=False)[0]
                    if res.keypoints is not None and len(res.keypoints) > 0:
                        xy = res.keypoints.xy.cpu().numpy()
                        cf = res.keypoints.conf.cpu().numpy()
                        ids = (res.boxes.id.int().cpu().tolist()
                               if res.boxes.id is not None else list(range(len(xy))))
                        for pid, k, c in zip(ids, xy, cf):
                            draw_person(canvas, k, c, COLORS[pid % len(COLORS)],
                                        p["min_conf"], p["line_w"], dot_r)

                writer.write(canvas)
                n += 1
                if p["preview"] and n % 2 == 0:
                    self._put(("frame", canvas.copy()), block=False)
                self._put(("progress", n, total), block=False)

            cap.release()
            writer.release()
            self._put(("done", p["output"], cancelled))
        except Exception as e:  # noqa: BLE001
            self._put(("error", str(e)))

    # ---------- 메인 스레드: 결과 수신 ----------
    def poll(self):
        last_frame = None
        finished = False
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "frame":
                    last_frame = item[1]
                elif kind == "progress":
                    _, n, total = item
                    self.progress["value"] = min(100, n * 100 / total)
                    self.status_var.set(f"처리 중... {n}/{total} 프레임")
                elif kind == "status":
                    self.status_var.set(item[1])
                elif kind == "done":
                    _, out, cancelled = item
                    self._finish()
                    finished = True
                    if cancelled:
                        self.status_var.set("중지되었습니다.")
                    else:
                        self.progress["value"] = 100
                        self.status_var.set(f"완료: {out}")
                        if messagebox.askyesno("완료", f"저장되었습니다.\n{out}\n\n"
                                                      "뷰어에서 바로 재생할까요?"):
                            self.viewer.load(out)
                            self.nb.select(self.viewer)
                elif kind == "error":
                    self._finish()
                    finished = True
                    self.status_var.set("오류가 발생했습니다.")
                    messagebox.showerror("오류", item[1])
        except queue.Empty:
            pass

        if last_frame is not None:
            self.show_frame(last_frame)
        if not finished:
            self.after(30, self.poll)

    def _finish(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def show_frame(self, bgr):
        self._photo = bgr_to_photo(bgr, PREVIEW_W, PREVIEW_H)
        self.canvas.delete("all")
        self.canvas.create_image(PREVIEW_W // 2, PREVIEW_H // 2, image=self._photo)


if __name__ == "__main__":
    App().mainloop()
