#!/usr/bin/env python3
"""
workspace_window.py -- PLAYERS / RACES / LISTS を1つのウィンドウに統合
====================================================================
左レール: 3セクションの切り替え (未保存ドット・件数バッジ付き) + チーム得点のライブ表示
右: 選択中セクションの編集画面 (切り替えても入力内容は消えない)
下: トースト (破壊的操作の直後は UNDO 付き) とショートカット

Ctrl+1/2/3 でセクション移動、Ctrl+S で現在のセクションを保存、Ctrl+Tab で循環。
LISTS の CHECK 欄から RACES の該当レースへ直接ジャンプできる。
"""
import math
import tkinter as tk

from lists_window import ListsPanel
from players_window import PlayersPanel
from races_window import RacesPanel
from ui_kit import (ACCENT, BG, INK, INK2, INK3, LINE, LINE2, RAISE, SURF, AMBER, BLUE,
                    GREEN, PINK, RED, bind_wheel, fnt, label, measure, mix, round_rect,
                    team_color)

TABS = [("players", "PLAYERS", "名簿とプレイヤー別集計", BLUE),
        ("races", "RACES", "読み取り結果を直す", PINK),
        ("lists", "LISTS", "OCRミス / 表示名の辞書", AMBER)]


class _Nav:
    """左レールの1項目。"""

    W, H = 194, 62

    def __init__(self, master, key, title, sub, accent, command, index):
        self.key, self.accent, self.title, self.sub = key, accent, title, sub
        self.active = False
        self.dirty = False
        self.badge = ""
        self.widget = tk.Canvas(master, width=self.W, height=self.H, bg=BG,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.widget.bind("<Button-1>", lambda e: command(key))
        self.widget.bind("<Enter>", lambda e: self._hover(True))
        self.widget.bind("<Leave>", lambda e: self._hover(False))
        self._h = False
        self._index = index
        self.draw()

    def _hover(self, on):
        self._h = on
        self.draw()

    def draw(self):
        cv = self.widget
        try:
            cv.delete("all")
            a = self.accent
            face = mix(a, BG, .80) if self.active else (RAISE if self._h else BG)
            round_rect(cv, 2, 3, self.W - 2, self.H - 3, 10, fill=face,
                       outline=mix(a, BG, .45) if self.active else (LINE if self._h else BG))
            if self.active:
                cv.create_rectangle(2, 14, 6, self.H - 14, fill=a, outline="")
            self._icon(cv, 22, self.H / 2, a if self.active else INK2)
            cv.create_text(44, 22, text=self.title, anchor="w",
                           fill=INK if self.active else INK2, font=fnt(11, True))
            cv.create_text(44, 40, text=self.sub, anchor="w",
                           fill=INK3 if not self.active else mix(INK, a, .35),
                           font=fnt(7, False, False))
            cv.create_text(self.W - 12, 20, text=str(self._index), anchor="e",
                           fill=mix(a, BG, .35) if self.active else LINE2, font=fnt(8, True))
            if self.badge:
                cv.create_text(self.W - 12, 42, text=self.badge, anchor="e",
                               fill=INK3, font=fnt(8, True))
            if self.dirty:
                cv.create_oval(self.W - 46, 37, self.W - 38, 45, fill=AMBER, outline="")
        except Exception:
            pass

    def _icon(self, cv, x, y, col):
        if self.key == "players":
            for dx in (-6, 6):
                cv.create_oval(x + dx - 4, y - 9, x + dx + 4, y - 1, outline=col, width=2)
                cv.create_arc(x + dx - 7, y - 2, x + dx + 7, y + 12, start=0, extent=180,
                              style="arc", outline=col, width=2)
        elif self.key == "races":
            for r in range(3):
                for c in range(4):
                    if (r + c) % 2 == 0:
                        cv.create_rectangle(x - 8 + c * 5, y - 8 + r * 5,
                                            x - 3 + c * 5, y - 3 + r * 5, fill=col, outline="")
            cv.create_line(x - 9, y - 9, x - 9, y + 10, fill=col, width=2)
        else:
            for i, dy in enumerate((-7, 0, 7)):
                cv.create_oval(x - 9, y + dy - 2, x - 5, y + dy + 2, fill=col, outline="")
                cv.create_line(x - 1, y + dy, x + 9 - i * 3, y + dy, fill=col, width=2)


class _Pulse:
    """チーム得点のライブバー。"""

    MAX_HEIGHT = 180

    def __init__(self, master, tags):
        self.widget = tk.Canvas(master, width=194, height=self.MAX_HEIGHT, bg=BG,
                                highlightthickness=0, bd=0)
        self.tags = list(tags)
        self.cur = {}
        self.target = {}

    def set_data(self, tags, scores):
        self.tags = list(tags)
        self.target = {t: float(scores.get(t, 0)) for t in tags}
        for t in tags:
            self.cur.setdefault(t, 0.0)
        self.widget.configure(height=self.MAX_HEIGHT)
        self.draw()

    def step(self):
        moving = False
        for t, v in self.target.items():
            c = self.cur.get(t, 0.0)
            d = v - c
            if abs(d) > 0.4:
                self.cur[t] = c + d * 0.28
                moving = True
            else:
                self.cur[t] = v
        self.draw()
        return moving

    def draw(self):
        cv = self.widget
        try:
            cv.delete("all")
            if not self.tags:
                cv.create_text(4, 6, anchor="nw", text="START でタグを設定", fill=INK3, font=fnt(8))
                cv.configure(scrollregion=cv.bbox("all") or (0, 0, 194, self.MAX_HEIGHT))
                return
            top = max(1.0, max(self.cur.get(t, 0) for t in self.tags))
            for i, t in enumerate(self.tags):
                y = 6 + i * 26
                col = team_color(i)
                cv.create_text(4, y + 7, anchor="w", text=t[:9], fill=INK2, font=fnt(9, True))
                val = int(round(self.cur.get(t, 0)))
                cv.create_text(190, y + 7, anchor="e", text=str(val), fill=col, font=fnt(10, True))
                round_rect(cv, 4, y + 15, 190, y + 21, 3, fill=mix(col, BG, .88), outline="")
                w = 186 * (self.cur.get(t, 0) / top)
                if w > 3:
                    round_rect(cv, 4, y + 15, 4 + w, y + 21, 3, fill=col, outline="")
            cv.configure(scrollregion=cv.bbox("all") or (0, 0, 194, self.MAX_HEIGHT))
        except Exception:
            pass


class WorkspaceWindow(tk.Toplevel):
    def __init__(self, master, theme, *, roster, on_apply_roster, get_last_names,
                 on_export, styles, fix_text, dict_text, help_fixes, help_dict,
                 on_save_lists, get_unmatched, unlisted_fn,
                 list_races, load_race, save_race, revert_race,
                 context_fn, on_closed):
        super().__init__(master)
        self._on_closed = on_closed
        self._context_fn = context_fn
        self._job = None
        self._toast_job = None
        self._undo_fn = None
        self.tab = "races"

        self.title("MK7 Workspace")
        self.configure(bg=BG)
        self.geometry("1320x880")
        self.minsize(1080, 700)
        bind_wheel(self)

        # ── ヘッダー ──────────────────────────
        head = tk.Frame(self, bg=SURF, height=62)
        head.pack(fill="x")
        head.pack_propagate(False)
        strip = tk.Canvas(head, height=3, bg=SURF, highlightthickness=0)
        strip.pack(fill="x", side="top")
        self._strip = strip
        inner = tk.Frame(head, bg=SURF)
        inner.pack(fill="both", expand=True, padx=18)
        tk.Label(inner, text="MK7", bg=SURF, fg=BLUE, font=fnt(16, True)).pack(side="left")
        tk.Label(inner, text="WORKSPACE", bg=SURF, fg=INK, font=fnt(16, True)).pack(side="left", padx=(6, 0))
        tk.Label(inner, text="players · races · lists", bg=SURF, fg=INK3,
                 font=fnt(8, False, False)).pack(side="left", padx=(10, 0), pady=(6, 0))
        self.lbl_session = tk.Label(inner, text="", bg=SURF, fg=INK2, font=fnt(8))
        self.lbl_session.pack(side="right")
        self.lbl_usage = tk.Label(inner, text="", bg=SURF, fg=INK3, font=fnt(8, True))
        self.lbl_usage.pack(side="right", padx=14)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # ── 左レール ──────────────────────────
        rail = tk.Frame(body, bg=BG, width=214)
        rail.pack(side="left", fill="y", padx=(10, 0), pady=12)
        rail.pack_propagate(False)
        self._nav = {}
        for i, (key, title, sub, acc) in enumerate(TABS, 1):
            n = _Nav(rail, key, title, sub, acc, self.show_tab, i)
            n.widget.pack(pady=(0, 6))
            self._nav[key] = n

        tk.Frame(rail, bg=LINE, height=1).pack(fill="x", pady=10, padx=6)
        label(rail, "TEAM PULSE", 8, True, INK3, BG).pack(anchor="w", padx=6)

        pulse_box = tk.Frame(rail, bg=BG, height=_Pulse.MAX_HEIGHT)
        pulse_box.pack(fill="x", pady=(6, 0))
        pulse_box.pack_propagate(False)
        self.pulse = _Pulse(pulse_box, [])
        pulse_scroll = tk.Scrollbar(pulse_box, orient="vertical", command=self.pulse.widget.yview)
        self.pulse.widget.configure(yscrollcommand=pulse_scroll.set)
        self.pulse.widget.pack(side="left", fill="both", expand=True)
        pulse_scroll.pack(side="right", fill="y")

        tk.Frame(rail, bg=LINE, height=1).pack(fill="x", pady=10, padx=6)
        self.lbl_ctx = tk.Label(rail, text="", bg=BG, fg=INK3, font=fnt(8, False, False),
                                justify="left", wraplength=190, anchor="w")
        self.lbl_ctx.pack(anchor="w", padx=6, fill="x")
        tk.Label(rail, text="Ctrl+1/2/3  切替\nCtrl+S  保存\nCtrl+Tab  次へ\nAlt+↑↓  順位入替",
                 bg=BG, fg=LINE2, font=fnt(8), justify="left").pack(side="bottom", anchor="w", padx=6)

        # ── 右コンテンツ ──────────────────────
        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        notice = self.toast
        self.players = PlayersPanel(
            self.content, theme, roster, on_apply_roster, get_last_names, lambda: None,
            on_export=on_export, styles=styles, host=self,
            tags_fn=lambda: self._ctx().get("tags", []), on_dirty=self._sync, on_notice=notice)
        self.races = RacesPanel(
            self.content, theme, list_races, load_race, save_race, revert_race, lambda: None,
            host=self, tags_fn=lambda: self._ctx().get("tags", []),
            on_dirty=self._sync, on_notice=notice)
        self.lists = ListsPanel(
            self.content, theme, fix_text, dict_text, help_fixes, help_dict,
            on_save_lists, get_unmatched, lambda: None, host=self,
            on_jump_race=self.jump_race, unlisted_fn=unlisted_fn,
            on_dirty=self._sync, on_notice=notice)
        self.panels = {"players": self.players, "races": self.races, "lists": self.lists}
        for p in self.panels.values():
            p.frame.grid(row=0, column=0, sticky="nsew")

        # ── ステータスバー ────────────────────
        bar = tk.Frame(self, bg=SURF, height=38)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self._dot = tk.Canvas(bar, width=10, height=38, bg=SURF, highlightthickness=0)
        self._dot.pack(side="left", padx=(16, 6))
        self.lbl_toast = tk.Label(bar, text="準備完了", bg=SURF, fg=INK2, font=fnt(9, False, False))
        self.lbl_toast.pack(side="left")
        self.btn_undo = tk.Button(bar, text="UNDO", command=self._do_undo, bg=mix(AMBER, SURF, .7),
                                  fg=AMBER, font=fnt(8, True), relief="flat", bd=0,
                                  activebackground=mix(AMBER, SURF, .5), activeforeground=AMBER,
                                  padx=10, pady=3, cursor="hand2")
        self.lbl_dirty = tk.Label(bar, text="", bg=SURF, fg=AMBER, font=fnt(8, True))
        self.lbl_dirty.pack(side="right", padx=16)

        for i, key in enumerate(("players", "races", "lists"), 1):
            self.bind("<Control-Key-%d>" % i, lambda e, k=key: self._key_tab(k))
        self.bind("<Control-Tab>", lambda e: self._key_next())
        self.bind("<Control-s>", lambda e: self._key_save())
        self.bind("<Control-S>", lambda e: self._key_save())
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.show_tab("players" if not roster else "races")
        self._tick()

    # ── タブ ──────────────────────────────
    def show_tab(self, key):
        if key not in self.panels:
            return
        self.tab = key
        self.panels[key].frame.tkraise()
        for k, n in self._nav.items():
            n.active = (k == key)
            n.draw()
        self._paint_strip(ACCENT[key])
        self._sync()
        self._refresh_header()

    def _key_tab(self, key):
        self.show_tab(key)
        return "break"

    def _key_next(self):
        order = [t[0] for t in TABS]
        self.show_tab(order[(order.index(self.tab) + 1) % len(order)])
        return "break"

    def _key_save(self):
        p = self.panels[self.tab]
        try:
            p.save()
        except Exception as e:
            self.toast("保存できませんでした: %s" % e, RED)
        self._sync()
        return "break"

    def jump_race(self, seq):
        self.show_tab("races")
        self.races.refresh_list(select=seq)
        self.toast("race %02d を開きました。" % seq, PINK)

    def _paint_strip(self, accent):
        cv = self._strip
        try:
            cv.delete("all")
            w = max(1, cv.winfo_width())
            for i in range(w):
                t = i / w
                c = mix(BLUE, PINK, t) if t < .5 else mix(PINK, AMBER, (t - .5) * 2)
                cv.create_line(i, 0, i, 3, fill=c)
            cv.create_rectangle(0, 0, w, 3, fill=accent, outline="")
        except Exception:
            pass

    # ── 状態 ──────────────────────────────
    def _ctx(self):
        try:
            return self._context_fn() or {}
        except Exception:
            return {}

    def _refresh_header(self):
        c = self._ctx()
        self.lbl_session.configure(text=c.get("path") or "セッション未開始")
        self.lbl_usage.configure(text=c.get("usage") or "")
        self.lbl_ctx.configure(text="確定 %s レース\n名簿 %s 人%s" % (
            c.get("counted", 0), c.get("roster", 0),
            "\n未確定の読み取りあり" if c.get("pending") else ""))
        self.pulse.set_data(c.get("tags", []), c.get("scores", {}))
        self._nav["players"].badge = "%d人" % c.get("roster", 0)
        self._nav["races"].badge = "%dレース" % c.get("counted", 0)

    def _sync(self):
        dirty = []
        for key, p in self.panels.items():
            d = False
            try:
                d = bool(p.dirty)
            except Exception:
                d = False
            self._nav[key].dirty = d
            self._nav[key].draw()
            if d:
                dirty.append(key.upper())
        self.lbl_dirty.configure(text="未保存: " + " / ".join(dirty) if dirty else "")

    def _tick(self):
        self._job = None
        self._refresh_header()
        self._sync()
        moving = self.pulse.step()
        self._job = self.after(33 if moving else 900, self._tick)

    # ── トースト ──────────────────────────
    def toast(self, msg, color=GREEN, undo=None):
        self.lbl_toast.configure(text=msg, fg=INK)
        try:
            self._dot.delete("all")
            self._dot.create_oval(1, 15, 9, 23, fill=color, outline="")
        except Exception:
            pass
        self._undo_fn = undo
        if undo:
            self.btn_undo.pack(side="left", padx=12)
        else:
            self.btn_undo.pack_forget()
        if self._toast_job:
            try:
                self.after_cancel(self._toast_job)
            except Exception:
                pass
        self._toast_job = self.after(9000, self._fade_toast)

    def _fade_toast(self):
        self._toast_job = None
        self.lbl_toast.configure(fg=INK3)
        self.btn_undo.pack_forget()
        self._undo_fn = None
        try:
            self._dot.delete("all")
        except Exception:
            pass

    def _do_undo(self):
        fn, self._undo_fn = self._undo_fn, None
        self.btn_undo.pack_forget()
        if fn:
            fn()

    # ── 終了 ──────────────────────────────
    def _close(self):
        dirty = [k.upper() for k, p in self.panels.items() if getattr(p, "dirty", False)]
        if dirty:
            from ui_kit import ask
            if ask(self, "未保存の編集", "%s に未保存の編集があります。破棄して閉じますか?"
                   % " / ".join(dirty), ("破棄して閉じる", "やめる"), AMBER) != "破棄して閉じる":
                return
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._toast_job:
            try:
                self.after_cancel(self._toast_job)
            except Exception:
                pass
            self._toast_job = None
        try:
            self._on_closed()
        finally:
            self.destroy()
