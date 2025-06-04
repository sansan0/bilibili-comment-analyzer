import tkinter as tk


class ToolTip:
    """
    为Tkinter控件添加悬停提示功能
    """
    
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.tipwindow = None
        
    def enter(self, event=None):
        self.showtip()
        
    def leave(self, event=None):
        self.hidetip()
        
    def showtip(self):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 20
        y = y + cy + self.widget.winfo_rooty() + 20
        
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        
        # 设置提示框样式
        label = tk.Label(tw, text=self.text, 
                        justify=tk.LEFT,
                        background="#ffffe0", 
                        relief=tk.SOLID, 
                        borderwidth=1,
                        font=("Microsoft YaHei", 9),
                        padx=8, 
                        pady=5)
        label.pack(ipadx=1)
        
    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def create_tooltip(widget, text):
    """
    便捷函数：为控件创建提示
    
    Args:
        widget: 要添加提示的控件
        text: 提示文本
    
    Returns:
        ToolTip对象
    """
    return ToolTip(widget, text)