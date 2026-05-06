import os
import sys
import tkinter as tk


def _resource_path(relative):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _show_splash():
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.configure(bg="#FFFFFF")
    splash.attributes("-topmost", True)

    # Borda sutil
    outer = tk.Frame(splash, bg="#CCCCCC", padx=1, pady=1)
    outer.pack(fill="both", expand=True)
    inner = tk.Frame(outer, bg="#FFFFFF")
    inner.pack(fill="both", expand=True)

    # Logo
    try:
        from PIL import Image, ImageTk
        img = Image.open(_resource_path(os.path.join("assets", "logo.png")))
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        img.thumbnail((300, 170), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        lbl = tk.Label(inner, image=photo, bg="#FFFFFF")
        lbl.image = photo
        lbl.pack(padx=50, pady=(30, 8))
    except Exception:
        tk.Label(
            inner, text="Gerador de Relatórios OAB",
            font=("Verdana", 13, "bold"), fg="#1565C0", bg="#FFFFFF"
        ).pack(padx=50, pady=(30, 8))

    tk.Label(inner, text="Carregando...", font=("Verdana", 8),
             fg="#999999", bg="#FFFFFF").pack(pady=(0, 16))

    # Barra de progresso
    bar_bg = tk.Frame(inner, bg="#E3F2FD", height=5)
    bar_bg.pack(fill="x", padx=0, pady=0)
    bar_bg.pack_propagate(False)
    bar = tk.Frame(bar_bg, bg="#1565C0", height=5, width=0)
    bar.place(x=0, y=0, relheight=1)

    # Centraliza na tela
    splash.update_idletasks()
    w = splash.winfo_reqwidth()
    h = splash.winfo_reqheight()
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    splash.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
    splash.update()

    # Anima a barra de 0 a 100%
    def _animate(step=0):
        if step <= 100:
            bar.place(x=0, y=0, relheight=1, width=int(w * step / 100))
            splash.update()
            splash.after(12, _animate, step + 2)

    _animate()
    return splash


if __name__ == "__main__":
    splash = _show_splash()
    splash.update()

    from app import App  # import pesado acontece aqui

    splash.destroy()

    app = App()
    app.mainloop()
