#!/usr/bin/env python3
import os, sys, shutil, platform, pathlib, tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

IS_WIN = platform.system()=="Windows"
IS_MAC = platform.system()=="Darwin"

# ----- tiny helpers -----
fmt=lambda n:(lambda s:[(s:=s/1024)[0] and None for _ in()]) and None

def human_size(b):
    u=["B","KB","MB","GB","TB"];x=0
    try:
        b=float(b)
        while b>=1024 and x<len(u)-1:
            b/=1024;x+=1
        return f"{b:.0f} {u[x]}"
    except: return "-"

def system_open(p: pathlib.Path):
    try:
        if IS_WIN: os.startfile(str(p))
        elif IS_MAC: os.system(f"open '{str(p).replace("'","'\\''")}'&")
        else: os.system(f"xdg-open '{str(p).replace("'","'\\''")}'&")
    except Exception as e:
        messagebox.showerror("PaddlMs Explorer", str(e))

# ----- app -----
class App(tk.Tk):
    def __init__(self, start=None):
        super().__init__()
        self.title("PaddlMs Explorer")
        self.geometry("1100x650")
        self.configure(bg="#0b0f0c")
        self.show_hidden=False
        self.clip=[]; self.clipop=None
        self.cwd=pathlib.Path(start or pathlib.Path.home())
        self._style()
        self._ui()
        self._binds()
        self._roots(); self.cd(self.cwd)

    # --- style ---
    def _style(self):
        s=ttk.Style();
        try: s.theme_use("clam")
        except: pass
        self.FG="#a8ff60"; self.BG="#0b0f0c"; self.E="#0f1511"; self.H="#142019"
        self.option_add("*Font", "Consolas 10")

        for k in ("TFrame","TLabelframe","TLabelframe.Label","TLabel","TButton","TEntry"):
            s.configure(k, background=self.BG, foreground=self.FG)
        s.configure("Treeview", background=self.E, fieldbackground=self.E, foreground=self.FG, rowheight=24, bordercolor=self.BG)
        s.map("Treeview", background=[("selected", self.H)])

    # --- ui ---
    def _ui(self):
        top=ttk.Frame(self); top.pack(fill=tk.X)
        self.path=tk.StringVar()
        e=ttk.Entry(top,textvariable=self.path); e.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=8,pady=8)
        e.bind('<Return>',lambda _:(self.cd(pathlib.Path(self.path.get()))))
        self.q=tk.StringVar(); q=ttk.Entry(top,textvariable=self.q,width=28); q.pack(side=tk.LEFT,padx=4,pady=8); q.insert(0,'Search…')
        q.bind('<FocusIn>',lambda _:(q.icursor(tk.END)))
        q.bind('<KeyRelease>',lambda _:(self._fill_files()))
        self.hbtn=ttk.Button(top,text="👁 Hidden: off",command=self.toggle_hidden); self.hbtn.pack(side=tk.LEFT,padx=8)

        pw=ttk.Panedwindow(self,orient=tk.HORIZONTAL); pw.pack(fill=tk.BOTH,expand=True)
        # left tree
        lf=ttk.Frame(pw); self.tree=ttk.Treeview(lf, columns=("p",), displaycolumns=())
        ys=ttk.Scrollbar(lf,orient='vertical',command=self.tree.yview); self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side=tk.LEFT,fill=tk.BOTH,expand=True); ys.pack(side=tk.RIGHT,fill=tk.Y); pw.add(lf,weight=1)
        self.tree.bind('<<TreeviewOpen>>',self._open_node)
        self.tree.bind('<<TreeviewSelect>>',self._sel_node)
        # right list
        rf=ttk.Frame(pw)
        cols=("name","type","size","date","full")
        self.list=ttk.Treeview(rf,columns=cols,show='headings')
        for c,w,a in [("name",420,'w'),("type",120,'w'),("size",100,'e'),("date",160,'w')]:
            self.list.heading(c,text=c.capitalize()); self.list.column(c,width=w,anchor={'w':tk.W,'e':tk.E}[a])
        self.list.column("full",width=0,stretch=False)
        y2=ttk.Scrollbar(rf,orient='vertical',command=self.list.yview); x2=ttk.Scrollbar(rf,orient='horizontal',command=self.list.xview)
        self.list.configure(yscrollcommand=y2.set,xscrollcommand=x2.set)
        self.list.pack(fill=tk.BOTH,expand=True); y2.pack(side=tk.RIGHT,fill=tk.Y); x2.pack(side=tk.BOTTOM,fill=tk.X)
        pw.add(rf,weight=3)
        self.list.bind('<Double-1>',lambda _:(self.open_sel()))
        self.list.bind('<Button-3>',self._ctx)
        self.status=ttk.Label(self,text='Ready'); self.status.pack(fill=tk.X,side=tk.BOTTOM,padx=8,pady=6)
        # ctx menu
        m=self.menu=tk.Menu(self,tearoff=0,bg="#0f1511",fg=self.FG,activebackground=self.H)
        for n,f in [("Open",self.open_sel),("New folder",self.new_folder),("Rename",self.rename),("Cut",self.cut),("Copy",self.copy),("Paste",self.paste),("Delete",self.delete)]:
            m.add_command(label=n,command=f)

    # --- binds ---
    def _binds(self):
        self.bind('<Control-l>',lambda _:(self.focus_path()))
        self.bind('<Control-f>',lambda _:(self.focus_find()))
        self.bind('<F5>',lambda _:(self._fill_files()))
        self.bind('<Delete>',lambda _:(self.delete()))
        self.bind('<F2>',lambda _:(self.rename()))
        self.bind('<Control-n>',lambda _:(self.new_folder()))
        self.bind('<Control-c>',lambda _:(self.copy()))
        self.bind('<Control-x>',lambda _:(self.cut()))
        self.bind('<Control-v>',lambda _:(self.paste()))
        self.bind('<Alt-Up>',lambda _:(self.cd(self.cwd.parent)))
        self.bind('<Control-h>',lambda _:(self.toggle_hidden()))

    # --- nav ---
    def _roots(self):
        self.tree.delete(*self.tree.get_children(""))
        roots=[]
        if IS_WIN:
            import string
            for L in string.ascii_uppercase:
                d=pathlib.Path(f"{L}:/")
                if d.exists(): roots.append(d)
        else:
            roots=[pathlib.Path('/'), pathlib.Path.home()]
        seen=set()
        for r in roots:
            if str(r) in seen: continue
            seen.add(str(r))
            i=self.tree.insert('',tk.END,text=f"🗀 {r}",values=(str(r),))
            self.tree.insert(i,tk.END,text='…')
        self._expand_to(self.cwd)

    def _expand_to(self,p: pathlib.Path):
        target=str(p.resolve())
        for root in self.tree.get_children(''):
            rp=self.tree.item(root,'values')[0]
            if target.startswith(str(pathlib.Path(rp))):
                self.tree.item(root,open=True)
                self._load_children(root,pathlib.Path(rp))

    def _load_children(self,node,p: pathlib.Path):
        self.tree.delete(*self.tree.get_children(node))
        try:
            for c in sorted([x for x in p.iterdir() if x.is_dir()], key=lambda x:x.name.lower()):
                if not self.show_hidden and c.name.startswith('.'):
                    continue
                i=self.tree.insert(node,tk.END,text=f"🗀 {c.name}",values=(str(c),))
                self.tree.insert(i,tk.END,text='…')
        except: pass

    def _open_node(self, _):
        i=self.tree.focus(); p=pathlib.Path(self.tree.item(i,'values')[0])
        self._load_children(i,p)

    def _sel_node(self, _):
        i=self.tree.focus(); p=pathlib.Path(self.tree.item(i,'values')[0])
        self.cd(p)

    def cd(self,p: pathlib.Path):
        try:
            p=p.resolve();
            if not p.exists(): return
            self.cwd=p
            self.path.set(str(p))
            self._fill_files()
        except Exception as e:
            messagebox.showerror("Hacker Explorer", str(e))

    # --- list fill ---
    def _match(self,name):
        q=self.q.get().strip()
        return (q=='' or q=='Search…' or q.lower() in name.lower())

    def _fill_files(self):
        self.list.delete(*self.list.get_children(''))
        try:
            items=list(self.cwd.iterdir())
        except Exception as e:
            messagebox.showerror("Hacker Explorer", str(e)); return
        files=0
        for x in sorted(items,key=lambda p:(not p.is_dir(), p.name.lower())):
            if not self.show_hidden and x.name.startswith('.'):
                continue
            if not self._match(x.name):
                continue
            t='DIR' if x.is_dir() else x.suffix[1:].upper() or 'FILE'
            try:
                sz = human_size(x.stat().st_size) if x.is_file() else ''
                dt = x.stat().st_mtime
            except: sz=''; dt=0
            from datetime import datetime
            dt = datetime.fromtimestamp(dt).strftime('%Y-%m-%d %H:%M') if dt else ''
            self.list.insert('',tk.END,values=(x.name,t,sz,dt,str(x)))
            files+=1
        self.status.config(text=f"{self.cwd} — {files} items")

    # --- actions ---
    def _selpath(self):
        i=self.list.focus()
        if not i: return None
        return pathlib.Path(self.list.item(i,'values')[4])

    def open_sel(self):
        p=self._selpath()
        if not p: return
        if p.is_dir(): self.cd(p)
        else: system_open(p)

    def new_folder(self):
        name=simpledialog.askstring("New folder","Name:",initialvalue="new_folder",parent=self)
        if not name: return
        try:
            (self.cwd/name).mkdir(exist_ok=False)
            self._fill_files()
        except Exception as e: messagebox.showerror("Hacker Explorer",str(e))

    def rename(self):
        p=self._selpath();
        if not p: return
        n=simpledialog.askstring("Rename","New name:",initialvalue=p.name,parent=self)
        if not n or n==p.name: return
        try:
            p.rename(p.with_name(n)); self._fill_files()
        except Exception as e: messagebox.showerror("Hacker Explorer",str(e))

    def delete(self):
        p=self._selpath();
        if not p: return
        if not messagebox.askyesno("Delete",f"Delete {p.name}?"): return
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            self._fill_files()
        except Exception as e: messagebox.showerror("Hacker Explorer",str(e))

    def copy(self):
        p=self._selpath();
        if p: self.clip=[p]; self.clipop='copy'

    def cut(self):
        p=self._selpath();
        if p: self.clip=[p]; self.clipop='cut'

    def paste(self):
        if not self.clip: return
        for p in self.clip:
            dst=self.cwd/p.name
            try:
                if p.is_dir():
                    if dst.exists(): shutil.copytree(p,dst,dirs_exist_ok=True)
                    else: shutil.copytree(p,dst)
                else:
                    shutil.copy2(p,dst)
                if self.clipop=='cut':
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            except Exception as e: messagebox.showerror("Hacker Explorer",str(e))
        if self.clipop=='cut': self.clip=[]; self.clipop=None
        self._fill_files()

    # --- misc ---
    def _ctx(self,e):
        try: self.menu.tk_popup(e.x_root,e.y_root)
        finally: self.menu.grab_release()

    def toggle_hidden(self):
        self.show_hidden=not self.show_hidden
        self.hbtn.config(text=f"👁 Hidden: {'on' if self.show_hidden else 'off'}")
        self._fill_files()

    def focus_path(self):
        for w in self.children.values():
            if isinstance(w,ttk.Frame):
                for c in w.winfo_children():
                    if isinstance(c,ttk.Entry) and c.cget('textvariable')==str(self.path):
                        c.focus_set(); c.select_range(0,tk.END); return

    def focus_find(self):
        for w in self.children.values():
            if isinstance(w,ttk.Frame):
                for c in w.winfo_children():
                    if isinstance(c,ttk.Entry) and c.cget('textvariable')==str(self.q):
                        c.focus_set(); c.select_range(0,tk.END); return

if __name__=='__main__':
    App().mainloop()

